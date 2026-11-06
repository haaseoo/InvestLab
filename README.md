# InvestLab

주식·ETF 보유 자산을 분석하는 개인 투자 포트폴리오 웹서비스입니다. 조회 전용이며 매수·매도 주문이나 자동매매 기능은 없습니다. 투자 자문이 아닙니다.

현재 상태는 **Phase 4**입니다. Mock 데이터로 전체 흐름·분석 엔진·시뮬레이터가 동작하고, Supabase 로그인과 사용자별 데이터 저장(RLS), 한국투자증권 실제 계좌 조회(읽기 전용)가 연결되어 있습니다. AI는 아직 연결되지 않았습니다.

## 기술 스택

| 영역 | 사용 기술 |
| --- | --- |
| Frontend | Next.js 16 (App Router), TypeScript, Tailwind CSS 4, shadcn/ui, Recharts, TanStack Query, Lucide, Pretendard |
| Backend | Python 3.11+, FastAPI, Pydantic v2, httpx, pytest, Ruff |
| DB·인증 | Supabase PostgreSQL·Auth, SQLAlchemy 2 + psycopg 3, PyJWT(JWKS 검증), @supabase/supabase-js |
| 증권 | 한국투자증권 Open API (조회 전용) |
| 예정 | OpenAI API (Phase 5) |

마이그레이션은 Alembic 대신 `supabase/migrations/`의 SQL 파일로 관리합니다. RLS 정책·권한·트리거가 모두 SQL이라 한 곳에서 검토하기 위해서입니다.

## 로컬 실행

Node.js 20.9 이상과 Python 3.11 이상이 필요합니다. API 키 없이 실행됩니다.

```bash
# 터미널 1: API (http://localhost:8000, 문서 /docs)
cd apps/api
python3.11 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/uvicorn app.main:app --reload --port 8000

# 터미널 2: 웹 (http://localhost:3000)
cd apps/web
npm install
npm run dev
```

## Mock 모드

기본 모드입니다. `data/mock/`의 Seed 파일만 읽으며 외부 서비스가 필요 없습니다. 모든 값은 가상이고 화면에 `DEMO`로 표시됩니다.

- `data/mock/portfolio.json`: 보유 종목, 가상 시세, 가상 환율
- `data/mock/history.json`: 가상 자산 이력. `portfolio.json`을 고치면 `apps/api`에서 `.venv/bin/python scripts/generate_mock_history.py`로 다시 생성합니다.
- `data/mock/etf_compositions.json`(선택): ETF 구성 종목. **기본으로 포함하지 않습니다.** 실제 출처에서 확인한 데이터가 있을 때만 넣으면 구성 종목 중복 분석이 계산됩니다. 형식은 [API 명세](docs/api-spec.md#etf-구성-종목-파일)를 참고하세요.

## LIVE 모드와 로그인

LIVE 데이터는 **로그인한 사용자가 본인 한국투자증권 키를 등록했을 때만** 볼 수 있습니다. 서버는 Supabase 토큰의 서명·만료·발급자·대상·역할을 검증한 뒤, 토큰의 사용자 id로 그 사용자의 암호화된 키를 찾아 본인 계좌 잔고만 조회합니다. 다른 사용자의 키나 계좌에 닿는 경로는 없습니다. KIS 조회가 실패하면 오류 화면을 보여 주며 Mock 데이터로 대체하지 않습니다.

- 로그인: 화면 오른쪽 위 **로그인** → 이메일·비밀번호. 공개 가입은 받지 않고, 운영자가 Supabase에서 초대합니다(아래 "사용자 초대").
- 로그인하면 설정(기본 데이터 모드, 계좌번호 마스킹)과 시뮬레이션 결과를 저장할 수 있습니다.
- Mock 모드는 로그인 없이 동작하며 항상 DEMO로 표시됩니다.

## 환경변수

Mock 모드에는 필요 없습니다. 값을 바꾸려면 `cp .env.example .env`로 복사합니다. 웹의 API 주소는 `apps/web/.env.local`의 `NEXT_PUBLIC_API_BASE_URL`로 지정합니다(기본값 `http://localhost:8000`). `NEXT_PUBLIC_` 변수는 브라우저에 노출되므로 비밀 값을 넣지 않습니다.

## Supabase 연결

1. Supabase 프로젝트를 만들고 Authentication에서 본인 계정을 추가한 뒤 **신규 가입을 끕니다.**
2. 루트 `.env`에 `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `DATABASE_URL`(Session pooler)을 넣습니다. DB 통합 테스트를 돌리려면 실제 사용자 UID를 `LIVE_OWNER_USER_ID`에 넣습니다(앱은 쓰지 않습니다).
3. `apps/web/.env.local`에 `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`를 넣습니다.
4. 마이그레이션을 검증(롤백)한 뒤 적용합니다.

```bash
cd apps/api
.venv/bin/python scripts/migrate.py status   # 적용 현황
.venv/bin/python scripts/migrate.py check    # 트랜잭션에서 실행 후 롤백
.venv/bin/python scripts/migrate.py apply    # 적용
```

Service Role·Secret Key는 쓰지 않습니다. 서버는 사용자 요청마다 트랜잭션 안에서 `authenticated` 역할로 전환해 RLS를 그대로 적용받습니다.

## 한국투자증권 연결

키는 사용자마다 각자 등록합니다. 서버에는 암호화 키 하나만 둡니다.

1. 서버 `.env`에 `KIS_CREDENTIAL_KEY`(32바이트 base64, 만드는 법은 `.env.example`)를 넣습니다. **따로 백업해 두세요.** 잃어버리거나 바꾸면 모든 사용자가 키를 다시 등록해야 합니다.
2. 각 사용자는 [KIS Developers](https://apiportal.koreainvestment.com/)에서 Open API를 신청해 App Key·Secret을 발급받습니다.
3. 로그인 후 **설정 → 내 한국투자증권 연결**에 App Key·Secret·계좌번호(8자리-2자리)를 입력합니다. 서버가 잔고를 한 번 조회해 맞는지 확인한 뒤에만 저장합니다.
4. (선택) ETF의 유형·추종 지수, 섹터는 KIS가 주지 않습니다. `data/live/classifications.example.json`을 참고해 `data/live/classifications.json`을 만들면 반영됩니다. 이 파일은 서버 전체(모든 사용자)에 적용되며 커밋되지 않습니다.

키와 접근 토큰은 AES-256-GCM으로 암호화해 `public.kis_credentials`에 사용자별로 저장하며(RLS), 토큰은 재시작 때도 재사용됩니다(발급 시 KIS 알림톡이 갑니다). 앱은 조회 API만 부르지만, KIS App Key 자체는 주문 권한도 있고 서버 운영자는 기술적으로 복호화할 수 있습니다. 등록하는 사람에게 이 점을 알려 주세요. 사용하는 API, 필드 매핑, 호출 제한은 [docs/kis-integration.md](docs/kis-integration.md)에 있습니다.

### 사용자 초대

공개 가입은 꺼 둡니다. Supabase 대시보드 **Authentication → Users → Invite user**로 초대하면, 받은 사람이 메일 링크에서 비밀번호를 정하고 로그인합니다. 링크가 배포한 웹 주소로 오도록 **Authentication → URL Configuration**의 Site URL과 Redirect URLs에 웹 주소를 넣어 두세요. 웹을 배포하기 전에는 링크가 `localhost`로 가므로 초대받은 사람의 기기에서 열리지 않습니다.

로그인 아이디는 이메일입니다. 비밀번호는 Supabase Auth만 다루며 InvestLab 서버를 거치지 않습니다. 비밀번호를 잊으면 같은 화면에서 재설정 메일을 보냅니다.

## 테스트

```bash
cd apps/api && .venv/bin/pytest && .venv/bin/ruff check . && .venv/bin/ruff format --check .
cd apps/api && .venv/bin/pytest -m "not integration"   # 실제 Supabase 없이 실행
cd apps/web && npx tsc --noEmit && npm run lint && npx prettier --check . && npm run build
```

## 현재 구현 기능

- 대시보드: 총 평가자산과 거래 통화 구성, 원금·손익·수익률·종목 수, 자산 구성, 종목별 평가금액, 가상 이력 차트, 분석 엔진 인사이트(AI 아님), 기준·조회 시각
- 보유 종목: 검색, 정렬, 원화 환산/거래 통화 전환, 모바일 카드 보기
- 분석: 상위 1·3·5 종목 집중도, HHI·유효 종목 수, 자산군·투자 대상 국가·섹터·거래 통화 비중, 동일 지수 추종 ETF, ETF 구성 종목 중복(데이터가 있을 때만), 계산하지 않은 지표와 사유
- 시뮬레이터: 추가 매수 평균단가, 목표 비중 리밸런싱, 하락 시나리오와 종목별 민감도
- 설정: 데이터 모드, 본인 KIS 키 등록·해제, 서버 LIVE 준비 상태, 실제 계좌 스냅샷 저장, 시뮬레이션 기록
- LIVE: 한국투자증권 국내·해외 잔고(현재가·평가금액·환율 포함) 조회, 저장한 스냅샷으로 그리는 총자산 변화
- API: `/health`, `/providers/status`, `/portfolio`, `/portfolio/holdings`, `/portfolio/summary`, `/portfolio/history`, `/analytics/allocation`, `/analytics/risk`, `/simulations/buy`, `/simulations/rebalance`, `/simulations/scenario`
- 시세·환율 누락 처리, LIVE 접근 차단, CORS 제한, 로그 마스킹

- 로그인·로그아웃, 초대 링크로 첫 비밀번호 설정, 사용자별 KIS 키(암호화 저장), 사용자 설정·시뮬레이션 기록 저장, 실제 계좌 스냅샷 저장 구조

AI 리포트 화면은 안내 문구만 표시합니다. 실제 계좌 스냅샷은 각 사용자가 설정 화면에서 직접 저장합니다(자동 저장 없음).

KIS 테스트는 가짜 전송 계층만 쓰며 실제 한국투자증권에 접속하지 않습니다. `integration` 표시가 붙은 테스트는 실제 Supabase에 접속합니다. DB 테스트는 하나의 트랜잭션 안에서 실행 후 롤백하므로 데이터를 남기지 않습니다. 실제 계정의 로그인 성공은 비밀번호가 필요해 자동 테스트하지 않으며 직접 확인해야 합니다.

## 향후 개발 계획

| Phase | 내용 |
| --- | --- |
| 2 | 완료: 분석 엔진과 시뮬레이터 |
| 3 | 완료: Supabase 인증, 테이블, RLS, 사용자별 저장, 스냅샷 구조 |
| 4 | 완료: KIS 토큰 관리, 국내·해외 잔고와 시세, 읽기 전용 실계좌 연동 |
| 5 | OpenAI 리포트, 접근성·성능 개선, 배포 준비 |

## 문서

- [아키텍처](docs/architecture.md)
- [API 명세](docs/api-spec.md)
- [디자인 시스템](docs/design-system.md)
- [KIS 연동](docs/kis-integration.md)
- [실습 기록: 2026-11-02 KIS 실계좌 연동](docs/dev-log/2026-11-02-phase4.md)
- [실습 기록: 2026-11-06 사용자별 KIS 키와 초대](docs/dev-log/2026-11-06-multi-user-kis.md)
