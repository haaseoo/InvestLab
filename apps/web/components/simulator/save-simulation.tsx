"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, Save } from "lucide-react";
import Link from "next/link";

import { useAuth } from "@/components/auth-provider";
import { SimulationError } from "@/components/simulator/sim-ui";
import { Button } from "@/components/ui/button";
import { useSource } from "@/hooks/use-source";
import { api } from "@/lib/api";
import type { SimulationType } from "@/types/user";

interface Props {
  type: SimulationType;
  input: object | undefined;
  result: { as_of?: string | null } & object;
}

/** 시뮬레이션 결과 저장. Mock 결과는 DEMO로 표시되어 저장되며 투자 실적이 아니다. */
export function SaveSimulation({ type, input, result }: Props) {
  const { configured, session } = useAuth();
  const { source } = useSource();
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: () =>
      api.saveSimulation({
        simulation_type: type,
        source,
        input: input ?? {},
        result,
        as_of: result.as_of ?? null,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["simulation-history"] }),
  });

  if (!configured) return null;
  if (!session) {
    return (
      <p className="text-[13px] text-subtle">
        <Link href="/login" className="font-medium text-foreground underline underline-offset-2">
          로그인
        </Link>
        하면 이 결과를 기록으로 저장할 수 있습니다.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="outline"
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending || mutation.isSuccess}
          className="h-10 rounded-full px-4"
        >
          {mutation.isSuccess ? <Check aria-hidden="true" /> : <Save aria-hidden="true" />}
          {mutation.isSuccess ? "저장됨" : mutation.isPending ? "저장 중…" : "결과 저장"}
        </Button>
        <span className="text-xs text-subtle">
          {source === "mock"
            ? "DEMO 데이터 기반 결과로 저장됩니다."
            : "LIVE 데이터 기반 결과로 저장됩니다."}
        </span>
      </div>
      <SimulationError error={mutation.error} />
    </div>
  );
}
