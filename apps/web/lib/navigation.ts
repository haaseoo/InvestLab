import { ChartPie, FlaskConical, LayoutGrid, type LucideIcon, WalletCards } from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  /** 헤더에 표시하는 페이지 제목 */
  title: string;
  icon: LucideIcon;
}

/** 주요 메뉴. 설정은 헤더의 계정 메뉴에서 연다. AI 리포트는 OpenAI 연동(Phase 5) 후 다시 넣는다. */
export const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "홈", title: "내 투자 현황", icon: LayoutGrid },
  { href: "/holdings", label: "보유 종목", title: "보유 종목", icon: WalletCards },
  { href: "/analytics", label: "분석", title: "포트폴리오 분석", icon: ChartPie },
  { href: "/simulator", label: "시뮬레이터", title: "시뮬레이터", icon: FlaskConical },
];

/** 메뉴에는 없지만 헤더 제목이 필요한 화면 */
export const PAGE_TITLES: Record<string, string> = {
  "/settings": "설정",
  "/reports": "AI 리포트",
  "/login": "로그인",
  "/reset-password": "비밀번호 재설정",
};

export function pageTitle(pathname: string): string {
  const item = NAV_ITEMS.find(({ href }) => pathname === href || pathname.startsWith(`${href}/`));
  return item?.title ?? PAGE_TITLES[pathname] ?? "InvestLab";
}
