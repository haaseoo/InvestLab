import json
import logging
from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient

from app.core.config import REPO_ROOT
from app.core.logging import install_log_masking, mask_account, mask_sensitive
from app.main import create_app
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
        settings = make_settings(
            kis_app_key="SECRETKEY123", kis_app_secret="SECRETVAL456", kis_account_no="5001234501"
        )
        text = TestClient(create_app(settings)).get("/api/v1/providers/status").text
        assert "SECRETKEY123" not in text
        assert "SECRETVAL456" not in text
        assert "5001234501" not in text


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

    def test_other_user_is_403(self, live_client):
        response = live_client.get(
            "/api/v1/portfolio", params={"source": "live"}, headers=bearer("other-token")
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "LIVE_FORBIDDEN"

    def test_missing_owner_config_is_denied(self):
        app = create_app(make_settings())
        from tests.conftest import FakeVerifier

        app.state.token_verifier = FakeVerifier()
        response = TestClient(app).get(
            "/api/v1/portfolio", params={"source": "live"}, headers=bearer("owner-token")
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "LIVE_OWNER_NOT_CONFIGURED"

    @pytest.mark.parametrize("path", LIVE_ENDPOINTS)
    def test_authorized_owner_gets_error_not_mock_fallback(self, live_client, path):
        assert OWNER_ID
        response = live_client.get(path, params={"source": "live"}, headers=bearer("owner-token"))
        assert response.status_code == 503
        body = response.json()
        assert body["error"]["code"] == "LIVE_NOT_IMPLEMENTED"
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
