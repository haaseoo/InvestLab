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

## 결측 처리

- `null`은 알 수 없음, `0`은 실제 0입니다. 화면에서 null은 `–`로 표시합니다.
- `valuation_status`: `reported`(제공값), `calculated`(계산값), `unavailable`(조회 실패).
- 시세나 환율이 없는 종목은 합계·비중에서 빠지고 `unvalued_symbols`에 기록되며 `is_complete`가 `false`가 됩니다. 화면은 경고를 표시합니다.
- 값이 하나도 없으면 합계는 0이 아니라 null입니다.
- 역수·교차 환율을 추정하지 않습니다. 평가 통화가 섞이면 합산하지 않고 오류를 냅니다.

## LIVE 접근 제어

KIS 인증정보는 서버에 하나뿐이라 로그인만으로는 부족합니다. 다른 가입자가 소유자의 계좌를 보지 못하도록 소유자 확인까지 거칩니다. 판단할 수 없으면 거부합니다.

1. 토큰 검증기 없음 → 503 `AUTH_NOT_CONFIGURED` (현재 상태)
2. 토큰 없음 → 401 `AUTH_REQUIRED`
3. 토큰 무효 → 401 `INVALID_TOKEN`
4. 소유자 미지정 → 503 `LIVE_OWNER_NOT_CONFIGURED`
5. 소유자 아님 → 403 `LIVE_FORBIDDEN`
6. 통과 → KIS Provider 호출. 현재는 503 `LIVE_NOT_IMPLEMENTED`

프론트엔드의 모드 선택은 표시 설정일 뿐 권한이 아닙니다. TanStack Query 키에 `source`가 포함되어 LIVE 실패 중에 Mock 캐시가 보이지 않습니다.

## 보안 기본값

- 비밀 값은 `SecretStr`로 보관하고 서버 밖으로 내보내지 않습니다. 상태 API는 설정 여부만 반환합니다.
- CORS는 허용 목록의 주소, GET·POST, `Authorization`·`Content-Type`으로 제한합니다.
- 응답에 `Cache-Control: no-store`를 붙입니다.
- 로그 메시지에서 Bearer 토큰, 키·시크릿 쌍, 계좌번호 형식을 마스킹합니다. 예외 트레이스백 본문은 마스킹 대상이 아니므로 Phase 4에서 외부 호출 예외에 비밀 값이 실리지 않게 처리해야 합니다.
- 주문 API는 구현하지 않습니다.
- 개발 서버를 외부에 공개하려면 CORS와 인증 설정을 별도로 검증해야 합니다.

## 앞으로 필요한 결정

- **매입 환율:** 환차손익을 반영하려면 매입 시점 환율이 필요합니다. KIS 응답 제공 여부를 Phase 4에서 확인합니다.
- **스냅샷 저장 주기:** Phase 3에서 정합니다.
