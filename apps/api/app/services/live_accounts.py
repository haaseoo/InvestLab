"""사용자별 LIVE 계좌.

- 사용자는 본인이 등록한 KIS 키로 본인 계좌만 조회한다. 키는 로그인 사용자 id로 RLS를 거쳐
  읽으므로 다른 사용자의 키나 계좌에 닿는 경로가 없다.
- DB에는 암호문만 있다. 복호화한 키는 이 프로세스 메모리(Provider)에만 둔다.
- Provider는 사용자마다 하나를 재사용한다. 그래야 30초 조회 공유, 토큰 재사용, 1분 1회 재발급
  제한이 사용자 단위로 지켜진다. 다른 곳에서 키가 바뀌었을 수 있으므로 일정 시간마다 DB를 다시 본다.
"""

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import httpx
from sqlalchemy.exc import DBAPIError
from starlette.concurrency import run_in_threadpool

from app.core.crypto import CredentialCipher, DecryptionError
from app.core.errors import (
    AppError,
    DatabaseNotConfiguredError,
    KisCredentialStoreNotConfiguredError,
    KisCredentialsUnreadableError,
    KisNotConfiguredError,
)
from app.core.security import AuthenticatedUser
from app.db import repositories as repo
from app.db.database import Database
from app.integrations.kis.client import AccessToken, KisClient
from app.integrations.kis.credentials import KisCredentials
from app.integrations.kis.industry import OverseasIndustries
from app.providers.kis import KISPortfolioProvider, MasterLookup

logger = logging.getLogger("investlab.kis")

PURPOSE_CREDENTIALS = "credentials"
PURPOSE_TOKEN = "token"  # noqa: S105 - 암호화 용도 이름이며 비밀 값이 아니다
# 다른 기기·서버에서 키를 바꾸거나 지운 것을 반영하는 주기
RECHECK_SECONDS = 300.0


@dataclass(frozen=True)
class CredentialStatus:
    registered: bool
    account_masked: str | None = None
    updated_at: datetime | None = None


@dataclass
class _Entry:
    version: datetime
    provider: KISPortfolioProvider
    checked_at: float


class MemoryTokenStore:
    """키 검증용. 검증에 성공하면 발급된 토큰을 DB에 함께 저장한다."""

    def __init__(self) -> None:
        self.token: AccessToken | None = None

    async def load(self) -> AccessToken | None:
        return self.token

    async def save(self, token: AccessToken) -> None:
        self.token = token

    async def clear(self) -> None:
        self.token = None


class DbTokenStore:
    """접근 토큰을 사용자 행에 암호화해 둔다. 실패해도 조회는 계속한다(다음에 재발급될 뿐이다)."""

    def __init__(
        self, db: Database, cipher: CredentialCipher, user: AuthenticatedUser, version: datetime
    ):
        self._db = db
        self._cipher = cipher
        self._user = user
        self._version = version

    async def load(self) -> AccessToken | None:
        def run():
            with self._db.user_transaction(self._user) as conn:
                return repo.get_kis_token(conn)

        try:
            row = await run_in_threadpool(run)
            if row is None:
                return None
            value = self._cipher.decrypt(
                row.token_enc, user_id=self._user.id, purpose=PURPOSE_TOKEN
            )
            return AccessToken(value=value.decode(), expires_at=row.expires_at)
        except (AppError, DBAPIError, DecryptionError, UnicodeDecodeError):
            logger.warning("KIS token cache could not be read")
            return None

    async def save(self, token: AccessToken) -> None:
        await self._write(token)

    async def clear(self) -> None:
        await self._write(None)

    async def _write(self, token: AccessToken | None) -> None:
        enc = (
            self._cipher.encrypt(token.value.encode(), user_id=self._user.id, purpose=PURPOSE_TOKEN)
            if token
            else None
        )

        def run():
            with self._db.user_transaction(self._user) as conn:
                repo.set_kis_token(conn, enc, token.expires_at if token else None, self._version)

        try:
            await run_in_threadpool(run)
        except (AppError, DBAPIError):
            logger.warning("KIS token cache could not be written")


class LiveAccounts:
    def __init__(
        self,
        db: Database | None,
        cipher: CredentialCipher | None,
        master: MasterLookup,
        classification_file: Path,
        transport: httpx.AsyncBaseTransport | None = None,
        industries: OverseasIndustries | None = None,
    ):
        self._db = db
        self._cipher = cipher
        self._master = master
        self._classification_file = classification_file
        self._transport = transport  # 테스트용 가짜 KIS
        # 공개 업종명 표. 모든 사용자가 함께 쓴다.
        self._industries = industries
        self._entries: dict[str, _Entry] = {}
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    @property
    def store_available(self) -> bool:
        return self._cipher is not None

    def _require(self) -> tuple[Database, CredentialCipher]:
        if self._db is None:
            raise DatabaseNotConfiguredError()
        if self._cipher is None:
            raise KisCredentialStoreNotConfiguredError()
        return self._db, self._cipher

    def _provider(self, credentials: KisCredentials, token_store) -> KISPortfolioProvider:
        client = KisClient(
            credentials.app_key,
            credentials.app_secret,
            None,
            transport=self._transport,
            token_store=token_store,
        )
        return KISPortfolioProvider(
            credentials, client, self._master, self._classification_file, self._industries
        )

    # --- 조회 ---

    async def provider_for(self, user: AuthenticatedUser) -> KISPortfolioProvider:
        db, cipher = self._require()
        async with self._locks[user.id]:
            entry = self._entries.get(user.id)
            now = time.monotonic()
            if entry and now - entry.checked_at < RECHECK_SECONDS:
                return entry.provider

            row = await self._load_row(db, user)
            if row is None:
                self._entries.pop(user.id, None)
                raise KisNotConfiguredError()
            if entry and entry.version == row.updated_at:
                entry.checked_at = now
                return entry.provider

            credentials = self._decrypt(cipher, user, row.credentials_enc)
            provider = self._provider(credentials, DbTokenStore(db, cipher, user, row.updated_at))
            self._entries[user.id] = _Entry(row.updated_at, provider, now)
            return provider

    async def status(self, user: AuthenticatedUser) -> CredentialStatus:
        db, _ = self._require()
        row = await self._load_row(db, user)
        if row is None:
            return CredentialStatus(registered=False)
        return CredentialStatus(True, row.account_masked, row.updated_at)

    # --- 등록·삭제 ---

    async def register(
        self, user: AuthenticatedUser, credentials: KisCredentials
    ) -> CredentialStatus:
        """실제로 잔고를 조회해 본 뒤에만 저장한다. 잘못된 키·계좌는 저장되지 않는다."""
        db, cipher = self._require()
        async with self._locks[user.id]:
            tokens = MemoryTokenStore()
            await self._provider(credentials, tokens).get_account_summary()

            credentials_enc = cipher.encrypt(
                credentials.to_json(), user_id=user.id, purpose=PURPOSE_CREDENTIALS
            )
            token = tokens.token
            token_enc = (
                cipher.encrypt(token.value.encode(), user_id=user.id, purpose=PURPOSE_TOKEN)
                if token
                else None
            )

            def run():
                with db.user_transaction(user) as conn:
                    return repo.put_kis_credentials(
                        conn,
                        credentials_enc,
                        credentials.account_masked,
                        token_enc,
                        token.expires_at if token else None,
                    )

            row = await run_in_threadpool(run)
            self._entries.pop(user.id, None)
            logger.info("KIS credentials registered")
            return CredentialStatus(True, row.account_masked, row.updated_at)

    async def remove(self, user: AuthenticatedUser) -> None:
        db = self._db
        if db is None:
            raise DatabaseNotConfiguredError()
        async with self._locks[user.id]:

            def run():
                with db.user_transaction(user) as conn:
                    repo.delete_kis_credentials(conn)

            await run_in_threadpool(run)
            self._entries.pop(user.id, None)
            logger.info("KIS credentials removed")

    # --- 내부 ---

    @staticmethod
    async def _load_row(db: Database, user: AuthenticatedUser) -> repo.KisCredentialRow | None:
        def run():
            with db.user_transaction(user) as conn:
                return repo.get_kis_credentials(conn)

        return await run_in_threadpool(run)

    @staticmethod
    def _decrypt(cipher: CredentialCipher, user: AuthenticatedUser, blob: bytes) -> KisCredentials:
        try:
            raw = cipher.decrypt(blob, user_id=user.id, purpose=PURPOSE_CREDENTIALS)
            return KisCredentials.from_json(raw)
        except (DecryptionError, ValueError, KeyError, TypeError, AppError):
            # 마스터 키가 바뀌었거나 행이 손상됐다. 사용자가 다시 등록하면 된다.
            logger.warning("KIS credentials could not be decrypted")
            raise KisCredentialsUnreadableError() from None
