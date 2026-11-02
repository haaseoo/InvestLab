"""인증·인가.

- 인증: Supabase가 발급한 JWT를 서명·만료·발급자·대상·역할까지 검증한다(core/auth.py).
- LIVE 인가: KIS 인증정보는 서버 전역에 하나뿐이므로 "로그인했다"만으로는 부족하다.
  LIVE_OWNER_USER_ID와 일치하는 사용자만 허용한다.
- 어느 단계든 판단할 수 없으면 거부한다(fail closed).
"""

from dataclasses import dataclass
from typing import Protocol

from app.core.errors import (
    AuthNotConfiguredError,
    AuthRequiredError,
    LiveForbiddenError,
    LiveOwnerNotConfiguredError,
)


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


def is_live_owner(user: AuthenticatedUser, owner_user_id: str | None) -> bool:
    return bool(owner_user_id) and user.id == owner_user_id


def require_live_owner(user: AuthenticatedUser, owner_user_id: str | None) -> None:
    if not owner_user_id:
        raise LiveOwnerNotConfiguredError()
    if user.id != owner_user_id:
        raise LiveForbiddenError()


async def authorize_live_access(
    token: str | None,
    verifier: TokenVerifier | None,
    owner_user_id: str | None,
) -> AuthenticatedUser:
    user = await authenticate(token, verifier)
    require_live_owner(user, owner_user_id)
    return user
