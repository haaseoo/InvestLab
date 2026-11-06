"""한국투자증권 연동 테스트. 가짜 전송 계층만 쓰며 실제 KIS에 접속하지 않는다."""

import json
import logging
import os
import stat
from decimal import Decimal as D

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.errors import (
    KisApiError,
    KisAuthError,
    KisCredentialsInputError,
    KisNotConfiguredError,
    KisRateLimitedError,
    KisResponseError,
    KisUnavailableError,
)
from app.integrations.kis.client import KisClient
from app.integrations.kis.credentials import KisCredentials
from app.integrations.kis.master import classify, parse_master
from app.integrations.kis.parse import parse_domestic, parse_overseas
from app.main import create_app
from app.providers.kis import KISPortfolioProvider, live_provider_status
from app.schemas.portfolio import AssetClass, AssetType, Source, ValuationStatus
from tests.conftest import OWNER_ID, FakeLiveAccounts, FakeVerifier, make_settings
from tests.kis_fakes import (
    ACCOUNT,
    APP_KEY,
    APP_SECRET,
    TOKEN,
    FakeKis,
    FakeMaster,
    domestic_row,
    overseas_row,
)

BALANCE = "/uapi/domestic-stock/v1/trading/inquire-balance"
PARAMS = {"CANO": "12345678", "ACNT_PRDT_CD": "01"}

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def no_sleep(_):
    return None


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def make_client(fake: FakeKis, tmp_path, clock=None) -> KisClient:
    return KisClient(
        APP_KEY,
        APP_SECRET,
        tmp_path / "token.json",
        transport=fake.transport(),
        sleep=no_sleep,
        clock=clock or Clock(),
    )


CREDENTIALS = KisCredentials.parse(APP_KEY, APP_SECRET, ACCOUNT)


def make_provider(fake: FakeKis, tmp_path, master=None) -> KISPortfolioProvider:
    return KISPortfolioProvider(
        CREDENTIALS,
        make_client(fake, tmp_path),
        master or FakeMaster(),
        tmp_path / "classifications.json",
    )


# --- 토큰 ---


class TestToken:
    async def test_token_cached_in_file_with_owner_only_permission(self, tmp_path):
        fake = FakeKis()
        await make_client(fake, tmp_path).get(
            BALANCE, "TTTC8434R", {"CANO": "12345678", "ACNT_PRDT_CD": "01"}
        )
        path = tmp_path / "token.json"
        assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
        saved = json.loads(path.read_text())
        # 키 자체는 저장하지 않는다
        assert APP_KEY not in path.read_text() and APP_SECRET not in path.read_text()
        assert saved["token"] == TOKEN

    async def test_restart_reuses_cached_token(self, tmp_path):
        fake = FakeKis()
        params = {"CANO": "12345678", "ACNT_PRDT_CD": "01"}
        await make_client(fake, tmp_path).get(BALANCE, "TTTC8434R", params)
        await make_client(fake, tmp_path).get(BALANCE, "TTTC8434R", params)
        assert fake.count("/oauth2/tokenP") == 1

    async def test_cache_from_other_app_key_is_ignored(self, tmp_path):
        fake = FakeKis()
        (tmp_path / "token.json").write_text(
            json.dumps(
                {"fingerprint": "other", "token": "x", "expires_at": "2099-01-01T00:00:00+00:00"}
            )
        )
        await make_client(fake, tmp_path).get(BALANCE, "TTTC8434R", PARAMS)
        assert fake.count("/oauth2/tokenP") == 1

    async def test_expired_cache_is_reissued(self, tmp_path):
        fake = FakeKis()
        client = make_client(fake, tmp_path)
        from app.integrations.kis.client import _key_fingerprint

        (tmp_path / "token.json").write_text(
            json.dumps(
                {
                    "fingerprint": _key_fingerprint(APP_KEY),
                    "token": "old",
                    "expires_at": "2000-01-01T00:00:00+00:00",
                }
            )
        )
        await client.get(BALANCE, "TTTC8434R", PARAMS)
        assert fake.count("/oauth2/tokenP") == 1

    async def test_rejected_credentials(self, tmp_path):
        fake = FakeKis(token_status=403)
        with pytest.raises(KisAuthError) as exc:
            await make_client(fake, tmp_path).get(BALANCE, "TTTC8434R", PARAMS)
        assert exc.value.details["kis_code"] == "EGW00103"
        assert not (tmp_path / "token.json").exists()

    async def test_reissue_limited_to_once_per_minute(self, tmp_path):
        fake = FakeKis(token_status=403)
        clock = Clock()
        client = make_client(fake, tmp_path, clock)
        with pytest.raises(KisAuthError):
            await client.get(BALANCE, "TTTC8434R", PARAMS)
        clock.now += 30
        with pytest.raises(KisRateLimitedError):
            await client.get(BALANCE, "TTTC8434R", PARAMS)
        assert fake.count("/oauth2/tokenP") == 1
        clock.now += 31
        fake.token_status = 200
        await client.get(BALANCE, "TTTC8434R", PARAMS)
        assert fake.count("/oauth2/tokenP") == 2

    async def test_rejected_cached_token_is_reissued_once(self, tmp_path):
        from app.integrations.kis.client import _key_fingerprint

        # 파일에는 아직 유효해 보이지만 KIS가 만료로 거부하는 토큰
        (tmp_path / "token.json").write_text(
            json.dumps(
                {
                    "fingerprint": _key_fingerprint(APP_KEY),
                    "token": "revoked",
                    "expires_at": "2099-01-01T00:00:00+00:00",
                }
            )
        )
        fake = FakeKis()
        res = await make_client(fake, tmp_path).get(
            BALANCE, "TTTC8434R", {"CANO": "12345678", "ACNT_PRDT_CD": "01"}
        )
        assert res.body["rt_cd"] == "0"
        assert fake.count("/oauth2/tokenP") == 1
        assert json.loads((tmp_path / "token.json").read_text())["token"] == TOKEN

    async def test_token_rejected_twice_is_auth_error(self, tmp_path):
        fake = FakeKis()
        fake.override = lambda r: (
            httpx.Response(500, json={"rt_cd": "1", "msg_cd": "EGW00121"})
            if r.url.path == BALANCE
            else None
        )
        clock = Clock()
        client = make_client(fake, tmp_path, clock)
        # 첫 발급 직후 다시 거부되면 1분 제한 때문에 재발급하지 않고 멈춘다
        with pytest.raises(KisRateLimitedError):
            await client.get(BALANCE, "TTTC8434R", PARAMS)
        assert fake.count("/oauth2/tokenP") == 1

    def test_missing_keys(self, tmp_path):
        with pytest.raises(KisNotConfiguredError):
            KisClient("", APP_SECRET, tmp_path / "t.json")


# --- 조회 ---


class TestRequests:
    async def test_order_paths_are_refused(self, tmp_path):
        fake = FakeKis()
        client = make_client(fake, tmp_path)
        for path in (
            "/uapi/domestic-stock/v1/trading/order-cash",
            "/uapi/overseas-stock/v1/trading/order",
            "/uapi/domestic-stock/v1/trading/order-rvsecncl",
        ):
            with pytest.raises(ValueError):
                await client.get(path, "TTTC0802U", {})
        assert fake.calls == []

    async def test_rate_limit_retries_then_succeeds(self, tmp_path):
        fake = FakeKis()
        state = {"n": 0}

        def limited(request):
            if request.url.path == BALANCE and state["n"] < 2:
                state["n"] += 1
                return httpx.Response(
                    500,
                    json={
                        "rt_cd": "1",
                        "msg_cd": "EGW00201",
                        "msg1": "초당 거래건수를 초과하였습니다.",
                    },
                )
            return None

        fake.override = limited
        res = await make_client(fake, tmp_path).get(
            BALANCE, "TTTC8434R", {"CANO": "12345678", "ACNT_PRDT_CD": "01"}
        )
        assert res.body["rt_cd"] == "0"
        assert fake.count(BALANCE) == 3

    async def test_rate_limit_gives_up(self, tmp_path):
        fake = FakeKis()
        fake.override = lambda r: (
            httpx.Response(500, json={"rt_cd": "1", "msg_cd": "EGW00201", "msg1": "x"})
            if r.url.path == BALANCE
            else None
        )
        with pytest.raises(KisRateLimitedError):
            await make_client(fake, tmp_path).get(BALANCE, "TTTC8434R", PARAMS)
        assert fake.count(BALANCE) == 3

    async def test_api_error_carries_only_code(self, tmp_path):
        fake = FakeKis()
        fake.override = lambda r: (
            httpx.Response(
                200, json={"rt_cd": "1", "msg_cd": "OPSQ0002", "msg1": f"계좌 {ACCOUNT} 오류"}
            )
            if r.url.path == BALANCE
            else None
        )
        with pytest.raises(KisApiError) as exc:
            await make_client(fake, tmp_path).get(BALANCE, "TTTC8434R", PARAMS)
        assert exc.value.details == {"tr_id": "TTTC8434R", "kis_code": "OPSQ0002"}
        assert ACCOUNT not in str(exc.value)

    async def test_network_error(self, tmp_path):
        def boom(request):
            raise httpx.ConnectTimeout("timeout", request=request)

        client = KisClient(
            APP_KEY,
            APP_SECRET,
            tmp_path / "t.json",
            transport=httpx.MockTransport(boom),
            sleep=no_sleep,
        )
        with pytest.raises(KisUnavailableError):
            await client.get(BALANCE, "TTTC8434R", PARAMS)

    async def test_non_json_response(self, tmp_path):
        fake = FakeKis()
        fake.override = lambda r: (
            httpx.Response(502, text="<html>") if r.url.path == BALANCE else None
        )
        with pytest.raises(KisUnavailableError):
            await make_client(fake, tmp_path).get(BALANCE, "TTTC8434R", PARAMS)

    async def test_pagination_follows_continuation_keys(self, tmp_path):
        fake = FakeKis()
        pages = []

        def paged(request):
            if request.url.path != BALANCE:
                return None
            pages.append((request.headers["tr_cont"], request.url.params.get("CTX_AREA_NK100")))
            if len(pages) == 1:
                return fake.ok(
                    {
                        "output1": [domestic_row()],
                        "output2": [],
                        "ctx_area_fk100": "F1",
                        "ctx_area_nk100": "N1",
                    },
                    tr_cont="M",
                )
            return fake.ok(
                {
                    "output1": [domestic_row(pdno="000660")],
                    "output2": [],
                    "ctx_area_fk100": "",
                    "ctx_area_nk100": "",
                }
            )

        fake.override = paged
        result = await make_client(fake, tmp_path).get_pages(
            BALANCE,
            "TTTC8434R",
            {"CTX_AREA_FK100": "", "CTX_AREA_NK100": ""},
            "ctx_area_fk100",
            "ctx_area_nk100",
        )
        assert len(result) == 2
        assert pages == [("", ""), ("N", "N1")]

    async def test_endless_pagination_is_rejected(self, tmp_path):
        fake = FakeKis()
        fake.override = lambda r: (
            fake.ok(
                {"output1": [], "output2": [], "ctx_area_fk100": "a", "ctx_area_nk100": "b"},
                tr_cont="M",
            )
            if r.url.path == BALANCE
            else None
        )
        with pytest.raises(KisResponseError):
            await make_client(fake, tmp_path).get_pages(
                BALANCE, "TTTC8434R", {}, "ctx_area_fk100", "ctx_area_nk100"
            )

    async def test_secrets_never_logged(self, tmp_path, caplog):
        caplog.set_level(logging.DEBUG)
        fake = FakeKis()
        fake.override = lambda r: (
            httpx.Response(200, json={"rt_cd": "1", "msg_cd": "OPSQ0002", "msg1": ACCOUNT})
            if r.url.path == BALANCE
            else None
        )
        with pytest.raises(KisApiError):
            await make_client(fake, tmp_path).get(BALANCE, "TTTC8434R", PARAMS)
        logs = caplog.text
        for secret in (APP_KEY, APP_SECRET, TOKEN, "12345678"):
            assert secret not in logs


# --- 응답 해석 ---


class TestParse:
    def test_domestic(self):
        holdings, cash = parse_domestic(
            [
                {
                    "output1": [domestic_row(), domestic_row(pdno="000660", hldg_qty="0")],
                    "output2": [{"dnca_tot_amt": "500000"}],
                }
            ]
        )
        assert [h.symbol for h in holdings] == ["005930"]  # 수량 0(당일 전량 매도) 제외
        h = holdings[0]
        assert (h.quantity, h.average_cost, h.price, h.reported_value) == (
            D(10),
            D(70000),
            D(75000),
            D(750000),
        )
        assert h.currency == "KRW" and h.domestic
        assert cash == D(500000)

    def test_overseas_uses_executed_quantity(self):
        holdings, fx, cash = parse_overseas(
            {
                "output1": [overseas_row()],
                "output2": [
                    {"crcy_cd": "USD", "frst_bltn_exrt": "1400.5", "frcr_dncl_amt_2": "1.5"}
                ],
            }
        )
        # 잔고수량(cblc_qty13=1)이 아니라 체결수량합계(2)를 쓴다
        assert holdings[0].quantity == D(2)
        assert holdings[0].market == "NASDAQ" and holdings[0].country == "US"
        assert [(f.currency, f.rate) for f in fx] == [("USD", D("1400.5"))]
        assert cash == {"USD": D("1.5")}

    def test_zero_price_is_unknown_not_zero(self):
        holdings, _, _ = parse_overseas(
            {"output1": [overseas_row(ovrs_now_pric1="0.00000", frcr_evlu_amt2="0")], "output2": []}
        )
        assert holdings[0].price is None and holdings[0].reported_value is None

    def test_fx_falls_back_to_row_rate(self):
        _, fx, _ = parse_overseas({"output1": [overseas_row(bass_exrt="1399")], "output2": []})
        assert [(f.currency, f.rate) for f in fx] == [("USD", D(1399))]

    @pytest.mark.parametrize("field", ["pdno", "ccld_qty_smtl1", "avg_unpr3", "buy_crcy_cd"])
    def test_missing_field_is_rejected_not_guessed(self, field):
        row = overseas_row()
        del row[field]
        with pytest.raises(KisResponseError) as exc:
            parse_overseas({"output1": [row], "output2": []})
        assert exc.value.details["field"] == field

    def test_malformed_number(self):
        with pytest.raises(KisResponseError):
            parse_domestic([{"output1": [domestic_row(hldg_qty="abc")], "output2": []}])

    def test_account_format(self):
        c = KisCredentials.parse(APP_KEY, APP_SECRET, "12345678-01")
        assert (c.cano, c.product) == ("12345678", "01")
        c = KisCredentials.parse(f" {APP_KEY} ", APP_SECRET, "1234567801")
        assert (c.app_key, c.cano, c.product) == (APP_KEY, "12345678", "01")
        with pytest.raises(KisCredentialsInputError) as exc:
            KisCredentials.parse("short", "bad secret!", "1234-5678")
        assert len(exc.value.details["reasons"]) == 3
        # 실패 사유에 입력값을 싣지 않는다
        assert "short" not in str(exc.value.details) and "1234-5678" not in str(exc.value.details)

    def test_credentials_never_in_repr(self):
        text = repr(CREDENTIALS) + str(CREDENTIALS)
        for secret in (APP_KEY, APP_SECRET, "12345678"):
            assert secret not in text
        assert "01" in text


class TestMaster:
    def test_parse_and_classify(self):
        # 공식 마스터 파일 형식(탭 구분 24열). 값은 테스트용이다.
        def line(symbol, stype, etyp):
            cols = [
                "US",
                "22",
                "NAS",
                "나스닥",
                symbol,
                "NAS" + symbol,
                "이름",
                "NAME",
                stype,
                "USD",
            ]
            cols += [""] * 12 + [etyp, ""]
            return "\t".join(cols)

        table = parse_master(
            "\n".join(
                [line("STK", "2", ""), line("ETF1", "3", "001"), line("ETN1", "3", "002"), "bad"]
            )
        )
        assert classify(table["STK"]) == "stock"
        assert classify(table["ETF1"]) == "etf"
        assert classify(table["ETN1"]) == "other"
        assert classify(None) is None


# --- Provider ---


class TestProvider:
    async def test_holdings_converted_and_classified(self, tmp_path):
        provider = make_provider(FakeKis(), tmp_path)
        holdings = {h.symbol: h for h in await provider.get_holdings("KRW")}
        assert set(holdings) == {"005930", "AAAA", "BBBB"}

        dom = holdings["005930"]
        assert dom.asset_class is AssetClass.DOMESTIC_STOCK and dom.asset_type is AssetType.STOCK
        assert dom.market_value == D(750000) and dom.valuation_status is ValuationStatus.REPORTED
        assert dom.exposure_country == "KR"

        us = holdings["AAAA"]
        assert us.asset_class is AssetClass.OVERSEAS_STOCK
        assert us.market_value == D(220) and us.fx_rate == D(1400)
        assert us.market_value_valuation == D(308000)
        assert us.cost_basis == D(200)

        etf = holdings["BBBB"]
        # ETF임은 알지만 유형 정보가 없으면 지어내지 않는다
        assert etf.asset_type is AssetType.ETF
        assert etf.asset_class is AssetClass.ETF_UNCLASSIFIED
        assert etf.exposure_country is None and etf.benchmark is None

        for h in holdings.values():
            assert h.source is Source.LIVE and h.is_demo is False

    async def test_unknown_kind_is_other_not_stock(self, tmp_path):
        provider = make_provider(
            FakeKis(), tmp_path, master=FakeMaster({"AAAA": None, "BBBB": None})
        )
        holdings = {h.symbol: h for h in await provider.get_holdings("KRW")}
        assert holdings["AAAA"].asset_type is AssetType.OTHER

    async def test_domestic_etf(self, tmp_path):
        fake = FakeKis(domestic_kind={"005930": "EF"})
        holdings = {h.symbol: h for h in await make_provider(fake, tmp_path).get_holdings("KRW")}
        assert holdings["005930"].asset_type is AssetType.ETF

    async def test_classification_file_overrides(self, tmp_path):
        (tmp_path / "classifications.json").write_text(
            json.dumps(
                {
                    "holdings": {
                        "BBBB": {
                            "asset_class": "broad_index_etf",
                            "exposure_country": "US",
                            "benchmark": "TEST INDEX",
                        }
                    }
                }
            )
        )
        holdings = {
            h.symbol: h for h in await make_provider(FakeKis(), tmp_path).get_holdings("KRW")
        }
        assert holdings["BBBB"].asset_class is AssetClass.BROAD_INDEX_ETF
        assert holdings["BBBB"].benchmark == "TEST INDEX"

    async def test_invalid_classification_file_is_ignored(self, tmp_path):
        (tmp_path / "classifications.json").write_text("{not json")
        holdings = await make_provider(FakeKis(), tmp_path).get_holdings("KRW")
        assert len(holdings) == 3

    async def test_missing_fx_leaves_foreign_unvalued(self, tmp_path):
        fake = FakeKis(fx_rate="0")
        fake.overseas_rows = [overseas_row(bass_exrt="0")]
        holdings = {h.symbol: h for h in await make_provider(fake, tmp_path).get_holdings("KRW")}
        assert holdings["AAAA"].market_value == D(220)
        assert holdings["AAAA"].market_value_valuation is None

    async def test_results_shared_briefly(self, tmp_path):
        fake = FakeKis()
        provider = make_provider(fake, tmp_path)
        await provider.get_holdings("KRW")
        await provider.get_fx_rates()
        await provider.get_quotes()
        assert fake.count("inquire-present-balance") == 1
        assert fake.count("search-stock-info") == 1

    async def test_overseas_failure_fails_everything(self, tmp_path):
        fake = FakeKis()
        fake.override = lambda r: (
            httpx.Response(200, json={"rt_cd": "1", "msg_cd": "ERR"})
            if r.url.path.endswith("inquire-present-balance")
            else None
        )
        with pytest.raises(KisApiError):
            await make_provider(fake, tmp_path).get_holdings("KRW")

    async def test_account_summary_masks_account(self, tmp_path):
        summary = await make_provider(FakeKis(), tmp_path).get_account_summary()
        assert summary.account_masked == "********01"
        assert summary.cash_balances == {"USD": D("12.34"), "KRW": D(500000)}

    def test_server_status_has_no_user_values(self):
        status = live_provider_status(True, True, True)
        assert status.state == "ready"
        assert live_provider_status(True, True, False).state != "ready"


# --- API ---


@pytest.fixture
def live_api(tmp_path):
    fake = FakeKis()
    app = create_app(make_settings())
    app.state.token_verifier = FakeVerifier()
    app.state.live_accounts = FakeLiveAccounts({OWNER_ID: make_provider(fake, tmp_path)})
    return TestClient(app, raise_server_exceptions=False), fake


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


class TestLiveApi:
    def test_user_gets_own_live_portfolio(self, live_api):
        api, _ = live_api
        r = api.get("/api/v1/portfolio", params={"source": "live"}, headers=bearer("owner-token"))
        assert r.status_code == 200
        body = r.json()
        assert body["source"] == "live" and body["is_demo"] is False
        assert {h["symbol"] for h in body["holdings"]} == {"005930", "AAAA", "BBBB"}
        # 750000 + 220×1400 + 180×1400
        assert D(body["summary"]["total_market_value"]) == D(1310000)
        assert "VOO" not in r.text
        for secret in (APP_KEY, APP_SECRET, TOKEN, "12345678"):
            assert secret not in r.text

    def test_user_without_keys_never_reaches_kis(self, live_api):
        api, fake = live_api
        r = api.get("/api/v1/portfolio", params={"source": "live"}, headers=bearer("other-token"))
        assert r.status_code == 409
        r = api.get("/api/v1/portfolio", params={"source": "live"})
        assert r.status_code == 401
        assert fake.calls == []

    def test_kis_error_is_error_not_mock(self, live_api):
        api, fake = live_api
        fake.override = lambda r: (
            httpx.Response(200, json={"rt_cd": "1", "msg_cd": "ERR"})
            if "balance" in r.url.path
            else None
        )
        r = api.get(
            "/api/v1/portfolio/holdings", params={"source": "live"}, headers=bearer("owner-token")
        )
        assert r.status_code == 502
        assert r.json()["error"]["code"] == "KIS_API_ERROR"
        assert "holdings" not in r.json()

    def test_live_history_requires_database(self, live_api):
        api, _ = live_api
        r = api.get(
            "/api/v1/portfolio/history", params={"source": "live"}, headers=bearer("owner-token")
        )
        assert r.status_code == 503
        assert r.json()["error"]["code"] == "DB_NOT_CONFIGURED"

    def test_live_simulation_and_risk(self, live_api):
        api, _ = live_api
        r = api.get(
            "/api/v1/analytics/risk", params={"source": "live"}, headers=bearer("owner-token")
        )
        assert r.status_code == 200
        assert r.json()["source"] == "live"
