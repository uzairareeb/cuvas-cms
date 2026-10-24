import EmptyState from "./EmptyState";
import { BarChart3 } from "lucide-react";

// Premium charts, hand-rolled SVG — no chart library dependency.
// Both render ONLY the rows the API returns; empty data shows an
// honest empty state instead of a fabricated zero chart.

const PALETTE = [
  "#17365D",
  "#2457A7",
  "#3B82C4",
  "#E7B34C",
  "#15803D",
  "#6654A3",
  "#64748B",
  "#B45309",
];

export function DonutChart({
  rows,
  centerLabel,
}: {
  rows: { name: string; count: number }[];
  centerLabel: string;
}) {
  const total = rows.reduce((s, r) => s + r.count, 0);
  if (total === 0) {
    return (
      <EmptyState
        icon={BarChart3}
        title="No data yet"
        message="Distribution will appear here once records exist."
      />
    );
  }
  const R = 15.9155; // circumference ≈ 100, so dash values are percents
  let offset = 25; // start at 12 o'clock
  const segments = rows.map((r, i) => {
    const pct = (r.count / total) * 100;
    const seg = { ...r, pct, offset, color: PALETTE[i % PALETTE.length] };
    offset -= pct;
    return seg;
  });
  return (
    <div className="flex flex-col items-center gap-5 sm:flex-row sm:gap-6">
      <div className="relative shrink-0">
        <svg
          viewBox="0 0 42 42"
          className="h-40 w-40 -rotate-0"
          role="img"
          aria-label={`${centerLabel}: ${total} total`}
        >
          <circle
            cx="21"
            cy="21"
            r={R}
            fill="none"
            stroke="#F4F7FB"
            strokeWidth="5"
          />
          {segments.map((s) => (
            <circle
              key={s.name}
              cx="21"
              cy="21"
              r={R}
              fill="none"
              stroke={s.color}
              strokeWidth="5"
              strokeDasharray={`${Math.max(s.pct - 1.5, 0)} 100`}
              strokeDashoffset={s.offset}
              strokeLinecap="butt"
            >
              <title>{`${s.name}: ${s.count} (${s.pct.toFixed(1)}%)`}</title>
            </circle>
          ))}
        </svg>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-bold tracking-tight text-navy">
            {total.toLocaleString("en-US")}
          </span>
          <span className="text-[11px] font-medium uppercase tracking-wide text-faint">
            {centerLabel}
          </span>
        </div>
      </div>
      <ul className="w-full min-w-0 flex-1 space-y-2">
        {segments.map((s) => (
          <li key={s.name} className="flex items-center gap-2.5 text-sm">
            <span
              className="h-2.5 w-2.5 shrink-0 rounded-[3px]"
              style={{ backgroundColor: s.color }}
              aria-hidden
            />
            <span className="min-w-0 flex-1 truncate text-ink">{s.name}</span>
            <span className="shrink-0 font-semibold text-navy">
              {s.count.toLocaleString("en-US")}
            </span>
            <span className="w-12 shrink-0 text-right text-xs text-faint">
              {s.pct.toFixed(1)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function GradientBars({
  rows,
}: {
  rows: { name: string; count: number }[];
}) {
  const max = Math.max(1, ...rows.map((r) => r.count));
  const total = rows.reduce((s, r) => s + r.count, 0);
  if (rows.length === 0 || total === 0) {
    return (
      <EmptyState
        icon={BarChart3}
        title="No data yet"
        message="Breakdown will appear here once records exist."
      />
    );
  }
  return (
    <ul className="space-y-3.5">
      {rows.map((r, i) => {
        const pct = (r.count / max) * 100;
        const share = (r.count / total) * 100;
        return (
          <li key={r.name} className="text-sm">
            <div className="mb-1.5 flex items-baseline justify-between gap-3">
              <span className="min-w-0 truncate font-medium text-ink">
                {r.name}
              </span>
              <span className="shrink-0">
                <span className="font-semibold text-navy">
                  {r.count.toLocaleString("en-US")}
                </span>
                <span className="ml-1.5 text-xs text-faint">
                  {share.toFixed(1)}%
                </span>
              </span>
            </div>
            <div
              className="h-2.5 overflow-hidden rounded-full bg-appbg ring-1 ring-inset ring-line/60"
              role="img"
              aria-label={`${r.name}: ${r.count}`}
            >
              <div
                className="h-full rounded-full transition-[width] duration-300"
                style={{
                  width: `${Math.max(3, pct)}%`,
                  background: `linear-gradient(90deg, #2457A7, ${
                    i % 2 === 0 ? "#17365D" : "#3B82C4"
                  })`,
                }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
