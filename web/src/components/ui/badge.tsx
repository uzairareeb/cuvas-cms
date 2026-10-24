import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

// Small status/count pill. Tones map to meaning, not decoration:
// gold = needs attention, success = done/paid, warning = pending,
// error = failed/overdue, muted = neutral/empty.
const badgeVariants = cva(
  "inline-flex shrink-0 items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold leading-5 transition-colors",
  {
    variants: {
      variant: {
        gold: "bg-gold/20 text-navy-deep ring-1 ring-inset ring-gold/50",
        navy: "bg-navy text-white",
        blue: "bg-brandblue/10 text-brandblue ring-1 ring-inset ring-brandblue/25",
        success:
          "bg-success/10 text-success ring-1 ring-inset ring-success/25",
        warning:
          "bg-warning/10 text-warning ring-1 ring-inset ring-warning/25",
        error: "bg-error/10 text-error ring-1 ring-inset ring-error/25",
        muted: "bg-appbg text-faint ring-1 ring-inset ring-line",
      },
    },
    defaultVariants: {
      variant: "muted",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
