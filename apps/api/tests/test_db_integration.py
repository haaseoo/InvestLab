"""실제 Supabase DB 통합 테스트.

- DATABASE_URL이 없으면 건너뛴다. `pytest -m "not integration"`으로 제외할 수 있다.
- 모든 작업은 하나의 트랜잭션 안에서 하고 마지막에 롤백한다. 실제 DB에 데이터가 남지 않는다.
- 다른 사용자는 트랜잭션 안에서만 임시로 만든다(롤백으로 사라진다).
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, create_engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError, ProgrammingError

from app.core.config import Settings
from app.core.errors import NotFoundError, SnapshotExistsError
from app.core.security import AuthenticatedUser
from app.db import repositories as repo
from app.db.database import _engine_url, as_user
from app.main import create_app
from app.providers.base import PortfolioProvider
from app.schemas.portfolio import (
    AccountSummary,
    AssetClass,
    AssetType,
    FxRate,
    Position,
    ProviderStatus,
    Quote,
    Source,
)
from app.schemas.user_data import SimulationHistoryCreate, UserSettings
from app.services.snapshots import build_snapshot_record
from app.services.valuation import build_holding

pytestmark = pytest.mark.integration

SETTINGS = Settings()  # 루트 .env를 읽는다
if SETTINGS.database_url is None or SETTINGS.live_owner_user_id is None:
    pytest.skip(
        "DATABASE_URL·LIVE_OWNER_USER_ID가 없어 DB 통합 테스트를 건너뜁니다.",
        allow_module_level=True,
    )

OWNER = AuthenticatedUser(id=SETTINGS.live_owner_user_id)
AS_OF = datetime(2026, 10, 30, 6, 30, tzinfo=UTC)
TABLES = [
    "profiles",
    "user_settings",
    "portfolio_snapshots",
    "holding_snapshots",
    "ai_reports",
    "simulation_history",
]


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(
        _engine_url(SETTINGS.database_url.get_secret_value()),
        connect_args={"connect_timeout": 10},
        hide_parameters=True,
    )
    yield eng
    eng.dispose()


@pytest.fixture
def conn(engine) -> Iterator[Connection]:
    """테스트 하나 = 트랜잭션 하나. 끝나면 무조건 롤백한다."""
    connection = engine.connect()
    outer = connection.begin()
    try:
        yield connection
    finally:
        outer.rollback()
        connection.close()


class RollbackDatabase:
    """API 테스트용. 앱의 user_transaction을 테스트 트랜잭션 안의 savepoint로 바꾼다."""

    def __init__(self, connection: Connection):
        self.connection = connection

    @contextmanager
    def user_transaction(self, user: AuthenticatedUser):
        with self.connection.begin_nested(), as_user(self.connection, user):
            yield self.connection


@contextmanager
def as_(conn: Connection, user: AuthenticatedUser):
    with conn.begin_nested(), as_user(conn, user):
        yield conn


def make_user(conn: Connection) -> AuthenticatedUser:
    """트랜잭션 안에서만 존재하는 임시 사용자."""
    user_id = str(uuid.uuid4())
    conn.execute(
        text(
            "insert into auth.users (id, aud, role, email, created_at, updated_at) "
            "values (cast(:id as uuid), 'authenticated', 'authenticated', :email, now(), now())"
        ),
        {"id": user_id, "email": f"test-{user_id[:8]}@example.invalid"},
    )
    return AuthenticatedUser(id=user_id)


class FakeLiveProvider(PortfolioProvider):
    """실제 계좌 데이터처럼 is_demo=False인 Provider. 테스트 전용."""

    source = Source.LIVE
    is_demo = False

    def __init__(self, as_of=AS_OF, price_missing=False):
        self.as_of = as_of
        self.price_missing = price_missing

    async def get_fx_rates(self):
        return [
            FxRate(
                base_currency="USD",
                quote_currency="KRW",
                rate=D("1400"),
                as_of=self.as_of,
                source=Source.LIVE,
            )
        ]

    async def get_holdings(self, valuation_currency):
        fx = await self.get_fx_rates()
        specs = [
            (
                "005930",
                "KRX",
                "KRW",
                "10",
                "70000",
                "80000",
                AssetType.STOCK,
                AssetClass.DOMESTIC_STOCK,
            ),
            ("VOO", "AMEX", "USD", "2", "500", "600.5", AssetType.ETF, AssetClass.BROAD_INDEX_ETF),
        ]
        holdings = []
        for symbol, market, currency, qty, cost, price, atype, aclass in specs:
            missing = self.price_missing and symbol == "VOO"
            holdings.append(
                build_holding(
                    Position(
                        symbol=symbol,
                        market=market,
                        asset_type=atype,
                        asset_class=aclass,
                        name=symbol,
                        quantity=D(qty),
                        average_cost=D(cost),
                        currency=currency,
                    ),
                    Quote(
                        symbol=symbol,
                        market=market,
                        price=None if missing else D(price),
                        currency=currency,
                        as_of=None if missing else self.as_of,
                        source=Source.LIVE,
                        is_demo=False,
                    ),
                    fx,
                    valuation_currency,
                    Source.LIVE,
                    False,
                )
            )
        return holdings

    async def get_account_summary(self):
        return AccountSummary(
            account_masked=None,
            cash_balances=None,
            as_of=self.as_of,
            source=Source.LIVE,
            is_demo=False,
        )

    async def get_quotes(self, symbols=None):
        return []

    async def get_history(self):
        return []

    async def get_etf_compositions(self):
        return []

    def get_provider_status(self):
        return ProviderStatus(
            source=Source.LIVE, state="ready", is_demo=False, label="LIVE", message="test"
        )


def record(provider=None):
    import asyncio

    provider = provider or FakeLiveProvider()
    holdings = asyncio.run(provider.get_holdings("KRW"))
    fx = asyncio.run(provider.get_fx_rates())
    return build_snapshot_record(provider, holdings, fx, "KRW")


# ---------------------------------------------------------------- 스키마·권한


class TestSchema:
    def test_rls_enabled_everywhere(self, conn):
        rows = conn.execute(
            text(
                "select relname, relrowsecurity from pg_class "
                "where relnamespace = 'public'::regnamespace and relname = any(:t)"
            ),
            {"t": TABLES},
        ).all()
        assert dict(rows) == dict.fromkeys(TABLES, True)

    def test_anon_has_no_table_privileges(self, conn):
        count = conn.execute(
            text(
                "select count(*) from information_schema.role_table_grants "
                "where table_schema = 'public' and grantee = 'anon' and table_name = any(:t)"
            ),
            {"t": TABLES},
        ).scalar_one()
        assert count == 0

    @pytest.mark.parametrize("table", TABLES)
    def test_anon_cannot_read(self, conn, table):
        with pytest.raises(ProgrammingError, match="permission denied"), conn.begin_nested():
            conn.execute(text("set local role anon"))
            conn.execute(text(f"select * from public.{table} limit 1"))  # noqa: S608

    def test_authenticated_without_claims_sees_nothing(self, conn):
        with conn.begin_nested():
            conn.execute(text("set local role authenticated"))
            assert conn.execute(text("select count(*) from public.user_settings")).scalar_one() == 0
            conn.execute(text("reset role"))

    def test_migration_recorded(self, conn):
        versions = (
            conn.execute(text("select version from investlab_meta.schema_migrations"))
            .scalars()
            .all()
        )
        assert "20261102120000" in versions

    def test_owner_has_default_rows(self, conn):
        with as_(conn, OWNER):
            settings = repo.get_settings(conn)
        assert settings.updated_at is not None


# ---------------------------------------------------------------- RLS: 사용자 분리


class TestRls:
    def test_new_user_trigger_creates_rows(self, conn):
        user = make_user(conn)
        with as_(conn, user):
            assert repo.get_settings(conn).preferred_source == "mock"
            profile = conn.execute(text("select count(*) from public.profiles")).scalar_one()
        assert profile == 1  # 자기 행 하나만 보인다

    def test_other_user_cannot_see_owner_rows(self, conn):
        with as_(conn, OWNER):
            snapshot_id = repo.insert_snapshot(conn, record())
            repo.insert_simulation(
                conn,
                SimulationHistoryCreate(simulation_type="buy", source="mock", input={}, result={}),
            )
        other = make_user(conn)
        with as_(conn, other):
            assert repo.list_snapshots(conn, 10) == []
            assert repo.list_simulations(conn, 10) == []
            with pytest.raises(NotFoundError):
                repo.get_snapshot(conn, snapshot_id)
            holdings = conn.execute(
                text("select count(*) from public.holding_snapshots")
            ).scalar_one()
            assert holdings == 0

    def test_other_user_cannot_delete_or_update_owner_rows(self, conn):
        with as_(conn, OWNER):
            snapshot_id = repo.insert_snapshot(conn, record())
        other = make_user(conn)
        with as_(conn, other):
            with pytest.raises(NotFoundError):
                repo.delete_snapshot(conn, snapshot_id)
            updated = conn.execute(
                text(
                    "update public.user_settings set preferred_source = 'live' "
                    "where user_id = cast(:id as uuid) returning user_id"
                ),
                {"id": OWNER.id},
            ).all()
            assert updated == []
        with as_(conn, OWNER):
            assert len(repo.list_snapshots(conn, 10)) == 1
            assert repo.get_settings(conn).preferred_source == "mock"

    def test_cannot_insert_rows_for_another_user(self, conn):
        other = make_user(conn)
        with pytest.raises(ProgrammingError, match="row-level security"), as_(conn, other):
            conn.execute(
                text(
                    "insert into public.simulation_history "
                    "(user_id, simulation_type, source, is_demo, input_json, result_json) "
                    "values (cast(:id as uuid), 'buy', 'mock', true, '{}', '{}')"
                ),
                {"id": OWNER.id},
            )

    def test_cannot_attach_holding_to_another_users_snapshot(self, conn):
        with as_(conn, OWNER):
            snapshot_id = repo.insert_snapshot(conn, record())
        other = make_user(conn)
        with pytest.raises(IntegrityError, match="holding_snapshots_parent_fk"), as_(conn, other):
            conn.execute(
                text(
                    "insert into public.holding_snapshots (portfolio_snapshot_id, user_id, symbol, "
                    "market, name, asset_type, quantity, average_cost, currency, cost_basis, "
                    "valuation_status) values (cast(:sid as uuid), auth.uid(), 'X', 'KRX', 'X', "
                    "'stock', 1, 1, 'KRW', 1, 'unavailable')"
                ),
                {"sid": snapshot_id},
            )

    def test_cannot_change_user_id_column(self, conn):
        other = make_user(conn)
        with pytest.raises(ProgrammingError, match="permission denied"), as_(conn, OWNER):
            conn.execute(
                text("update public.user_settings set user_id = cast(:id as uuid)"),
                {"id": other.id},
            )

    def test_snapshots_are_immutable(self, conn):
        with as_(conn, OWNER):
            repo.insert_snapshot(conn, record())
        with pytest.raises(ProgrammingError, match="permission denied"), as_(conn, OWNER):
            conn.execute(text("update public.portfolio_snapshots set total_market_value = 0"))


# ---------------------------------------------------------------- 저장·무결성


class TestStorage:
    def test_snapshot_roundtrip_and_totals(self, conn):
        rec = record()
        with as_(conn, OWNER):
            snapshot_id = repo.insert_snapshot(conn, rec)
            detail = repo.get_snapshot(conn, snapshot_id)
        assert detail.source == Source.LIVE
        assert detail.as_of == AS_OF
        assert detail.holding_count == 2
        # 80000×10 + 600.5×2×1400
        assert detail.total_market_value == D("800000") + D("1681400")
        assert sum(h.market_value_valuation for h in detail.holdings) == detail.total_market_value
        assert detail.fx_rates[0]["rate"] == "1400"
        assert len(detail.content_hash) == 64

    def test_incomplete_snapshot_flagged(self, conn):
        rec = record(FakeLiveProvider(price_missing=True))
        assert rec.is_complete is False
        with as_(conn, OWNER):
            detail = repo.get_snapshot(conn, repo.insert_snapshot(conn, rec))
        voo = next(h for h in detail.holdings if h.symbol == "VOO")
        assert voo.market_value is None and voo.valuation_status == "unavailable"

    def test_duplicate_as_of_rejected(self, conn):
        with as_(conn, OWNER):
            repo.insert_snapshot(conn, record())
        with pytest.raises(SnapshotExistsError), as_(conn, OWNER):
            repo.insert_snapshot(conn, record())

    def test_db_rejects_mock_source(self, conn):
        with pytest.raises(DBAPIError, match="row-level security|portfolio_snapshots_source_check"):
            with as_(conn, OWNER):
                conn.execute(
                    text(
                        "insert into public.portfolio_snapshots (user_id, source, valuation_currency, "
                        "total_market_value, total_cost_basis, holding_count, valued_holding_count, "
                        "is_complete, as_of, content_hash) values (auth.uid(), 'mock', 'KRW', 1, 1, "
                        "0, 0, true, now(), repeat('a', 64))"
                    )
                )

    def test_db_rejects_inconsistent_complete_flag(self, conn):
        with pytest.raises(IntegrityError, match="complete_flag"), as_(conn, OWNER):
            conn.execute(
                text(
                    "insert into public.portfolio_snapshots (user_id, source, valuation_currency, "
                    "total_market_value, total_cost_basis, holding_count, valued_holding_count, "
                    "is_complete, as_of, content_hash) values (auth.uid(), 'live', 'KRW', 1, 1, "
                    "2, 1, true, now(), repeat('a', 64))"
                )
            )

    def test_settings_roundtrip(self, conn):
        with as_(conn, OWNER):
            saved = repo.put_settings(conn, UserSettings(preferred_source="live"))
            assert saved.preferred_source == "live"
            assert repo.get_settings(conn).preferred_source == "live"

    def test_settings_rejects_invalid_value_in_db(self, conn):
        with pytest.raises(IntegrityError), as_(conn, OWNER):
            conn.execute(text("update public.user_settings set preferred_source = 'paper'"))

    def test_simulation_history(self, conn):
        with as_(conn, OWNER):
            item = repo.insert_simulation(
                conn,
                SimulationHistoryCreate(
                    simulation_type="scenario", source="mock", input={"a": 1}, result={"b": "2"}
                ),
            )
            assert item.is_demo is True
            assert [i.id for i in repo.list_simulations(conn, 10)] == [item.id]
            repo.delete_simulation(conn, item.id)
            assert repo.list_simulations(conn, 10) == []


# ---------------------------------------------------------------- API + DB


class FakeVerifier:
    def __init__(self, users):
        self.users = users

    async def verify(self, token):
        from app.core.errors import InvalidTokenError

        if token not in self.users:
            raise InvalidTokenError()
        return self.users[token]


@pytest.fixture
def api(conn):
    other = make_user(conn)
    app = create_app(
        Settings(
            _env_file=None,
            supabase_url="https://example.supabase.co",
            live_owner_user_id=OWNER.id,
        )
    )
    app.state.token_verifier = FakeVerifier({"owner": OWNER, "other": other})
    app.state.db = RollbackDatabase(conn)
    return TestClient(app)


def h(token):
    return {"Authorization": f"Bearer {token}"}


class TestApiWithDb:
    def test_settings_get_put(self, api):
        assert api.get("/api/v1/settings", headers=h("owner")).json()["preferred_source"] == "mock"
        r = api.put(
            "/api/v1/settings",
            headers=h("owner"),
            json={
                "preferred_source": "live",
                "preferred_currency": "KRW",
                "theme": "light",
                "mask_account_numbers": True,
            },
        )
        assert r.status_code == 200
        assert api.get("/api/v1/settings", headers=h("owner")).json()["preferred_source"] == "live"
        # 다른 사용자의 설정은 바뀌지 않는다
        assert api.get("/api/v1/settings", headers=h("other")).json()["preferred_source"] == "mock"

    def test_settings_validation(self, api):
        r = api.put("/api/v1/settings", headers=h("owner"), json={"preferred_source": "paper"})
        assert r.status_code == 422

    def test_kis_not_connected_saves_nothing(self, api):
        r = api.post("/api/v1/snapshots", params={"source": "live"}, headers=h("owner"))
        assert r.status_code == 503
        assert r.json()["error"]["code"] == "KIS_NOT_CONFIGURED"
        assert api.get("/api/v1/snapshots", headers=h("owner")).json()["snapshots"] == []

    def test_mock_snapshot_rejected(self, api):
        r = api.post("/api/v1/snapshots", params={"source": "mock"}, headers=h("owner"))
        assert r.status_code == 422
        assert api.get("/api/v1/snapshots", headers=h("owner")).json()["snapshots"] == []

    def test_live_snapshot_with_connected_provider(self, api):
        api.app.state.providers[Source.LIVE] = FakeLiveProvider()
        r = api.post("/api/v1/snapshots", params={"source": "live"}, headers=h("owner"))
        assert r.status_code == 201
        body = r.json()
        assert body["source"] == "live" and body["holding_count"] == 2
        dup = api.post("/api/v1/snapshots", params={"source": "live"}, headers=h("owner"))
        assert dup.status_code == 409
        assert dup.json()["error"]["code"] == "SNAPSHOT_EXISTS"
        listed = api.get("/api/v1/snapshots", headers=h("owner")).json()["snapshots"]
        assert [s["id"] for s in listed] == [body["id"]]
        # 다른 사용자: 목록·상세·삭제 모두 불가
        assert api.get("/api/v1/snapshots", headers=h("other")).json()["snapshots"] == []
        assert api.get(f"/api/v1/snapshots/{body['id']}", headers=h("other")).status_code == 404
        assert api.delete(f"/api/v1/snapshots/{body['id']}", headers=h("other")).status_code == 404
        assert api.delete(f"/api/v1/snapshots/{body['id']}", headers=h("owner")).status_code == 204

    def test_kis_snapshot_feeds_live_history(self, api, tmp_path):
        """KIS Provider(가짜 전송 계층) → 스냅샷 저장 → LIVE 이력 차트."""
        from app.providers.kis import KISPortfolioProvider
        from tests.kis_fakes import ACCOUNT, APP_KEY, APP_SECRET, FakeKis, FakeMaster

        fake = FakeKis()
        settings = Settings(
            _env_file=None,
            kis_app_key=APP_KEY,
            kis_app_secret=APP_SECRET,
            kis_account_no=ACCOUNT,
            kis_token_cache_path=tmp_path / "token.json",
            live_classification_file=tmp_path / "none.json",
        )
        from app.integrations.kis.client import KisClient

        api.app.state.providers[Source.LIVE] = KISPortfolioProvider(
            settings,
            client=KisClient(
                APP_KEY, APP_SECRET, tmp_path / "token.json", transport=fake.transport()
            ),
            master=FakeMaster(),
        )
        assert (
            api.get(
                "/api/v1/portfolio/history", params={"source": "live"}, headers=h("owner")
            ).json()["points"]
            == []
        )
        r = api.post("/api/v1/snapshots", params={"source": "live"}, headers=h("owner"))
        assert r.status_code == 201
        assert D(r.json()["total_market_value"]) == D(1310000)
        points = api.get(
            "/api/v1/portfolio/history", params={"source": "live"}, headers=h("owner")
        ).json()["points"]
        assert len(points) == 1 and D(points[0]["total_market_value"]) == D(1310000)
        # 다른 사용자는 LIVE 이력 자체에 접근할 수 없다
        other = api.get("/api/v1/portfolio/history", params={"source": "live"}, headers=h("other"))
        assert other.status_code == 403

    def test_non_owner_cannot_capture_live(self, api):
        api.app.state.providers[Source.LIVE] = FakeLiveProvider()
        r = api.post("/api/v1/snapshots", params={"source": "live"}, headers=h("other"))
        assert r.status_code == 403

    def test_simulation_history_api(self, api):
        body = {"simulation_type": "buy", "source": "mock", "input": {"q": "1"}, "result": {"r": 1}}
        r = api.post("/api/v1/simulations/history", headers=h("owner"), json=body)
        assert r.status_code == 201 and r.json()["is_demo"] is True
        live = api.post(
            "/api/v1/simulations/history", headers=h("other"), json={**body, "source": "live"}
        )
        assert live.status_code == 403
        assert len(api.get("/api/v1/simulations/history", headers=h("owner")).json()["items"]) == 1
        assert api.get("/api/v1/simulations/history", headers=h("other")).json()["items"] == []

    def test_invalid_token_rejected(self, api):
        assert api.get("/api/v1/settings", headers=h("forged")).status_code == 401


def _counts(engine) -> tuple[int, int, int]:
    with engine.connect() as c:
        snapshots = c.execute(text("select count(*) from public.portfolio_snapshots")).scalar_one()
        history = c.execute(text("select count(*) from public.simulation_history")).scalar_one()
        temp_users = c.execute(
            text("select count(*) from auth.users where email like '%@example.invalid'")
        ).scalar_one()
    return snapshots, history, temp_users


@pytest.fixture(scope="module", autouse=True)
def baseline_counts(engine):
    """실제 사용자가 저장한 스냅샷이 있을 수 있으므로 테스트 전 개수를 기준으로 삼는다."""
    return _counts(engine)


def test_nothing_persisted_after_tests(engine, baseline_counts):
    """롤백이 실제로 동작했는지: 테스트 전후의 행 수가 같고 임시 사용자가 없어야 한다."""
    after = _counts(engine)
    assert after == baseline_counts
    assert after[2] == 0
