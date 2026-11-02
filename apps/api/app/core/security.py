"""LIVE 접근 인가.

KIS 인증정보는 서버 전역에 하나뿐이므로 "로그인했다"만으로는 부족하다. 가입한 다른 사용자가
소유자의 계좌를 보지 못하도록 LIVE_OWNER_USER_ID와 일치하는 사용자만 허용한다.
어느 단계든 판단할 수 없으면 거부한다(fail closed).
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


class TokenVerifier(Protocol):
    async def verify(self, token: str) -> AuthenticatedUser:
        """검증 실패 시 InvalidTokenError를 발생시킨다."""
        ...


async def authorize_live_access(
    token: str | None,
    verifier: TokenVerifier | None,
    owner_user_id: str | None,
) -> AuthenticatedUser:
    if verifier is None:
        raise AuthNotConfiguredError()
    if not token:
        raise AuthRequiredError()
    user = await verifier.verify(token)
    if not owner_user_id:
        raise LiveOwnerNotConfiguredError()
    if user.id != owner_user_id:
        raise LiveForbiddenError()
    return user
