"""실제 검증기(SupabaseTokenVerifier)를 붙인 API 인증·인가 테스트. DB 없이 실행된다."""

import logging
import time

import pytest
from fastapi.testclient import TestClient

from app.core.logging import install_log_masking
from app.main import create_app
from tests.conftest import make_settings
from tests.jwt_helpers import OTHER_ID, OWNER_ID, SUPABASE_URL, JwksServer, KeyPair

LIVE_GET = [
    "/api/v1/portfolio",
    "/api/v1/portfolio/holdings",
    "/api/v1/analytics/risk",
    "/api/v1/portfolio/history",
]


@pytest.fixture
def key():
    return KeyPair()


@pytest.fixture
def client(key):
    app = create_app(make_settings(supabase_url=SUPABASE_URL, live_owner_user_id=OWNER_ID))
    app.state.token_verifier = JwksServer(key).verifier()
    return TestClient(app)


def auth(token):
    return {"Authorization": f"Bearer {token}"}


class TestLive:
    @pytest.mark.parametrize("path", LIVE_GET)
    def test_no_token_401(self, client, path):
        r = client.get(path, params={"source": "live"})
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "AUTH_REQUIRED"

    @pytest.mark.parametrize("path", LIVE_GET)
    def test_owner_reaches_provider_and_gets_not_configured(self, client, key, path):
        r = client.get(path, params={"source": "live"}, headers=auth(key.sign()))
        assert r.status_code == 503
        assert r.json()["error"]["code"] in {"KIS_NOT_CONFIGURED", "DB_NOT_CONFIGURED"}
        assert "VOO" not in r.text  # Mock으로 대체하지 않는다

    def test_non_owner_403(self, client, key):
        r = client.get(
            "/api/v1/portfolio", params={"source": "live"}, headers=auth(key.sign(sub=OTHER_ID))
        )
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "LIVE_FORBIDDEN"

    def test_expired_401(self, client, key):
        token = key.sign(exp=int(time.time()) - 3600)
        r = client.get("/api/v1/portfolio", params={"source": "live"}, headers=auth(token))
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "INVALID_TOKEN"

    def test_forged_401(self, client):
        r = client.get(
            "/api/v1/portfolio", params={"source": "live"}, headers=auth(KeyPair().sign())
        )
        assert r.status_code == 401

    def test_mock_needs_no_login(self, client):
        r = client.get("/api/v1/portfolio")
        assert r.status_code == 200
        assert r.json()["is_demo"] is True

    def test_mock_with_token_still_demo(self, client, key):
        r = client.get("/api/v1/portfolio", headers=auth(key.sign()))
        assert r.json()["source"] == "mock" and r.json()["is_demo"] is True


class TestAccount:
    def test_me(self, client, key):
        body = client.get("/api/v1/me", headers=auth(key.sign())).json()
        assert body == {
            "user_id": OWNER_ID,
            "email": "owner@example.com",
            "is_live_owner": True,
            "database_available": False,
        }

    def test_me_other_user_not_owner(self, client, key):
        body = client.get("/api/v1/me", headers=auth(key.sign(sub=OTHER_ID))).json()
        assert body["is_live_owner"] is False

    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("get", "/api/v1/me"),
            ("get", "/api/v1/settings"),
            ("put", "/api/v1/settings"),
            ("get", "/api/v1/snapshots"),
            ("post", "/api/v1/snapshots?source=live"),
            ("get", "/api/v1/simulations/history"),
        ],
    )
    def test_user_endpoints_require_login(self, client, method, path):
        r = getattr(client, method)(path)
        assert r.status_code in (401, 422)
        if r.status_code == 401:
            assert r.json()["error"]["code"] == "AUTH_REQUIRED"

    def test_db_not_configured(self, client, key):
        r = client.get("/api/v1/settings", headers=auth(key.sign()))
        assert r.status_code == 503
        assert r.json()["error"]["code"] == "DB_NOT_CONFIGURED"

    def test_mock_snapshot_forbidden_before_db(self, client, key):
        app = client.app
        app.state.db = object()  # DB 접근 전에 거부되는지 확인
        r = client.post("/api/v1/snapshots", params={"source": "mock"}, headers=auth(key.sign()))
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "MOCK_SNAPSHOT_FORBIDDEN"

    def test_auth_not_configured_without_supabase_url(self):
        c = TestClient(create_app(make_settings()))
        r = c.get("/api/v1/me", headers=auth("x"))
        assert r.status_code == 503
        assert r.json()["error"]["code"] == "AUTH_NOT_CONFIGURED"

    def test_provider_status_reports_auth(self, client):
        live = next(
            p
            for p in client.get("/api/v1/providers/status").json()["providers"]
            if p["source"] == "live"
        )
        checks = {c["key"]: c["ok"] for c in live["checks"]}
        assert checks["auth"] is True
        assert checks["owner"] is True
        assert checks["database"] is False
        assert checks["kis_credentials"] is False
        assert live["state"] == "not_configured"


class TestNoSecretsInLogs:
    def test_tokens_and_dsn_masked(self, client, key, caplog):
        install_log_masking()
        token = key.sign()
        dsn = "postgresql://postgres.ref:SuperSecret123@aws-0.pooler.supabase.com:5432/postgres"
        with caplog.at_level(logging.DEBUG):
            client.get("/api/v1/portfolio", params={"source": "live"}, headers=auth(token))
            logging.getLogger("investlab.test").error("connect %s with Bearer %s", dsn, token)
            try:
                raise RuntimeError(f"failed {dsn} token={token}")
            except RuntimeError:
                logging.getLogger("investlab.test").exception("boom")
        text = caplog.text
        assert token not in text
        assert "SuperSecret123" not in text
        assert "sb_secret_" not in text

    def test_publishable_and_secret_keys_masked(self, caplog):
        install_log_masking()
        with caplog.at_level(logging.INFO):
            logging.getLogger("investlab.test").info("keys sb_publishable_abc123 sb_secret_xyz789")
        assert "abc123" not in caplog.text and "xyz789" not in caplog.text
