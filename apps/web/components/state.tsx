"use client";

import { CircleAlert, RefreshCw } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface ErrorStateProps {
  title: string;
  description?: string;
  code?: string;
  onRetry?: () => void;
  children?: ReactNode;
}

export function ErrorState({ title, description, code, onRetry, children }: ErrorStateProps) {
  return (
    <div
      role="alert"
      className="flex flex-col items-center gap-4 card-surface px-5 py-12 text-center"
    >
      <span className="grid size-12 place-items-center rounded-full bg-coral-soft">
        <CircleAlert className="size-5 text-coral" aria-hidden="true" />
      </span>
      <div className="space-y-1.5">
        <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
        {description && <p className="max-w-lg text-sm text-subtle">{description}</p>}
        {code && <p className="text-xs num text-subtle">오류 코드 {code}</p>}
      </div>
      {children}
      {onRetry && (
        <Button onClick={onRetry} className="h-11 rounded-full px-5">
          <RefreshCw aria-hidden="true" />
          다시 시도
        </Button>
      )}
    </div>
  );
}

export function LoadingSkeleton({ variant = "dashboard" }: { variant?: "dashboard" | "table" }) {
  return (
    <div role="status" aria-label="데이터를 불러오는 중" className="space-y-4">
      {variant === "dashboard" ? (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            {[0, 1, 2, 3, 4].map((i) => (
              <Skeleton
                key={i}
                className={cn("h-28 rounded-2xl", i === 0 && "col-span-2 lg:col-span-1")}
              />
            ))}
          </div>
          <div className="grid gap-4 lg:grid-cols-3">
            <Skeleton className="h-80 rounded-2xl lg:col-span-2" />
            <Skeleton className="h-80 rounded-2xl" />
          </div>
        </>
      ) : (
        <Skeleton className="h-[480px] rounded-2xl" />
      )}
    </div>
  );
}
