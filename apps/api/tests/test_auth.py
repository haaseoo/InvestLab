"""JWT 검증 단위 테스트. 서명·만료·발급자·대상·역할과 알려진 공격 방식을 확인한다."""

import asyncio
import base64
import hashlib
import hmac
import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization

from app.core.errors import AuthUnavailableError, InvalidTokenError
from tests.jwt_helpers import OWNER_ID, JwksServer, KeyPair


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def key():
    return KeyPair()


@pytest.fixture
def server(key):
    return JwksServer(key)


def verify(server, token, **kwargs):
    return run(server.verifier(**kwargs).verify(token))


def rejects(server, token, **kwargs):
    with pytest.raises(InvalidTokenError):
        verify(server, token, **kwargs)


class TestValidToken:
    def test_valid(self, server, key):
        user = verify(server, key.sign())
        assert user.id == OWNER_ID
        assert user.email == "owner@example.com"

    def test_within_leeway(self, server, key):
        now = int(time.time())
        verify(server, key.sign(exp=now - 10), leeway=30)

    def test_jwks_is_cached(self, server, key):
        verifier = server.verifier()
        run(verifier.verify(key.sign()))
        run(verifier.verify(key.sign()))
        assert server.calls == 1

    def test_key_rotation_picks_up_new_kid(self, key):
        new_key = KeyPair(kid="rotated")
        server = JwksServer(key)
        verifier = server.verifier()
        run(verifier.verify(key.sign()))
        server.keys.append(new_key)
        verifier._fetched_at -= 60  # 재조회 최소 간격이 지난 상태
        run(verifier.verify(new_key.sign()))
        assert server.calls == 2


class TestRejected:
    def test_expired(self, server, key):
        rejects(server, key.sign(exp=int(time.time()) - 120), leeway=30)

    def test_missing_exp(self, server, key):
        rejects(server, key.sign(exp=None))

    def test_wrong_issuer(self, server, key):
        rejects(server, key.sign(iss="https://evil.supabase.co/auth/v1"))

    def test_wrong_audience(self, server, key):
        rejects(server, key.sign(aud="anon"))

    def test_anon_role(self, server, key):
        rejects(server, key.sign(role="anon"))

    def test_service_role(self, server, key):
        rejects(server, key.sign(role="service_role"))

    def test_sub_not_uuid(self, server, key):
        rejects(server, key.sign(sub="admin"))

    def test_tampered_payload(self, server, key):
        header, payload, signature = key.sign().split(".")
        claims = json.loads(base64.urlsafe_b64decode(payload + "=="))
        claims["sub"] = "22222222-2222-4222-8222-222222222222"
        forged = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
        rejects(server, f"{header}.{forged}.{signature}")

    def test_tampered_signature(self, server, key):
        header, payload, signature = key.sign().split(".")
        flipped = ("A" if signature[0] != "A" else "B") + signature[1:]
        rejects(server, f"{header}.{payload}.{flipped}")

    def test_signed_by_other_key_with_same_kid(self, server):
        attacker = KeyPair(kid="test-kid")
        rejects(server, attacker.sign())

    def test_alg_none(self, server):
        token = jwt.encode(
            {"sub": OWNER_ID, "aud": "authenticated", "role": "authenticated"},
            key=None,
            algorithm="none",
            headers={"kid": "test-kid"},
        )
        rejects(server, token)

    def test_hs256_with_public_key_as_secret(self, server, key):
        """알고리즘 혼동 공격: 공개 키를 HMAC 비밀로 써서 서명한 토큰."""
        public_pem = key.private.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        now = int(time.time())

        def b64(data: bytes) -> str:
            return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

        # PyJWT는 이런 토큰 생성을 거부하므로 서명을 직접 만든다.
        header = b64(json.dumps({"alg": "HS256", "typ": "JWT", "kid": "test-kid"}).encode())
        payload = b64(
            json.dumps(
                {
                    "sub": OWNER_ID,
                    "aud": "authenticated",
                    "iss": "https://test-project.supabase.co/auth/v1",
                    "role": "authenticated",
                    "iat": now,
                    "exp": now + 60,
                }
            ).encode()
        )
        signature = b64(
            hmac.new(public_pem, f"{header}.{payload}".encode(), hashlib.sha256).digest()
        )
        token = f"{header}.{payload}.{signature}"
        rejects(server, token)

    def test_header_alg_mismatch_with_key(self, server, key):
        token = key.sign()
        header, payload, signature = token.split(".")
        h = json.loads(base64.urlsafe_b64decode(header + "=="))
        h["alg"] = "RS256"
        header = base64.urlsafe_b64encode(json.dumps(h).encode()).rstrip(b"=").decode()
        rejects(server, f"{header}.{payload}.{signature}")

    def test_unknown_kid_refetch_is_rate_limited(self, server, key):
        verifier = server.verifier()
        run(verifier.verify(key.sign()))
        stranger = KeyPair(kid="unknown")
        for _ in range(5):
            with pytest.raises(InvalidTokenError):
                run(verifier.verify(stranger.sign()))
        assert server.calls == 1  # 최소 간격 안에서는 다시 받지 않는다

    @pytest.mark.parametrize("token", ["", "not-a-jwt", "a.b.c", "eyJ.eyJ.sig"])
    def test_garbage(self, server, token):
        rejects(server, token)


def test_jwks_unreachable_is_503_not_accept(key):
    server = JwksServer(key, fail=True)
    with pytest.raises(AuthUnavailableError):
        verify(server, key.sign())
