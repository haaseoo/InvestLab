# 아키텍처

## 구조

```
apps/web   Next.js. 화면만 담당하며 금융 계산을 하지 않는다.
   │  HTTP (/api/v1), 금액은 문자열
apps/api   FastAPI
   ├─ routers/    요청 처리, source 해석과 LIVE 인가
   ├─ services/   valuation(종목 평가), analytics(집계), portfolio(응답 조립)
   ├─ providers/  PortfolioProvider ─ MockPortfolioProvider (data/mock)
   │                                └ KISPortfolioProvider (Phase 4 전까지 항상 오류)
   ├─ schemas/    공통 금융 모델
   └─ core/       설정, 오류, 로그 마스킹, LIVE 인가
```

복잡한 마이크로서비스 없이 웹과 API 두 프로세스로 구성합니다.

## Provider 패턴

`PortfolioProvider`는 `get_holdings`, `get_account_summary`, `get_quotes`, `get_provider_status`에 더해 `get_fx_rates`, `get_history`를 정의합니다. 환율과 이력은 환산 근거 표시와 추이 차트에 필요해 추가했습니다.

모든 Provider는 `services.valuation.build_holding`으로 같은 `Holding`을 만들고, 서비스 계층은 Provider 종류로 분기하지 않습니다. KIS 공식 모의투자(PAPER)는 가상 JSON인 MOCK과 다른 개념이며, 나중에 구현체와 `Source` 값을 추가하면 됩니다.

## 계산 규칙

금액은 `Decimal`로 계산하고 JSON 직렬화 때만 자릿수를 맞춥니다(금액 소수 2자리, 비율 4자리, 입력값은 원본 유지). 어떤 값이든 JSON에서는 문자열입니다.

| 값 | 계산식 | 전제 |
| --- | --- | --- |
| `cost_basis` | 수량 × 평균단가 | 수수료 미포함 |
| `market_value` | Provider 제공값, 없으면 수량 × 현재가 | 어느 쪽인지 `valuation_status`로 구분 |
| `unrealized_pnl` | 평가금액 − 원금 | |
| `unrealized_pnl_pct` | 평가손익 ÷ 원금 × 100 | 원금 0이면 null |
| `*_valuation` | 거래 통화 금액 × 환율 | 기준 시점 환율 하나를 사용. 환차손익 미반영 |
| `total_cost_basis` | Σ 환산 원금 | 시세 없어도 포함, 환율 없으면 제외 |
| `total_market_value` | Σ 환산 평가금액 | 값을 아는 종목만 |
| `total_unrealized_pnl_pct` | Σ 환산 손익 ÷ `valued_cost_basis` × 100 | 분모는 평가금액을 아는 종목의 원금 |
| `weight_pct` | 환산 평가금액 ÷ Σ 환산 평가금액 × 100 | 값을 아는 종목만 |
| `top{1,3,5}_pct` | 상위 N개 `weight_pct` 합 | ETF 내부 편입 종목은 펼치지 않음 |

수익률은 평가손익 기준입니다. 배당·분배금, 수수료, 세금, 입출금, 실현손익을 반영한 총수익률이 아닙니다. 예수금은 평가자산에 포함하지 않습니다. MDD·변동성·샤프지수는 충분한 이력이 생기기 전에는 계산하지 않습니다.

## 분석 엔진 (Phase 2)

모든 계산은 `apps/api/app/services`의 순수 함수이며 `Decimal`을 씁니다. 각 함수의 docstring에 계산식과 전제가 있습니다.

| 모듈 | 함수 | 내용 |
| --- | --- | --- |
| `analytics` | `compute_allocation` | 자산군·자산 유형·시장·통화·투자 대상 국가·섹터별 비중 |
| `analytics` | `compute_concentration` | 상위 1·3·5 비중, HHI(Σ비중%²), 유효 종목 수(10000 ÷ HHI) |
| `overlap` | `find_benchmark_groups` | 추종 지수가 같은 ETF 2개 이상의 묶음 |
| `overlap` | `analyze_constituent_overlap` | ETF 구성 종목을 펼친 기초 종목 노출. 두 경로 이상만 중복으로 본다 |
| `insights` | `build_insights` | 계산된 수치를 문장으로 옮긴다. 판단·권유·예측을 하지 않는다 |
| `simulations` | `simulate_buy` | 추가 매수 후 평균단가·원금·비중 |
| `simulations` | `simulate_rebalance` | 목표 비중 대비 가상 조정 금액과 이론 수량 |
| `simulations` | `simulate_scenario` | 가격·환율 가정 변화율 적용 후 평가금액, 종목별 단독 민감도 |

### 데이터를 만들지 않는 원칙

- **국가:** `country`는 상장 국가, `exposure_country`는 투자 대상 국가입니다. 국내 상장 해외지수 ETF는 추종 지수의 국가로 분류합니다. 금처럼 국가로 나눌 수 없으면 `null`이며 "국가 구분 없음"으로 따로 표시합니다.
- **섹터:** 개별 종목과 섹터 ETF만 분류합니다. 지수 ETF는 구성 종목 없이 섹터를 나눌 수 없어 `null`이며 "섹터 정보 없음"으로 묶습니다. 이 묶음은 항상 마지막에 두며 실제 분류처럼 다루지 않습니다.
- **ETF 중복:** 동일 지수 추종은 추종 지수 메타데이터만으로 판단합니다. 구성 종목 중복은 `get_etf_compositions()`가 데이터를 줄 때만 계산하며, 없으면 `unavailable` 상태와 데이터가 없는 ETF 목록만 반환합니다. Mock에는 구성 종목 데이터가 없습니다.
- **이력 기반 지표:** 변동성, MDD, 샤프 지수, 베타는 실제 가격 이력이 생기기 전까지 계산하지 않고 사유와 함께 `unavailable_metrics`로 반환합니다. Mock 이력은 가상이라 사용하지 않습니다.

### 시뮬레이션 전제

- **추가 매수:** 평균단가와 원금에는 수수료·세금을 넣지 않고 총 필요 금액에만 넣습니다. 수수료·세금·환율은 입력했을 때만 적용하며, 적용 여부를 결과의 전제에 적습니다. 추가분도 현재가로 평가하고, 금액 모드는 1주 단위로 내림합니다(소수 허용 시 제외). 현재 보유 종목만 대상으로 합니다.
- **리밸런싱:** 목표 합계는 100%(±0.01%p)여야 합니다. 입력하지 않은 항목은 목표 0%로 보고 표시합니다. 매매 단위, 수수료·세금, 현금 잔고, 가격 변동, 과세는 반영하지 않으며 결과에 이론적 시뮬레이션이라고 표시합니다.
- **하락 시나리오:** 종목 지정 변화율이 자산군 변화율보다 우선하며 둘을 겹쳐 적용하지 않습니다. 환율 변화는 해당 통화로 거래되는 종목에만 적용합니다. 예측이 아니라 가정 기반 민감도 분석입니다.

## 결측 처리

- `null`은 알 수 없음, `0`은 실제 0입니다. 화면에서 null은 `–`로 표시합니다.
- `valuation_status`: `reported`(제공값), `calculated`(계산값), `unavailable`(조회 실패).
- 시세나 환율이 없는 종목은 합계·비중에서 빠지고 `unvalued_symbols`에 기록되며 `is_complete`가 `false`가 됩니다. 화면은 경고를 표시합니다.
- 값이 하나도 없으면 합계는 0이 아니라 null입니다.
- 역수·교차 환율을 추정하지 않습니다. 평가 통화가 섞이면 합산하지 않고 오류를 냅니다.

## 인증과 데이터베이스 (Phase 3)

### 토큰 검증 (`app/core/auth.py`)

브라우저는 Supabase JS로 로그인하고, FastAPI 요청에 `Authorization: Bearer <access_token>`을 붙입니다. 서버는 다음을 모두 확인하고, 하나라도 어기면 401을 반환합니다.

| 항목 | 기준 |
| --- | --- |
| 서명 | `{SUPABASE_URL}/auth/v1/.well-known/jwks.json` 공개 키. ES256·RS256만 허용하며 HS256과 `none`은 거부 |
| kid | 헤더의 kid와 일치하는 키만 사용. 키 알고리즘과 헤더 알고리즘이 다르면 거부 |
| exp·iat | 필수. 시계 오차 허용은 30초 |
| iss | `{SUPABASE_URL}/auth/v1` |
| aud·role | `authenticated` |
| sub | UUID |

공개 키 목록은 10분간 캐시합니다. 모르는 kid가 오면 다시 받아 오되, 30초 안에는 다시 받지 않아 요청 폭증에 쓰이지 않게 합니다. 키를 받지 못하면 통과시키지 않고 503(`AUTH_UNAVAILABLE`)을 반환합니다. 서명 검증 없이 디코딩만 하는 경로는 없습니다.

### RLS가 적용되는 DB 접근 (`app/db/database.py`)

`DATABASE_URL`의 `postgres` 역할은 RLS를 우회(BYPASSRLS)합니다. 그래서 사용자 데이터는 `user_transaction()`으로만 다룹니다.

1. `request.jwt.claims`에 검증된 사용자 id를 넣습니다(`set_config(..., true)`, 트랜잭션 한정).
2. `SET LOCAL ROLE authenticated`로 권한을 낮춥니다.
3. Supabase의 `auth.uid()`와 RLS 정책이 브라우저에서 직접 접근할 때와 똑같이 적용됩니다.

Service Role Key는 쓰지 않습니다. `postgres` 권한 그대로 실행하는 것은 마이그레이션 스크립트뿐입니다.

### 테이블과 권한

| 테이블 | authenticated 권한 | RLS 조건 | 비고 |
| --- | --- | --- | --- |
| profiles | SELECT, INSERT, UPDATE(display_name) | `auth.uid() = id` | 새 사용자 트리거가 생성 |
| user_settings | SELECT, INSERT, UPDATE(4개 설정 열) | `auth.uid() = user_id` | 새 사용자 트리거가 생성 |
| portfolio_snapshots | SELECT, INSERT, DELETE | 본인 + INSERT는 `source = 'live'` | `source` CHECK도 `live`만 허용. 수정 불가 |
| holding_snapshots | SELECT, INSERT, DELETE | 본인 | 상위 스냅샷과 `(id, user_id)` 복합 외래키 |
| ai_reports | SELECT, INSERT, DELETE | 본인 | Phase 5에서 사용 |
| simulation_history | SELECT, INSERT, DELETE | 본인 | Mock 결과는 `is_demo = true`로 저장 |

`anon`(비로그인)은 어떤 테이블에도 권한이 없습니다. 수정 권한은 열 단위로 줘서 `user_id`·`id`는 바꿀 수 없습니다.

### 스냅샷 무결성

- **저장 조건:** Provider가 Mock(`is_demo`)이면 거부합니다(API와 DB 제약 이중 차단). LIVE 소유자만 저장할 수 있습니다.
- **기준 시각:** 시세 시각 중 가장 오래된 것을 `as_of`로 저장합니다. `as_of`가 없으면 저장하지 않습니다.
- **합계 검증:** 금액은 소수 4자리로 맞춘 뒤 합산합니다. 총액이 종목 합계와 다르면 저장하지 않습니다.
- **함께 저장하는 정보:** 통화, 환율 목록(`fx_rates`), 평가 상태, 내용 해시(SHA-256)
- **중복 방지:** 같은 사용자·출처·기준 시각의 스냅샷은 한 번만 저장됩니다(409 `SNAPSHOT_EXISTS`).
- **DB 제약:** `is_complete`와 평가 종목 수의 일치, 평가금액과 평가 상태의 일치, 미래 기준 시각 금지를 CHECK로 강제합니다.

## LIVE 접근 제어

KIS 인증정보는 서버에 하나뿐이라 로그인만으로는 부족합니다. 다른 가입자가 소유자의 계좌를 보지 못하도록 소유자 확인까지 거칩니다. 판단할 수 없으면 거부합니다.

1. 토큰 검증기 없음(`SUPABASE_URL` 미설정) → 503 `AUTH_NOT_CONFIGURED`
2. 토큰 없음 → 401 `AUTH_REQUIRED`
3. 토큰 무효(서명·만료·발급자·대상·역할) → 401 `INVALID_TOKEN`
4. 소유자 미지정 → 503 `LIVE_OWNER_NOT_CONFIGURED`
5. 소유자 아님 → 403 `LIVE_FORBIDDEN`
6. 통과 → KIS Provider 호출. 현재는 503 `LIVE_NOT_IMPLEMENTED`

프론트엔드의 모드 선택은 표시 설정일 뿐 권한이 아닙니다. TanStack Query 키에 `source`가 포함되어 LIVE 실패 중에 Mock 캐시가 보이지 않습니다.

## 보안 기본값

- 비밀 값은 `SecretStr`로 보관하고 서버 밖으로 내보내지 않습니다. 상태 API는 설정 여부만 반환합니다.
- CORS는 허용 목록의 주소, GET·POST, `Authorization`·`Content-Type`으로 제한합니다.
- 응답에 `Cache-Control: no-store`를 붙입니다.
- 로그 메시지와 예외 트레이스백에서 Bearer 토큰, JWT, DB 연결 문자열, Supabase 키, 키·시크릿 쌍, 계좌번호 형식을 마스킹합니다.
- DB 오류 응답에는 SQL이나 원인 메시지를 싣지 않습니다(`DB_UNAVAILABLE`). SQLAlchemy는 `hide_parameters`로 파라미터를 숨깁니다.
- 주문 API는 구현하지 않습니다.
- 개발 서버를 외부에 공개하려면 CORS와 인증 설정을 별도로 검증해야 합니다.

## 앞으로 필요한 결정

- **매입 환율:** 환차손익을 반영하려면 매입 시점 환율이 필요합니다. KIS 응답 제공 여부를 Phase 4에서 확인합니다.
- **스냅샷 저장 주기:** Phase 3에서 정합니다.
