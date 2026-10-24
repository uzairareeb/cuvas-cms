"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  GraduationCap,
  ReceiptText,
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
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

function fmtRs(n: number) {
  return "Rs " + n.toLocaleString("en-US");
}

function fmtDate(s: string | null) {
  if (!s) return "";
  const d = new Date(s.replace(" ", "T"));
  return Number.isNaN(d.getTime()) ? s : d.toLocaleString();
}

function Bars({
  rows,
}: {
  rows: { name: string; count: number }[];
}) {
  const max = Math.max(1, ...rows.map((r) => r.count));
  if (rows.length === 0) {
    return <p className="text-sm text-faint">No data yet.</p>;
  }
  return (
    <ul className="space-y-2.5">
      {rows.map((r) => (
        <li key={r.name} className="text-sm">
          <div className="mb-1 flex items-baseline justify-between gap-3">
            <span className="min-w-0 truncate text-ink">{r.name}</span>
            <span className="shrink-0 font-medium text-navy">{r.count}</span>
          </div>
          <div className="h-2 overflow-hidden rounded bg-appbg">
            <div
              className="h-full rounded bg-brandblue"
              style={{ width: `${Math.max(3, (r.count / max) * 100)}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}

function KpiCard({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: string;
  icon: LucideIcon;
}) {
  return (
    <Card className="rounded-xl">
      <CardContent className="flex items-center gap-4 p-5">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-navy text-white">
          <Icon className="h-5 w-5" aria-hidden />
        </span>
        <span className="min-w-0">
          <span className="block truncate text-2xl font-semibold text-navy">
            {value}
          </span>
          <span className="block text-sm text-faint">{label}</span>
        </span>
      </CardContent>
    </Card>
  );
}

function Skeleton() {
  return (
    <div className="animate-pulse space-y-6" aria-label="Loading dashboard">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-24 rounded-xl bg-surface shadow" />
        ))}
      </div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <div className="h-56 rounded-xl bg-surface shadow" />
        <div className="h-56 rounded-xl bg-surface shadow" />
      </div>
      <div className="h-64 rounded-xl bg-surface shadow" />
    </div>
  );
}

const QUICK_LINKS: { label: string; href: string }[] = [
  { label: "Students", href: "/admin/students" },
  { label: "Vouchers", href: "/admin/vouchers" },
  { label: "Results", href: "/admin/results" },
  { label: "Clearance", href: "/admin/clearance" },
  { label: "Scholarships", href: "/admin/scholarships" },
  { label: "Reports", href: "/admin/reports" },
  { label: "Audit Log", href: "/admin/audit" },
  { label: "Backup", href: "/admin/backup" },
  { label: "Current Admin Dashboard", href: "/admin" },
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
        <div className="mx-auto w-full max-w-7xl">
          <Skeleton />
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-appbg px-4">
        <Card className="w-full max-w-md rounded-xl">
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

  return (
    <Shell user={user} title="Admin Dashboard">
      {!data ? (
        <Skeleton />
      ) : (
        <div className="space-y-6">
          {error ? (
            <p
              role="alert"
              className="rounded-md border border-error/40 bg-error/5 px-3 py-2 text-sm text-error"
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

          <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard
              label="Total Students"
              value={data.kpis.total_students.toLocaleString("en-US")}
              icon={GraduationCap}
            />
            <KpiCard
              label="Active Faculty"
              value={data.kpis.active_faculty.toLocaleString("en-US")}
              icon={Users}
            />
            <KpiCard
              label="Pending Vouchers"
              value={data.kpis.pending_vouchers.toLocaleString("en-US")}
              icon={ReceiptText}
            />
            <KpiCard
              label="Total Outstanding"
              value={fmtRs(data.kpis.total_outstanding)}
              icon={Wallet}
            />
          </section>

          <section className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <Card className="rounded-xl">
              <CardHeader>
                <CardTitle className="text-base text-navy">
                  Students by Program
                </CardTitle>
              </CardHeader>
              <CardContent>
                <Bars rows={data.students_by_program} />
              </CardContent>
            </Card>
            <Card className="rounded-xl">
              <CardHeader>
                <CardTitle className="text-base text-navy">
                  Students by Session
                </CardTitle>
              </CardHeader>
              <CardContent>
                <Bars rows={data.students_by_session} />
              </CardContent>
            </Card>
          </section>

          <section className="grid grid-cols-1 gap-4 xl:grid-cols-3">
            <Card className="rounded-xl">
              <CardHeader>
                <CardTitle className="text-base text-navy">
                  Pending Approvals
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="divide-y divide-line">
                  {data.pending_approvals.map((q) => (
                    <li key={q.key}>
                      <a
                        href={q.href}
                        className="flex items-center justify-between gap-3 py-2 text-sm hover:underline"
                      >
                        <span className="min-w-0 truncate text-ink">
                          {q.label}
                        </span>
                        <span
                          className={
                            q.count > 0
                              ? "shrink-0 rounded-full bg-gold px-2 py-0.5 text-xs font-semibold text-navy-deep"
                              : "shrink-0 rounded-full bg-appbg px-2 py-0.5 text-xs font-medium text-faint"
                          }
                        >
                          {q.count} waiting
                        </span>
                      </a>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>

            <Card className="rounded-xl">
              <CardHeader>
                <CardTitle className="text-base text-navy">
                  Recent Notifications
                </CardTitle>
              </CardHeader>
              <CardContent>
                {data.recent_notifications.length === 0 ? (
                  <p className="text-sm text-faint">No notifications yet.</p>
                ) : (
                  <ul className="space-y-3">
                    {data.recent_notifications.map((n, i) => (
                      <li key={i} className="text-sm">
                        <p className="font-medium leading-snug text-ink">
                          {n.title}
                        </p>
                        <p className="text-xs text-faint">
                          {fmtDate(n.created_at)}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>

            <Card className="rounded-xl">
              <CardHeader>
                <CardTitle className="text-base text-navy">Quick Links</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="grid grid-cols-1 gap-1">
                  {QUICK_LINKS.map((l) => (
                    <li key={l.label}>
                      <a
                        href={l.href}
                        className="block rounded-md px-2 py-1.5 text-sm text-brandblue hover:bg-appbg hover:underline"
                      >
                        {l.label}
                      </a>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          </section>

          <section className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <Card className="rounded-xl">
              <CardHeader>
                <CardTitle className="text-base text-navy">
                  Pending Vouchers
                </CardTitle>
              </CardHeader>
              <CardContent>
                {data.pending_vouchers.length === 0 ? (
                  <p className="text-sm text-faint">No pending vouchers.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-line text-left text-faint">
                          <th className="py-2 pr-3 font-medium">Challan</th>
                          <th className="py-2 pr-3 font-medium">Student</th>
                          <th className="py-2 pr-3 font-medium">Amount</th>
                          <th className="py-2 font-medium">Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.pending_vouchers.map((v) => (
                          <tr
                            key={v.challan_no}
                            className="border-b border-line/60 last:border-0"
                          >
                            <td className="py-2 pr-3 whitespace-nowrap">
                              {v.challan_no}
                            </td>
                            <td className="py-2 pr-3">{v.student_name}</td>
                            <td className="py-2 pr-3 whitespace-nowrap">
                              {fmtRs(v.amount)}
                            </td>
                            <td className="py-2">{v.status}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card className="rounded-xl">
              <CardHeader>
                <CardTitle className="text-base text-navy">
                  Recent Students
                </CardTitle>
              </CardHeader>
              <CardContent>
                {data.recent_students.length === 0 ? (
                  <p className="text-sm text-faint">No students yet.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-line text-left text-faint">
                          <th className="py-2 pr-3 font-medium">Reg. No.</th>
                          <th className="py-2 pr-3 font-medium">Name</th>
                          <th className="py-2 pr-3 font-medium">Program</th>
                          <th className="py-2 font-medium">Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.recent_students.map((s) => (
                          <tr
                            key={s.reg_no}
                            className="border-b border-line/60 last:border-0"
                          >
                            <td className="py-2 pr-3 whitespace-nowrap">
                              {s.reg_no}
                            </td>
                            <td className="py-2 pr-3">{s.name}</td>
                            <td className="py-2 pr-3">{s.program ?? "—"}</td>
                            <td className="py-2">{s.status ?? "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>
          </section>

          <section>
            <Card className="rounded-xl">
              <CardHeader>
                <CardTitle className="text-base text-navy">
                  Recent Activity
                </CardTitle>
              </CardHeader>
              <CardContent>
                {data.recent_activity.length === 0 ? (
                  <p className="text-sm text-faint">No activity recorded yet.</p>
                ) : (
                  <ul className="divide-y divide-line">
                    {data.recent_activity.map((a, i) => (
                      <li key={i} className="py-2 text-sm">
                        <span className="font-medium text-ink">{a.action}</span>
                        {a.detail ? (
                          <span className="text-faint"> — {a.detail}</span>
                        ) : null}
                        <span className="block text-xs text-faint">
                          {fmtDate(a.created_at)}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </section>
        </div>
      )}
    </Shell>
  );
}
