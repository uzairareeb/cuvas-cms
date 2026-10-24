"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, login, me } from "@/lib/api";
import { LOGO_SRC } from "@/lib/logo";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
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
    <main className="flex min-h-screen items-center justify-center bg-appbg px-4 py-10">
      <Card className="w-full max-w-md rounded-xl shadow-md">
        <CardHeader className="items-center space-y-3 text-center">
          {/* Official CUVAS logo, used as supplied (aspect preserved). */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={LOGO_SRC}
            alt="Cholistan University of Veterinary and Animal Sciences, Bahawalpur"
            className="h-auto w-72 max-w-full"
          />
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-navy">
              MY CUVAS
            </h1>
            <p className="text-sm text-faint">University Management System</p>
          </div>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                name="username"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            {error ? (
              <p
                role="alert"
                className="rounded-md border border-error/40 bg-error/5 px-3 py-2 text-sm text-error"
              >
                {error}
              </p>
            ) : null}
            <Button type="submit" className="w-full" disabled={busy}>
              {busy ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}
