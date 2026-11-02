"""PostgreSQL 접근.

서버는 postgres 역할로 접속하지만, 이 역할은 RLS를 우회(BYPASSRLS)한다. 그래서 사용자 데이터는
반드시 user_transaction()으로만 다룬다. 이 트랜잭션은
1. request.jwt.claims에 검증된 사용자 id(sub)를 넣고
2. SET LOCAL ROLE authenticated로 권한을 낮춰
Supabase의 auth.uid()와 RLS 정책이 그대로 적용되게 한다. Service Role Key는 쓰지 않는다.
"""

import json
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, OperationalError

from app.core.errors import DatabaseUnavailableError
from app.core.security import AuthenticatedUser


def _engine_url(raw: str):
    url = make_url(raw)
    if url.drivername in ("postgres", "postgresql"):
        url = url.set(drivername="postgresql+psycopg")
    return url


@contextmanager
def as_user(conn: Connection, user: AuthenticatedUser) -> Iterator[Connection]:
    """현재 트랜잭션 안에서만 authenticated 역할과 사용자 claims를 적용한다."""
    claims = json.dumps({"sub": user.id, "role": "authenticated"})
    conn.execute(text("select set_config('request.jwt.claims', :claims, true)"), {"claims": claims})
    conn.execute(text("set local role authenticated"))
    conn.execute(text("set local statement_timeout = '10s'"))
    try:
        yield conn
    finally:
        # 트랜잭션이 끝나면 자동으로 원복되지만, 같은 트랜잭션을 이어 쓰는 경우(테스트)를 위해
        # 명시적으로 되돌린다. 이미 실패한 트랜잭션이면 롤백이 원복한다.
        try:
            conn.execute(text("reset role"))
            conn.execute(text("select set_config('request.jwt.claims', '', true)"))
        except DBAPIError:
            pass


class Database:
    def __init__(self, url: str):
        self.engine: Engine = create_engine(
            _engine_url(url),
            pool_pre_ping=True,
            pool_size=3,
            max_overflow=2,
            pool_recycle=1800,
            connect_args={"connect_timeout": 10},
            # 오류 메시지에 SQL 파라미터(사용자 데이터)를 싣지 않는다.
            hide_parameters=True,
        )

    @contextmanager
    def user_transaction(self, user: AuthenticatedUser) -> Iterator[Connection]:
        try:
            with self.engine.begin() as conn, as_user(conn, user):
                yield conn
        except OperationalError as exc:
            raise DatabaseUnavailableError() from exc

    def ping(self) -> bool:
        try:
            with self.engine.connect() as conn:
                conn.execute(text("select 1"))
            return True
        except DBAPIError:
            return False
