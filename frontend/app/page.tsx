"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { Logo, Spinner } from "@/components/ui";

export default function Home() {
  const router = useRouter();
  const { user, loading } = useAuth();

  // 未登录 → /login；已登录按角色跳转
  useEffect(() => {
    if (loading) return;
    if (!user) router.replace("/login");
    else router.replace(user.role === "admin" ? "/admin" : "/chat");
  }, [loading, user, router]);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6">
      <div className="scale-in">
        <Logo size="lg" />
      </div>
      <Spinner className="h-6 w-6 text-vermilion" />
      <p className="fade-in text-xs tracking-[0.2em] text-slate/70">正在进入法智…</p>
    </main>
  );
}
