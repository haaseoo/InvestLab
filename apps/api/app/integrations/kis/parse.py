"""KIS 잔고 응답 → 내부 값. 순수 함수라 실제 호출 없이 테스트한다.

필드는 공식 예제(open-trading-api examples_llm)의 컬럼 정의와 2026-11-02 실제 응답 구조로 확인했다.

국내 주식잔고조회(TTTC8434R, INQR_DVSN=02 종목별)
  output1: pdno 종목코드, prdt_name 종목명, hldg_qty 보유수량, pchs_avg_pric 매입평균가격,
           prpr 현재가, evlu_amt 평가금액
  output2: dnca_tot_amt 예수금총금액
해외주식 체결기준현재잔고(CTRP6504R, WCRC_FRCR_DVSN_CD=02 외화 기준)
  output1: pdno, prdt_name, ccld_qty_smtl1 체결수량합계, avg_unpr3 평균단가,
           ovrs_now_pric1 현재가, frcr_evlu_amt2 외화평가금액, buy_crcy_cd 통화, ovrs_excg_cd 거래소
  output2(통화별): crcy_cd 통화, frst_bltn_exrt 최초고시환율, frcr_dncl_amt_2 외화예수금
  수량은 cblc_qty13(잔고수량)이 아니라 ccld_qty_smtl1을 쓴다. 당일 매수분은 cblc_qty13에 빠져 있고,
  평가금액·매입금액은 ccld_qty_smtl1 기준으로 계산되어 있음을 실제 응답으로 확인했다.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from app.core.errors import KisResponseError

# 해외 거래소 코드 → (표시 시장명, 상장 국가)
OVERSEAS_MARKETS = {
    "NASD": ("NASDAQ", "US"),
    "NAS": ("NASDAQ", "US"),
    "NYSE": ("NYSE", "US"),
    "AMEX": ("AMEX", "US"),
    "SEHK": ("HKEX", "HK"),
    "SHAA": ("SSE", "CN"),
    "SZAA": ("SZSE", "CN"),
    "TKSE": ("TSE", "JP"),
    "HASE": ("HNX", "VN"),
    "VNSE": ("HOSE", "VN"),
}


@dataclass(frozen=True)
class KisHolding:
    symbol: str
    name: str
    market: str
    exchange_code: str
    country: str | None
    currency: str
    quantity: Decimal
    average_cost: Decimal
    # 0 또는 빈 값이면 None(시세 없음)이다. 상장 종목의 가격이 0일 수는 없다.
    price: Decimal | None
    reported_value: Decimal | None
    domestic: bool


@dataclass(frozen=True)
class KisFx:
    currency: str
    rate: Decimal


def _rows(value: Any) -> list[dict[str, Any]]:
    if value is None or value == "":
        return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list) and all(isinstance(r, dict) for r in value):
        return value
    raise KisResponseError(details={"field": "output"})


def _text(row: dict[str, Any], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise KisResponseError(details={"field": key})
    return value.strip()


def _number(row: dict[str, Any], key: str) -> Decimal:
    raw = row.get(key)
    try:
        value = Decimal(str(raw).strip())
    except (InvalidOperation, ValueError):
        raise KisResponseError(details={"field": key}) from None
    if not value.is_finite():
        raise KisResponseError(details={"field": key})
    return value


def _positive_or_none(row: dict[str, Any], key: str) -> Decimal | None:
    raw = row.get(key)
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    value = _number(row, key)
    return value if value > 0 else None


def _price_and_value(row: dict[str, Any], price_key: str, value_key: str):
    price = _positive_or_none(row, price_key)
    # 시세가 없으면 평가금액도 믿지 않는다(0으로 계산된 값일 수 있다).
    value = _number(row, value_key) if price is not None else None
    return price, value


def parse_domestic(pages: list[dict[str, Any]]) -> tuple[list[KisHolding], Decimal | None]:
    holdings: list[KisHolding] = []
    for page in pages:
        for row in _rows(page.get("output1")):
            quantity = _number(row, "hldg_qty")
            if quantity <= 0:
                # 당일 전량 매도한 종목은 수량 0으로 며칠간 남는다(공식 안내).
                continue
            price, value = _price_and_value(row, "prpr", "evlu_amt")
            holdings.append(
                KisHolding(
                    symbol=_text(row, "pdno"),
                    name=_text(row, "prdt_name"),
                    market="KRX",
                    exchange_code="KRX",
                    country="KR",
                    currency="KRW",
                    quantity=quantity,
                    average_cost=_number(row, "pchs_avg_pric"),
                    price=price,
                    reported_value=value,
                    domestic=True,
                )
            )
    summary = _rows(pages[-1].get("output2")) if pages else []
    cash = _number(summary[0], "dnca_tot_amt") if summary else None
    return holdings, cash


def parse_overseas(
    body: dict[str, Any],
) -> tuple[list[KisHolding], list[KisFx], dict[str, Decimal]]:
    holdings: list[KisHolding] = []
    row_rates: dict[str, Decimal] = {}
    for row in _rows(body.get("output1")):
        quantity = _number(row, "ccld_qty_smtl1")
        if quantity <= 0:
            continue
        exchange = _text(row, "ovrs_excg_cd")
        currency = _text(row, "buy_crcy_cd")
        market, country = OVERSEAS_MARKETS.get(exchange, (exchange, None))
        price, value = _price_and_value(row, "ovrs_now_pric1", "frcr_evlu_amt2")
        holdings.append(
            KisHolding(
                symbol=_text(row, "pdno"),
                name=_text(row, "prdt_name"),
                market=market,
                exchange_code=exchange,
                country=country,
                currency=currency,
                quantity=quantity,
                average_cost=_number(row, "avg_unpr3"),
                price=price,
                reported_value=value,
                domestic=False,
            )
        )
        rate = _positive_or_none(row, "bass_exrt")
        if rate is not None:
            row_rates.setdefault(currency, rate)

    rates: dict[str, Decimal] = {}
    cash: dict[str, Decimal] = {}
    for row in _rows(body.get("output2")):
        currency = _text(row, "crcy_cd")
        rate = _positive_or_none(row, "frst_bltn_exrt")
        if rate is not None:
            rates[currency] = rate
        if row.get("frcr_dncl_amt_2") not in (None, ""):
            cash[currency] = _number(row, "frcr_dncl_amt_2")
    # 통화별 요약에 환율이 없을 때만 종목 행의 기준환율을 쓴다(실제 응답에서 두 값은 같았다).
    for currency, rate in row_rates.items():
        rates.setdefault(currency, rate)
    return holdings, [KisFx(c, r) for c, r in sorted(rates.items())], cash
