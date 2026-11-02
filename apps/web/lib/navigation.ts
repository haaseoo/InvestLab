import {
  ChartPie,
  FlaskConical,
  LayoutGrid,
  type LucideIcon,
  Settings,
  Sparkles,
  WalletCards,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  /** 헤더에 표시하는 페이지 제목 */
  title: string;
  icon: LucideIcon;
}

export const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "대시보드", title: "내 투자 현황", icon: LayoutGrid },
  { href: "/holdings", label: "보유 종목", title: "보유 종목", icon: WalletCards },
  { href: "/analytics", label: "분석", title: "포트폴리오 분석", icon: ChartPie },
  { href: "/reports", label: "AI 리포트", title: "AI 리포트", icon: Sparkles },
  { href: "/simulator", label: "시뮬레이터", title: "시뮬레이터", icon: FlaskConical },
  { href: "/settings", label: "설정", title: "설정", icon: Settings },
];
