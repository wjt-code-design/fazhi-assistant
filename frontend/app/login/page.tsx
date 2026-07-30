"use client";
import { useState, useEffect, FormEvent, CSSProperties } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { Logo, Spinner } from "@/components/ui";

export default function LoginPage() {
  const router = useRouter();
  const { user, loading, login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // 已登录则直接跳走
  useEffect(() => {
    if (!loading && user) {
      router.replace(user.role === "admin" ? "/admin" : "/chat");
    }
  }, [loading, user, router]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (username.trim().length < 3) {
      setError("用户名至少 3 个字符");
      return;
    }
    if (password.length < 8) {
      setError("密码至少 8 位");
      return;
    }
    if (mode === "register" && password !== confirm) {
      setError("两次输入的密码不一致");
      return;
    }
    setBusy(true);
    try {
      const u = mode === "login" ? await login(username.trim(), password) : await register(username.trim(), password);
      router.replace(u.role === "admin" ? "/admin" : "/chat");
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败，请重试");
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <Spinner className="h-8 w-8 text-accent" />
      </main>
    );
  }

  return (
    <main className="min-h-screen flex flex-col md:flex-row">
      {/* 左侧品牌区（桌面 55%，深底 + 朱红微光 + 细线网格 + 漂浮巨型 §） */}
      <section className="brand-panel relative flex min-h-[160px] flex-col justify-between overflow-hidden px-8 py-8 md:min-h-screen md:w-[55%] md:px-14 md:py-12">
        <span className="section-mark section-mark-float absolute -right-12 top-1/2 hidden text-[22rem] text-white md:block">
          §
        </span>
        <Logo dark />
        <div className="relative hidden md:block">
          <p className="page-enter mb-5 inline-flex items-center gap-2 rounded-full border border-white/15 px-3.5 py-1.5 text-xs tracking-wider text-white/60" style={{ "--stagger": "80ms" } as CSSProperties}>
            <span className="pulse-dot" />
            基于公开法律条文 · RAG 检索增强
          </p>
          <h1 className="page-enter font-serif text-[2.75rem] font-bold leading-[1.25] tracking-tight text-white" style={{ "--stagger": "160ms" } as CSSProperties}>
            法律智慧，
            <br />
            触手可及。
          </h1>
          <p className="page-enter mt-5 max-w-md text-[0.9375rem] leading-[1.8] text-white/60" style={{ "--stagger": "240ms" } as CSSProperties}>
            引用出处清晰，回答严谨克制，300 字内直达要点。
          </p>
          <div className="page-enter mt-8 flex items-center gap-6 text-xs tracking-wide text-white/45" style={{ "--stagger": "320ms" } as CSSProperties}>
            <span className="flex items-center gap-1.5">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
              条文可溯源
            </span>
            <span className="flex items-center gap-1.5">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
              严谨克制
            </span>
            <span className="flex items-center gap-1.5">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
              流式秒回
            </span>
          </div>
        </div>
        <p className="relative hidden text-xs tracking-wide text-white/40 md:block">
          仅供参考 · 不构成正式法律意见
        </p>
      </section>

      {/* 右侧表单区（45%） */}
      <section className="flex flex-1 items-center justify-center px-6 py-12 md:py-0">
        <div className="w-full max-w-[380px]">
          <div className="page-enter mb-10 flex justify-center md:hidden">
            <Logo />
          </div>
          <h2 className="page-enter font-serif text-[1.5rem] font-semibold tracking-[-0.01em] text-ink" style={{ "--stagger": "60ms" } as CSSProperties}>
            {mode === "login" ? "欢迎回来" : "创建账号"}
          </h2>
          <p className="page-enter mt-1.5 text-sm text-slate" style={{ "--stagger": "120ms" } as CSSProperties}>
            {mode === "login" ? "登录后开始提问" : "注册后即可免费使用"}
          </p>

          {/* 登录 / 注册 切换（底部划线式） */}
          <div className="page-enter tabs mt-8" style={{ "--stagger": "180ms" } as CSSProperties}>
            <button
              type="button"
              className={`tab flex-1 ${mode === "login" ? "active" : ""}`}
              onClick={() => {
                setMode("login");
                setError("");
              }}
            >
              登录
            </button>
            <button
              type="button"
              className={`tab flex-1 ${mode === "register" ? "active" : ""}`}
              onClick={() => {
                setMode("register");
                setError("");
              }}
            >
              注册
            </button>
          </div>

          <form onSubmit={onSubmit} className="page-enter card mt-6 border-l-[3px] border-l-accent p-8" style={{ "--stagger": "240ms" } as CSSProperties}>
            <div className="mb-5">
              <label htmlFor="username" className="field-label">
                用户名
              </label>
              <input
                id="username"
                className="input"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="3-32 个字符"
                autoComplete="username"
                required
              />
            </div>
            <div className="mb-5">
              <label htmlFor="password" className="field-label">
                密码
              </label>
              <input
                id="password"
                type="password"
                className="input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={mode === "register" ? "至少 8 位" : "请输入密码"}
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                required
              />
            </div>
            {mode === "register" && (
              <div className="mb-5 fade-in">
                <label htmlFor="confirm" className="field-label">
                  确认密码
                </label>
                <input
                  id="confirm"
                  type="password"
                  className="input"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  placeholder="再次输入密码"
                  autoComplete="new-password"
                  required
                />
              </div>
            )}
            {error && (
              <p className="scale-in mb-4 flex items-center gap-2 rounded-lg border border-[#f3c8c8] bg-[#fdecec] px-3.5 py-2.5 text-sm text-error">
                <svg className="shrink-0" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                {error}
              </p>
            )}
            <button type="submit" disabled={busy} className="btn btn-primary w-full">
              {busy ? <Spinner /> : mode === "login" ? "登 录" : "创建账号"}
            </button>
            <p className="mt-6 text-center text-xs leading-relaxed text-slate">
              本工具回答仅供参考，具体问题请咨询执业律师
            </p>
          </form>
        </div>
      </section>
    </main>
  );
}
