"use client";

import { Assumptions, DataProvenanceBar } from "@/components/data-provenance";
import { HoldingsTable } from "@/components/holdings-table";
import { QueryError } from "@/components/query-error";
import { LoadingSkeleton } from "@/components/state";
import { usePortfolio } from "@/hooks/use-portfolio";

export default function HoldingsPage() {
  const portfolio = usePortfolio();

  if (portfolio.isPending) return <LoadingSkeleton variant="table" />;
  if (portfolio.isError) {
    return <QueryError error={portfolio.error} onRetry={() => portfolio.refetch()} />;
  }

  return (
    <div>
      <DataProvenanceBar portfolio={portfolio.data} isFetching={portfolio.isFetching} />
      <HoldingsTable holdings={portfolio.data.holdings} />
      <Assumptions items={portfolio.data.assumptions} />
    </div>
  );
}
