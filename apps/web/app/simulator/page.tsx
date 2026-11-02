import { FlaskConical } from "lucide-react";

import { Card } from "@/components/card";
import { EmptyState } from "@/components/empty-state";

export const metadata = { title: "시뮬레이터" };

export default function SimulatorPage() {
  return (
    <Card>
      <EmptyState
        icon={FlaskConical}
        title="시뮬레이터는 아직 제공되지 않습니다"
        description="추가 매수, 리밸런싱, 하락 시나리오 계산이 추가될 예정입니다. 결과는 예측이 아니라 가정 기반 계산이며 실제 주문은 실행하지 않습니다."
      />
    </Card>
  );
}
