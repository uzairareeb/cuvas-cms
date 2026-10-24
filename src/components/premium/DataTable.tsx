import type { ReactNode } from "react";

import { cn } from "@/lib/utils";
import EmptyState from "./EmptyState";
import { Inbox } from "lucide-react";

// Clean premium table: small-caps muted header, hairline rows with
// hover wash, generous cell padding. Reused by every list slice.
export interface DataColumn {
  label: string;
  align?: "left" | "right";
  className?: string;
}

export default function DataTable({
  columns,
  rows,
  emptyMessage,
}: {
  columns: DataColumn[];
  rows: ReactNode[][];
  emptyMessage: string;
}) {
  if (rows.length === 0) {
    return (
      <EmptyState icon={Inbox} title="Nothing here yet" message={emptyMessage} />
    );
  }
  return (
    <div className="-mx-5 overflow-x-auto px-5 sm:-mx-6 sm:px-6">
      <table className="w-full min-w-[480px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-line">
            {columns.map((c, i) => (
              <th
                key={i}
                scope="col"
                className={cn(
                  "whitespace-nowrap px-3 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-faint first:pl-0 last:pr-0",
                  c.align === "right" && "text-right",
                  c.className
                )}
              >
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr
              key={ri}
              className="border-b border-line/70 transition-colors last:border-0 hover:bg-appbg/70"
            >
              {row.map((cell, ci) => (
                <td
                  key={ci}
                  className={cn(
                    "px-3 py-3 align-top text-ink first:pl-0 last:pr-0",
                    columns[ci]?.align === "right" && "text-right"
                  )}
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
