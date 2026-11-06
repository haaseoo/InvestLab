"""한국투자증권 Open API 클라이언트(조회 전용).

- 조회(GET)와 토큰 발급(POST /oauth2/tokenP)만 한다. 주문 API 경로는 호출할 수 없게 막는다.
- 접근 토큰은 메모리와 TokenStore에 캐시한다. 공식 안내상 토큰은 1일 유효하고 재발급은 1분당
  1회로 제한되며, 발급할 때마다 알림톡이 간다. 그래서 서버 재시작 때도 재사용한다.
  운영에서는 사용자별로 DB에 암호화해 두고(services/live_accounts.py), 테스트는 파일을 쓴다.
- App Key·Secret·토큰·계좌번호는 로그, 예외 메시지, 응답 어디에도 싣지 않는다.
  KIS 오류는 msg_cd(오류 코드)만 전달한다.
"""

import asyncio
import hashlib
import json
import logging
import os
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

import httpx

from app.core.errors import (
    KisApiError,
    KisAuthError,
    KisNotConfiguredError,
    KisRateLimitedError,
    KisResponseError,
    KisUnavailableError,
)

logger = logging.getLogger("investlab.kis")
# httpx는 INFO 수준에서 요청 URL 전체(계좌번호 파라미터 포함)를 로그로 남긴다. 경고 이상만 남긴다.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

PROD_BASE_URL = "https://openapi.koreainvestment.com:9443"
TOKEN_PATH = "/oauth2/tokenP"  # noqa: S105 - URL 경로이며 비밀 값이 아니다
# 조회용 경로만 허용한다. trading/ 아래에서는 잔고 조회만 쓴다.
ALLOWED_PATH_PREFIXES = (
    "/uapi/domestic-stock/v1/quotations/",
    "/uapi/overseas-price/v1/quotations/",
)
ALLOWED_TRADING_PATHS = frozenset(
    {
        "/uapi/domestic-stock/v1/trading/inquire-balance",
        "/uapi/overseas-stock/v1/trading/inquire-present-balance",
    }
)

RATE_LIMIT_CODE = "EGW00201"
# 만료(EGW00123)·유효하지 않은(EGW00121) 토큰. 한 번만 재발급 후 재시도한다.
TOKEN_ERROR_CODES = frozenset({"EGW00121", "EGW00123"})
TOKEN_REISSUE_INTERVAL = 60.0
# 만료 직전 토큰은 쓰지 않는다.
TOKEN_EXPIRY_MARGIN = timedelta(minutes=10)
# 공식 예제의 호출 간 대기(0.1초)보다 약간 길게 둔다.
MIN_CALL_INTERVAL = 0.12
RATE_LIMIT_RETRIES = 2
MAX_PAGES = 10


def _key_fingerprint(app_key: str) -> str:
    """캐시된 토큰이 어느 App Key로 발급됐는지 구분한다. 키 자체는 저장하지 않는다."""
    return hashlib.sha256(app_key.encode()).hexdigest()[:16]


@dataclass
class AccessToken:
    value: str
    expires_at: datetime

    def usable(self, now: datetime) -> bool:
        return self.expires_at - TOKEN_EXPIRY_MARGIN > now


class TokenStore(Protocol):
    """토큰 영구 캐시. 읽지 못하면 None을 돌려주고, 저장 실패가 조회를 막지 않게 한다."""

    async def load(self) -> AccessToken | None: ...

    async def save(self, token: AccessToken) -> None: ...

    async def clear(self) -> None: ...


class FileTokenStore:
    """토큰 파일 캐시(권한 600). 파일이 깨졌거나 다른 키의 토큰이면 없는 것으로 본다."""

    def __init__(self, path: Path | None, fingerprint: str):
        self._path = path
        self._fingerprint = fingerprint

    async def load(self) -> AccessToken | None:
        if self._path is None or not self._path.exists():
            return None
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            if raw.get("fingerprint") != self._fingerprint:
                return None
            return AccessToken(
                value=str(raw["token"]), expires_at=datetime.fromisoformat(raw["expires_at"])
            )
        except (OSError, ValueError, KeyError, TypeError):
            return None

    async def save(self, token: AccessToken) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(
                {
                    "fingerprint": self._fingerprint,
                    "token": token.value,
                    "expires_at": token.expires_at.isoformat(),
                }
            )
            # 처음부터 소유자만 읽을 수 있는 파일로 만든다.
            fd = os.open(self._path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(payload)
            os.chmod(self._path, 0o600)
        except OSError:
            logger.warning("KIS token cache could not be written")

    async def clear(self) -> None:
        if self._path is not None:
            try:
                self._path.unlink(missing_ok=True)
            except OSError:
                logger.warning("KIS token cache could not be removed")


@dataclass
class KisResponse:
    body: dict[str, Any]
    tr_cont: str


class KisClient:
    def __init__(
        self,
        app_key: str,
        app_secret: str,
        token_cache_path: Path | None,
        base_url: str = PROD_BASE_URL,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: httpx.Timeout | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
        token_store: TokenStore | None = None,
    ):
        if not app_key or not app_secret:
            raise KisNotConfiguredError()
        self._app_key = app_key
        self._app_secret = app_secret
        self._base_url = base_url
        self._store: TokenStore = token_store or FileTokenStore(
            token_cache_path, _key_fingerprint(app_key)
        )
        self._transport = transport
        self._timeout = timeout or httpx.Timeout(10.0, connect=5.0)
        self._sleep = sleep
        self._clock = clock
        self._token: AccessToken | None = None
        self._token_lock = asyncio.Lock()
        self._call_lock = asyncio.Lock()
        self._last_call = -MIN_CALL_INTERVAL
        self._last_issue_attempt: float | None = None

    def _http(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url, timeout=self._timeout, transport=self._transport
        )

    # --- 토큰 ---

    async def _get_token(self) -> str:
        async with self._token_lock:
            now = datetime.now(UTC)
            if self._token is None or not self._token.usable(now):
                cached = await self._store.load()
                self._token = cached if cached and cached.usable(now) else None
            if self._token is None:
                self._token = await self._issue_token()
                await self._store.save(self._token)
            return self._token.value

    async def _invalidate_token(self, rejected: str) -> None:
        async with self._token_lock:
            if self._token is not None and self._token.value == rejected:
                self._token = None
                await self._store.clear()

    async def _issue_token(self) -> AccessToken:
        now = self._clock()
        if (
            self._last_issue_attempt is not None
            and now - self._last_issue_attempt < TOKEN_REISSUE_INTERVAL
        ):
            # 공식 제한(1분당 1회)을 넘기지 않도록 서버에 보내지 않는다.
            raise KisRateLimitedError("접근 토큰 재발급은 1분에 한 번만 할 수 있습니다.")
        self._last_issue_attempt = now
        try:
            async with self._http() as http:
                res = await http.post(
                    TOKEN_PATH,
                    json={
                        "grant_type": "client_credentials",
                        "appkey": self._app_key,
                        "appsecret": self._app_secret,
                    },
                    headers={"content-type": "application/json; charset=utf-8"},
                )
        except httpx.HTTPError as exc:
            logger.warning("KIS token request failed: %s", type(exc).__name__)
            raise KisUnavailableError() from None

        body = _json_or_none(res)
        if res.status_code != 200 or not body or not body.get("access_token"):
            code = str(body.get("error_code", "")) if body else ""
            logger.warning("KIS token rejected: status=%s code=%s", res.status_code, code or "-")
            raise KisAuthError(details={"status": res.status_code, "kis_code": code or None})

        try:
            expires_in = int(body["expires_in"])
        except (KeyError, TypeError, ValueError):
            raise KisResponseError(details={"field": "expires_in"}) from None
        logger.info("KIS access token issued")
        return AccessToken(
            value=str(body["access_token"]),
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in),
        )

    # --- 조회 ---

    async def get(
        self, path: str, tr_id: str, params: dict[str, str], tr_cont: str = ""
    ) -> KisResponse:
        if path not in ALLOWED_TRADING_PATHS and not path.startswith(ALLOWED_PATH_PREFIXES):
            raise ValueError("조회용으로 허용되지 않은 KIS 경로입니다.")

        token_retried = False
        attempt = 0
        while True:
            token = await self._get_token()
            res = await self._send(path, tr_id, params, tr_cont, token)
            body = _json_or_none(res)
            if body is None:
                logger.warning("KIS non-JSON response: tr=%s status=%s", tr_id, res.status_code)
                if res.status_code >= 500:
                    raise KisUnavailableError()
                raise KisResponseError(details={"tr_id": tr_id})

            msg_cd = str(body.get("msg_cd") or "")
            if body.get("rt_cd") == "0" and res.status_code == 200:
                return KisResponse(body=body, tr_cont=res.headers.get("tr_cont", ""))

            if msg_cd == RATE_LIMIT_CODE:
                if attempt < RATE_LIMIT_RETRIES:
                    attempt += 1
                    await self._sleep(0.5 * attempt)
                    continue
                raise KisRateLimitedError()
            if msg_cd in TOKEN_ERROR_CODES and not token_retried:
                token_retried = True
                await self._invalidate_token(token)
                continue

            logger.warning(
                "KIS error: tr=%s status=%s code=%s", tr_id, res.status_code, msg_cd or "-"
            )
            if msg_cd in TOKEN_ERROR_CODES:
                raise KisAuthError(details={"kis_code": msg_cd})
            raise KisApiError(details={"tr_id": tr_id, "kis_code": msg_cd or None})

    async def get_pages(
        self,
        path: str,
        tr_id: str,
        params: dict[str, str],
        fk_key: str | None = None,
        nk_key: str | None = None,
    ) -> list[dict[str, Any]]:
        """연속 조회. 응답 헤더 tr_cont가 M/F면 다음 페이지가 있다(공식 예제와 동일)."""
        pages: list[dict[str, Any]] = []
        params = dict(params)
        tr_cont = ""
        for _ in range(MAX_PAGES):
            res = await self.get(path, tr_id, params, tr_cont)
            pages.append(res.body)
            if res.tr_cont not in ("M", "F"):
                return pages
            if fk_key and nk_key:
                params[fk_key.upper()] = str(res.body.get(fk_key, ""))
                params[nk_key.upper()] = str(res.body.get(nk_key, ""))
            tr_cont = "N"
        # 끝까지 받지 못한 잔고는 일부만 보여 주게 되므로 사용하지 않는다.
        raise KisResponseError("연속 조회 페이지가 너무 많아 잔고를 모두 받지 못했습니다.")

    async def _send(
        self, path: str, tr_id: str, params: dict[str, str], tr_cont: str, token: str
    ) -> httpx.Response:
        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {token}",
            "appkey": self._app_key,
            "appsecret": self._app_secret,
            "tr_id": tr_id,
            "tr_cont": tr_cont,
            "custtype": "P",
        }
        async with self._call_lock:
            wait = MIN_CALL_INTERVAL - (self._clock() - self._last_call)
            if wait > 0:
                await self._sleep(wait)
            try:
                async with self._http() as http:
                    return await http.get(path, params=params, headers=headers)
            except httpx.HTTPError as exc:
                logger.warning("KIS request failed: tr=%s %s", tr_id, type(exc).__name__)
                raise KisUnavailableError() from None
            finally:
                self._last_call = self._clock()


def _json_or_none(res: httpx.Response) -> dict[str, Any] | None:
    try:
        data = res.json()
    except ValueError:
        return None
    return data if isinstance(data, dict) else None
