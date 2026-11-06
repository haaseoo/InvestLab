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
| GET | `/api/v1/analytics/risk` | `source=live`만 필요 | 구현 |
| POST | `/api/v1/simulations/buy` | `source=live`만 필요 | 구현 |
| POST | `/api/v1/simulations/rebalance` | `source=live`만 필요 | 구현 |
| POST | `/api/v1/simulations/scenario` | `source=live`만 필요 | 구현 |
| GET | `/api/v1/me` | 필요 | 구현 |
| GET, PUT | `/api/v1/settings` | 필요 | 구현 |
| GET, POST | `/api/v1/snapshots` | 필요 (POST는 본인 KIS 키 등록) | 구현 |
| GET, PUT, DELETE | `/api/v1/kis/credentials` | 필요 | 구현 |
| GET, DELETE | `/api/v1/snapshots/{id}` | 필요 | 구현 |
| GET, POST | `/api/v1/simulations/history` | 필요 | 구현 |
| DELETE | `/api/v1/simulations/history/{id}` | 필요 | 구현 |
| POST | `/api/v1/analytics/report` | 필요 | Phase 5, 현재 404 |

## 공통

### 쿼리: `source`

`mock`(기본값) 또는 `live`. `live`는 `Authorization: Bearer <token>`이 필요하고 인가를 통과해야 합니다.

### 데이터 출처

모든 데이터 응답에 `source`와 `is_demo`가 있습니다. `mock`은 `data/mock`의 가상 데이터이고, `live`는 한국투자증권 실제 계좌 데이터입니다. KIS 잔고 응답에는 시세 시각이 없어 `as_of`는 조회 시각이며, 장이 닫혀 있으면 현재가는 마지막 체결가입니다. ETF 유형이 확인되지 않은 종목의 `asset_class`는 `etf_unclassified`입니다.

### 오류 응답

```json
{ "error": { "code": "AUTH_NOT_CONFIGURED", "message": "사용자 인증이 아직 구성되지 않아 LIVE 데이터를 조회할 수 없습니다.", "details": {} } }
```

| HTTP | code | 의미 |
| --- | --- | --- |
| 401 | `AUTH_REQUIRED` | 토큰 없음 |
| 401 | `INVALID_TOKEN` | 토큰 무효 |
| 404 | `HOLDING_NOT_FOUND` | 시뮬레이션 대상 종목이 보유 종목에 없음 |
| 422 | `VALIDATION_ERROR` | 요청 형식 오류. `details.fields`에 항목, `details.reasons`에 사유 |
| 422 | `INVALID_SIMULATION_INPUT` | 시뮬레이션 입력이 계산 조건에 맞지 않음(목표 합계, 모르는 항목 등) |
| 500 | `MOCK_DATA_UNAVAILABLE` | Seed 파일을 읽지 못함 |
| 500 | `INTERNAL_ERROR` | 예기치 못한 오류. 내부 정보는 응답에 넣지 않음 |
| 409 | `SNAPSHOT_EXISTS` | 같은 기준 시각의 스냅샷이 이미 있음 |
| 422 | `MOCK_SNAPSHOT_FORBIDDEN` | Mock 데이터를 스냅샷으로 저장하려 함 |
| 422 | `SNAPSHOT_INTEGRITY` | 합계 불일치, 기준 시각 없음 등으로 저장하지 않음 |
| 503 | `AUTH_NOT_CONFIGURED` | `SUPABASE_URL` 미설정으로 토큰을 검증할 수 없음 |
| 503 | `AUTH_UNAVAILABLE` | 인증 서버 공개 키를 가져오지 못함 |
| 503 | `DB_NOT_CONFIGURED` | `DATABASE_URL` 미설정 |
| 503 | `DB_UNAVAILABLE` | DB 접속·쿼리 실패. 상세 원인은 응답에 싣지 않음 |
| 409 | `KIS_NOT_CONFIGURED` | 본인 KIS 키를 등록하지 않음 |
| 409 | `KIS_CREDENTIALS_UNREADABLE` | 저장된 키를 복호화하지 못함(마스터 키 변경 등). 다시 등록 필요 |
| 422 | `INVALID_KIS_CREDENTIALS` | 키·계좌번호 형식 오류. `details.reasons`에 사유(입력값은 싣지 않음) |
| 503 | `KIS_CREDENTIAL_STORE_NOT_CONFIGURED` | `KIS_CREDENTIAL_KEY` 미설정 |
| 503 | `KIS_AUTH_FAILED` | KIS 접근 토큰 발급 거부. `details.kis_code`만 포함 |
| 503 | `KIS_RATE_LIMITED` | KIS 호출 한도(`EGW00201`) 또는 토큰 재발급 1분 제한 |
| 503 | `KIS_UNAVAILABLE` | KIS 서버 연결 실패·시간 초과 |
| 502 | `KIS_API_ERROR` | KIS가 오류 반환. `details`에 `tr_id`, `kis_code`만 포함 |
| 502 | `KIS_RESPONSE_INVALID` | KIS 응답에 필수 필드가 없거나 형식이 다름 |

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

`source=live` 이력은 KIS가 아니라 소유자가 저장한 스냅샷(RLS)에서 옵니다. 완전한(`is_complete`) 스냅샷만 `as_of` 순으로 반환하며 `captured_at`에는 스냅샷의 `as_of`가 들어갑니다. DB가 없으면 503 `DB_NOT_CONFIGURED`입니다.

## GET /api/v1/analytics/allocation

쿼리 `dimension`: `asset_class`(기본값), `asset_type`, `market`, `currency`, `exposure_country`, `sector`. 분류 값이 없는 종목은 `is_unclassified: true`인 묶음 하나로 모아 마지막에 둡니다. 각 묶음의 `symbols`에 종목코드가 들어 있습니다. 공통 메타와 `dimension`, `slices`, `excluded_symbols`를 반환합니다. 평가금액을 알 수 없는 종목은 비중에서 빠지고 `excluded_symbols`에 기록됩니다.

오류 예시: `dimension=foo` → 422 `VALIDATION_ERROR`

## GET /api/v1/analytics/risk

공통 메타에 다음이 더해집니다.

| 필드 | 내용 |
| --- | --- |
| `concentration` | `top1_pct`, `top3_pct`, `top5_pct`, `hhi`(0~10000), `effective_holdings` |
| `allocations` | `asset_class`, `exposure_country`, `sector`, `currency` 차원의 비중 목록 |
| `overlap.benchmark_groups` | 추종 지수가 같은 ETF 묶음과 합계 비중 |
| `overlap.constituent_overlap` | `status`(`not_applicable`·`unavailable`·`partial`·`complete`), `covered_etfs`, `missing_etfs`, `overlaps` |
| `unavailable_metrics` | 계산하지 않은 지표와 사유 |
| `insights` | 분석 엔진이 계산한 사실 문장(`key`, `title`, `detail`). AI 결과가 아님 |
| `excluded_symbols`, `assumptions` | 제외 종목과 계산 전제 |

Mock 응답 예시(발췌):

```json
{
  "source": "mock", "is_demo": true, "as_of": "2026-10-30T15:30:00+09:00",
  "concentration": { "top1_pct": "20.2055", "top3_pct": "51.0643", "top5_pct": "69.5087", "hhi": "1269.5804", "effective_holdings": "7.8766" },
  "overlap": {
    "benchmark_groups": [{ "benchmark": "S&P 500", "combined_weight_pct": "28.7956", "holdings": ["…"] }],
    "constituent_overlap": { "status": "unavailable", "covered_etfs": [], "missing_etfs": ["VOO", "QQQ", "SOXX", "360750", "133690", "411060"], "overlaps": [] }
  },
  "insights": [{ "key": "top3", "title": "상위 3개 종목 비중 51.06%", "detail": "…" }]
}
```

### ETF 구성 종목 파일

`data/mock/etf_compositions.json`이 있으면 Mock Provider가 읽습니다. 기본으로는 없습니다. 실제 출처에서 확인한 데이터만 넣습니다. 구성 비중 합이 100.5%를 넘으면 오류입니다.

```json
{
  "compositions": [
    {
      "etf_symbol": "SOXX", "etf_market": "NASDAQ", "as_of": "2026-10-30T00:00:00+00:00", "provider": "데이터 제공처",
      "constituents": [{ "symbol": "NVDA", "market": "NASDAQ", "name": "NVIDIA", "weight_pct": "8.12" }]
    }
  ]
}
```

## 시뮬레이션 공통

요청 본문의 숫자는 문자열로 보내는 것을 권장합니다(정밀도 보존). 응답에는 공통 메타와 `is_theoretical: true`, `assumptions`가 포함됩니다. 결과는 저장하지 않으며 주문을 실행하지 않습니다.

## POST /api/v1/simulations/buy

| 필드 | 필수 | 설명 |
| --- | --- | --- |
| `symbol`, `market` | 예 | 보유 종목 |
| `mode` | 예 | `quantity` 또는 `amount` |
| `quantity` / `amount` | 모드에 따라 | 수량, 또는 수수료·세금 제외 매수 금액(거래 통화) |
| `price` | 예 | 가정 매수가(거래 통화) |
| `allow_fractional` | 아니오 | 기본 `false`. 소수 수량 허용 |
| `fee_amount`, `tax_amount` | 아니오 | 없으면 미적용 |
| `fx_rate` | 아니오 | 없으면 현재 환율 |

```json
{ "symbol": "005930", "market": "KRX", "mode": "quantity", "quantity": "10", "price": "80000" }
```

응답의 `before`·`after`에 수량, 평균단가, 원금, 평가금액, 비중이 있고, `purchase`에 매수 금액, 수수료, 세금, 총 필요 금액, 적용 환율과 출처(`same_currency`·`input`·`current`·`unavailable`), 남는 금액이 있습니다. `weights`는 전 종목의 비중 변화입니다. 위 예시의 새 평균단가는 `71876.92`(9,344,000 ÷ 130)입니다.

## POST /api/v1/simulations/rebalance

```json
{ "dimension": "asset_class", "targets": [{ "key": "broad_index_etf", "target_pct": "50" }, { "key": "other", "target_pct": "50" }], "additional_cash": "0" }
```

`dimension`이 `holding`이면 `key`는 `시장:종목코드`(예: `KRX:005930`)입니다. 목표 합계가 100%가 아니거나, 중복·미지 항목이 있으면 422 `INVALID_SIMULATION_INPUT`입니다. 응답 `rows`에 현재·목표 비중, 차이, 목표 금액, 조정 금액, 이론 수량(종목 단위), `implicit_target`이 있고 `constraints_not_applied`에 반영하지 않은 제약이 있습니다.

## POST /api/v1/simulations/scenario

```json
{
  "shocks": [{ "type": "asset_class", "key": "sector_etf", "change_pct": "-30" }],
  "fx_shocks": [{ "currency": "USD", "change_pct": "-5" }],
  "standalone_change_pct": "-20"
}
```

변화율은 -100 이상 1000 이하이며 하나 이상 지정해야 합니다. 응답에는 전체 변화(`total_before`, `total_after`, `total_change`, `total_change_pct`), 종목별 결과 `rows`(적용된 변화율과 출처), `standalone`(종목별 단독 민감도)이 있습니다.

## 인증

로그인이 필요한 API는 `Authorization: Bearer <Supabase access token>`을 요구합니다. 검증 기준은 [아키텍처 문서](architecture.md#토큰-검증-appcoreauthpy)에 있습니다. 모든 사용자 데이터는 RLS로 본인 것만 조회·변경됩니다.

## GET /api/v1/me

```json
{ "user_id": "uuid", "email": "user@example.com", "database_available": true }
```

## GET·PUT /api/v1/settings

```json
{ "theme": "light", "preferred_currency": "KRW", "preferred_source": "mock", "mask_account_numbers": true, "updated_at": "…" }
```

PUT 본문은 `updated_at`을 뺀 같은 형식입니다. `theme`은 `light`·`dark`·`system`, `preferred_source`는 `mock`·`live`만 허용합니다.

## 스냅샷

- `POST /api/v1/snapshots?source=live`: LIVE Provider에서 현재 보유 데이터를 받아 검증 후 저장합니다. 201과 상세를 반환합니다. `source=mock`은 422 `MOCK_SNAPSHOT_FORBIDDEN`, 본인 키가 없으면 409 `KIS_NOT_CONFIGURED`입니다. KIS 조회가 실패하면 해당 KIS 오류를 반환하며 아무것도 저장하지 않습니다. 같은 30초 캐시 결과를 두 번 저장하면 409 `SNAPSHOT_EXISTS`입니다.
- `GET /api/v1/snapshots?limit=30`: 기준 시각 최신순 요약 목록
- `GET /api/v1/snapshots/{id}`: 상세(`fx_rates`, `content_hash`, `holdings`). 본인 것이 아니면 404
- `DELETE /api/v1/snapshots/{id}`: 204. 종목 스냅샷도 함께 삭제됩니다.

## 한국투자증권 키

- `GET /api/v1/kis/credentials`: `{ "registered": true, "account_masked": "********01", "updated_at": "…" }`. 키는 다시 내보내지 않습니다.
- `PUT /api/v1/kis/credentials`: `{ "app_key": "…", "app_secret": "…", "account_no": "12345678-01" }`. 잔고를 한 번 조회해 확인한 뒤 암호화해 저장하고 위 상태를 돌려줍니다. 키가 틀리면 `KIS_AUTH_FAILED` 등 KIS 오류를 돌려주며 저장하지 않습니다.
- `DELETE /api/v1/kis/credentials`: 204. 키와 접근 토큰을 삭제합니다. 스냅샷·기록은 남습니다.

## 시뮬레이션 기록

- `POST /api/v1/simulations/history`: `{ "simulation_type": "buy|rebalance|scenario", "source": "mock|live", "input": {}, "result": {}, "as_of": null }`. 각 JSON은 256KB 이하입니다. `source=live` 결과는 본인 KIS 키를 등록한 사용자만 저장할 수 있고, Mock 결과는 `is_demo: true`로 저장됩니다.
- `GET /api/v1/simulations/history?limit=20`, `DELETE /api/v1/simulations/history/{id}`
