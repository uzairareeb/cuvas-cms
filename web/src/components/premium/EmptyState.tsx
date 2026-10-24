import type { LucideIcon } from "lucide-react";

// Quiet empty state: icon in a tinted disc, one line of explanation.
// No fake illustration, no dead-end wording.
export default function EmptyState({
  icon: Icon,
  title,
  message,
}: {
  icon: LucideIcon;
  title: string;
  message: string;
}) {
  return (
    <div className="flex flex-col items-center px-4 py-8 text-center">
      <span className="flex h-11 w-11 items-center justify-center rounded-full bg-appbg text-faint ring-1 ring-inset ring-line">
        <Icon className="h-5 w-5" aria-hidden />
      </span>
      <p className="mt-3 text-sm font-medium text-ink">{title}</p>
      <p className="mt-0.5 max-w-xs text-[13px] leading-snug text-faint">
        {message}
      </p>
    </div>
  );
}
