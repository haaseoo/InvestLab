"use client";

import { Card } from "@/components/card";
import { ProviderChecklist } from "@/components/query-error";
import { SourceModeSwitcher } from "@/components/source-mode-switcher";
import { Skeleton } from "@/components/ui/skeleton";
import { useProvidersStatus } from "@/hooks/use-portfolio";
import { useSource } from "@/hooks/use-source";

const PLANNED = ["사용자 프로필", "테마 설정", "계좌정보 마스킹 표시", "데이터 관리"];

export default function SettingsPage() {
  const { source } = useSource();
  const status = useProvidersStatus();
  const live = status.data?.providers.find((p) => p.source === "live");

  return (
    <div className="grid gap-3 md:gap-4 lg:grid-cols-2">
      <Card title="데이터 모드" action={<SourceModeSwitcher />}>
        <p className="text-sm text-subtle">
          {source === "mock"
            ? "현재 MOCK 모드입니다. 시연용 가상 데이터를 표시합니다."
            : "현재 LIVE 모드입니다. 연결된 실제 계좌만 조회하며 가상 데이터로 대체하지 않습니다."}
        </p>
      </Card>

      <Card title="한국투자증권 연결 상태">
        {status.isPending && <Skeleton className="h-32 rounded-xl" />}
        {status.isError && (
          <p role="alert" className="text-sm text-coral-strong">
            상태를 확인하지 못했습니다. API 서버 실행 여부를 확인해 주세요.
          </p>
        )}
        {live && (
          <div className="space-y-4">
            <p className="text-sm text-subtle">{live.message}</p>
            <ProviderChecklist checks={live.checks} />
          </div>
        )}
      </Card>

      <Card title="준비 중인 설정" className="lg:col-span-2">
        <p className="mb-2 text-sm text-subtle">
          아래 항목은 아직 동작하지 않으며 Supabase 연동 이후 제공합니다.
        </p>
        <ul className="list-disc space-y-1 pl-4 text-sm text-subtle">
          {PLANNED.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
