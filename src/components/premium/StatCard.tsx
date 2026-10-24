import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

// KPI card: tinted icon tile, large figure, label and one honest
// descriptor line (never a computed-looking fake trend — the API
// gives no deltas, so no deltas are shown).
const TONES: Record<string, string> = {
  navy: "bg-navy/10 text-navy ring-navy/15",
  blue: "bg-brandblue/10 text-brandblue ring-brandblue/15",
  gold: "bg-gold/20 text-navy-deep ring-gold/40",
  green: "bg-success/10 text-success ring-success/15",
};

export default function StatCard({
  label,
  value,
  subtext,
  icon: Icon,
  tone = "navy",
}: {
  label: string;
  value: string;
  subtext: string;
  icon: LucideIcon;
  tone?: keyof typeof TONES;
}) {
  return (
    <div className="group animate-fade-up rounded-2xl border border-line bg-surface p-5 shadow-card transition-all duration-200 hover:-translate-y-0.5 hover:shadow-card-hover">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-[13px] font-medium uppercase tracking-wide text-faint">
            {label}
          </p>
          <p className="mt-1.5 truncate text-[28px] font-bold leading-8 tracking-tight text-navy">
            {value}
          </p>
          <p className="mt-1 truncate text-[13px] text-faint">{subtext}</p>
        </div>
        <span
          className={cn(
            "flex h-12 w-12 shrink-0 items-center justify-center rounded-xl ring-1 ring-inset transition-transform duration-200 group-hover:scale-105",
            TONES[tone]
          )}
        >
          <Icon className="h-5 w-5" aria-hidden />
        </span>
      </div>
    </div>
  );
}
