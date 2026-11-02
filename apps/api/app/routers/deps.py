"""라우터 공통 의존성. source=live는 인가를 통과해야만 Provider를 돌려준다."""

from typing import Annotated

from fastapi import Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings
from app.core.security import authorize_live_access
from app.providers.base import PortfolioProvider
from app.schemas.portfolio import Source

_bearer = HTTPBearer(auto_error=False)


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


async def resolve_provider(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    source: Annotated[Source, Query(description="데이터 출처. 기본값은 mock")] = Source.MOCK,
) -> PortfolioProvider:
    if source is Source.LIVE:
        await authorize_live_access(
            token=credentials.credentials if credentials else None,
            verifier=request.app.state.token_verifier,
            owner_user_id=request.app.state.settings.live_owner_user_id,
        )
    return request.app.state.providers[source]


ProviderDep = Annotated[PortfolioProvider, Depends(resolve_provider)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]
