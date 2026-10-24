"use client";

import { useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  BookOpen,
  Building2,
  CalendarDays,
  ChevronDown,
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
import { Badge } from "@/components/ui/badge";

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

// Mirrors the role-aware admin sidebar of the legacy UI. Only
// "Overview" is a Next page so far; every other item points at the
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

const COLLAPSE_KEY = "mycuvas-nav-collapsed";

// Collapsed groups persist in localStorage. Loaded in an effect so
// server and client render identically on first paint (all groups
// open), then the stored preference applies — no hydration mismatch.
function useCollapsedGroups() {
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(COLLAPSE_KEY);
      if (raw) setCollapsed(JSON.parse(raw) as Record<string, boolean>);
    } catch {
      /* corrupted value — keep everything open */
    }
  }, []);
  function toggle(label: string) {
    setCollapsed((prev) => {
      const next = { ...prev, [label]: !prev[label] };
      try {
        window.localStorage.setItem(COLLAPSE_KEY, JSON.stringify(next));
      } catch {
        /* private mode — preference simply won't persist */
      }
      return next;
    });
  }
  return { collapsed, toggle };
}

function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const { collapsed, toggle } = useCollapsedGroups();
  return (
    <nav
      aria-label="Main navigation"
      className="scrollbar-thin flex-1 space-y-4 overflow-y-auto px-3 py-4"
    >
      {NAV.map((group, gi) => {
        const isOpen = group.label === null || !collapsed[group.label];
        return (
          <div key={gi}>
            {group.label ? (
              <button
                type="button"
                onClick={() => toggle(group.label as string)}
                aria-expanded={isOpen}
                className="flex w-full items-center justify-between rounded-md px-2 py-1 text-left text-[11px] font-semibold uppercase tracking-wider text-white/50 transition-colors hover:text-white/80"
              >
                {group.label}
                <ChevronDown
                  className={cn(
                    "h-3.5 w-3.5 transition-transform duration-200",
                    !isOpen && "-rotate-90"
                  )}
                  aria-hidden
                />
              </button>
            ) : null}
            {isOpen ? (
              <ul className="animate-fade-in mt-1 space-y-0.5">
                {group.items.map((item) => {
                  const active = item.next && pathname === item.href;
                  const classes = cn(
                    "group relative flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition-all duration-200",
                    active
                      ? "bg-white/10 font-semibold text-white"
                      : "text-white/75 hover:bg-white/5 hover:text-white"
                  );
                  const inner = (
                    <>
                      {active ? (
                        <span
                          className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-full bg-gold"
                          aria-hidden
                        />
                      ) : null}
                      <item.icon
                        className={cn(
                          "h-4 w-4 shrink-0 transition-colors",
                          active
                            ? "text-gold"
                            : "text-white/60 group-hover:text-white/90"
                        )}
                        aria-hidden
                      />
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
            ) : null}
          </div>
        );
      })}
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
        className="h-auto w-full rounded-lg bg-white p-1.5 shadow-sm"
      />
      <p className="mt-3 text-base font-semibold leading-tight tracking-tight text-white">
        MY CUVAS
      </p>
      <p className="text-xs text-white/60">University Management System</p>
      <div className="mt-3 h-0.5 w-10 rounded bg-gold" aria-hidden />
    </div>
  );
}

function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase())
    .join("");
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
      <aside className="sticky top-0 hidden h-screen w-[272px] shrink-0 flex-col bg-navy-deep shadow-pop lg:flex">
        <SidebarHeader />
        <SidebarNav />
        <div className="border-t border-white/10 px-4 py-3">
          <div className="flex items-center gap-3">
            <span
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gold/20 text-sm font-bold text-gold ring-1 ring-inset ring-gold/40"
              aria-hidden
            >
              {initials(user.name) || "A"}
            </span>
            <span className="min-w-0">
              <span className="block truncate text-sm font-medium text-white">
                {user.name}
              </span>
              <span className="block truncate text-xs capitalize text-white/60">
                {user.role}
              </span>
            </span>
          </div>
        </div>
      </aside>

      {/* Mobile sidebar (slide-over) */}
      {open ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="animate-fade-in absolute inset-0 bg-navy-deep/50 backdrop-blur-[1px]"
            onClick={() => setOpen(false)}
            aria-hidden
          />
          <aside className="animate-drawer-in absolute inset-y-0 left-0 flex w-[272px] flex-col bg-navy-deep shadow-pop">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <SidebarHeader />
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="m-2 rounded-md p-1.5 text-white/80 transition-colors hover:bg-white/10"
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
        <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-line bg-surface/90 px-4 py-3 shadow-topbar backdrop-blur sm:px-6">
          <button
            type="button"
            onClick={() => setOpen(true)}
            className="rounded-lg p-1.5 text-faint transition-colors hover:bg-appbg lg:hidden"
            aria-label="Open menu"
          >
            <Menu className="h-5 w-5" />
          </button>
          <div className="min-w-0 flex-1">
            <nav
              aria-label="Breadcrumb"
              className="hidden text-xs text-faint sm:block"
            >
              <span>MY CUVAS</span>
              <span className="mx-1.5" aria-hidden>
                /
              </span>
              <span className="font-medium text-navy">{title}</span>
            </nav>
            <h1 className="truncate text-lg font-semibold tracking-tight text-navy">
              {title}
            </h1>
          </div>
          <div className="hidden items-center gap-2.5 md:flex">
            <span
              className="flex h-9 w-9 items-center justify-center rounded-full bg-navy/10 text-sm font-bold text-navy ring-1 ring-inset ring-navy/15"
              aria-hidden
            >
              {initials(user.name) || "A"}
            </span>
            <span className="text-right">
              <span className="block text-sm font-medium leading-tight text-ink">
                {user.name}
              </span>
              <span className="mt-0.5 block leading-tight">
                <Badge variant="blue" className="capitalize">
                  {user.role}
                </Badge>
              </span>
            </span>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={onSignOut}
            disabled={signingOut}
            className="rounded-lg"
          >
            <LogOut className="mr-1.5 h-4 w-4" aria-hidden />
            Sign out
          </Button>
        </header>
        <main className="mx-auto w-full max-w-[1280px] flex-1 px-4 py-6 sm:px-6">
          {children}
        </main>
        <footer className="border-t border-line px-4 py-4 sm:px-6">
          <p className="mx-auto w-full max-w-[1280px] text-xs text-faint">
            MY CUVAS — Cholistan University of Veterinary and Animal Sciences,
            Bahawalpur · University Management System
          </p>
        </footer>
      </div>
    </div>
  );
}
