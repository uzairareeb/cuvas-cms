"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertCircle, Lock, User } from "lucide-react";

import { ApiError, login, me } from "@/lib/api";
import { LOGO_SRC } from "@/lib/logo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Already signed in? Send each role where it belongs: admins to
  // the Next dashboard, everyone else to their (still legacy) home —
  // those paths resolve through the fallback proxy to Flask.
  useEffect(() => {
    let live = true;
    me()
      .then((info) => {
        if (!live) return;
        if (info.user.role === "admin") {
          router.replace("/dashboard");
        } else {
          window.location.href = info.home;
        }
      })
      .catch(() => {
        /* not signed in — stay on the form */
      });
    return () => {
      live = false;
    };
  }, [router]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const result = await login(username.trim(), password);
      if (result.user.role === "admin") {
        router.push("/dashboard");
      } else {
        window.location.href = result.home;
      }
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Sign-in failed. Please try again."
      );
      setBusy(false);
    }
  }

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-navy-deep px-4 py-10">
      {/* Premium backdrop: deep navy gradient, gold glow, faint grid. */}
      <div
        className="pointer-events-none absolute inset-0"
        aria-hidden
        style={{
          background:
            "radial-gradient(720px 360px at 85% -5%, rgba(231,179,76,0.22), transparent 60%), radial-gradient(900px 500px at -10% 110%, rgba(36,87,167,0.45), transparent 60%), linear-gradient(160deg, #0f2b4c 0%, #17365d 55%, #0f2b4c 100%)",
        }}
      />
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.07]"
        aria-hidden
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.6) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.6) 1px, transparent 1px)",
          backgroundSize: "44px 44px",
        }}
      />

      <div className="animate-fade-up relative w-full max-w-md">
        <div className="overflow-hidden rounded-2xl bg-surface shadow-pop">
          <div className="h-1.5 bg-gradient-to-r from-navy via-gold to-navy" aria-hidden />
          <div className="px-6 pb-7 pt-7 sm:px-8">
            <div className="flex flex-col items-center text-center">
              {/* Official CUVAS logo, used as supplied (aspect preserved). */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={LOGO_SRC}
                alt="Cholistan University of Veterinary and Animal Sciences, Bahawalpur"
                className="h-auto w-72 max-w-full"
              />
              <h1 className="mt-5 text-[22px] font-bold tracking-tight text-navy">
                MY CUVAS
              </h1>
              <p className="mt-0.5 text-sm text-faint">
                University Management System
              </p>
              <p className="mt-4 text-[13px] leading-snug text-faint">
                Sign in with your university account to continue.
              </p>
            </div>

            <form onSubmit={onSubmit} className="mt-6 space-y-4">
              <div className="space-y-2">
                <Label htmlFor="username">Username</Label>
                <div className="relative">
                  <User
                    className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint"
                    aria-hidden
                  />
                  <Input
                    id="username"
                    name="username"
                    autoComplete="username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    required
                    className="h-11 rounded-xl pl-9 transition-shadow focus-visible:ring-2 focus-visible:ring-brandblue/60"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <div className="relative">
                  <Lock
                    className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint"
                    aria-hidden
                  />
                  <Input
                    id="password"
                    name="password"
                    type="password"
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    className="h-11 rounded-xl pl-9 transition-shadow focus-visible:ring-2 focus-visible:ring-brandblue/60"
                  />
                </div>
              </div>
              {error ? (
                <p
                  role="alert"
                  className="flex items-start gap-2 rounded-xl border border-error/40 bg-error/5 px-3.5 py-2.5 text-sm text-error"
                >
                  <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                  <span>{error}</span>
                </p>
              ) : null}
              <Button
                type="submit"
                className="h-11 w-full rounded-xl bg-navy text-base font-semibold shadow-card transition-all duration-200 hover:bg-navy-deep hover:shadow-card-hover"
                disabled={busy}
              >
                {busy ? "Signing in…" : "Sign in"}
              </Button>
            </form>
          </div>
        </div>
        <p className="mt-5 text-center text-xs text-white/60">
          Authorized access only · Cholistan University of Veterinary and
          Animal Sciences, Bahawalpur
        </p>
      </div>
    </main>
  );
}
