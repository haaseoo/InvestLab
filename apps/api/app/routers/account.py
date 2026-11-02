"""계정과 사용자 설정. 모두 로그인이 필요하다."""

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from app.core.security import is_live_owner
from app.db import repositories as repo
from app.routers.deps import DatabaseDep, SettingsDep, UserDep
from app.schemas.user_data import MeResponse, UserSettings, UserSettingsResponse

router = APIRouter(prefix="/api/v1")


@router.get("/me", response_model=MeResponse)
async def me(request: Request, user: UserDep, settings: SettingsDep) -> MeResponse:
    return MeResponse(
        user_id=user.id,
        email=user.email,
        is_live_owner=is_live_owner(user, settings.live_owner_user_id),
        database_available=request.app.state.db is not None,
    )


@router.get("/settings", response_model=UserSettingsResponse)
async def get_user_settings(user: UserDep, db: DatabaseDep) -> UserSettingsResponse:
    def run():
        with db.user_transaction(user) as conn:
            return repo.get_settings(conn)

    return await run_in_threadpool(run)


@router.put("/settings", response_model=UserSettingsResponse)
async def put_user_settings(
    body: UserSettings, user: UserDep, db: DatabaseDep
) -> UserSettingsResponse:
    def run():
        with db.user_transaction(user) as conn:
            return repo.put_settings(conn, body)

    return await run_in_threadpool(run)
