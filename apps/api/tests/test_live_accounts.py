"""사용자별 KIS 키 저장·사용. DB는 메모리 가짜로, KIS는 가짜 전송 계층으로 대신한다.

실제 SQL·RLS는 test_db_integration.py가 확인한다.
"""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest

from app.core.crypto import CredentialCipher, generate_key
from app.core.errors import (
    DatabaseNotConfiguredError,
    KisAuthError,
    KisCredentialStoreNotConfiguredError,
    KisCredentialsUnreadableError,
    KisNotConfiguredError,
)
from app.core.security import AuthenticatedUser
from app.db import repositories as repo
from app.integrations.kis.credentials import KisCredentials
from app.services.live_accounts import LiveAccounts
from tests.kis_fakes import ACCOUNT, APP_KEY, APP_SECRET, TOKEN, FakeKis, FakeMaster

pytestmark = pytest.mark.anyio

ALICE = AuthenticatedUser(id="11111111-1111-1111-1111-111111111111")
BOB = AuthenticatedUser(id="22222222-2222-2222-2222-222222222222")
CREDENTIALS = KisCredentials.parse(APP_KEY, APP_SECRET, ACCOUNT)


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeConn:
    def __init__(self, rows: dict, user_id: str):
        self.rows = rows
        self.uid = user_id


class FakeDb:
    """user_transaction은 사용자 id만 넘긴다. 저장소 함수가 그 id의 행만 다룬다(RLS 흉내)."""

    def __init__(self):
        self.rows: dict[str, dict] = {}
        self.clock = datetime(2026, 11, 6, tzinfo=UTC)

    @contextmanager
    def user_transaction(self, user):
        yield FakeConn(self.rows, user.id)

    def tick(self) -> datetime:
        self.clock += timedelta(seconds=1)
        return self.clock


@pytest.fixture
def db(monkeypatch) -> FakeDb:
    fake = FakeDb()

    def get_credentials(conn):
        row = conn.rows.get(conn.uid)
        if row is None:
            return None
        return repo.KisCredentialRow(row["cred"], row["masked"], row["updated_at"])

    def put_credentials(conn, cred, masked, token, expires):
        conn.rows[conn.uid] = {
            "cred": cred,
            "masked": masked,
            "token": token,
            "expires": expires,
            "updated_at": fake.tick(),
        }
        return get_credentials(conn)

    def delete_credentials(conn):
        return conn.rows.pop(conn.uid, None) is not None

    def get_token(conn):
        row = conn.rows.get(conn.uid)
        if row is None or row["token"] is None:
            return None
        return repo.KisTokenRow(row["token"], row["expires"])

    def set_token(conn, token, expires, version):
        row = conn.rows.get(conn.uid)
        if row is not None and row["updated_at"] == version:
            row["token"], row["expires"] = token, expires

    monkeypatch.setattr(repo, "get_kis_credentials", get_credentials)
    monkeypatch.setattr(repo, "put_kis_credentials", put_credentials)
    monkeypatch.setattr(repo, "delete_kis_credentials", delete_credentials)
    monkeypatch.setattr(repo, "get_kis_token", get_token)
    monkeypatch.setattr(repo, "set_kis_token", set_token)
    return fake


@pytest.fixture
def kis() -> FakeKis:
    return FakeKis()


def make_accounts(db, kis, tmp_path, key: str | None = None) -> LiveAccounts:
    return LiveAccounts(
        db=db,
        cipher=CredentialCipher(key or KEY),
        master=FakeMaster(),
        classification_file=tmp_path / "none.json",
        transport=kis.transport(),
    )


KEY = generate_key()


class TestRegister:
    async def test_verifies_then_stores_only_ciphertext(self, db, kis, tmp_path):
        accounts = make_accounts(db, kis, tmp_path)
        status = await accounts.register(ALICE, CREDENTIALS)
        assert status.registered and status.account_masked == "********01"
        # 실제로 잔고를 조회해 본 뒤에 저장한다
        assert kis.count("inquire-balance") == 1
        row = db.rows[ALICE.id]
        stored = row["cred"] + row["token"]
        for secret in (APP_KEY, APP_SECRET, TOKEN, "12345678"):
            assert secret.encode() not in stored

    async def test_wrong_keys_are_not_stored(self, db, tmp_path):
        kis = FakeKis(token_status=403)
        with pytest.raises(KisAuthError):
            await make_accounts(db, kis, tmp_path).register(ALICE, CREDENTIALS)
        assert db.rows == {}

    async def test_token_from_verification_is_reused(self, db, kis, tmp_path):
        await make_accounts(db, kis, tmp_path).register(ALICE, CREDENTIALS)
        # 서버 재시작(새 인스턴스) 뒤에도 DB의 토큰을 쓰고 재발급하지 않는다
        provider = await make_accounts(db, kis, tmp_path).provider_for(ALICE)
        await provider.get_holdings("KRW")
        assert kis.count("/oauth2/tokenP") == 1


class TestProviderFor:
    async def test_not_registered(self, db, kis, tmp_path):
        with pytest.raises(KisNotConfiguredError):
            await make_accounts(db, kis, tmp_path).provider_for(ALICE)

    async def test_provider_is_reused_per_user(self, db, kis, tmp_path):
        accounts = make_accounts(db, kis, tmp_path)
        await accounts.register(ALICE, CREDENTIALS)
        first = await accounts.provider_for(ALICE)
        assert await accounts.provider_for(ALICE) is first
        with pytest.raises(KisNotConfiguredError):
            await accounts.provider_for(BOB)

    async def test_ciphertext_moved_to_other_user_is_unreadable(self, db, kis, tmp_path):
        accounts = make_accounts(db, kis, tmp_path)
        await accounts.register(ALICE, CREDENTIALS)
        db.rows[BOB.id] = dict(db.rows[ALICE.id])
        with pytest.raises(KisCredentialsUnreadableError):
            await accounts.provider_for(BOB)

    async def test_other_master_key_is_unreadable(self, db, kis, tmp_path):
        await make_accounts(db, kis, tmp_path).register(ALICE, CREDENTIALS)
        with pytest.raises(KisCredentialsUnreadableError):
            await make_accounts(db, kis, tmp_path, key=generate_key()).provider_for(ALICE)

    async def test_reregister_replaces_provider(self, db, kis, tmp_path):
        accounts = make_accounts(db, kis, tmp_path)
        await accounts.register(ALICE, CREDENTIALS)
        first = await accounts.provider_for(ALICE)
        await accounts.register(ALICE, KisCredentials.parse(APP_KEY, APP_SECRET, "12345678-01"))
        assert await accounts.provider_for(ALICE) is not first

    async def test_remove(self, db, kis, tmp_path):
        accounts = make_accounts(db, kis, tmp_path)
        await accounts.register(ALICE, CREDENTIALS)
        await accounts.provider_for(ALICE)
        await accounts.remove(ALICE)
        assert db.rows == {}
        with pytest.raises(KisNotConfiguredError):
            await accounts.provider_for(ALICE)
        assert (await accounts.status(ALICE)).registered is False


class TestNotConfigured:
    async def test_no_cipher(self, db, tmp_path):
        accounts = LiveAccounts(db, None, FakeMaster(), tmp_path / "c.json")
        with pytest.raises(KisCredentialStoreNotConfiguredError):
            await accounts.provider_for(ALICE)
        with pytest.raises(KisCredentialStoreNotConfiguredError):
            await accounts.register(ALICE, CREDENTIALS)

    async def test_no_database(self, tmp_path):
        accounts = LiveAccounts(None, CredentialCipher(KEY), FakeMaster(), tmp_path / "c.json")
        with pytest.raises(DatabaseNotConfiguredError):
            await accounts.provider_for(ALICE)


class TestCredentialsApi:
    @pytest.fixture
    def api(self, db, kis, tmp_path):
        from fastapi.testclient import TestClient

        from app.main import create_app
        from tests.conftest import OWNER_ID, FakeVerifier, make_settings

        app = create_app(make_settings())
        app.state.token_verifier = FakeVerifier()
        app.state.live_accounts = make_accounts(db, kis, tmp_path)
        self.owner = OWNER_ID
        return TestClient(app, raise_server_exceptions=False)

    H = {"Authorization": "Bearer owner-token"}
    BODY = {"app_key": APP_KEY, "app_secret": APP_SECRET, "account_no": ACCOUNT}

    def test_register_status_delete(self, api, db):
        assert api.get("/api/v1/kis/credentials", headers=self.H).json()["registered"] is False
        r = api.put("/api/v1/kis/credentials", headers=self.H, json=self.BODY)
        assert r.status_code == 200
        for secret in (APP_KEY, APP_SECRET, TOKEN, "12345678"):
            assert secret not in r.text
        assert r.json()["account_masked"] == "********01"
        assert list(db.rows) == [self.owner]
        live = api.get("/api/v1/portfolio", params={"source": "live"}, headers=self.H)
        assert live.status_code == 200 and live.json()["source"] == "live"
        # 다른 사용자는 키가 없으므로 조회할 수 없다
        other = api.get(
            "/api/v1/portfolio",
            params={"source": "live"},
            headers={"Authorization": "Bearer other-token"},
        )
        assert other.status_code == 409
        assert api.delete("/api/v1/kis/credentials", headers=self.H).status_code == 204
        assert db.rows == {}

    def test_invalid_input_is_not_echoed(self, api, db):
        body = {"app_key": "bad-key", "app_secret": "s", "account_no": "999"}
        r = api.put("/api/v1/kis/credentials", headers=self.H, json=body)
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "INVALID_KIS_CREDENTIALS"
        assert "bad-key" not in r.text and "999" not in r.text
        assert db.rows == {}

    def test_unknown_field_rejected(self, api):
        r = api.put("/api/v1/kis/credentials", headers=self.H, json={**self.BODY, "x": APP_KEY})
        assert r.status_code == 422
        assert APP_KEY not in r.text

    def test_wrong_keys_rejected_without_saving(self, api, db, kis):
        kis.token_status = 403
        r = api.put("/api/v1/kis/credentials", headers=self.H, json=self.BODY)
        assert r.json()["error"]["code"] == "KIS_AUTH_FAILED"
        assert db.rows == {}
