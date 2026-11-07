"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, Database, LogIn, LogOut, Trash2 } from "lucide-react";
import Link from "next/link";

import { useAuth } from "@/components/auth-provider";
import { Card, DemoBadge } from "@/components/card";
import { KisCredentialsCard } from "@/components/kis-credentials-card";
import { ProviderChecklist } from "@/components/query-error";
import { SimulationError } from "@/components/simulator/sim-ui";
import { SourceModeSwitcher } from "@/components/source-mode-switcher";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useKisCredentials,
  useSimulationHistory,
  useSnapshots,
  useUserSettings,
} from "@/hooks/use-account";
import { useProvidersStatus } from "@/hooks/use-portfolio";
import { useSource } from "@/hooks/use-source";
import { api } from "@/lib/api";
import { formatDateTime, formatMoney } from "@/lib/format";
import type { UserSettings } from "@/types/user";

const SIMULATION_LABEL = { buy: "추가 매수", rebalance: "리밸런싱", scenario: "하락 시나리오" };

function AccountCard() {
  const { configured, session, signOut } = useAuth();
  const kis = useKisCredentials();

  return (
    <Card title="계정">
      {!configured ? (
        <p className="text-sm text-subtle">로그인 설정이 없어 계정 기능을 사용할 수 없습니다.</p>
      ) : !session ? (
        <div className="space-y-3">
          <p className="text-sm text-subtle">
            로그인하면 설정과 시뮬레이션 기록을 저장하고, 본인 한국투자증권 키를 등록해 실제 계좌를
            조회할 수 있습니다.
          </p>
          <Link
            href="/login"
            className="inline-flex h-11 items-center gap-1.5 rounded-full bg-primary px-5 text-sm font-medium text-primary-foreground hover:bg-primary/85"
          >
            <LogIn className="size-4" aria-hidden="true" />
            로그인
          </Link>
        </div>
      ) : (
        <div className="space-y-4">
          <dl className="grid gap-3 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-[13px] text-subtle">이메일</dt>
              <dd className="font-medium break-all">{session.user.email}</dd>
            </div>
            <div>
              <dt className="text-[13px] text-subtle">한국투자증권 연결</dt>
              <dd className="font-medium">
                {kis.isPending
                  ? "확인 중"
                  : kis.data?.registered
                    ? `연결됨 (${kis.data.account_masked})`
                    : kis.isError
                      ? "확인하지 못함"
                      : "없음"}
              </dd>
            </div>
          </dl>
          <Button variant="outline" onClick={() => signOut()} className="h-11 rounded-full px-5">
            <LogOut aria-hidden="true" />
            로그아웃
          </Button>
        </div>
      )}
    </Card>
  );
}

function PreferencesCard() {
  const { session } = useAuth();
  const settings = useUserSettings();
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: (next: Omit<UserSettings, "updated_at">) => api.putSettings(next),
    onSuccess: (saved) => {
      queryClient.setQueryData(["user-settings", session?.user.id ?? null], saved);
    },
  });

  if (!session) return null;
  const current = settings.data;
  const save = (patch: Partial<UserSettings>) => {
    if (!current) return;
    mutation.mutate({
      theme: current.theme,
      preferred_currency: current.preferred_currency,
      preferred_source: current.preferred_source,
      mask_account_numbers: current.mask_account_numbers,
      ...patch,
    });
  };

  return (
    <Card title="저장된 설정">
      {settings.isPending && <Skeleton className="h-28 rounded-xl" />}
      {settings.isError && <SimulationError error={settings.error} />}
      {current && (
        <div className="space-y-4 text-sm">
          <label className="flex items-center justify-between gap-3">
            <span>
              <span className="font-medium">계좌번호 마스킹</span>
              <span className="block text-[13px] text-subtle">
                화면에 계좌번호를 표시하게 되면 적용합니다. 서버 로그·응답에서는 항상 가립니다.
              </span>
            </span>
            <input
              type="checkbox"
              checked={current.mask_account_numbers}
              onChange={(e) => save({ mask_account_numbers: e.target.checked })}
              className="size-5 accent-[var(--foreground)]"
            />
          </label>
          <div className="flex items-center justify-between gap-3 text-subtle">
            <span>테마 · 평가 통화</span>
            <span>라이트 · KRW (현재 버전 고정)</span>
          </div>
          {mutation.isPending && <p className="text-xs text-subtle">저장 중…</p>}
          <SimulationError error={mutation.error} />
          {current.updated_at && (
            <p className="text-xs text-subtle">마지막 저장 {formatDateTime(current.updated_at)}</p>
          )}
        </div>
      )}
    </Card>
  );
}

function SnapshotsCard() {
  const { session } = useAuth();
  const kis = useKisCredentials();
  const snapshots = useSnapshots();
  const queryClient = useQueryClient();
  const capture = useMutation({
    mutationFn: () => api.captureSnapshot(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["snapshots"] });
      // 대시보드의 LIVE 총자산 변화 차트는 저장된 스냅샷으로 그린다.
      queryClient.invalidateQueries({ queryKey: ["history", "live"] });
    },
  });

  if (!session) return null;
  return (
    <Card title="자산 기록 저장">
      <p className="mb-3 text-[13px] text-subtle">
        실제 계좌의 평가 결과를 기준 시각과 함께 저장합니다. 2개 이상 쌓이면 홈에 총자산 변화가
        나타납니다.
      </p>
      {snapshots.isPending && <Skeleton className="h-16 rounded-xl" />}
      {snapshots.isError && <SimulationError error={snapshots.error} />}
      {snapshots.data &&
        (snapshots.data.snapshots.length === 0 ? (
          <p className="rounded-xl bg-secondary/60 p-3.5 text-sm text-subtle">
            저장된 실제 스냅샷이 없습니다.
          </p>
        ) : (
          <ul className="divide-y rounded-xl border text-sm">
            {snapshots.data.snapshots.map((s) => (
              <li key={s.id} className="flex justify-between gap-3 px-3.5 py-2.5">
                <span className="num text-subtle">기준 {formatDateTime(s.as_of)}</span>
                <span className="font-semibold num">
                  {formatMoney(s.total_market_value, s.valuation_currency)}
                </span>
              </li>
            ))}
          </ul>
        ))}
      {kis.data?.registered && (
        <div className="mt-3 space-y-2">
          <Button
            variant="outline"
            onClick={() => capture.mutate()}
            disabled={capture.isPending}
            className="h-10 rounded-full px-4"
          >
            <Database aria-hidden="true" />
            지금 스냅샷 저장
          </Button>
          <SimulationError error={capture.error} />
        </div>
      )}
    </Card>
  );
}

function HistoryCard() {
  const { session } = useAuth();
  const history = useSimulationHistory();
  const queryClient = useQueryClient();
  const remove = useMutation({
    mutationFn: (id: string) => api.deleteSimulation(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["simulation-history"] }),
  });

  if (!session) return null;
  return (
    <Card title="시뮬레이션 기록">
      {history.isPending && <Skeleton className="h-16 rounded-xl" />}
      {history.isError && <SimulationError error={history.error} />}
      {history.data &&
        (history.data.items.length === 0 ? (
          <p className="rounded-xl bg-secondary/60 p-3.5 text-sm text-subtle">
            저장한 시뮬레이션이 없습니다. 시뮬레이터에서 결과를 저장할 수 있습니다.
          </p>
        ) : (
          <ul className="divide-y rounded-xl border text-sm">
            {history.data.items.map((item) => (
              <li key={item.id} className="flex items-center gap-3 px-3.5 py-2">
                <span className="min-w-0 flex-1">
                  <span className="font-medium">{SIMULATION_LABEL[item.simulation_type]}</span>
                  <span className="ml-2 text-xs num text-subtle">
                    {formatDateTime(item.created_at)}
                  </span>
                </span>
                {item.is_demo && <DemoBadge />}
                <button
                  type="button"
                  onClick={() => remove.mutate(item.id)}
                  aria-label={`${SIMULATION_LABEL[item.simulation_type]} 기록 삭제`}
                  className="grid size-10 place-items-center rounded-full text-subtle hover:bg-secondary hover:text-foreground"
                >
                  <Trash2 className="size-4" aria-hidden="true" />
                </button>
              </li>
            ))}
          </ul>
        ))}
      <SimulationError error={remove.error} />
    </Card>
  );
}

export default function SettingsPage() {
  const { source } = useSource();
  const status = useProvidersStatus();
  const live = status.data?.providers.find((p) => p.source === "live");

  return (
    <div>
      <div className="grid gap-3 md:gap-4 lg:grid-cols-2">
        <AccountCard />

        <Card title="보기 모드" action={<SourceModeSwitcher />}>
          <p className="text-sm text-subtle">
            {source === "mock"
              ? "체험용 가상 데이터를 보고 있습니다. 한국투자증권 키를 등록하면 실제 계좌로 바뀝니다."
              : "연결된 실제 계좌를 보고 있습니다. 조회에 실패해도 가상 데이터로 대신 채우지 않습니다."}
          </p>
        </Card>

        <KisCredentialsCard />
        <SnapshotsCard />
        <HistoryCard />
      </div>

      <details className="group mt-6">
        <summary className="inline-flex h-10 cursor-pointer list-none items-center gap-1 px-1 text-sm font-semibold text-subtle hover:text-foreground [&::-webkit-details-marker]:hidden">
          고급 설정
          <ChevronDown className="size-4 transition-transform group-open:rotate-180" />
        </summary>
        <div className="mt-2 grid gap-3 md:gap-4 lg:grid-cols-2">
          <PreferencesCard />
          <Card title="서버 연결 상태">
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
        </div>
      </details>
    </div>
  );
}
