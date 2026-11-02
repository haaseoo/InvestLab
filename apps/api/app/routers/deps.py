"""라우터 공통 의존성.

- source=live는 서명 검증된 토큰 + 소유자 확인을 통과해야만 Provider를 돌려준다.
- 사용자 데이터 API는 검증된 토큰이 필요하며, DB 접근은 RLS가 적용되는 트랜잭션으로만 한다.
"""

from typing import Annotated

from fastapi import Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings
from app.core.errors import DatabaseNotConfiguredError
from app.core.security import AuthenticatedUser, authenticate, authorize_live_access
from app.db.database import Database
from app.providers.base import PortfolioProvider
from app.schemas.portfolio import Source

_bearer = HTTPBearer(auto_error=False)
Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


async def resolve_provider(
    request: Request,
    credentials: Credentials,
    source: Annotated[Source, Query(description="데이터 출처. 기본값은 mock")] = Source.MOCK,
) -> PortfolioProvider:
    if source is Source.LIVE:
        await authorize_live_access(
            token=credentials.credentials if credentials else None,
            verifier=request.app.state.token_verifier,
            owner_user_id=request.app.state.settings.live_owner_user_id,
        )
    return request.app.state.providers[source]


async def current_user(request: Request, credentials: Credentials) -> AuthenticatedUser:
    return await authenticate(
        credentials.credentials if credentials else None, request.app.state.token_verifier
    )


def get_database(request: Request) -> Database:
    db = request.app.state.db
    if db is None:
        raise DatabaseNotConfiguredError()
    return db


ProviderDep = Annotated[PortfolioProvider, Depends(resolve_provider)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]
UserDep = Annotated[AuthenticatedUser, Depends(current_user)]
DatabaseDep = Annotated[Database, Depends(get_database)]
