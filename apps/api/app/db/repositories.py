"""사용자 데이터 저장소. 모든 함수는 Database.user_transaction()의 연결을 받는다.

RLS가 본인 행만 보여 주지만, 의도를 분명히 하려고 조건에도 auth.uid()를 쓴다.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Connection, text
from sqlalchemy.exc import IntegrityError

from app.core.errors import NotFoundError, SnapshotExistsError
from app.schemas.user_data import (
    SimulationHistoryCreate,
    SimulationHistoryItem,
    SnapshotDetail,
    SnapshotHolding,
    SnapshotRecord,
    SnapshotSummary,
    UserSettings,
    UserSettingsResponse,
)

SETTINGS_COLUMNS = "theme, preferred_currency, preferred_source, mask_account_numbers, updated_at"
SNAPSHOT_COLUMNS = (
    "id::text, source, valuation_currency, total_market_value, total_cost_basis, "
    "holding_count, valued_holding_count, is_complete, as_of, captured_at"
)


# ---------------------------------------------------------------- 설정


def get_settings(conn: Connection) -> UserSettingsResponse:
    row = (
        conn.execute(
            text(f"select {SETTINGS_COLUMNS} from public.user_settings where user_id = auth.uid()")
        )
        .mappings()
        .first()
    )
    if row is None:
        # 트리거로 만들어지지만, 없으면 기본값을 돌려준다(저장은 PUT에서).
        return UserSettingsResponse(updated_at=None)
    return UserSettingsResponse(**row)


def put_settings(conn: Connection, settings: UserSettings) -> UserSettingsResponse:
    row = (
        conn.execute(
            text(
                "insert into public.user_settings "
                "(user_id, theme, preferred_currency, preferred_source, mask_account_numbers) "
                "values (auth.uid(), :theme, :preferred_currency, :preferred_source, :mask) "
                "on conflict (user_id) do update set "
                "theme = excluded.theme, preferred_currency = excluded.preferred_currency, "
                "preferred_source = excluded.preferred_source, "
                "mask_account_numbers = excluded.mask_account_numbers "
                f"returning {SETTINGS_COLUMNS}"
            ),
            {
                "theme": settings.theme,
                "preferred_currency": settings.preferred_currency,
                "preferred_source": settings.preferred_source.value,
                "mask": settings.mask_account_numbers,
            },
        )
        .mappings()
        .one()
    )
    return UserSettingsResponse(**row)


# ---------------------------------------------------------------- 스냅샷


def insert_snapshot(conn: Connection, record: SnapshotRecord) -> str:
    """스냅샷과 종목을 같은 트랜잭션에 넣는다. 하나라도 실패하면 전체가 롤백된다."""
    try:
        with conn.begin_nested():
            snapshot_id = conn.execute(
                text(
                    "insert into public.portfolio_snapshots (user_id, source, valuation_currency, "
                    "total_market_value, total_cost_basis, holding_count, valued_holding_count, "
                    "is_complete, fx_rates, as_of, content_hash) values (auth.uid(), :source, "
                    ":currency, :mv, :cost, :count, :valued, :complete, cast(:fx as jsonb), :as_of, "
                    ":hash) returning id::text"
                ),
                {
                    "source": record.source.value,
                    "currency": record.valuation_currency,
                    "mv": record.total_market_value,
                    "cost": record.total_cost_basis,
                    "count": record.holding_count,
                    "valued": record.valued_holding_count,
                    "complete": record.is_complete,
                    "fx": json.dumps([fx.model_dump(mode="json") for fx in record.fx_rates]),
                    "as_of": record.as_of,
                    "hash": record.content_hash,
                },
            ).scalar_one()
            if record.holdings:
                conn.execute(
                    text(
                        "insert into public.holding_snapshots (portfolio_snapshot_id, user_id, "
                        "symbol, market, name, asset_type, quantity, average_cost, current_price, "
                        "currency, cost_basis, market_value, fx_rate, cost_basis_valuation, "
                        "market_value_valuation, valuation_status) values (cast(:sid as uuid), "
                        "auth.uid(), :symbol, :market, :name, :asset_type, :quantity, "
                        ":average_cost, :current_price, :currency, :cost_basis, :market_value, "
                        ":fx_rate, :cost_basis_valuation, :market_value_valuation, :status)"
                    ),
                    [
                        {
                            "sid": snapshot_id,
                            **h.model_dump(exclude={"valuation_status"}),
                            "status": h.valuation_status,
                        }
                        for h in record.holdings
                    ],
                )
    except IntegrityError as exc:
        if "portfolio_snapshots_unique_as_of" in str(exc.orig):
            raise SnapshotExistsError() from exc
        raise
    return snapshot_id


def list_snapshots(conn: Connection, limit: int) -> list[SnapshotSummary]:
    rows = conn.execute(
        text(
            f"select {SNAPSHOT_COLUMNS} from public.portfolio_snapshots "
            "where user_id = auth.uid() order by as_of desc limit :limit"
        ),
        {"limit": limit},
    ).mappings()
    return [SnapshotSummary(**_snapshot_row(r)) for r in rows]


def get_snapshot(conn: Connection, snapshot_id: str) -> SnapshotDetail:
    row = (
        conn.execute(
            text(
                f"select {SNAPSHOT_COLUMNS}, fx_rates, content_hash from public.portfolio_snapshots "
                "where user_id = auth.uid() and id = cast(:id as uuid)"
            ),
            {"id": snapshot_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise NotFoundError()
    holdings = conn.execute(
        text(
            "select symbol, market, name, asset_type, quantity, average_cost, current_price, "
            "currency, cost_basis, market_value, fx_rate, cost_basis_valuation, "
            "market_value_valuation, valuation_status from public.holding_snapshots "
            "where user_id = auth.uid() and portfolio_snapshot_id = cast(:id as uuid) "
            "order by market_value_valuation desc nulls last"
        ),
        {"id": snapshot_id},
    ).mappings()
    return SnapshotDetail(
        **_snapshot_row(row),
        fx_rates=row["fx_rates"],
        content_hash=row["content_hash"],
        holdings=[SnapshotHolding(**h) for h in holdings],
    )


def delete_snapshot(conn: Connection, snapshot_id: str) -> None:
    deleted = conn.execute(
        text(
            "delete from public.portfolio_snapshots "
            "where user_id = auth.uid() and id = cast(:id as uuid) returning id"
        ),
        {"id": snapshot_id},
    ).first()
    if deleted is None:
        raise NotFoundError()


def _snapshot_row(row: Any) -> dict[str, Any]:
    keys = SnapshotSummary.model_fields.keys()
    return {k: row[k] for k in keys}


# ---------------------------------------------------------------- 시뮬레이션 기록


def insert_simulation(conn: Connection, item: SimulationHistoryCreate) -> SimulationHistoryItem:
    row = (
        conn.execute(
            text(
                "insert into public.simulation_history (user_id, simulation_type, source, is_demo, "
                "input_json, result_json, as_of) values (auth.uid(), :type, :source, :is_demo, "
                "cast(:input as jsonb), cast(:result as jsonb), :as_of) "
                "returning id::text, simulation_type, source, is_demo, input_json, result_json, "
                "as_of, created_at"
            ),
            {
                "type": item.simulation_type,
                "source": item.source.value,
                "is_demo": item.source.value == "mock",
                "input": json.dumps(item.input, ensure_ascii=False),
                "result": json.dumps(item.result, ensure_ascii=False),
                "as_of": item.as_of,
            },
        )
        .mappings()
        .one()
    )
    return _simulation(row)


def list_simulations(conn: Connection, limit: int) -> list[SimulationHistoryItem]:
    rows = conn.execute(
        text(
            "select id::text, simulation_type, source, is_demo, input_json, result_json, as_of, "
            "created_at from public.simulation_history where user_id = auth.uid() "
            "order by created_at desc limit :limit"
        ),
        {"limit": limit},
    ).mappings()
    return [_simulation(r) for r in rows]


def delete_simulation(conn: Connection, item_id: str) -> None:
    deleted = conn.execute(
        text(
            "delete from public.simulation_history "
            "where user_id = auth.uid() and id = cast(:id as uuid) returning id"
        ),
        {"id": item_id},
    ).first()
    if deleted is None:
        raise NotFoundError()


def _simulation(row: Any) -> SimulationHistoryItem:
    return SimulationHistoryItem(
        id=row["id"],
        simulation_type=row["simulation_type"],
        source=row["source"],
        is_demo=row["is_demo"],
        input=row["input_json"],
        result=row["result_json"],
        as_of=row["as_of"],
        created_at=row["created_at"],
    )


# ---------------------------------------------------------------- KIS 인증정보(암호문만 다룬다)


@dataclass(frozen=True)
class KisCredentialRow:
    credentials_enc: bytes
    account_masked: str
    updated_at: datetime


@dataclass(frozen=True)
class KisTokenRow:
    token_enc: bytes
    expires_at: datetime


def get_kis_credentials(conn: Connection) -> KisCredentialRow | None:
    row = conn.execute(
        text(
            "select credentials_enc, account_masked, updated_at "
            "from public.kis_credentials where user_id = auth.uid()"
        )
    ).first()
    if row is None:
        return None
    return KisCredentialRow(bytes(row[0]), row[1], row[2])


def put_kis_credentials(
    conn: Connection,
    credentials_enc: bytes,
    account_masked: str,
    token_enc: bytes | None,
    token_expires_at: datetime | None,
) -> KisCredentialRow:
    """인증정보를 바꾸면 이전 키로 발급된 토큰도 함께 바꾼다(검증할 때 발급한 토큰 또는 없음)."""
    row = conn.execute(
        text(
            "insert into public.kis_credentials "
            "(user_id, credentials_enc, account_masked, token_enc, token_expires_at) "
            "values (auth.uid(), :cred, :masked, :token, :expires) "
            "on conflict (user_id) do update set "
            "credentials_enc = excluded.credentials_enc, "
            "account_masked = excluded.account_masked, "
            "token_enc = excluded.token_enc, token_expires_at = excluded.token_expires_at, "
            "updated_at = now() "
            "returning credentials_enc, account_masked, updated_at"
        ),
        {
            "cred": credentials_enc,
            "masked": account_masked,
            "token": token_enc,
            "expires": token_expires_at,
        },
    ).one()
    return KisCredentialRow(bytes(row[0]), row[1], row[2])


def delete_kis_credentials(conn: Connection) -> bool:
    deleted = conn.execute(
        text("delete from public.kis_credentials where user_id = auth.uid() returning user_id")
    ).first()
    return deleted is not None


def get_kis_token(conn: Connection) -> KisTokenRow | None:
    row = conn.execute(
        text(
            "select token_enc, token_expires_at from public.kis_credentials "
            "where user_id = auth.uid() and token_enc is not null"
        )
    ).first()
    if row is None:
        return None
    return KisTokenRow(bytes(row[0]), row[1])


def set_kis_token(
    conn: Connection,
    token_enc: bytes | None,
    expires_at: datetime | None,
    credentials_updated_at: datetime,
) -> None:
    """인증정보가 그 사이 바뀌었으면(updated_at 불일치) 이전 키의 토큰을 덮어쓰지 않는다."""
    conn.execute(
        text(
            "update public.kis_credentials set token_enc = :token, token_expires_at = :expires "
            "where user_id = auth.uid() and updated_at = :version"
        ),
        {"token": token_enc, "expires": expires_at, "version": credentials_updated_at},
    )
