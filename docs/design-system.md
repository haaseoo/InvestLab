# 디자인 시스템

콘셉트는 Light Minimal Fintech Dashboard입니다. 토큰은 `apps/web/app/globals.css`에 있고 모든 화면이 이를 사용합니다.

> 프로젝트 지시에 언급된 수면 추적 앱 이미지는 전달되지 않아, 지시문에 적힌 특징과 색상을 기준으로 구현했습니다.

## 색상

| 토큰 | 값 | 용도 |
| --- | --- | --- |
| `--background` | `#FAFAFA` | 페이지 배경 |
| `--card` | `#FFFFFF` | 카드 |
| `--secondary` | `#F5F5F5` | 보조 면 |
| `--foreground`, `--primary` | `#171717` | 본문, 기본 버튼 |
| `--border` | `#EEEEEE` | 테두리 |
| `--text-secondary` | `#8D949B` | 큰 글자·아이콘·장식 |
| `--text-subtle` | `#697077` | 작은 보조 글자 (추가) |
| `--coral` | `#FF4D6D` | 로고, 아이콘 포인트 |
| `--coral-soft`, `--coral-strong` | `#FFF0F3`, `#C01F45` | 배지·경고의 배경과 글자 (추가) |
| `--up` | `#D92D3A` | 상승 |
| `--down` | `#1B5FC9` | 하락 |

### 스펙과 다른 부분

`#8D949B`는 흰 배경 대비 약 3:1로, 작은 글자의 WCAG AA 기준(4.5:1)에 못 미칩니다. 그래서 큰 글자와 아이콘에만 쓰고 작은 보조 글자에는 `#697077`을 씁니다. `#FF4D6D`도 글자로 쓰기엔 대비가 낮아 아이콘에만 씁니다.

### 상승·하락

국내 관례대로 상승은 빨강, 하락은 파랑입니다. 코랄·차트 파랑과 섞이지 않도록 더 깊은 색을 쓰고, 항상 `▲`/`▼`와 `+`/`-`를 함께 표시합니다. 스크린리더에는 "상승", "하락"을 말로 전달합니다. `PnlText` 컴포넌트를 사용합니다.

## 차트

블루·코랄·퍼플을 중심으로, 보조로 시안과 피치를 씁니다. 색은 순위가 아니라 자산군에 고정합니다(`lib/chart.ts`).

| 순서 | 값 | 자산군 |
| --- | --- | --- |
| 1 | `#348FF5` 블루 | 시장지수 ETF |
| 2 | `#F0647C` 코랄 | 국내 개별주 |
| 3 | `#8048F8` 퍼플 | 해외 개별주 |
| 4 | `#1FA3B8` 시안 | 섹터·테마 ETF |
| 5 | `#E3A14A` 피치 | 기타 자산 |

검증 결과(밝은 배경): 명도, 채도, 색각 이상 구분(인접 최저 ΔE 16.5), 정상 시각 구분을 모두 통과했습니다. 코랄·시안·피치는 배경 대비가 3:1 미만이라 범례에 이름과 수치를 글자로 함께 표시합니다. 블루와 퍼플은 서로 비슷해 순서상 이웃하지 않게 사이에 코랄을 두었습니다.

차트 코랄 `#F0647C`는 상승 색 `#D92D3A`보다 밝은 장식용 색입니다. 상승·하락은 언제나 기호와 부호로도 표시하므로 차트 색과 혼동되지 않습니다.

분류 정보가 없는 묶음(섹터 정보 없음 등)은 회색 빗금 막대로 표시해 실제 분류와 구분합니다.

차트 규칙은 2px 선, 2px 조각 간격, 옅은 격자, 축 하나입니다. 글자는 차트 색이 아닌 텍스트 토큰을 씁니다.

## 타이포그래피

Pretendard Variable v1.3.9(OFL-1.1)를 `next/font/local`로 직접 호스팅합니다. 외부 요청이 없으며 로드 실패 시 Apple SD Gothic Neo, Malgun Gothic, 시스템 글꼴로 대체합니다. 파일이 약 2MB이므로 초기 로딩이 문제가 되면 Phase 5에서 서브셋을 검토합니다.

| 요소 | 크기 |
| --- | --- |
| 페이지 제목 | 24~28px |
| 섹션 제목 | 18px |
| 카드 제목 | 14~15px |
| 본문 | 14~15px |
| 보조 텍스트 | 12~13px |

숫자는 `num` 유틸리티로 고정폭 숫자를 쓰고 오른쪽 정렬합니다.

## 레이아웃

- 데스크톱(768px 이상): 240px 좌측 사이드바, 콘텐츠 최대 1240px
- 모바일(768px 미만): 하단 탭바, 표는 카드 목록으로 전환, 터치 영역 44px 이상
- 360px 미만: 대시보드 지표 카드를 한 열로 배치

## 컴포넌트

| 요구 이름 | 위치 |
| --- | --- |
| AppSidebar (MobileNav 포함) | `components/layout/app-sidebar.tsx` |
| AppHeader | `components/layout/app-header.tsx` |
| StatCard | `components/stat-card.tsx` |
| PortfolioChart | `components/portfolio-chart.tsx` |
| AssetAllocationChart | `components/asset-allocation-chart.tsx` |
| HoldingsTable | `components/holdings-table.tsx` |
| RiskIndicator | `components/risk-indicator.tsx` |
| AIInsightCard (포트폴리오 인사이트) | `components/ai-insight-card.tsx` |
| AllocationBars | `components/allocation-bars.tsx` |
| 시뮬레이터 | `components/simulator/` |
| SourceModeSwitcher | `components/source-mode-switcher.tsx` |
| EmptyState | `components/empty-state.tsx` |
| ErrorState, LoadingSkeleton | `components/state.tsx` |
| ConfirmDialog | `components/confirm-dialog.tsx` |

## EasyUI 검토

[EasyUI](https://easyui.site/components)는 MIT 라이선스이며 애니메이션에 `framer-motion`을 사용합니다. 스펙의 "유지보수가 어려운 불필요한 애니메이션 지양"에 따라 코드와 의존성은 가져오지 않았고, 라벨·값·보조 설명으로 구성하는 Stat Card 방식만 참고했습니다.

## 인사이트 카드

카드 제목은 "포트폴리오 인사이트"이며 "분석 엔진 계산" 배지를 붙입니다. 문장은 분석 엔진이 계산한 수치를 옮긴 것이고 판단·권유·예측 표현을 쓰지 않습니다. 카드 아래에 "AI 해석 준비 중" 상태를 항상 표시해 AI 분석이 실행된 것처럼 보이지 않게 합니다.
