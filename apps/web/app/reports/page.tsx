import { Sparkles } from "lucide-react";

import { Card } from "@/components/card";
import { EmptyState } from "@/components/empty-state";

export const metadata = { title: "AI 리포트" };

export default function ReportsPage() {
  return (
    <Card>
      <EmptyState
        icon={Sparkles}
        title="AI 리포트는 아직 제공되지 않습니다"
        description="OpenAI 연동과 함께 추가될 예정입니다. 계산은 분석 엔진이 수행하고 AI는 그 결과를 해석합니다. 수익 보장이나 확정적인 주가 예측은 제공하지 않습니다."
      />
    </Card>
  );
}
