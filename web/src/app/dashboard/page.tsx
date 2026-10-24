"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Bell,
  BookOpen,
  ClipboardList,
  DatabaseBackup,
  FileText,
  GraduationCap,
  LayoutDashboard,
  Newspaper,
  ReceiptText,
  ScrollText,
  ShieldCheck,
  Sparkles,
  TicketCheck,
  Trophy,
  Users,
  Wallet,
  type LucideIcon,
} from "lucide-react";

import {
  adminDashboard,
  ApiError,
  me,
  type ApiUser,
  type DashboardData,
} from "@/lib/api";
import Shell from "@/components/shell/Shell";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import SectionCard from "@/components/premium/SectionCard";
import StatCard from "@/components/premium/StatCard";
import DataTable from "@/components/premium/DataTable";
import EmptyState from "@/components/premium/EmptyState";
import { DonutChart, GradientBars } from "@/components/premium/Charts";

function fmtRs(n: number) {
  return "Rs " + n.toLocaleString("en-US");
}

function fmtDate(s: string | null) {
  if (!s) return "";
  const d = new Date(s.replace(" ", "T"));
  return Number.isNaN(d.getTime()) ? s : d.toLocaleString();
}

// Status words come from the API verbatim; the tone mapping only
// colours them — unknown statuses fall back to a neutral pill.
function statusBadge(status: string | null) {
  const s = (status ?? "").toLowerCase();
  if (!status) return <Badge variant="muted">—</Badge>;
  if (/(paid|verified|approved|passed|active|clear)/.test(s))
    return <Badge variant="success">{status}</Badge>;
  if (/(pending|submitted|proof|waiting|review)/.test(s))
    return <Badge variant="warning">{status}</Badge>;
  if (/(reject|fail|cancel|expir|overdue)/.test(s))
    return <Badge variant="error">{status}</Badge>;
  return <Badge variant="muted">{status}</Badge>;
}

const APPROVAL_ICONS: Record<string, LucideIcon> = {
  voucher: ReceiptText,
  document: FileText,
  ticket: Newspaper,
  clearance: ShieldCheck,
  scholarship: Sparkles,
  society: Users,
  vehicle: TicketCheck,
  repeat: BookOpen,
};

function approvalIcon(key: string): LucideIcon {
  for (const [k, icon] of Object.entries(APPROVAL_ICONS)) {
    if (key.toLowerCase().includes(k)) return icon;
  }
  return FileText;
}

function Skeleton() {
  return (
    <div className="space-y-6" aria-label="Loading dashboard">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="skeleton-shimmer h-[118px] rounded-2xl" />
        ))}
      </div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <div className="skeleton-shimmer h-72 rounded-2xl" />
        <div className="skeleton-shimmer h-72 rounded-2xl" />
      </div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="skeleton-shimmer h-64 rounded-2xl" />
        ))}
      </div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <div className="skeleton-shimmer h-72 rounded-2xl" />
        <div className="skeleton-shimmer h-72 rounded-2xl" />
      </div>
      <div className="skeleton-shimmer h-56 rounded-2xl" />
    </div>
  );
}

const QUICK_LINKS: { label: string; href: string; icon: LucideIcon }[] = [
  { label: "Students", href: "/admin/students", icon: GraduationCap },
  { label: "Vouchers", href: "/admin/vouchers", icon: ReceiptText },
  { label: "Results", href: "/admin/results", icon: Trophy },
  { label: "Clearance", href: "/admin/clearance", icon: ShieldCheck },
  { label: "Scholarships", href: "/admin/scholarships", icon: Sparkles },
  { label: "Reports", href: "/admin/reports", icon: ScrollText },
  { label: "Audit Log", href: "/admin/audit", icon: ClipboardList },
  { label: "Backup", href: "/admin/backup", icon: DatabaseBackup },
  { label: "Legacy Admin Home", href: "/admin", icon: LayoutDashboard },
];

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<ApiUser | null>(null);
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  const load = useCallback(async () => {
    setError(null);
    try {
      const info = await me();
      if (info.user.role !== "admin") {
        // The Next dashboard is admin-only in this slice; other roles
        // keep their legacy home (served through the proxy).
        window.location.href = info.home;
        return;
      }
      setUser(info.user);
      setData(await adminDashboard());
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.replace("/login");
        return;
      }
      setError(
        err instanceof ApiError
          ? err.message
          : "Could not load the dashboard. Please try again."
      );
    }
  }, [router]);

  useEffect(() => {
    load();
  }, [load, attempt]);

  if (!user && !error) {
    return (
      <div className="min-h-screen bg-appbg px-4 py-6 sm:px-6">
        <div className="mx-auto w-full max-w-[1280px]">
          <Skeleton />
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-appbg px-4">
        <Card className="w-full max-w-md rounded-2xl shadow-card">
          <CardHeader>
            <CardTitle className="text-navy">Dashboard unavailable</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-error">{error}</p>
            <Button onClick={() => setAttempt((a) => a + 1)}>Retry</Button>
          </CardContent>
        </Card>
      </main>
    );
  }

  const totalWaiting = data
    ? data.pending_approvals.reduce((s, q) => s + q.count, 0)
    : 0;

  return (
    <Shell user={user} title="Admin Dashboard">
      {!data ? (
        <Skeleton />
      ) : (
        <div className="space-y-6">
          {error ? (
            <p
              role="alert"
              className="rounded-xl border border-error/40 bg-error/5 px-4 py-3 text-sm text-error"
            >
              {error}{" "}
              <button
                type="button"
                className="font-medium underline"
                onClick={() => setAttempt((a) => a + 1)}
              >
                Retry
              </button>
            </p>
          ) : null}

          {/* Page intro — live-data marker is honest: every figure below
              is rendered from the /api/v1/admin/dashboard response. */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-faint">
              Live snapshot of university operations — students, fees,
              approvals and recent activity.
            </p>
            <span className="inline-flex items-center gap-2 rounded-full bg-success/10 px-3 py-1 text-xs font-semibold text-success ring-1 ring-inset ring-success/25">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-60" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-success" />
              </span>
              Live data
            </span>
          </div>

          <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="Total Students"
              value={data.kpis.total_students.toLocaleString("en-US")}
              subtext="Across all programs"
              icon={GraduationCap}
              tone="navy"
            />
            <StatCard
              label="Active Faculty"
              value={data.kpis.active_faculty.toLocaleString("en-US")}
              subtext="Currently active"
              icon={Users}
              tone="blue"
            />
            <StatCard
              label="Pending Vouchers"
              value={data.kpis.pending_vouchers.toLocaleString("en-US")}
              subtext="Awaiting verification"
              icon={ReceiptText}
              tone="gold"
            />
            <StatCard
              label="Total Outstanding"
              value={fmtRs(data.kpis.total_outstanding)}
              subtext="Across all fee ledgers"
              icon={Wallet}
              tone="green"
            />
          </section>

          <section className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <SectionCard
              title="Students by Program"
              subtitle="Share of enrolment across programs"
            >
              <DonutChart
                rows={data.students_by_program}
                centerLabel="Students"
              />
            </SectionCard>
            <SectionCard
              title="Students by Session"
              subtitle="Enrolment per admission session"
            >
              <GradientBars rows={data.students_by_session} />
            </SectionCard>
          </section>

          <section className="grid grid-cols-1 gap-4 xl:grid-cols-3">
            <SectionCard
              title="Pending Approvals"
              subtitle="Queues waiting for an admin decision"
              action={
                totalWaiting > 0 ? (
                  <Badge variant="gold">{totalWaiting} waiting</Badge>
                ) : (
                  <Badge variant="success">All clear</Badge>
                )
              }
            >
              <ul className="-my-1 divide-y divide-line/70">
                {data.pending_approvals.map((q) => {
                  const Icon = approvalIcon(q.key);
                  return (
                    <li key={q.key}>
                      <a
                        href={q.href}
                        className="group -mx-2 flex items-center gap-3 rounded-lg px-2 py-2.5 transition-colors hover:bg-appbg"
                      >
                        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-navy/5 text-navy ring-1 ring-inset ring-line transition-colors group-hover:bg-navy/10">
                          <Icon className="h-4 w-4" aria-hidden />
                        </span>
                        <span className="min-w-0 flex-1 truncate text-sm font-medium text-ink">
                          {q.label}
                        </span>
                        {q.count > 0 ? (
                          <Badge variant="gold">{q.count} waiting</Badge>
                        ) : (
                          <Badge variant="muted">Clear</Badge>
                        )}
                      </a>
                    </li>
                  );
                })}
              </ul>
            </SectionCard>

            <SectionCard
              title="Recent Notifications"
              subtitle="Latest announcements to the university"
            >
              {data.recent_notifications.length === 0 ? (
                <EmptyState
                  icon={Bell}
                  title="No notifications yet"
                  message="New announcements will appear here."
                />
              ) : (
                <ul className="space-y-4">
                  {data.recent_notifications.map((n, i) => (
                    <li key={i} className="relative flex gap-3 text-sm">
                      <span
                        className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-brandblue ring-4 ring-brandblue/10"
                        aria-hidden
                      />
                      <span className="min-w-0">
                        <span className="block font-medium leading-snug text-ink">
                          {n.title}
                        </span>
                        <span className="mt-0.5 block text-xs text-faint">
                          {fmtDate(n.created_at)}
                        </span>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </SectionCard>

            <SectionCard
              title="Quick Links"
              subtitle="Jump straight to the busiest admin pages"
            >
              <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
                {QUICK_LINKS.map((l) => (
                  <li key={l.label}>
                    <a
                      href={l.href}
                      className="group flex items-center gap-2.5 rounded-xl border border-line px-3 py-2.5 text-sm font-medium text-ink transition-all duration-200 hover:-translate-y-px hover:border-brandblue/40 hover:bg-brandblue/5 hover:text-navy hover:shadow-card"
                    >
                      <l.icon
                        className="h-4 w-4 shrink-0 text-brandblue"
                        aria-hidden
                      />
                      <span className="min-w-0 flex-1 truncate">
                        {l.label}
                      </span>
                      <span
                        className="text-faint transition-transform duration-200 group-hover:translate-x-0.5"
                        aria-hidden
                      >
                        →
                      </span>
                    </a>
                  </li>
                ))}
              </ul>
            </SectionCard>
          </section>

          <section className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <SectionCard
              title="Pending Vouchers"
              subtitle="Latest vouchers awaiting verification"
            >
              <DataTable
                columns={[
                  { label: "Challan" },
                  { label: "Student" },
                  { label: "Amount", align: "right" },
                  { label: "Status" },
                ]}
                rows={data.pending_vouchers.map((v) => [
                  <span
                    key="c"
                    className="whitespace-nowrap font-medium text-navy"
                  >
                    {v.challan_no}
                  </span>,
                  <span key="s" className="whitespace-nowrap">
                    {v.student_name}
                  </span>,
                  <span key="a" className="whitespace-nowrap font-medium">
                    {fmtRs(v.amount)}
                  </span>,
                  <span key="t">{statusBadge(v.status)}</span>,
                ])}
                emptyMessage="No vouchers are waiting for verification right now."
              />
            </SectionCard>

            <SectionCard
              title="Recent Students"
              subtitle="Most recently added student records"
            >
              <DataTable
                columns={[
                  { label: "Reg. No." },
                  { label: "Name" },
                  { label: "Program" },
                  { label: "Status" },
                ]}
                rows={data.recent_students.map((s) => [
                  <span
                    key="r"
                    className="whitespace-nowrap font-medium text-navy"
                  >
                    {s.reg_no}
                  </span>,
                  <span key="n" className="whitespace-nowrap">
                    {s.name}
                  </span>,
                  <span key="p" className="whitespace-nowrap">
                    {s.program ?? "—"}
                  </span>,
                  <span key="t">{statusBadge(s.status)}</span>,
                ])}
                emptyMessage="No student records have been added yet."
              />
            </SectionCard>
          </section>

          <SectionCard
            title="Recent Activity"
            subtitle="Audit trail of the latest admin actions"
          >
            {data.recent_activity.length === 0 ? (
              <EmptyState
                icon={ClipboardList}
                title="No activity recorded yet"
                message="Admin actions will be logged here as they happen."
              />
            ) : (
              <ol className="relative space-y-5 border-l-2 border-line pl-5">
                {data.recent_activity.map((a, i) => (
                  <li key={i} className="relative text-sm">
                    <span
                      className="absolute -left-[27px] top-1 h-2.5 w-2.5 rounded-full bg-gold ring-4 ring-gold/20"
                      aria-hidden
                    />
                    <p className="leading-snug">
                      <span className="font-medium text-ink">{a.action}</span>
                      {a.detail ? (
                        <span className="text-faint"> — {a.detail}</span>
                      ) : null}
                    </p>
                    <p className="mt-0.5 text-xs text-faint">
                      {fmtDate(a.created_at)}
                    </p>
                  </li>
                ))}
              </ol>
            )}
          </SectionCard>
        </div>
      )}
    </Shell>
  );
}
