# 한국투자증권 연동 (Phase 4)

조회 전용으로 연결되어 있습니다. 주문·정정·취소·자동매매는 구현하지 않으며, 클라이언트가 주문 경로를 호출할 수 없게 허용 목록으로 막습니다.

## 확인 출처

- 공식 저장소 [koreainvestment/open-trading-api](https://github.com/koreainvestment/open-trading-api)의 `examples_llm`(요청 파라미터·응답 컬럼 정의), `kis_auth.py`(헤더·토큰·연속 조회), `stocks_info`(종목 마스터 형식)
- 2026-11-02 실제 계좌 응답의 **구조**(필드 이름과 값 형태). 금액·종목은 기록하지 않았습니다.
- ETF 구분 코드는 계좌와 무관한 공개 종목(005930, 069500, 360750, VOO, QQQ)으로 확인했습니다.

## 사용하는 API

| 용도 | 경로 | TR ID | 비고 |
| --- | --- | --- | --- |
| 토큰 발급 | `/oauth2/tokenP` | – | 1일 유효, 재발급 1분당 1회, 발급 시 알림톡 |
| 국내 잔고 | `/uapi/domestic-stock/v1/trading/inquire-balance` | `TTTC8434R` | `INQR_DVSN=02`(종목별), 연속 조회 `CTX_AREA_FK100/NK100` |
| 해외 잔고 | `/uapi/overseas-stock/v1/trading/inquire-present-balance` | `CTRP6504R` | 체결기준현재잔고. `WCRC_FRCR_DVSN_CD=02`, `NATN_CD=000` 한 번으로 전 국가 |
| 국내 종목 구분 | `/uapi/domestic-stock/v1/quotations/search-stock-info` | `CTPF1002R` | `scty_grp_id_cd`: `ST` 주권, `EF` ETF |
| 해외 종목 구분 | 공식 마스터 파일 `{nas,nys,ams,...}mst.cod.zip` | – | 증권유형 `2` 주식, `3` ETP(구분코드 `001` ETF), 업종분류코드(20번째 열) |
| 해외 업종명 | `/uapi/overseas-price/v1/quotations/industry-price` | `HHDFS76370100` | 해외주식 업종별코드조회. 거래소(`EXCD`)별 `icod` → `name` |

별도의 현재가 API는 부르지 않습니다. 두 잔고 응답에 현재가·평가금액·환율이 모두 들어 있어 화면 하나당 KIS 호출은 2번(국내 종목이 있으면 종목당 1번 추가, 하루 캐시)입니다.

해외 잔고는 `TTTS3012R`(해외주식 잔고) 대신 `CTRP6504R`을 씁니다. 거래소별로 나눠 부를 필요가 없고, 통화별 환율(`frst_bltn_exrt`)과 외화 예수금이 함께 오기 때문입니다.

해외 ETF 구분은 API로 할 수 없습니다. 상품기본정보(`CTPF1702R`)의 `ovrs_stck_dvsn_cd`는 VOO·QQQ도 일반 주식과 같은 `01`로 줍니다. 그래서 공식 마스터 파일을 하루 한 번 받아 서버 로컬(`.cache/kis_master/`)에 두 필드만 저장합니다(유형, ETP 구분, 업종분류코드). 받지 못하면 "기타"로 두며 주식으로 가정하지 않습니다.

해외 개별주의 섹터는 마스터 파일의 업종분류코드(예: 공개 종목 AAPL `730`, JPM `610`, ETF는 `000`)를 업종별코드조회 API의 업종명으로 바꿔 씁니다. 업종명 표는 계좌와 무관한 공개 데이터라 거래소별로 하루 한 번 받아 `.cache/kis_master/`에 두고 모든 사용자가 함께 씁니다. 표를 받지 못하거나 코드가 표에 없으면 "섹터 정보 없음"으로 두며, 코드로 이름을 추측하지 않습니다. 실패한 거래소는 10분 동안 다시 부르지 않습니다.

화면에는 KIS 업종명을 GICS 11개 섹터(정보기술·금융·헬스케어·임의소비재·커뮤니케이션 서비스·산업재·필수소비재·에너지·소재·유틸리티·부동산)로 묶어 "정보기술 (Information Technology)"처럼 한글명과 영문명을 함께 보여 줍니다(`app/integrations/kis/gics.py`). 표에 없는 업종명은 "섹터 정보 없음"입니다. KIS 업종이 GICS와 다르거나 비어 있는 대표 종목(V·MA·PYPL → 금융, WMT → 필수소비재, LIN → 소재)은 종목 단위로 바로잡습니다. `classifications.json`의 섹터 지정이 여전히 가장 우선합니다.

## 필드 매핑

| 내부 값 | 국내(`TTTC8434R` output1) | 해외(`CTRP6504R` output1) |
| --- | --- | --- |
| symbol | `pdno` | `pdno` |
| name | `prdt_name` | `prdt_name` |
| quantity | `hldg_qty` | `ccld_qty_smtl1` (체결수량합계) |
| average_cost | `pchs_avg_pric` | `avg_unpr3` |
| current_price | `prpr` | `ovrs_now_pric1` |
| reported_market_value | `evlu_amt` | `frcr_evlu_amt2` (외화) |
| currency | KRW | `buy_crcy_cd` |
| 환율 | – | output2 `frst_bltn_exrt` (없으면 행의 `bass_exrt`) |
| 예수금 | output2 `dnca_tot_amt` | output2 `frcr_dncl_amt_2` |

- 해외 수량은 `cblc_qty13`(잔고수량)이 아니라 `ccld_qty_smtl1`을 씁니다. 당일 매수분은 `cblc_qty13`에 빠지지만 평가금액·매입금액은 `ccld_qty_smtl1` 기준임을 실제 응답으로 확인했습니다.
- 현재가가 0이거나 비어 있으면 시세 없음(`null`)으로 보고 평가금액도 쓰지 않습니다.
- 필수 필드가 없거나 숫자가 아니면 그 응답 전체를 쓰지 않습니다(`KIS_RESPONSE_INVALID`).
- 실제 계좌로 확인한 결과, 원화 환산 총평가액이 KIS가 계산한 원화 합계와 0.002% 이내로 일치했습니다.
- 국내 잔고 필드 매핑은 공식 정의를 따랐지만, 확인 당시 국내 보유 종목이 없어 실제 값으로는 검증하지 못했습니다.

## 분류

KIS는 시장지수형/섹터형 ETF, 투자 대상 국가, 추종 지수를 주지 않습니다. 섹터는 해외 개별주만 공식 업종명을 GICS 섹터로 묶어 채웁니다. 나머지는 추정하지 않고 다음과 같이 둡니다.

- 주식: 국내 개별주 / 해외 개별주, 투자 대상 국가 = 상장 국가, 섹터 = 해외는 GICS 섹터(KIS 업종명에서 변환)·국내는 없음
- ETF: `ETF (유형 미분류)`, 투자 대상 국가·섹터·추종 지수 없음
- 사용자가 `data/live/classifications.json`에 직접 지정하면 그 값을 씁니다. 보유 종목이 드러나므로 `.gitignore` 대상이며, 형식은 `data/live/classifications.example.json`에 있습니다.

## 토큰과 호출 제한

- 토큰은 메모리와 사용자 행(`public.kis_credentials.token_enc`, AES-256-GCM 암호화)에 저장합니다. 서버를 재시작해도 재사용하며, 키를 다시 등록하면 이전 키의 토큰은 덮어쓰지 않습니다. 만료 10분 전부터 새로 발급합니다.
- 호출 제한·재발급 제한은 사용자(App Key)마다 따로 적용됩니다.
- 발급 시도는 1분에 한 번으로 제한합니다. 넘으면 KIS에 보내지 않고 `KIS_RATE_LIMITED`를 돌려줍니다.
- 만료·무효 토큰 응답(`EGW00123`, `EGW00121`)을 받으면 한 번만 재발급 후 재시도합니다.
- 호출 사이에 최소 0.12초를 둡니다. `EGW00201`(초당 한도)은 0.5초, 1초 대기 후 두 번까지 재시도합니다.
- 연속 조회는 최대 10페이지입니다. 더 있으면 일부만 보여 주지 않고 오류로 처리합니다.
- 한 화면이 여러 API를 동시에 부르므로 잔고 결과를 30초 동안 공유합니다.

## 실패 처리

| 상황 | 응답 |
| --- | --- |
| 키·계좌 미설정, 계좌 형식 오류 | 503 `KIS_NOT_CONFIGURED` |
| 토큰 발급 거부 | 503 `KIS_AUTH_FAILED` (KIS 오류 코드만 포함) |
| 호출 한도 | 503 `KIS_RATE_LIMITED` |
| 연결 실패·시간 초과 | 503 `KIS_UNAVAILABLE` |
| KIS 오류 응답 | 502 `KIS_API_ERROR` (`msg_cd`만 포함, `msg1`은 싣지 않음) |
| 응답 형식 이상 | 502 `KIS_RESPONSE_INVALID` |

국내·해외 중 하나라도 실패하면 전체를 오류로 돌려줍니다. 일부 잔고로 총액을 보여 주지 않고, Mock으로 대체하지 않습니다.

## 비밀 값

- App Key·Secret·토큰·계좌번호는 응답·예외 메시지·로그에 싣지 않습니다. 응답에는 계좌번호 자체가 없습니다(내부 요약은 끝 2자리만 남긴 마스킹).
- `httpx`는 INFO 로그에 요청 URL 전체(계좌 파라미터 포함)를 남기므로 WARNING 이상만 기록하게 했고, 로그 마스킹에 `CANO=`·`ACNT_PRDT_CD=` 패턴을 추가했습니다.

## LIVE 이력

KIS는 과거 평가금액을 주지 않습니다. 대시보드의 LIVE 총자산 변화는 소유자가 설정 화면에서 저장한 스냅샷으로 그립니다. 평가하지 못한 종목이 있는(불완전한) 스냅샷은 선에 넣지 않습니다. 자동 저장(스케줄러)은 아직 없습니다.

## 미지원

주문, 정정, 취소, 자동매매, 웹소켓 실시간 시세, 모의투자, 선물옵션·채권·ELW 잔고, ETF 구성 종목(확인된 데이터 출처 없음).
