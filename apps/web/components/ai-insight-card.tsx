import { Sparkles } from "lucide-react";

import { Card } from "@/components/card";
import { EmptyState } from "@/components/empty-state";

/** AI 분석은 Phase 5에서 연결한다. 그 전에는 인사이트처럼 보이는 문구를 만들지 않는다. */
export function AIInsightCard({ className }: { className?: string }) {
  return (
    <Card title="AI 투자 인사이트" className={className}>
      <EmptyState
        icon={Sparkles}
        title="아직 AI 분석이 연결되지 않았습니다"
        description="OpenAI 연동 후 계산된 포트폴리오 지표를 바탕으로 요약과 검토 항목을 보여 드립니다."
        className="flex-1"
      />
    </Card>
  );
}
