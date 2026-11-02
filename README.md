# InvestLab

주식·ETF 보유 자산을 분석하는 개인 투자 포트폴리오 웹서비스입니다. 조회 전용이며 매수·매도 주문이나 자동매매 기능은 없습니다. 투자 자문이 아닙니다.

현재 상태는 **Phase 1**입니다. Mock 데이터로 전체 흐름이 동작하며, 실제 계좌·Supabase·AI는 아직 연결되어 있지 않습니다.

## 기술 스택

| 영역 | 사용 기술 |
| --- | --- |
| Frontend | Next.js 16 (App Router), TypeScript, Tailwind CSS 4, shadcn/ui, Recharts, TanStack Query, Lucide, Pretendard |
| Backend | Python 3.11+, FastAPI, Pydantic v2, httpx, pytest, Ruff |
| 예정 | Supabase (Phase 3), 한국투자증권 Open API (Phase 4), OpenAI API (Phase 5) |

SQLAlchemy와 Alembic은 DB를 연결하는 Phase 3에서 추가합니다.

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

## LIVE 모드

화면에서 LIVE를 선택할 수 있지만 **현재는 실제 계좌가 연결되지 않으며**, 연결 준비 상태와 오류를 안내합니다. 오류가 나도 Mock 데이터로 대체하지 않습니다. `source=live` 요청은 토큰 검증과 계좌 소유자 확인을 모두 통과해야 하며, 토큰 검증기가 없는 지금은 모두 거부됩니다.

## 환경변수

Mock 모드에는 필요 없습니다. 값을 바꾸려면 `cp .env.example .env`로 복사합니다. 웹의 API 주소는 `apps/web/.env.local`의 `NEXT_PUBLIC_API_BASE_URL`로 지정합니다(기본값 `http://localhost:8000`). `NEXT_PUBLIC_` 변수는 브라우저에 노출되므로 비밀 값을 넣지 않습니다.

## Supabase 연결 방법 (Phase 3 예정)

1. Supabase Dashboard에서 프로젝트를 직접 생성합니다. 조직 주소만으로는 연결할 수 없으므로 프로젝트 정보가 필요합니다.
2. 프로젝트 URL과 키를 `.env`에 넣습니다. Service Role·Secret Key는 서버에만 둡니다.
3. `supabase/migrations/`의 마이그레이션을 적용합니다(Phase 3에서 작성).

## KIS 연결 준비사항 (Phase 4 예정)

1. [KIS Developers](https://apiportal.koreainvestment.com/)에서 Open API를 신청하고 App Key·Secret을 발급받습니다.
2. `.env`에 `KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCOUNT_NO`를 넣습니다.
3. `LIVE_OWNER_USER_ID`에 본인의 Supabase 사용자 id를 넣습니다.

엔드포인트와 TR ID는 [docs/kis-integration.md](docs/kis-integration.md)에 있습니다.

## 테스트

```bash
cd apps/api && .venv/bin/pytest && .venv/bin/ruff check . && .venv/bin/ruff format --check .
cd apps/web && npx tsc --noEmit && npm run lint && npx prettier --check . && npm run build
```

## 현재 구현 기능

- 대시보드: 총 평가자산, 원금, 평가손익, 수익률, 종목 수, 자산 구성, 종목별 평가금액, 가상 이력 차트, 기준·조회 시각
- 보유 종목: 검색, 정렬, 원화 환산/거래 통화 전환, 모바일 카드 보기
- 분석: 상위 종목 집중도, 자산군별 비중만 제공
- 설정: 데이터 모드, KIS 연결 준비 상태만 제공
- API: `/health`, `/providers/status`, `/portfolio`, `/portfolio/holdings`, `/portfolio/summary`, `/portfolio/history`, `/analytics/allocation`
- 시세·환율 누락 처리, LIVE 접근 차단, CORS 제한, 로그 마스킹

AI 리포트와 시뮬레이터 화면은 안내 문구만 표시합니다.

## 향후 개발 계획

| Phase | 내용 |
| --- | --- |
| 2 | 국가·섹터 분석, ETF 중복 데이터 구조, 추가 매수·리밸런싱·하락 시나리오 계산 |
| 3 | Supabase 인증, 테이블, RLS, 사용자별 저장, 포트폴리오 스냅샷 |
| 4 | KIS 토큰 관리, 국내·해외 잔고와 시세, 읽기 전용 실계좌 연동 |
| 5 | OpenAI 리포트, 시뮬레이터 UI, 접근성·성능 개선, 배포 준비 |

## 문서

- [아키텍처](docs/architecture.md)
- [API 명세](docs/api-spec.md)
- [디자인 시스템](docs/design-system.md)
- [KIS 연동](docs/kis-integration.md)
