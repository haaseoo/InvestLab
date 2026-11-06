"""인증·인가.

- 인증: Supabase가 발급한 JWT를 서명·만료·발급자·대상·역할까지 검증한다(core/auth.py).
- LIVE 인가: 사용자는 본인이 등록한 KIS 키로 본인 계좌만 조회한다. 키는 사용자 id로 찾으므로
  다른 사용자의 계좌에 닿을 경로가 없다(app/services/live_accounts.py).
- 어느 단계든 판단할 수 없으면 거부한다(fail closed).
"""

from dataclasses import dataclass
from typing import Protocol

from app.core.errors import AuthNotConfiguredError, AuthRequiredError


@dataclass(frozen=True)
class AuthenticatedUser:
    id: str
    email: str | None = None


class TokenVerifier(Protocol):
    async def verify(self, token: str) -> AuthenticatedUser:
        """검증 실패 시 InvalidTokenError를 발생시킨다."""
        ...


async def authenticate(token: str | None, verifier: TokenVerifier | None) -> AuthenticatedUser:
    if verifier is None:
        raise AuthNotConfiguredError()
    if not token:
        raise AuthRequiredError()
    return await verifier.verify(token)
