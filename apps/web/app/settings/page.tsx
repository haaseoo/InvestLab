"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Database, LogIn, LogOut, Trash2 } from "lucide-react";
import Link from "next/link";

import { useAuth } from "@/components/auth-provider";
import { Card, DemoBadge } from "@/components/card";
import { ProviderChecklist } from "@/components/query-error";
import { SimulationError } from "@/components/simulator/sim-ui";
import { SourceModeSwitcher } from "@/components/source-mode-switcher";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useMe, useSimulationHistory, useSnapshots, useUserSettings } from "@/hooks/use-account";
import { useProvidersStatus } from "@/hooks/use-portfolio";
import { useSource } from "@/hooks/use-source";
import { api } from "@/lib/api";
import { formatDateTime, formatMoney } from "@/lib/format";
import type { Source } from "@/types/portfolio";
import type { UserSettings } from "@/types/user";

const SIMULATION_LABEL = { buy: "추가 매수", rebalance: "리밸런싱", scenario: "하락 시나리오" };

function AccountCard() {
  const { configured, session, signOut } = useAuth();
  const me = useMe();

  return (
    <Card title="계정">
      {!configured ? (
        <p className="text-sm text-subtle">로그인 설정이 없어 계정 기능을 사용할 수 없습니다.</p>
      ) : !session ? (
        <div className="space-y-3">
          <p className="text-sm text-subtle">
            로그인하면 설정과 시뮬레이션 기록을 저장하고, 소유자 계정은 LIVE 데이터를 조회할 수
            있습니다.
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
              <dt className="text-[13px] text-subtle">LIVE 조회 권한</dt>
              <dd className="font-medium">
                {me.isPending ? "확인 중" : me.data?.is_live_owner ? "있음 (계좌 소유자)" : "없음"}
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
  const { setSource } = useSource();
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
              <span className="font-medium">로그인 시 기본 데이터 모드</span>
              <span className="block text-[13px] text-subtle">
                로그인할 때 이 모드로 전환합니다.
              </span>
            </span>
            <select
              value={current.preferred_source}
              onChange={(e) => {
                const next = e.target.value as Source;
                save({ preferred_source: next });
                setSource(next);
              }}
              className="h-11 rounded-xl border bg-card px-3 text-base md:text-sm"
            >
              <option value="mock">MOCK</option>
              <option value="live">LIVE</option>
            </select>
          </label>
          <label className="flex items-center justify-between gap-3">
            <span>
              <span className="font-medium">계좌번호 마스킹</span>
              <span className="block text-[13px] text-subtle">
                KIS 연결 후 계좌번호를 표시할 때 적용합니다.
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
  const me = useMe();
  const snapshots = useSnapshots();
  const queryClient = useQueryClient();
  const capture = useMutation({
    mutationFn: () => api.captureSnapshot(),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["snapshots"] }),
  });

  if (!session) return null;
  return (
    <Card title="실제 계좌 스냅샷">
      <p className="mb-3 text-[13px] text-subtle">
        LIVE 계좌의 평가 결과를 기준 시각과 함께 저장합니다. Mock 데이터는 저장하지 않습니다.
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
      {me.data?.is_live_owner && (
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
    <div className="grid gap-3 md:gap-4 lg:grid-cols-2">
      <AccountCard />

      <Card title="데이터 모드" action={<SourceModeSwitcher />}>
        <p className="text-sm text-subtle">
          {source === "mock"
            ? "현재 MOCK 모드입니다. 시연용 가상 데이터를 표시합니다."
            : "현재 LIVE 모드입니다. 연결된 실제 계좌만 조회하며 가상 데이터로 대체하지 않습니다."}
        </p>
      </Card>

      <PreferencesCard />

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

      <SnapshotsCard />
      <HistoryCard />
    </div>
  );
}
