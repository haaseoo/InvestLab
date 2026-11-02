# 한국투자증권 연동 (Phase 4 준비 자료)

**현재 구현되어 있지 않습니다.** `KISPortfolioProvider`는 API를 호출하지 않고 항상 `LIVE_NOT_IMPLEMENTED` 오류를 냅니다.

## 확인 출처

2026-11-02에 공식 저장소 [koreainvestment/open-trading-api](https://github.com/koreainvestment/open-trading-api)의 `README.md`, `llms.txt`, `kis_devlp.yaml`, `examples_llm/kis_auth.py`와 아래 예제 파일에서 확인했습니다. 구현 전에 [API 포털](https://apiportal.koreainvestment.com/)에서 다시 확인해야 합니다.

## 도메인

| 환경 | 주소 |
| --- | --- |
| 실전 | `https://openapi.koreainvestment.com:9443` |
| 모의투자 | `https://openapivts.koreainvestment.com:29443` |

모의투자(PAPER)는 초기 범위가 아닙니다.

## 엔드포인트

조회용만 사용합니다. 주문 API는 사용하지 않습니다.

| 용도 | 경로 | TR ID (실전) | TR ID (모의) | 예제 |
| --- | --- | --- | --- | --- |
| 토큰 발급 | `/oauth2/tokenP` | – | – | `examples_llm/auth/auth_token` |
| 국내 잔고 | `/uapi/domestic-stock/v1/trading/inquire-balance` | `TTTC8434R` | `VTTC8434R` | `examples_llm/domestic_stock/inquire_balance` |
| 해외 잔고 | `/uapi/overseas-stock/v1/trading/inquire-balance` | `TTTS3012R` | `VTTS3012R` | `examples_llm/overseas_stock/inquire_balance` |
| 국내 현재가 | `/uapi/domestic-stock/v1/quotations/inquire-price` | `FHKST01010100` | `FHKST01010100` | `examples_llm/domestic_stock/inquire_price` |
| 해외 현재가 | `/uapi/overseas-price/v1/quotations/price` | `HHDFS00000300` | `HHDFS00000300` | `examples_llm/overseas_stock/price` |

## 요청 공통 사항

- 헤더: `authorization: Bearer <token>`, `appkey`, `appsecret`, `tr_id`, `custtype: P`(개인·법인 일반 고객)
- 계좌: `CANO`(8자리), `ACNT_PRDT_CD`(2자리, 종합계좌 `01`)
- 연속 조회: 국내 `CTX_AREA_FK100`/`NK100`, 해외 `CTX_AREA_FK200`/`NK200`
- 해외 잔고 거래소 코드 `OVRS_EXCG_CD`: 실전에서 `NASD`(미국 전체), `NAS`, `NYSE`, `AMEX`, 그 외 `SEHK`, `SHAA`, `SZAA`, `TKSE`, `HASE`, `VNSE`

## 호출 제한

- 토큰 재발급은 1분당 1회입니다(공식 README). 토큰을 서버에 캐시하고 응답의 `access_token_token_expired`로 만료를 판단합니다. 프로세스를 재시작해도 재발급이 몰리지 않게 저장 방식을 정해야 합니다.
- 초당 호출 한도를 넘으면 `EGW00201` 오류가 납니다. 구체적인 한도 수치는 포털에서 확인해야 합니다. 공식 예제는 호출 사이에 대기 시간을 둡니다.
- 모의투자 계좌의 REST 호출 한도는 실전보다 낮습니다.

## 구현 체크리스트

- [ ] 응답 필드 이름과 의미를 포털 문서로 확인하고 `Position`, `Quote`, `reported_market_value`에 매핑
- [ ] 평균단가, 평가금액, 환율 필드의 존재 여부 확인. 없는 값을 추정하지 않음
- [ ] `asset_class` 판별 근거 확인. KIS가 ETF 구분을 제공하지 않으면 `other`로 두지 말고 별도 처리 방안 결정
- [ ] 해외 잔고의 거래소별 조회와 통화 처리 확인
- [ ] `httpx` 타임아웃과 제한적 재시도. `EGW00201`과 토큰 오류를 구분
- [ ] 시세 실패 시 `current_price=None`으로 부분 결과 반환
- [ ] 전체 실패 시 오류 반환. Mock으로 대체하지 않음
- [ ] 키·토큰·계좌번호가 로그, 예외 메시지, 응답에 남지 않는지 테스트
- [ ] 첫 연결은 사용자 확인 후 진행. App Key와 계좌번호는 사용자가 `.env`에 직접 입력

## 미지원

주문, 정정, 취소, 자동매매, 웹소켓 실시간 시세는 구현하지 않습니다. 선물옵션, 채권, ELW 잔고는 초기 범위가 아닙니다.
