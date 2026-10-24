"use client";

import { useState, type ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  BookOpen,
  Building2,
  CalendarDays,
  ClipboardList,
  DatabaseBackup,
  FileText,
  GraduationCap,
  LayoutDashboard,
  LibraryBig,
  LogOut,
  Menu,
  Newspaper,
  ReceiptText,
  ScrollText,
  ShieldCheck,
  Sparkles,
  TicketCheck,
  Trophy,
  Truck,
  Users,
  UserRoundCog,
  Wallet,
  X,
  type LucideIcon,
} from "lucide-react";

import { logout, type ApiUser } from "@/lib/api";
import { LOGO_SRC } from "@/lib/logo";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  next?: boolean; // true only for pages the Next app itself serves
}

interface NavGroup {
  label: string | null;
  items: NavItem[];
}

// Mirrors the role-aware admin sidebar of the legacy UI. In Slice 1
// only "Overview" is a Next page; every other item points at the
// EXISTING legacy path, which the fallback rewrite proxies to Flask
// — so each link genuinely works today.
const NAV: NavGroup[] = [
  {
    label: null,
    items: [
      { label: "Overview", href: "/dashboard", icon: LayoutDashboard, next: true },
    ],
  },
  {
    label: "Management",
    items: [
      { label: "Departments", href: "/admin/departments", icon: Building2 },
      { label: "Programs", href: "/admin/programs", icon: BookOpen },
      { label: "Sessions", href: "/admin/sessions", icon: CalendarDays },
      { label: "Courses", href: "/admin/courses", icon: LibraryBig },
      { label: "Students", href: "/admin/students", icon: GraduationCap },
      { label: "Faculty", href: "/admin/faculty", icon: Users },
      { label: "Staff", href: "/admin/staff", icon: UserRoundCog },
    ],
  },
  {
    label: "Finance",
    items: [
      { label: "Fee Heads", href: "/admin/fee-heads", icon: ReceiptText },
      { label: "Fee Plans", href: "/admin/fee-plans", icon: Wallet },
      { label: "Vouchers", href: "/admin/vouchers", icon: FileText },
      {
        label: "Fee Collection Report",
        href: "/admin/reports/fees",
        icon: ScrollText,
      },
    ],
  },
  {
    label: "Examinations",
    items: [
      { label: "Results", href: "/admin/results", icon: Trophy },
      { label: "Grade Scale", href: "/admin/grade-scale", icon: ClipboardList },
      { label: "Roll Number Slips", href: "/admin/slips.pdf", icon: TicketCheck },
    ],
  },
  {
    label: "Services",
    items: [
      { label: "Clearance", href: "/admin/clearance", icon: ShieldCheck },
      { label: "Scholarships", href: "/admin/scholarships", icon: Sparkles },
      { label: "Course Repeat", href: "/admin/repeat", icon: BookOpen },
      { label: "Attendance", href: "/admin/attendance", icon: ClipboardList },
      { label: "Timetable", href: "/admin/timetable", icon: CalendarDays },
      { label: "Transport", href: "/admin/transport", icon: Truck },
      { label: "Societies", href: "/admin/societies", icon: Users },
      { label: "Vehicle Passes", href: "/admin/vehicle-passes", icon: TicketCheck },
      { label: "Campus Links", href: "/admin/campus", icon: LibraryBig },
      { label: "Documents", href: "/admin/documents", icon: FileText },
      { label: "Support Tickets", href: "/admin/tickets", icon: Newspaper },
      { label: "Document Repository", href: "/admin/repository", icon: DatabaseBackup },
      { label: "Notifications", href: "/admin/notifications", icon: Newspaper },
    ],
  },
  {
    label: "System",
    items: [
      { label: "Reports", href: "/admin/reports", icon: ScrollText },
      { label: "Audit Log", href: "/admin/audit", icon: ClipboardList },
      { label: "Backup", href: "/admin/backup", icon: DatabaseBackup },
    ],
  },
];

function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-4">
      {NAV.map((group, gi) => (
        <div key={gi}>
          {group.label ? (
            <p className="px-2 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-white/50">
              {group.label}
            </p>
          ) : null}
          <ul className="space-y-0.5">
            {group.items.map((item) => {
              const active = item.next && pathname === item.href;
              const classes = cn(
                "flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm transition-colors",
                active
                  ? "bg-white/10 font-semibold text-white shadow-[inset_3px_0_0_0_var(--color-accent)]"
                  : "text-white/75 hover:bg-white/5 hover:text-white"
              );
              const inner = (
                <>
                  <item.icon className="h-4 w-4 shrink-0" aria-hidden />
                  <span className="truncate">{item.label}</span>
                </>
              );
              return (
                <li key={item.label}>
                  {item.next ? (
                    <Link href={item.href} className={classes} onClick={onNavigate}>
                      {inner}
                    </Link>
                  ) : (
                    // Legacy page — a plain anchor so the browser does a
                    // full load through the fallback proxy to Flask.
                    <a href={item.href} className={classes} onClick={onNavigate}>
                      {inner}
                    </a>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}

function SidebarHeader() {
  return (
    <div className="border-b border-white/10 px-4 py-4">
      {/* Official CUVAS logo, used as supplied (aspect preserved). */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={LOGO_SRC}
        alt="Cholistan University of Veterinary and Animal Sciences, Bahawalpur"
        className="h-auto w-full rounded bg-white p-1"
      />
      <p className="mt-3 text-base font-semibold leading-tight text-white">
        MY CUVAS
      </p>
      <p className="text-xs text-white/60">University Management System</p>
      <div className="mt-3 h-0.5 w-10 rounded bg-gold" aria-hidden />
    </div>
  );
}

export default function Shell({
  user,
  title,
  children,
}: {
  user: ApiUser;
  title: string;
  children: ReactNode;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);

  async function onSignOut() {
    setSigningOut(true);
    try {
      await logout();
    } catch {
      /* session already gone — the destination is the same */
    }
    router.push("/login");
  }

  return (
    <div className="flex min-h-screen bg-appbg">
      {/* Desktop sidebar */}
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col bg-navy-deep lg:flex">
        <SidebarHeader />
        <SidebarNav />
      </aside>

      {/* Mobile sidebar (slide-over) */}
      {open ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-black/40"
            onClick={() => setOpen(false)}
            aria-hidden
          />
          <aside className="absolute inset-y-0 left-0 flex w-64 flex-col bg-navy-deep shadow-xl">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <SidebarHeader />
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="m-2 rounded-md p-1.5 text-white/80 hover:bg-white/10"
                aria-label="Close menu"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <SidebarNav onNavigate={() => setOpen(false)} />
          </aside>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-line bg-surface px-4 py-3 sm:px-6">
          <button
            type="button"
            onClick={() => setOpen(true)}
            className="rounded-md p-1.5 text-faint hover:bg-appbg lg:hidden"
            aria-label="Open menu"
          >
            <Menu className="h-5 w-5" />
          </button>
          <h1 className="min-w-0 flex-1 truncate text-lg font-semibold text-navy">
            {title}
          </h1>
          <div className="hidden text-right sm:block">
            <p className="text-sm font-medium leading-tight text-ink">
              {user.name}
            </p>
            <p className="text-xs capitalize leading-tight text-faint">
              {user.role}
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={onSignOut}
            disabled={signingOut}
          >
            <LogOut className="mr-1.5 h-4 w-4" aria-hidden />
            Sign out
          </Button>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6">
          {children}
        </main>
      </div>
    </div>
  );
}
