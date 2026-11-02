"""한국투자증권 공식 해외 종목 마스터 파일로 ETF 여부를 판별한다.

해외주식 잔고·상품기본정보 API는 ETF를 구분해 주지 않는다(VOO도 일반 해외주식 코드로 온다).
공식 마스터 파일(open-trading-api/stocks_info, 해외종목코드정보.h)의 증권 유형 필드는
1:Index 2:Stock 3:ETP(ETF) 4:Warrant이고, 구분코드는 001:ETF 002:ETN 003:ETC 004:Others다.

- 파일은 하루 한 번 받아 서버 로컬(.cache)에 필요한 두 필드만 저장한다.
- 받을 수 없으면 판별하지 않는다(None). 주식으로 가정하지 않는다.
"""

import io
import json
import logging
import zipfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

logger = logging.getLogger("investlab.kis")

MASTER_URL = "https://new.real.download.dws.co.kr/common/master/{code}mst.cod.zip"
KST = ZoneInfo("Asia/Seoul")
MAX_ZIP_BYTES = 30 * 1024 * 1024
MAX_FILE_BYTES = 60 * 1024 * 1024

# 잔고 응답의 거래소 코드 → 마스터 파일 코드
EXCHANGE_MASTER = {
    "NASD": "nas",
    "NAS": "nas",
    "NYSE": "nys",
    "AMEX": "ams",
    "SEHK": "hks",
    "SHAA": "shs",
    "SZAA": "szs",
    "TKSE": "tse",
    "HASE": "hnx",
    "VNSE": "hsx",
}
# 미국 종목은 잔고의 거래소 코드와 마스터 파일이 다를 수 있어(예: NYSE Arca) 세 파일을 모두 본다.
US_MASTERS = ("nas", "nys", "ams")

SECURITY_TYPE_ETP = "3"
SECURITY_TYPE_STOCK = "2"
ETP_KIND_ETF = "001"


class SecurityKind:
    STOCK = "stock"
    ETF = "etf"
    OTHER = "other"


def parse_master(text: str) -> dict[str, tuple[str, str]]:
    """탭 구분 행 → {종목코드: (증권유형, ETP 구분코드)}"""
    result: dict[str, tuple[str, str]] = {}
    for line in text.splitlines():
        cols = line.split("\t")
        if len(cols) < 23:
            continue
        symbol = cols[4].strip()
        if symbol:
            result[symbol] = (cols[8].strip(), cols[22].strip())
    return result


def classify(entry: tuple[str, str] | None) -> str | None:
    if entry is None:
        return None
    security_type, etp_kind = entry
    if security_type == SECURITY_TYPE_STOCK:
        return SecurityKind.STOCK
    if security_type == SECURITY_TYPE_ETP:
        return SecurityKind.ETF if etp_kind == ETP_KIND_ETF else SecurityKind.OTHER
    return SecurityKind.OTHER


class OverseasMaster:
    def __init__(self, cache_dir: Path | None, transport: httpx.AsyncBaseTransport | None = None):
        self._cache_dir = cache_dir
        self._transport = transport
        self._tables: dict[str, tuple[str, dict[str, tuple[str, str]]]] = {}

    async def kind(self, exchange: str, symbol: str) -> str | None:
        code = EXCHANGE_MASTER.get(exchange)
        if code is None:
            return None
        codes = US_MASTERS if code in US_MASTERS else (code,)
        # 잔고의 거래소 파일을 먼저 본다.
        for c in sorted(codes, key=lambda x: x != code):
            table = await self._table(c)
            if table is not None and symbol in table:
                return classify(table[symbol])
        return None

    async def _table(self, code: str) -> dict[str, tuple[str, str]] | None:
        today = datetime.now(KST).strftime("%Y%m%d")
        cached = self._tables.get(code)
        if cached and cached[0] == today:
            return cached[1]
        table = self._read_cache(code, today)
        if table is None:
            table = await self._download(code)
            if table is None:
                # 오늘 파일을 받지 못하면 이전에 받은 표를 그대로 쓴다(종목 유형은 거의 바뀌지 않는다).
                return cached[1] if cached else self._read_cache(code, None)
            self._write_cache(code, today, table)
        self._tables[code] = (today, table)
        return table

    def _cache_file(self, code: str) -> Path | None:
        return self._cache_dir / f"{code}.json" if self._cache_dir else None

    def _read_cache(self, code: str, day: str | None) -> dict[str, tuple[str, str]] | None:
        path = self._cache_file(code)
        if path is None or not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if day is not None and raw.get("day") != day:
                return None
            return {k: (v[0], v[1]) for k, v in raw["entries"].items()}
        except (OSError, ValueError, KeyError, TypeError, IndexError):
            return None

    def _write_cache(self, code: str, day: str, table: dict[str, tuple[str, str]]) -> None:
        path = self._cache_file(code)
        if path is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"day": day, "entries": table}), encoding="utf-8")
        except OSError:
            logger.warning("KIS master cache could not be written")

    async def _download(self, code: str) -> dict[str, tuple[str, str]] | None:
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(20.0, connect=5.0), transport=self._transport
            ) as http:
                res = await http.get(MASTER_URL.format(code=code))
            if res.status_code != 200 or len(res.content) > MAX_ZIP_BYTES:
                logger.warning("KIS master download rejected: %s %s", code, res.status_code)
                return None
            with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
                # 압축을 디스크에 풀지 않고 첫 파일만 메모리에서 읽는다.
                info = zf.infolist()[0]
                if info.file_size > MAX_FILE_BYTES:
                    return None
                text = zf.read(info).decode("cp949", errors="replace")
            return parse_master(text)
        except (httpx.HTTPError, zipfile.BadZipFile, IndexError, OSError) as exc:
            logger.warning("KIS master download failed: %s %s", code, type(exc).__name__)
            return None
