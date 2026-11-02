"""Supabase JWT 검증.

Supabase 프로젝트의 비대칭 서명 키(JWKS)로 검증한다. 검증 항목:
- 서명: JWKS의 공개 키로 확인한다. 허용 알고리즘은 비대칭(ES256, RS256)뿐이다.
  HS256과 none은 거부한다(알고리즘 혼동 공격 방지).
- kid: 토큰 헤더의 kid와 일치하는 키만 쓴다. 키의 알고리즘과 헤더 알고리즘이 달라도 거부한다.
- 만료(exp)·발급 시각(iat): 필수이며 시계 오차는 leeway 초까지만 허용한다.
- 발급자(iss): {SUPABASE_URL}/auth/v1
- 대상(aud): authenticated
- 역할(role): authenticated
- sub: UUID 형식

서명 검증 없이 디코딩만 하는 경로는 없다.
"""

import asyncio
import time
import uuid

import httpx
import jwt

from app.core.errors import AuthUnavailableError, InvalidTokenError
from app.core.security import AuthenticatedUser

ALLOWED_ALGORITHMS = ("ES256", "RS256")
JWKS_TTL_SECONDS = 600
# 모르는 kid가 오면 키를 다시 받아 오되, 공격자가 이를 이용해 요청을 폭증시키지 못하게 간격을 둔다.
JWKS_REFRESH_MIN_INTERVAL = 30


class SupabaseTokenVerifier:
    def __init__(
        self,
        supabase_url: str,
        audience: str = "authenticated",
        leeway_seconds: int = 30,
        http_client: httpx.AsyncClient | None = None,
    ):
        base = supabase_url.rstrip("/")
        self.issuer = f"{base}/auth/v1"
        self.jwks_url = f"{self.issuer}/.well-known/jwks.json"
        self.audience = audience
        self.leeway = leeway_seconds
        self._client = http_client
        self._keys: dict[str, jwt.PyJWK] = {}
        self._fetched_at = 0.0
        self._lock = asyncio.Lock()

    async def _fetch_keys(self) -> None:
        client = self._client or httpx.AsyncClient(timeout=5.0)
        try:
            response = await client.get(self.jwks_url)
            response.raise_for_status()
            jwks = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise AuthUnavailableError() from exc
        finally:
            if self._client is None:
                await client.aclose()

        keys: dict[str, jwt.PyJWK] = {}
        for data in jwks.get("keys", []):
            kid = data.get("kid")
            if not kid or data.get("alg") not in ALLOWED_ALGORITHMS:
                continue
            try:
                keys[kid] = jwt.PyJWK(data)
            except jwt.PyJWTError:
                continue
        self._keys = keys
        self._fetched_at = time.monotonic()

    async def _key_for(self, kid: str) -> jwt.PyJWK | None:
        async with self._lock:
            age = time.monotonic() - self._fetched_at
            if not self._keys or age > JWKS_TTL_SECONDS:
                await self._fetch_keys()
            elif kid not in self._keys and age > JWKS_REFRESH_MIN_INTERVAL:
                await self._fetch_keys()
            return self._keys.get(kid)

    async def verify(self, token: str) -> AuthenticatedUser:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise InvalidTokenError() from exc

        algorithm = header.get("alg")
        kid = header.get("kid")
        if algorithm not in ALLOWED_ALGORITHMS or not isinstance(kid, str):
            raise InvalidTokenError()

        key = await self._key_for(kid)
        if key is None or key.algorithm_name != algorithm:
            raise InvalidTokenError()

        try:
            claims = jwt.decode(
                token,
                key.key,
                algorithms=[algorithm],
                audience=self.audience,
                issuer=self.issuer,
                leeway=self.leeway,
                options={"require": ["exp", "iat", "sub", "iss", "aud"]},
            )
        except jwt.PyJWTError as exc:
            raise InvalidTokenError() from exc

        if claims.get("role") != "authenticated":
            raise InvalidTokenError()
        try:
            user_id = str(uuid.UUID(claims["sub"]))
        except (ValueError, TypeError) as exc:
            raise InvalidTokenError() from exc

        email = claims.get("email")
        return AuthenticatedUser(id=user_id, email=email if isinstance(email, str) else None)
