"""테스트용 JWT 발급기. 실제 Supabase 키가 아니라 테스트마다 만든 EC 키로 서명한다."""

import json
import time
import uuid

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from jwt.algorithms import ECAlgorithm

from app.core.auth import SupabaseTokenVerifier

SUPABASE_URL = "https://test-project.supabase.co"
ISSUER = f"{SUPABASE_URL}/auth/v1"
OWNER_ID = "11111111-1111-4111-8111-111111111111"
OTHER_ID = "22222222-2222-4222-8222-222222222222"


class KeyPair:
    def __init__(self, kid: str = "test-kid"):
        self.kid = kid
        self.private = ec.generate_private_key(ec.SECP256R1())
        jwk = json.loads(ECAlgorithm.to_jwk(self.private.public_key()))
        self.jwk = {**jwk, "kid": kid, "alg": "ES256", "use": "sig"}

    def sign(self, claims: dict | None = None, headers: dict | None = None, **overrides) -> str:
        now = int(time.time())
        payload = {
            "sub": OWNER_ID,
            "aud": "authenticated",
            "iss": ISSUER,
            "role": "authenticated",
            "email": "owner@example.com",
            "iat": now,
            "exp": now + 3600,
            **(claims or {}),
        }
        for key, value in overrides.items():
            if value is None:
                payload.pop(key, None)
            else:
                payload[key] = value
        return jwt.encode(
            payload, self.private, algorithm="ES256", headers={"kid": self.kid, **(headers or {})}
        )


class JwksServer:
    """httpx.MockTransport로 JWKS 응답을 흉내 낸다. 호출 횟수를 센다."""

    def __init__(self, *keys: KeyPair, fail: bool = False):
        self.keys = list(keys)
        self.calls = 0
        self.fail = fail

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        assert request.url.path == "/auth/v1/.well-known/jwks.json"
        if self.fail:
            return httpx.Response(503)
        return httpx.Response(200, json={"keys": [k.jwk for k in self.keys]})

    def verifier(self, leeway: int = 30) -> SupabaseTokenVerifier:
        client = httpx.AsyncClient(transport=httpx.MockTransport(self.handler))
        return SupabaseTokenVerifier(SUPABASE_URL, leeway_seconds=leeway, http_client=client)


def random_user_id() -> str:
    return str(uuid.uuid4())
