"""해외 업종코드 → 업종명. 공식 API '해외주식 업종별코드조회'(HHDFS76370100)를 쓴다.

- 거래소(NAS·NYS·AMS…)마다 코드 목록이 따로 있다. 종목의 업종분류코드는 종목 마스터 파일에서 온다.
- 계좌와 무관한 공개 데이터라 모든 사용자가 하루 한 번 받은 결과를 함께 쓴다. 조회에는 그 순간
  요청한 사용자의 클라이언트를 쓴다.
- 받지 못하면 업종명을 모르는 것으로 둔다(None). 코드로 이름을 추측하지 않는다.
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.core.errors import AppError
from app.integrations.kis.client import KisClient

logger = logging.getLogger("investlab.kis")

INDUSTRY_PATH = "/uapi/overseas-price/v1/quotations/industry-price"
INDUSTRY_TR = "HHDFS76370100"
KST = ZoneInfo("Asia/Seoul")
CACHE_VERSION = 1
# 실패한 거래소는 이 시간 동안 다시 부르지 않는다(화면마다 KIS를 부르지 않게).
RETRY_SECONDS = 600.0


def parse_industries(pages: list[dict]) -> dict[str, str]:
    names: dict[str, str] = {}
    for page in pages:
        for row in page.get("output2") or []:
            if not isinstance(row, dict):
                continue
            code, name = str(row.get("icod") or "").strip(), str(row.get("name") or "").strip()
            if code and name:
                names[code] = name
    return names


class OverseasIndustries:
    def __init__(self, cache_dir: Path | None, clock=None):
        self._cache_dir = cache_dir
        self._tables: dict[str, tuple[str, dict[str, str]]] = {}
        self._failed: dict[str, float] = {}
        self._lock = asyncio.Lock()
        self._clock = clock or (lambda: asyncio.get_running_loop().time())

    async def name(self, client: KisClient, exchange: str, code: str) -> str | None:
        table = await self._table(client, exchange)
        return table.get(code) if table else None

    async def _table(self, client: KisClient, exchange: str) -> dict[str, str] | None:
        today = datetime.now(KST).strftime("%Y%m%d")
        async with self._lock:
            cached = self._tables.get(exchange)
            if cached and cached[0] == today:
                return cached[1]
            table = self._read_cache(exchange, today)
            if table is None:
                failed_at = self._failed.get(exchange)
                if failed_at is not None and self._clock() - failed_at < RETRY_SECONDS:
                    return cached[1] if cached else self._read_cache(exchange, None)
                table = await self._fetch(client, exchange)
                if table is None:
                    self._failed[exchange] = self._clock()
                    # 업종명은 거의 바뀌지 않으므로 이전에 받은 표가 있으면 쓴다.
                    return cached[1] if cached else self._read_cache(exchange, None)
                self._write_cache(exchange, today, table)
            self._failed.pop(exchange, None)
            self._tables[exchange] = (today, table)
            return table

    async def _fetch(self, client: KisClient, exchange: str) -> dict[str, str] | None:
        try:
            pages = await client.get_pages(
                INDUSTRY_PATH, INDUSTRY_TR, {"EXCD": exchange, "AUTH": ""}
            )
        except (AppError, ValueError) as exc:
            logger.warning("KIS industry list failed: %s %s", exchange, type(exc).__name__)
            return None
        table = parse_industries(pages)
        return table or None

    def _cache_file(self, exchange: str) -> Path | None:
        if self._cache_dir is None:
            return None
        return self._cache_dir / f"industry-{exchange.lower()}.v{CACHE_VERSION}.json"

    def _read_cache(self, exchange: str, day: str | None) -> dict[str, str] | None:
        path = self._cache_file(exchange)
        if path is None or not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if day is not None and raw.get("day") != day:
                return None
            entries = raw["entries"]
            return {str(k): str(v) for k, v in entries.items()} or None
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return None

    def _write_cache(self, exchange: str, day: str, table: dict[str, str]) -> None:
        path = self._cache_file(exchange)
        if path is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps({"day": day, "entries": table}, ensure_ascii=False), encoding="utf-8"
            )
        except OSError:
            logger.warning("KIS industry cache could not be written")
