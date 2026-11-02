"""실제 Supabase Auth 서버 테스트. 계정을 만들거나 바꾸지 않는다.

- 가입 차단: 설정에서 disable_signup이 켜졌는지 먼저 확인하고, 켜져 있을 때만 가입을 시도한다.
  (꺼져 있으면 실제 계정이 생기므로 시도하지 않고 실패 처리한다.)
- 로그인 거부: 존재하지 않는 계정으로 로그인하면 거부되어야 한다.
- 실제 JWKS: 프로젝트 공개 키로 검증기를 만들고, 위조 토큰이 거부되는지 확인한다.

소유자 계정으로의 실제 로그인 성공은 비밀번호가 필요하므로 자동 테스트하지 않는다.
"""

import asyncio
import uuid
from pathlib import Path

import httpx
import pytest

from app.core.auth import SupabaseTokenVerifier
from app.core.config import REPO_ROOT, Settings
from app.core.errors import InvalidTokenError
from tests.jwt_helpers import KeyPair

pytestmark = pytest.mark.integration


def _read_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    pairs = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            pairs[k.strip()] = v.strip()
    return pairs


SETTINGS = Settings()
KEY = _read_env(REPO_ROOT / ".env").get("SUPABASE_PUBLISHABLE_KEY", "")
if not SETTINGS.supabase_url or not KEY:
    pytest.skip("SUPABASE_URL·SUPABASE_PUBLISHABLE_KEY가 없어 건너뜁니다.", allow_module_level=True)

AUTH = f"{SETTINGS.supabase_url.rstrip('/')}/auth/v1"
HEADERS = {"apikey": KEY, "Content-Type": "application/json"}


def test_signup_is_disabled():
    settings = httpx.get(f"{AUTH}/settings", headers=HEADERS, timeout=10).json()
    assert settings["disable_signup"] is True, (
        "가입이 열려 있어 가입 시도 테스트를 하지 않았습니다."
    )
    r = httpx.post(
        f"{AUTH}/signup",
        headers=HEADERS,
        json={
            "email": f"signup-test-{uuid.uuid4().hex[:8]}@example.invalid",
            "password": uuid.uuid4().hex,
        },
        timeout=10,
    )
    assert r.status_code in (400, 403, 422)
    assert "signup" in r.text.lower()


def test_wrong_credentials_rejected():
    r = httpx.post(
        f"{AUTH}/token",
        params={"grant_type": "password"},
        headers=HEADERS,
        json={
            "email": f"nobody-{uuid.uuid4().hex[:8]}@example.invalid",
            "password": "wrong-password-1",
        },
        timeout=10,
    )
    assert r.status_code == 400
    assert "access_token" not in r.text


def test_real_jwks_has_asymmetric_key():
    jwks = httpx.get(f"{AUTH}/.well-known/jwks.json", timeout=10).json()
    assert jwks["keys"]
    assert {k["alg"] for k in jwks["keys"]} <= {"ES256", "RS256"}


def test_real_verifier_rejects_forged_token():
    jwks = httpx.get(f"{AUTH}/.well-known/jwks.json", timeout=10).json()
    real_kid = jwks["keys"][0]["kid"]
    forged = KeyPair(kid=real_kid).sign(iss=AUTH)  # 실제 kid·발급자를 흉내 내도 서명이 다르다
    verifier = SupabaseTokenVerifier(SETTINGS.supabase_url)
    with pytest.raises(InvalidTokenError):
        asyncio.run(verifier.verify(forged))
