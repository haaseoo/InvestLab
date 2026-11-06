"""라우터 공통 의존성.

- source=live는 서명 검증된 토큰을 통과한 사용자에게 그 사용자 본인의 키로 만든 Provider를 돌려준다.
- 사용자 데이터 API는 검증된 토큰이 필요하며, DB 접근은 RLS가 적용되는 트랜잭션으로만 한다.
"""

from typing import Annotated

from fastapi import Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings
from app.core.errors import DatabaseNotConfiguredError
from app.core.security import AuthenticatedUser, authenticate
from app.db.database import Database
from app.providers.base import PortfolioProvider
from app.schemas.portfolio import Source
from app.services.live_accounts import LiveAccounts

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
        user = await authenticate(
            credentials.credentials if credentials else None, request.app.state.token_verifier
        )
        # LIVE 이력은 사용자 본인의 스냅샷(RLS)에서 읽으므로 확인된 사용자를 남겨 둔다.
        request.state.live_user = user
        return await request.app.state.live_accounts.provider_for(user)
    return request.app.state.mock_provider


async def current_user(request: Request, credentials: Credentials) -> AuthenticatedUser:
    return await authenticate(
        credentials.credentials if credentials else None, request.app.state.token_verifier
    )


def get_live_accounts(request: Request) -> LiveAccounts:
    return request.app.state.live_accounts


def get_database(request: Request) -> Database:
    db = request.app.state.db
    if db is None:
        raise DatabaseNotConfiguredError()
    return db


ProviderDep = Annotated[PortfolioProvider, Depends(resolve_provider)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]
UserDep = Annotated[AuthenticatedUser, Depends(current_user)]
DatabaseDep = Annotated[Database, Depends(get_database)]
LiveAccountsDep = Annotated[LiveAccounts, Depends(get_live_accounts)]
