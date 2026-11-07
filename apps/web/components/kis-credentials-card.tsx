"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { KeyRound, ShieldCheck, Trash2 } from "lucide-react";
import { type FormEvent, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { Card } from "@/components/card";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { SimulationError } from "@/components/simulator/sim-ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useKisCredentials } from "@/hooks/use-account";
import { useSource } from "@/hooks/use-source";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { KisCredentialsStatus } from "@/types/user";

const LIVE_QUERY_KEYS = ["portfolio", "history", "risk"];

/**
 * 본인 한국투자증권 키 등록. 입력값은 서버로 한 번 보내고 화면 상태에서 바로 지운다.
 * 브라우저 저장소에는 남기지 않는다. 서버는 등록 여부와 가린 계좌번호만 돌려준다.
 */
export function KisCredentialsCard() {
  const { session } = useAuth();
  const userId = session?.user.id ?? null;
  const status = useKisCredentials();
  const queryClient = useQueryClient();
  const { setSource } = useSource();
  const [appKey, setAppKey] = useState("");
  const [appSecret, setAppSecret] = useState("");
  const [accountNo, setAccountNo] = useState("");
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const refreshLive = (next: KisCredentialsStatus) => {
    queryClient.setQueryData(["kis-credentials", userId], next);
    queryClient.invalidateQueries({
      predicate: (q) => LIVE_QUERY_KEYS.includes(String(q.queryKey[0])) && q.queryKey[1] === "live",
    });
  };

  const save = useMutation({
    mutationFn: () =>
      api.putKisCredentials({ app_key: appKey, app_secret: appSecret, account_no: accountNo }),
    onSuccess: (next) => {
      setAppKey("");
      setAppSecret("");
      setAccountNo("");
      setEditing(false);
      refreshLive(next);
      // 키를 등록하면 바로 실제 계좌를 보여 준다.
      setSource("live");
    },
  });
  const remove = useMutation({
    mutationFn: () => api.deleteKisCredentials(),
    onSuccess: () => {
      refreshLive({ registered: false, account_masked: null, updated_at: null });
      setSource("mock");
    },
  });

  if (!session) return null;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate();
  };
  const registered = status.data?.registered ?? false;
  const showForm = status.data && (!registered || editing);

  return (
    <div id="kis" className="min-w-0 scroll-mt-20">
      <Card title="내 한국투자증권 연결" className="h-full">
        {status.isPending && <Skeleton className="h-28 rounded-xl" />}
        {status.isError && <SimulationError error={status.error} />}

        {status.data && registered && !editing && (
          <div className="space-y-4 text-sm">
            <div className="flex items-start gap-3 rounded-xl bg-secondary/60 p-3.5">
              <ShieldCheck className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
              <div>
                <p className="font-medium">
                  계좌 <span className="num">{status.data.account_masked}</span> 연결됨
                </p>
                {status.data.updated_at && (
                  <p className="text-[13px] text-subtle">
                    등록 {formatDateTime(status.data.updated_at)}
                  </p>
                )}
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                onClick={() => setEditing(true)}
                className="h-10 rounded-full px-4"
              >
                <KeyRound aria-hidden="true" />키 다시 등록
              </Button>
              <Button
                variant="outline"
                onClick={() => setConfirmDelete(true)}
                disabled={remove.isPending}
                className="h-10 rounded-full px-4"
              >
                <Trash2 aria-hidden="true" />
                연결 해제
              </Button>
            </div>
            <SimulationError error={remove.error} />
          </div>
        )}

        {showForm && (
          <form onSubmit={submit} className="space-y-3 text-sm" autoComplete="off">
            <p className="text-[13px] text-subtle">
              KIS Developers에서 발급받은 실전투자 App Key·App Secret과 계좌번호를 입력하세요.
              등록할 때 잔고를 한 번 조회해 맞는지 확인합니다. 접근 토큰을 발급하므로 카카오톡
              알림이 갈 수 있습니다.
            </p>
            <label className="block space-y-1.5">
              <span className="font-medium">App Key</span>
              <Input
                value={appKey}
                onChange={(e) => setAppKey(e.target.value)}
                required
                spellCheck={false}
                autoCapitalize="off"
                autoComplete="off"
                className="h-11 rounded-xl font-mono text-base md:text-sm"
              />
            </label>
            <label className="block space-y-1.5">
              <span className="font-medium">App Secret</span>
              <Input
                type="password"
                value={appSecret}
                onChange={(e) => setAppSecret(e.target.value)}
                required
                spellCheck={false}
                autoComplete="new-password"
                className="h-11 rounded-xl font-mono text-base md:text-sm"
              />
            </label>
            <label className="block space-y-1.5">
              <span className="font-medium">계좌번호</span>
              <Input
                value={accountNo}
                onChange={(e) => setAccountNo(e.target.value)}
                required
                inputMode="numeric"
                placeholder="12345678-01"
                autoComplete="off"
                className="h-11 rounded-xl text-base md:text-sm"
              />
            </label>
            <div className="rounded-xl bg-secondary/60 p-3.5 text-[13px] text-subtle">
              키는 서버에서 암호화해 저장하고, 이 앱은 잔고 조회만 합니다(주문 기능 없음). 다만 App
              Key는 증권사 기준으로 주문 권한도 있는 키이고, 서버 운영자는 기술적으로 복호화할 수
              있습니다. 믿을 수 있는 운영자일 때만 등록하세요. 연결 해제하면 저장된 키가 바로
              삭제됩니다.
            </div>
            <div className="flex flex-wrap gap-2">
              <Button type="submit" disabled={save.isPending} className="h-11 rounded-full px-5">
                {save.isPending ? "확인 중…" : "확인 후 등록"}
              </Button>
              {registered && (
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setEditing(false);
                    save.reset();
                  }}
                  className="h-11 rounded-full px-5"
                >
                  취소
                </Button>
              )}
            </div>
            <SimulationError error={save.error} />
          </form>
        )}
      </Card>
      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title="한국투자증권 연결을 해제할까요?"
        description="저장된 App Key·Secret·계좌번호와 접근 토큰을 서버에서 삭제합니다. 저장해 둔 스냅샷과 기록은 남습니다."
        confirmLabel="연결 해제"
        onConfirm={() => remove.mutate()}
      />
    </div>
  );
}
