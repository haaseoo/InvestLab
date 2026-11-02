"""supabase/migrations의 SQL을 순서대로 적용한다.

    .venv/bin/python scripts/migrate.py status     # 적용 현황
    .venv/bin/python scripts/migrate.py check      # 대기 중인 파일을 트랜잭션에서 실행한 뒤 롤백
    .venv/bin/python scripts/migrate.py apply      # 대기 중인 파일 적용

- 파일 하나가 트랜잭션 하나다. 실패하면 그 파일 전체가 롤백된다.
- 적용 기록은 investlab_meta.schema_migrations에 남기고, 적용한 파일이 바뀌면 중단한다.
- DROP/TRUNCATE/DELETE가 들어 있는 파일은 실행하지 않는다.
- 연결 문자열과 예외 메시지는 출력하지 않는다(비밀번호가 섞일 수 있다).
"""

import hashlib
import re
import sys
from pathlib import Path

import psycopg

from app.core.config import REPO_ROOT, get_settings

MIGRATIONS_DIR = REPO_ROOT / "supabase" / "migrations"
FORBIDDEN = re.compile(r"\b(drop\s+(table|schema|database|column)|truncate|delete\s+from)\b", re.I)

META_SQL = """
create schema if not exists investlab_meta;
revoke all on schema investlab_meta from public, anon, authenticated;
create table if not exists investlab_meta.schema_migrations (
  version text primary key,
  name text not null,
  checksum text not null,
  applied_at timestamptz not null default now()
);
"""


def strip_comments(sql: str) -> str:
    return re.sub(r"--[^\n]*", "", sql)


def load_files() -> list[tuple[str, str, str, str]]:
    files = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        version, _, name = path.stem.partition("_")
        sql = path.read_text(encoding="utf-8")
        files.append((version, name, hashlib.sha256(sql.encode()).hexdigest(), sql))
    return files


def connect() -> psycopg.Connection:
    url = get_settings().database_url
    if url is None:
        sys.exit("DATABASE_URL이 설정되지 않았습니다.")
    try:
        return psycopg.connect(url.get_secret_value(), connect_timeout=10)
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"DB 접속 실패: {type(exc).__name__}")


def main(command: str) -> None:
    files = load_files()
    for version, name, _, sql in files:
        if FORBIDDEN.search(strip_comments(sql)):
            sys.exit(f"{version}_{name}: 금지된 문(DROP/TRUNCATE/DELETE)이 있어 중단합니다.")

    with connect() as conn:
        with conn.transaction():
            conn.execute(META_SQL)
        applied = dict(
            conn.execute(
                "select version, checksum from investlab_meta.schema_migrations"
            ).fetchall()
        )

        for version, name, checksum, _ in files:
            if version in applied and applied[version] != checksum:
                sys.exit(
                    f"{version}_{name}: 이미 적용된 파일의 내용이 바뀌었습니다. 새 파일로 추가하세요."
                )

        pending = [f for f in files if f[0] not in applied]
        if command == "status":
            for version, name, *_ in files:
                print(f"{'적용됨' if version in applied else '대기'}  {version}_{name}")
            return

        if not pending:
            print("대기 중인 마이그레이션이 없습니다.")
            return

        for version, name, checksum, sql in pending:
            label = f"{version}_{name}"
            try:
                if command == "check":
                    conn.execute("begin")
                    conn.execute(sql)
                    conn.execute("rollback")
                    print(f"check OK (롤백함)  {label}")
                else:
                    with conn.transaction():
                        conn.execute(sql)
                        conn.execute(
                            "insert into investlab_meta.schema_migrations (version, name, checksum) "
                            "values (%s, %s, %s)",
                            (version, name, checksum),
                        )
                    print(f"적용 완료  {label}")
            except psycopg.Error as exc:
                if command == "check":
                    conn.execute("rollback")
                diag = exc.diag
                # SQL 오류 내용만 보여 준다. 연결 정보는 포함되지 않는다.
                sys.exit(
                    f"{label} 실패: {type(exc).__name__} {diag.sqlstate or ''} "
                    f"{diag.message_primary or ''}"
                )


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"status", "check", "apply"}:
        sys.exit(__doc__)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    main(sys.argv[1])
