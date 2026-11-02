"""가상 포트폴리오 Provider. 외부 서비스 없이 data/mock의 Seed 파일만 읽는다."""

import json
from datetime import datetime
from decimal import Decimal
from functools import cached_property
from pathlib import Path

from pydantic import BaseModel, ValidationError

from app.core.errors import MockDataError
from app.providers.base import PortfolioProvider
from app.schemas.analysis import EtfComposition
from app.schemas.portfolio import (
    AccountSummary,
    FxRate,
    Holding,
    Position,
    ProviderStatus,
    Quote,
    SnapshotPoint,
    Source,
)
from app.services.valuation import build_holding

ETF_COMPOSITIONS_FILE = "etf_compositions.json"


class _SeedHolding(Position):
    # null이면 시세 조회 실패 상태를 재현한다.
    current_price: Decimal | None


class _SeedFx(BaseModel):
    base_currency: str
    quote_currency: str
    rate: Decimal
    as_of: datetime


class _SeedMeta(BaseModel):
    as_of: datetime
    notice: str


class _Seed(BaseModel):
    meta: _SeedMeta
    fx_rates: list[_SeedFx]
    holdings: list[_SeedHolding]


class MockPortfolioProvider(PortfolioProvider):
    source = Source.MOCK
    is_demo = True

    def __init__(self, data_dir: Path):
        self._data_dir = data_dir

    def _read(self, filename: str) -> dict:
        try:
            with (self._data_dir / filename).open(encoding="utf-8") as f:
                # float을 거치지 않도록 숫자도 Decimal로 읽는다.
                return json.load(f, parse_float=Decimal)
        except (OSError, json.JSONDecodeError) as exc:
            raise MockDataError(details={"file": filename}) from exc

    @cached_property
    def _seed(self) -> _Seed:
        try:
            return _Seed.model_validate(self._read("portfolio.json"))
        except ValidationError as exc:
            raise MockDataError(details={"file": "portfolio.json"}) from exc

    async def get_quotes(self, symbols: list[str] | None = None) -> list[Quote]:
        return [
            Quote(
                symbol=h.symbol,
                market=h.market,
                price=h.current_price,
                currency=h.currency,
                as_of=self._seed.meta.as_of if h.current_price is not None else None,
                source=self.source,
                is_demo=True,
            )
            for h in self._seed.holdings
            if symbols is None or h.symbol in symbols
        ]

    async def get_fx_rates(self) -> list[FxRate]:
        return [FxRate(**fx.model_dump(), source=self.source) for fx in self._seed.fx_rates]

    async def get_holdings(self, valuation_currency: str) -> list[Holding]:
        quotes = {(q.symbol, q.market): q for q in await self.get_quotes()}
        fx_rates = await self.get_fx_rates()
        return [
            build_holding(
                position=Position(**h.model_dump(exclude={"current_price"})),
                quote=quotes[(h.symbol, h.market)],
                fx_rates=fx_rates,
                valuation_currency=valuation_currency,
                source=self.source,
                is_demo=True,
            )
            for h in self._seed.holdings
        ]

    async def get_account_summary(self) -> AccountSummary:
        return AccountSummary(
            account_masked=None,
            cash_balances=None,
            as_of=self._seed.meta.as_of,
            source=self.source,
            is_demo=True,
        )

    async def get_history(self) -> list[SnapshotPoint]:
        raw = self._read("history.json")
        try:
            return [SnapshotPoint.model_validate(p) for p in raw["points"]]
        except (KeyError, ValidationError) as exc:
            raise MockDataError(details={"file": "history.json"}) from exc

    async def get_etf_compositions(self) -> list[EtfComposition]:
        """data/mock/etf_compositions.json이 있을 때만 읽는다.

        기본 Mock 데이터에는 이 파일이 없다. 실제 구성 종목을 확인하지 않은 값을 만들지 않기 위해서다.
        """
        if not (self._data_dir / ETF_COMPOSITIONS_FILE).exists():
            return []
        raw = self._read(ETF_COMPOSITIONS_FILE)
        try:
            return [EtfComposition.model_validate(c) for c in raw["compositions"]]
        except (KeyError, ValidationError) as exc:
            raise MockDataError(details={"file": ETF_COMPOSITIONS_FILE}) from exc

    def get_provider_status(self) -> ProviderStatus:
        return ProviderStatus(
            source=self.source,
            state="ready",
            is_demo=True,
            label="MOCK",
            message="시연용 가상 포트폴리오입니다. 실제 계좌나 시세가 아닙니다.",
        )
