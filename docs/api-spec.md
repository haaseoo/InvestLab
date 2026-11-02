# API 명세

기본 주소는 `http://localhost:8000`입니다. 대화형 문서는 `/docs`에서 볼 수 있습니다. 금액과 비율은 문자열이며 `null`은 값을 알 수 없다는 뜻입니다.

## 현황

| 메서드 | 경로 | 인증 | 상태 |
| --- | --- | --- | --- |
| GET | `/health` | 불필요 | 구현 |
| GET | `/api/v1/providers/status` | 불필요 | 구현 |
| GET | `/api/v1/portfolio` | `source=live`만 필요 | 구현 |
| GET | `/api/v1/portfolio/holdings` | `source=live`만 필요 | 구현 |
| GET | `/api/v1/portfolio/summary` | `source=live`만 필요 | 구현 |
| GET | `/api/v1/portfolio/history` | `source=live`만 필요 | 구현 |
| GET | `/api/v1/analytics/allocation` | `source=live`만 필요 | 구현 |
| GET | `/api/v1/analytics/risk` | 미정 | Phase 2, 현재 404 |
| POST | `/api/v1/simulations/buy` | 미정 | Phase 2, 현재 404 |
| POST | `/api/v1/simulations/rebalance` | 미정 | Phase 2, 현재 404 |
| POST | `/api/v1/analytics/report` | 필요 | Phase 5, 현재 404 |

## 공통

### 쿼리: `source`

`mock`(기본값) 또는 `live`. `live`는 `Authorization: Bearer <token>`이 필요하고 인가를 통과해야 합니다.

### 데이터 출처

모든 데이터 응답에 `source`와 `is_demo`가 있습니다. `mock`은 `data/mock`의 가상 데이터이고, `live`는 Phase 4부터 한국투자증권 데이터입니다.

### 오류 응답

```json
{ "error": { "code": "AUTH_NOT_CONFIGURED", "message": "사용자 인증이 아직 구성되지 않아 LIVE 데이터를 조회할 수 없습니다.", "details": {} } }
```

| HTTP | code | 의미 |
| --- | --- | --- |
| 401 | `AUTH_REQUIRED` | 토큰 없음 |
| 401 | `INVALID_TOKEN` | 토큰 무효 |
| 403 | `LIVE_FORBIDDEN` | 계좌 소유자가 아님 |
| 422 | `VALIDATION_ERROR` | 쿼리 값 오류. `details.fields`에 항목 표시 |
| 500 | `MOCK_DATA_UNAVAILABLE` | Seed 파일을 읽지 못함 |
| 500 | `INTERNAL_ERROR` | 예기치 못한 오류. 내부 정보는 응답에 넣지 않음 |
| 503 | `AUTH_NOT_CONFIGURED` | 토큰 검증기 미구성. 현재 모든 LIVE 요청의 응답 |
| 503 | `LIVE_OWNER_NOT_CONFIGURED` | `LIVE_OWNER_USER_ID` 미설정 |
| 503 | `LIVE_NOT_IMPLEMENTED` | 인가는 통과했지만 KIS 연동 미구현 |

LIVE 오류 시 Mock 데이터로 대체하지 않습니다.

## GET /health

정상 응답: `{"status":"ok"}`

## GET /api/v1/providers/status

Provider 준비 상태입니다. 비밀 값은 반환하지 않고 설정 여부만 반환합니다. `state`는 `ready`, `not_configured`, `not_implemented` 중 하나입니다.

```json
{
  "default_source": "mock",
  "providers": [
    { "source": "mock", "state": "ready", "is_demo": true, "label": "MOCK", "message": "…", "checks": [] },
    {
      "source": "live", "state": "not_implemented", "is_demo": false, "label": "LIVE", "message": "…",
      "checks": [{ "key": "kis_credentials", "label": "KIS App Key·Secret 설정", "ok": false }]
    }
  ]
}
```

## GET /api/v1/portfolio

대시보드용 전체 응답입니다. 공통 메타에 `summary`, `concentration`, `assumptions`, `fx_rates`, `holdings`, `allocation`이 더해집니다.

```json
{
  "source": "mock",
  "is_demo": true,
  "as_of": "2026-10-30T15:30:00+09:00",
  "retrieved_at": "2026-11-02T06:50:10.547406Z",
  "valuation_currency": "KRW",
  "summary": {
    "valuation_currency": "KRW",
    "total_cost_basis": "49060891.10",
    "total_market_value": "59365589.70",
    "valued_cost_basis": "49060891.10",
    "total_unrealized_pnl": "10304698.60",
    "total_unrealized_pnl_pct": "21.0039",
    "holding_count": 10,
    "valued_holding_count": 10,
    "unvalued_symbols": [],
    "is_complete": true
  },
  "concentration": { "top1_pct": "20.2055", "top3_pct": "51.0643", "top5_pct": "69.5087" },
  "assumptions": ["…"],
  "fx_rates": [{ "base_currency": "USD", "quote_currency": "KRW", "rate": "1385.50", "as_of": "…", "source": "mock" }],
  "holdings": ["Holding…"],
  "allocation": [{ "key": "broad_index_etf", "label": "시장지수 ETF", "market_value": "…", "weight_pct": "…", "holding_count": 4 }]
}
```

`as_of`는 가장 오래된 시세 시각, `retrieved_at`은 서버가 응답을 만든 시각입니다.

LIVE 요청 오류 예시(현재):

```
GET /api/v1/portfolio?source=live → 503 AUTH_NOT_CONFIGURED
```

## GET /api/v1/portfolio/holdings

공통 메타와 `holdings`를 반환합니다.

### Holding

| 필드 | 설명 |
| --- | --- |
| `symbol`, `market`, `name` | 종목코드, 시장, 종목명 |
| `asset_type` | `stock`, `etf`, `other` |
| `asset_class` | `broad_index_etf`, `sector_etf`, `domestic_stock`, `overseas_stock`, `other` |
| `country`, `sector` | 없으면 null |
| `quantity`, `average_cost`, `current_price` | 수량, 평균단가, 현재가(조회 실패 시 null) |
| `currency` | 거래 통화 |
| `cost_basis`, `market_value`, `unrealized_pnl`, `unrealized_pnl_pct` | 거래 통화 기준 |
| `valuation_currency`, `fx_rate`, `fx_as_of` | 평가 통화와 환산 근거. 같은 통화면 `fx_rate`는 1이고 `fx_as_of`는 null |
| `cost_basis_valuation`, `market_value_valuation`, `unrealized_pnl_valuation` | 평가 통화 기준. 환율이 없으면 null |
| `weight_pct` | 전체 평가금액 대비 비중 |
| `valuation_status` | `reported`, `calculated`, `unavailable` |
| `as_of`, `source`, `is_demo` | 시세 시각과 출처 |

## GET /api/v1/portfolio/summary

공통 메타와 `summary`, `concentration`, `assumptions`를 반환합니다.

## GET /api/v1/portfolio/history

```json
{
  "source": "mock",
  "is_demo": true,
  "retrieved_at": "…",
  "points": [
    { "captured_at": "2026-10-30T15:30:00+09:00", "total_market_value": "59365589.70", "total_cost_basis": "49060891.10", "valuation_currency": "KRW" }
  ]
}
```

Mock 이력은 가상입니다. 마지막 시점은 현재 Mock 합계와 일치합니다.

## GET /api/v1/analytics/allocation

쿼리 `dimension`: `asset_class`(기본값), `asset_type`, `market`, `currency`. 공통 메타와 `dimension`, `slices`, `excluded_symbols`를 반환합니다. 평가금액을 알 수 없는 종목은 비중에서 빠지고 `excluded_symbols`에 기록됩니다.

오류 예시: `dimension=foo` → 422 `VALIDATION_ERROR`
