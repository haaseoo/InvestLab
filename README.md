# InvestLab

주식·ETF 보유 자산을 분석하는 개인 투자 포트폴리오 웹서비스입니다. 조회 전용이며 매수·매도 주문이나 자동매매 기능은 없습니다. 투자 자문이 아닙니다.

현재 상태는 **Phase 3**입니다. Mock 데이터로 전체 흐름·분석 엔진·시뮬레이터가 동작하고, Supabase 로그인과 사용자별 데이터 저장(RLS)이 연결되어 있습니다. 한국투자증권(실제 계좌)과 AI는 아직 연결되지 않았습니다.

## 기술 스택

| 영역 | 사용 기술 |
| --- | --- |
| Frontend | Next.js 16 (App Router), TypeScript, Tailwind CSS 4, shadcn/ui, Recharts, TanStack Query, Lucide, Pretendard |
| Backend | Python 3.11+, FastAPI, Pydantic v2, httpx, pytest, Ruff |
| DB·인증 | Supabase PostgreSQL·Auth, SQLAlchemy 2 + psycopg 3, PyJWT(JWKS 검증), @supabase/supabase-js |
| 예정 | 한국투자증권 Open API (Phase 4), OpenAI API (Phase 5) |

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

LIVE 데이터는 **로그인한 계좌 소유자(`LIVE_OWNER_USER_ID`)만** 요청할 수 있습니다. 서버는 Supabase 토큰의 서명·만료·발급자·대상·역할을 검증한 뒤 소유자와 비교합니다. 현재는 한국투자증권이 연결되지 않아 소유자가 로그인해도 "실제 계좌 미연결"로 표시되며, Mock 데이터로 대체하지 않습니다.

- 로그인: 화면 오른쪽 위 **로그인** → 이메일·비밀번호. 신규 가입은 받지 않습니다.
- 로그인하면 설정(기본 데이터 모드, 계좌번호 마스킹)과 시뮬레이션 결과를 저장할 수 있습니다.
- Mock 모드는 로그인 없이 동작하며 항상 DEMO로 표시됩니다.

## 환경변수

Mock 모드에는 필요 없습니다. 값을 바꾸려면 `cp .env.example .env`로 복사합니다. 웹의 API 주소는 `apps/web/.env.local`의 `NEXT_PUBLIC_API_BASE_URL`로 지정합니다(기본값 `http://localhost:8000`). `NEXT_PUBLIC_` 변수는 브라우저에 노출되므로 비밀 값을 넣지 않습니다.

## Supabase 연결

1. Supabase 프로젝트를 만들고 Authentication에서 본인 계정을 추가한 뒤 **신규 가입을 끕니다.**
2. 루트 `.env`에 `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `DATABASE_URL`(Session pooler), `LIVE_OWNER_USER_ID`를 넣습니다.
3. `apps/web/.env.local`에 `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`를 넣습니다.
4. 마이그레이션을 검증(롤백)한 뒤 적용합니다.

```bash
cd apps/api
.venv/bin/python scripts/migrate.py status   # 적용 현황
.venv/bin/python scripts/migrate.py check    # 트랜잭션에서 실행 후 롤백
.venv/bin/python scripts/migrate.py apply    # 적용
```

Service Role·Secret Key는 쓰지 않습니다. 서버는 사용자 요청마다 트랜잭션 안에서 `authenticated` 역할로 전환해 RLS를 그대로 적용받습니다.

## KIS 연결 준비사항 (Phase 4 예정)

1. [KIS Developers](https://apiportal.koreainvestment.com/)에서 Open API를 신청하고 App Key·Secret을 발급받습니다.
2. `.env`에 `KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCOUNT_NO`를 넣습니다.
3. `LIVE_OWNER_USER_ID`에 본인의 Supabase 사용자 id를 넣습니다.

엔드포인트와 TR ID는 [docs/kis-integration.md](docs/kis-integration.md)에 있습니다.

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
- 설정: 데이터 모드, KIS 연결 준비 상태만 제공
- API: `/health`, `/providers/status`, `/portfolio`, `/portfolio/holdings`, `/portfolio/summary`, `/portfolio/history`, `/analytics/allocation`, `/analytics/risk`, `/simulations/buy`, `/simulations/rebalance`, `/simulations/scenario`
- 시세·환율 누락 처리, LIVE 접근 차단, CORS 제한, 로그 마스킹

- 로그인·로그아웃, 소유자 전용 LIVE 인가, 사용자 설정·시뮬레이션 기록 저장, 실제 계좌 스냅샷 저장 구조

AI 리포트 화면은 안내 문구만 표시합니다. 실제 계좌 스냅샷은 KIS 연결 전이라 저장되지 않습니다.

`integration` 표시가 붙은 테스트는 실제 Supabase에 접속합니다. DB 테스트는 하나의 트랜잭션 안에서 실행 후 롤백하므로 데이터를 남기지 않습니다. 소유자 계정의 실제 로그인 성공은 비밀번호가 필요해 자동 테스트하지 않으며 직접 확인해야 합니다.

## 향후 개발 계획

| Phase | 내용 |
| --- | --- |
| 2 | 완료: 분석 엔진과 시뮬레이터 |
| 3 | 완료: Supabase 인증, 테이블, RLS, 사용자별 저장, 스냅샷 구조 |
| 4 | KIS 토큰 관리, 국내·해외 잔고와 시세, 읽기 전용 실계좌 연동 |
| 5 | OpenAI 리포트, 접근성·성능 개선, 배포 준비 |

## 문서

- [아키텍처](docs/architecture.md)
- [API 명세](docs/api-spec.md)
- [디자인 시스템](docs/design-system.md)
- [KIS 연동](docs/kis-integration.md)
