"""포트폴리오 스냅샷(실제 계좌 실적) API.

- 조회·삭제: 로그인 사용자 본인 것만(RLS).
- 저장: 본인 KIS 키로 조회한 실제 데이터만. Mock은 저장하지 않는다.
  키를 등록하지 않았거나 조회에 실패하면 오류를 내므로 저장되는 것이 없다.
"""

from typing import Annotated

from fastapi import APIRouter, Query, Response, status
from starlette.concurrency import run_in_threadpool

from app.core.errors import MockSnapshotForbiddenError
from app.db import repositories as repo
from app.routers.deps import DatabaseDep, LiveAccountsDep, SettingsDep, UserDep
from app.schemas.portfolio import Source
from app.schemas.user_data import SnapshotDetail, SnapshotListResponse
from app.services import snapshots as service

router = APIRouter(prefix="/api/v1/snapshots")


@router.get("", response_model=SnapshotListResponse)
async def list_snapshots(
    user: UserDep, db: DatabaseDep, limit: Annotated[int, Query(ge=1, le=100)] = 30
) -> SnapshotListResponse:
    def run():
        with db.user_transaction(user) as conn:
            return SnapshotListResponse(snapshots=repo.list_snapshots(conn, limit))

    return await run_in_threadpool(run)


@router.get("/{snapshot_id}", response_model=SnapshotDetail)
async def get_snapshot(snapshot_id: str, user: UserDep, db: DatabaseDep) -> SnapshotDetail:
    _check_uuid(snapshot_id)

    def run():
        with db.user_transaction(user) as conn:
            return repo.get_snapshot(conn, snapshot_id)

    return await run_in_threadpool(run)


@router.post("", response_model=SnapshotDetail, status_code=status.HTTP_201_CREATED)
async def create_snapshot(
    user: UserDep,
    db: DatabaseDep,
    settings: SettingsDep,
    live_accounts: LiveAccountsDep,
    source: Annotated[Source, Query()],
) -> SnapshotDetail:
    if source is not Source.LIVE:
        raise MockSnapshotForbiddenError()
    provider = await live_accounts.provider_for(user)
    record = await service.capture(provider, settings.valuation_currency)

    def run():
        with db.user_transaction(user) as conn:
            snapshot_id = repo.insert_snapshot(conn, record)
            return repo.get_snapshot(conn, snapshot_id)

    return await run_in_threadpool(run)


@router.delete("/{snapshot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_snapshot(snapshot_id: str, user: UserDep, db: DatabaseDep) -> Response:
    _check_uuid(snapshot_id)

    def run():
        with db.user_transaction(user) as conn:
            repo.delete_snapshot(conn, snapshot_id)

    await run_in_threadpool(run)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _check_uuid(value: str) -> None:
    import uuid

    from app.core.errors import NotFoundError

    try:
        uuid.UUID(value)
    except ValueError as exc:
        raise NotFoundError() from exc
