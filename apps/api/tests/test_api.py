import json
import logging
from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient

from app.core.config import REPO_ROOT
from app.core.crypto import CredentialKeyError, generate_key
from app.core.logging import install_log_masking, mask_account, mask_sensitive
from app.main import create_app
from app.services.live_accounts import LiveAccounts
from tests.conftest import OWNER_ID, make_settings


class TestHealthAndStatus:
    def test_health(self, client):
        assert client.get("/health").json() == {"status": "ok"}

    def test_status_never_claims_live_connected(self, client):
        body = client.get("/api/v1/providers/status").json()
        assert body["default_source"] == "mock"
        states = {p["source"]: p for p in body["providers"]}
        assert states["mock"]["state"] == "ready"
        assert states["mock"]["is_demo"] is True
        assert states["live"]["state"] != "ready"
        assert not all(c["ok"] for c in states["live"]["checks"])

    def test_status_does_not_leak_secret_values(self):
        key = generate_key()
        settings = make_settings(kis_credential_key=key)
        body = TestClient(create_app(settings)).get("/api/v1/providers/status")
        assert key not in body.text
        live = next(p for p in body.json()["providers"] if p["source"] == "live")
        assert {c["key"]: c["ok"] for c in live["checks"]}["credential_store"] is True

    def test_invalid_credential_key_fails_startup(self):
        with pytest.raises(CredentialKeyError):
            create_app(make_settings(kis_credential_key="not-a-key"))


class TestMockPortfolio:
    def test_default_source_is_mock_and_labeled_demo(self, client):
        body = client.get("/api/v1/portfolio").json()
        assert body["source"] == "mock"
        assert body["is_demo"] is True
        assert all(h["is_demo"] and h["source"] == "mock" for h in body["holdings"])

    def test_decimals_are_strings_and_consistent(self, client):
        body = client.get("/api/v1/portfolio").json()
        for h in body["holdings"]:
            assert isinstance(h["market_value"], str)
            expected_cost = D(h["quantity"]) * D(h["average_cost"])
            expected_value = D(h["quantity"]) * D(h["current_price"])
            assert abs(D(h["cost_basis"]) - expected_cost) <= D("0.005")
            assert abs(D(h["market_value"]) - expected_value) <= D("0.005")
            assert abs(D(h["unrealized_pnl"]) - (expected_value - expected_cost)) <= D("0.005")
            assert h["valuation_status"] == "calculated"

    def test_includes_required_holding_types(self, client):
        holdings = client.get("/api/v1/portfolio").json()["holdings"]
        symbols = {h["symbol"] for h in holdings}
        assert {"VOO", "QQQ", "SOXX", "005930", "NVDA", "411060"} <= symbols

    def test_totals_match_independent_calculation(self, client):
        """Seed 원본에서 직접 계산해 API 합계와 비교한다."""
        seed = json.loads((REPO_ROOT / "data/mock/portfolio.json").read_text(encoding="utf-8"))
        fx = D(seed["fx_rates"][0]["rate"])
        cost = value = D(0)
        for h in seed["holdings"]:
            rate = fx if h["currency"] == "USD" else D(1)
            cost += D(h["quantity"]) * D(h["average_cost"]) * rate
            value += D(h["quantity"]) * D(h["current_price"]) * rate

        s = client.get("/api/v1/portfolio/summary").json()["summary"]
        assert abs(D(s["total_cost_basis"]) - cost) <= D("0.005")
        assert abs(D(s["total_market_value"]) - value) <= D("0.005")
        assert abs(D(s["total_unrealized_pnl"]) - (value - cost)) <= D("0.005")
        assert s["is_complete"] is True

    def test_weights_sum_to_100(self, client):
        holdings = client.get("/api/v1/portfolio/holdings").json()["holdings"]
        assert abs(sum(D(h["weight_pct"]) for h in holdings) - 100) < D("0.01")

    def test_allocation_dimensions(self, client):
        for dimension in ["asset_class", "asset_type", "market", "currency"]:
            body = client.get(
                "/api/v1/analytics/allocation", params={"dimension": dimension}
            ).json()
            assert abs(sum(D(s["weight_pct"]) for s in body["slices"]) - 100) < D("0.01")

    def test_history_is_demo_and_ends_at_current_totals(self, client):
        history = client.get("/api/v1/portfolio/history").json()
        assert history["is_demo"] is True
        assert len(history["points"]) >= 2
        s = client.get("/api/v1/portfolio/summary").json()["summary"]
        last = history["points"][-1]
        assert D(last["total_market_value"]) == D(s["total_market_value"])
        assert D(last["total_cost_basis"]) == D(s["total_cost_basis"])

    def test_cash_is_missing_not_zero(self):
        from app.providers.mock import MockPortfolioProvider

        provider = MockPortfolioProvider(REPO_ROOT / "data/mock")
        import asyncio

        assert asyncio.run(provider.get_account_summary()).cash_balances is None

    def test_failed_quote_is_null_and_flagged(self, partial_data_dir):
        c = TestClient(create_app(make_settings(mock_data_dir=partial_data_dir)))
        body = c.get("/api/v1/portfolio").json()
        nvda = next(h for h in body["holdings"] if h["symbol"] == "NVDA")
        assert nvda["current_price"] is None
        assert nvda["market_value"] is None
        assert nvda["weight_pct"] is None
        assert nvda["valuation_status"] == "unavailable"
        assert body["summary"]["unvalued_symbols"] == ["NVDA"]
        assert body["summary"]["is_complete"] is False

    def test_missing_seed_is_error_not_empty_portfolio(self, tmp_path):
        c = TestClient(create_app(make_settings(mock_data_dir=tmp_path)))
        response = c.get("/api/v1/portfolio")
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "MOCK_DATA_UNAVAILABLE"

    def test_financial_responses_are_not_cached(self, client):
        assert client.get("/api/v1/portfolio").headers["cache-control"] == "no-store"


LIVE_ENDPOINTS = [
    "/api/v1/portfolio",
    "/api/v1/portfolio/holdings",
    "/api/v1/portfolio/summary",
    "/api/v1/portfolio/history",
    "/api/v1/analytics/allocation",
]


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


class TestLiveAccess:
    @pytest.mark.parametrize("path", LIVE_ENDPOINTS)
    def test_source_live_alone_grants_nothing(self, client, path):
        response = client.get(path, params={"source": "live"})
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "AUTH_NOT_CONFIGURED"

    def test_any_token_rejected_without_verifier(self, client):
        response = client.get(
            "/api/v1/portfolio", params={"source": "live"}, headers=bearer("forged")
        )
        assert response.status_code == 503

    @pytest.mark.parametrize("path", LIVE_ENDPOINTS)
    def test_no_token_is_401(self, live_client, path):
        response = live_client.get(path, params={"source": "live"})
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "AUTH_REQUIRED"

    def test_invalid_token_is_401(self, live_client):
        response = live_client.get(
            "/api/v1/portfolio", params={"source": "live"}, headers=bearer("bad")
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "INVALID_TOKEN"

    def test_user_without_keys_is_not_configured(self, live_client):
        response = live_client.get(
            "/api/v1/portfolio", params={"source": "live"}, headers=bearer("other-token")
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "KIS_NOT_CONFIGURED"

    def test_missing_credential_key_is_denied(self, tmp_path):
        from tests.conftest import FakeVerifier

        app = create_app(make_settings())
        app.state.token_verifier = FakeVerifier()
        app.state.db = object()
        app.state.live_accounts = LiveAccounts(object(), None, object(), tmp_path / "c.json")
        response = TestClient(app).get(
            "/api/v1/portfolio", params={"source": "live"}, headers=bearer("owner-token")
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "KIS_CREDENTIAL_STORE_NOT_CONFIGURED"

    def test_missing_database_is_denied(self):
        from tests.conftest import FakeVerifier

        app = create_app(make_settings(kis_credential_key=generate_key()))
        app.state.token_verifier = FakeVerifier()
        response = TestClient(app).get(
            "/api/v1/portfolio", params={"source": "live"}, headers=bearer("owner-token")
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "DB_NOT_CONFIGURED"

    @pytest.mark.parametrize("path", LIVE_ENDPOINTS)
    def test_unconfigured_kis_is_error_not_mock_fallback(self, live_client, path):
        assert OWNER_ID
        response = live_client.get(path, params={"source": "live"}, headers=bearer("owner-token"))
        assert response.status_code == 409
        body = response.json()
        # 키를 등록하지 않았으면 오류다. Mock으로 대체하지 않는다.
        assert body["error"]["code"] == "KIS_NOT_CONFIGURED"
        assert "holdings" not in body
        assert "VOO" not in response.text

    def test_invalid_source_is_422(self, client):
        response = client.get("/api/v1/portfolio", params={"source": "admin"})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"


class TestCors:
    def test_allowed_origin(self, client):
        response = client.get("/health", headers={"Origin": "http://localhost:3000"})
        assert response.headers["access-control-allow-origin"] == "http://localhost:3000"

    def test_unknown_origin_gets_no_cors_header(self, client):
        response = client.get("/health", headers={"Origin": "https://evil.example"})
        assert "access-control-allow-origin" not in response.headers


class TestMasking:
    @pytest.mark.parametrize(
        ("raw", "secret"),
        [
            ("Authorization: Bearer abc.def-ghi", "abc.def-ghi"),
            ('{"appsecret": "s3cr3t"}', "s3cr3t"),
            ("appkey=KEY123&x=1", "KEY123"),
            ("access_token: tok_999", "tok_999"),
            ("계좌 50012345-01 조회", "50012345-01"),
            ("계좌 5001234501 조회", "5001234501"),
            ("GET /inquire-balance?CANO=50012345&ACNT_PRDT_CD=01", "50012345"),
        ],
    )
    def test_mask_sensitive(self, raw, secret):
        assert secret not in mask_sensitive(raw)

    def test_mask_account_keeps_last_two(self):
        assert mask_account("50012345-01") == "********01"

    def test_log_records_are_masked(self, caplog):
        install_log_masking()
        with caplog.at_level(logging.INFO, logger="investlab.test"):
            logging.getLogger("investlab.test").info("token=%s", "abc123")
        assert "abc123" not in caplog.text

    def test_uvicorn_access_log_keeps_args_and_masks_query(self):
        """uvicorn AccessFormatter가 args 5개를 풀어 쓰므로 비우면 매 요청 로그 오류가 난다."""
        from uvicorn.logging import AccessFormatter

        install_log_masking()
        record = logging.getLogRecordFactory()(
            "uvicorn.access",
            logging.INFO,
            __file__,
            1,
            '%s - "%s %s HTTP/%s" %d',
            ("127.0.0.1:1", "GET", "/x?token=abc123", "1.1", 200),
            None,
        )
        output = AccessFormatter(fmt="%(client_addr)s %(request_line)s %(status_code)s").format(
            record
        )
        assert "GET /x?token=***" in output
        assert "abc123" not in output

    def test_malformed_log_call_does_not_raise(self):
        install_log_masking()
        logging.getLogger("investlab.test").warning("%d", "not-a-number")

    def test_settings_repr_hides_secrets(self):
        settings = make_settings(kis_app_secret="TOPSECRET")
        assert "TOPSECRET" not in repr(settings)


class TestRiskApi:
    def test_meta_and_source(self, client):
        body = client.get("/api/v1/analytics/risk").json()
        assert body["source"] == "mock"
        assert body["is_demo"] is True
        assert body["as_of"] and body["retrieved_at"]

    def test_sector_matches_independent_calculation(self, client):
        seed = json.loads((REPO_ROOT / "data/mock/portfolio.json").read_text(encoding="utf-8"))
        fx = D(seed["fx_rates"][0]["rate"])
        values = {
            h["symbol"]: D(h["quantity"])
            * D(h["current_price"])
            * (fx if h["currency"] == "USD" else 1)
            for h in seed["holdings"]
        }
        total = sum(values.values())
        semis = sum(values[h["symbol"]] for h in seed["holdings"] if h["sector"] == "반도체")
        slices = client.get("/api/v1/analytics/risk").json()["allocations"]["sector"]
        semi = next(s for s in slices if s["key"] == "반도체")
        assert abs(D(semi["weight_pct"]) - semis / total * 100) < D("0.0001")
        assert slices[-1]["is_unclassified"] is True

    def test_mock_has_no_etf_constituent_data(self, client):
        overlap = client.get("/api/v1/analytics/risk").json()["overlap"]
        assert overlap["constituent_overlap"]["status"] == "unavailable"
        assert overlap["constituent_overlap"]["overlaps"] == []
        benchmarks = {g["benchmark"]: g for g in overlap["benchmark_groups"]}
        assert {h["symbol"] for h in benchmarks["S&P 500"]["holdings"]} == {"VOO", "360750"}
        assert {h["symbol"] for h in benchmarks["NASDAQ-100"]["holdings"]} == {"QQQ", "133690"}

    def test_history_based_metrics_not_computed(self, client):
        body = client.get("/api/v1/analytics/risk").json()
        keys = {m["key"] for m in body["unavailable_metrics"]}
        assert {"volatility", "max_drawdown", "sharpe_ratio"} <= keys
        assert "volatility" not in body["concentration"]

    def test_allocation_new_dimensions(self, client):
        for dimension in ["exposure_country", "sector"]:
            body = client.get(
                "/api/v1/analytics/allocation", params={"dimension": dimension}
            ).json()
            assert abs(sum(D(s["weight_pct"]) for s in body["slices"]) - 100) < D("0.01")

    def test_etf_compositions_file_is_used_when_present(self, tmp_path):
        import shutil

        for name in ["portfolio.json", "history.json"]:
            shutil.copy(REPO_ROOT / "data/mock" / name, tmp_path / name)
        (tmp_path / "etf_compositions.json").write_text(
            json.dumps(
                {
                    "compositions": [
                        {
                            "etf_symbol": "SOXX",
                            "etf_market": "NASDAQ",
                            "as_of": "2026-10-30T00:00:00+00:00",
                            "provider": "테스트",
                            "constituents": [
                                {
                                    "symbol": "NVDA",
                                    "market": "NASDAQ",
                                    "name": "NVIDIA",
                                    "weight_pct": "10",
                                }
                            ],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        c = TestClient(create_app(make_settings(mock_data_dir=tmp_path)))
        constituent = c.get("/api/v1/analytics/risk").json()["overlap"]["constituent_overlap"]
        assert constituent["status"] == "partial"
        assert constituent["overlaps"][0]["symbol"] == "NVDA"


BUY = {"symbol": "005930", "market": "KRX", "mode": "quantity", "quantity": "10", "price": "80000"}


class TestSimulationApi:
    def test_buy(self, client):
        body = client.post("/api/v1/simulations/buy", json=BUY).json()
        assert body["source"] == "mock" and body["is_theoretical"] is True
        assert body["after"]["quantity"] == "130"
        assert body["after"]["cost_basis"] == "9344000.00"
        assert body["after"]["average_cost"] == "71876.92"  # 9,344,000 / 130

    def test_buy_validation_error_has_reason(self, client):
        response = client.post("/api/v1/simulations/buy", json={**BUY, "quantity": None})
        assert response.status_code == 422
        assert any("quantity" in r for r in response.json()["error"]["details"]["reasons"])

    def test_buy_unknown_holding(self, client):
        response = client.post("/api/v1/simulations/buy", json={**BUY, "symbol": "NOPE"})
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "HOLDING_NOT_FOUND"

    def test_rebalance_keeps_total(self, client):
        holdings = client.get("/api/v1/portfolio/holdings").json()["holdings"]
        targets = [{"key": f"{h['market']}:{h['symbol']}", "target_pct": "10"} for h in holdings]
        body = client.post(
            "/api/v1/simulations/rebalance", json={"dimension": "holding", "targets": targets}
        ).json()
        assert abs(sum(D(r["adjustment_value"]) for r in body["rows"])) < D("0.1")

    def test_rebalance_bad_sum(self, client):
        response = client.post(
            "/api/v1/simulations/rebalance",
            json={"dimension": "asset_class", "targets": [{"key": "other", "target_pct": "50"}]},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "INVALID_SIMULATION_INPUT"

    def test_scenario(self, client):
        body = client.post(
            "/api/v1/simulations/scenario",
            json={"shocks": [{"type": "asset_class", "key": "sector_etf", "change_pct": "-100"}]},
        ).json()
        soxx = next(r for r in body["rows"] if r["symbol"] == "SOXX")
        assert D(body["total_change"]) == -D(soxx["value_before"])

    @pytest.mark.parametrize(
        ("path", "payload"),
        [
            ("/api/v1/analytics/risk", None),
            ("/api/v1/simulations/buy", BUY),
            (
                "/api/v1/simulations/rebalance",
                {"dimension": "holding", "targets": [{"key": "a", "target_pct": "100"}]},
            ),
            ("/api/v1/simulations/scenario", {"standalone_change_pct": "-10"}),
        ],
    )
    def test_live_blocked(self, client, live_client, path, payload):
        send = (
            (lambda c, **kw: c.get(path, **kw))
            if payload is None
            else (lambda c, **kw: c.post(path, json=payload, **kw))
        )
        assert send(client, params={"source": "live"}).status_code == 503
        response = send(live_client, params={"source": "live"}, headers=bearer("owner-token"))
        assert response.json()["error"]["code"] == "KIS_NOT_CONFIGURED"


def test_blank_env_values_are_unset():
    settings = make_settings(database_url="", supabase_url="  ", kis_credential_key="")
    assert settings.database_url is None
    assert settings.supabase_url is None
    assert settings.kis_credential_key is None
