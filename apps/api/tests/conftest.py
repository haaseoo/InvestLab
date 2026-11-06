import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import REPO_ROOT, Settings
from app.core.errors import InvalidTokenError, KisNotConfiguredError
from app.core.security import AuthenticatedUser
from app.main import create_app

OWNER_ID = "owner-user"


class FakeVerifier:
    async def verify(self, token: str) -> AuthenticatedUser:
        if token == "owner-token":
            return AuthenticatedUser(id=OWNER_ID)
        if token == "other-token":
            return AuthenticatedUser(id="other-user")
        raise InvalidTokenError()


class FakeLiveAccounts:
    """사용자 id → Provider. 등록하지 않은 사용자는 키가 없는 것으로 본다."""

    store_available = True

    def __init__(self, providers: dict | None = None):
        self.providers = providers or {}

    async def provider_for(self, user: AuthenticatedUser):
        provider = self.providers.get(user.id)
        if provider is None:
            raise KisNotConfiguredError()
        return provider


def make_settings(**overrides) -> Settings:
    # 개발자의 .env가 테스트에 섞이지 않게 한다.
    return Settings(_env_file=None, **overrides)


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(make_settings()))


@pytest.fixture
def live_client() -> TestClient:
    """토큰 검증기가 구성되고, 아직 아무도 KIS 키를 등록하지 않은 앱."""
    app = create_app(make_settings())
    app.state.token_verifier = FakeVerifier()
    app.state.live_accounts = FakeLiveAccounts()
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def partial_data_dir(tmp_path: Path) -> Path:
    """NVDA 시세가 없고 USD 환율은 있는 Seed."""
    shutil.copy(REPO_ROOT / "data/mock/history.json", tmp_path / "history.json")
    seed = json.loads((REPO_ROOT / "data/mock/portfolio.json").read_text(encoding="utf-8"))
    for holding in seed["holdings"]:
        if holding["symbol"] == "NVDA":
            holding["current_price"] = None
    (tmp_path / "portfolio.json").write_text(json.dumps(seed), encoding="utf-8")
    return tmp_path
