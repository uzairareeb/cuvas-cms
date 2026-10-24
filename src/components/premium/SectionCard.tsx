import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

// Premium content card: white surface, soft navy shadow, a title row
// with optional subtitle + trailing action, and a hairline divider
// between header and body. Every dashboard/report section uses this
// so later slices inherit the same look for free.
export default function SectionCard({
  title,
  subtitle,
  action,
  children,
  className,
  bodyClassName,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <section
      className={cn(
        "animate-fade-up overflow-hidden rounded-2xl border border-line bg-surface shadow-card transition-shadow duration-200 hover:shadow-card-hover",
        className
      )}
    >
      <header className="flex flex-wrap items-start justify-between gap-3 px-5 pt-5 sm:px-6">
        <div className="min-w-0">
          <h2 className="text-[15px] font-semibold tracking-tight text-navy">
            {title}
          </h2>
          {subtitle ? (
            <p className="mt-0.5 text-[13px] leading-snug text-faint">
              {subtitle}
            </p>
          ) : null}
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </header>
      <div className={cn("px-5 py-5 sm:px-6", bodyClassName)}>{children}</div>
    </section>
  );
}
