"use client";
import { useState, useEffect, FormEvent } from "react";
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
        <Spinner className="h-8 w-8 text-vermilion" />
      </main>
    );
  }

  return (
    <main className="min-h-screen flex flex-col md:flex-row">
      {/* 左侧品牌区（桌面 55%，深底 + 细线网格 + 巨型 §） */}
      <section className="brand-panel relative md:w-[55%] flex flex-col justify-between overflow-hidden px-8 py-8 md:px-14 md:py-12 min-h-[140px] md:min-h-screen">
        <span className="section-mark absolute -right-12 top-1/2 -translate-y-1/2 hidden text-[22rem] text-white md:block">
          §
        </span>
        <Logo dark />
        <div className="relative hidden md:block">
          <h1 className="font-serif text-[2.5rem] font-bold leading-tight tracking-tight text-white">
            法律智慧，
            <br />
            触手可及。
          </h1>
          <p className="mt-5 max-w-md text-[0.9375rem] leading-[1.7] text-white/60">
            基于公开法律条文的智能问答。引用出处清晰，回答严谨克制，300 字内直达要点。
          </p>
        </div>
        <p className="relative hidden text-xs tracking-wide text-white/40 md:block">
          仅供参考 · 不构成正式法律意见
        </p>
      </section>

      {/* 右侧表单区（45%） */}
      <section className="flex flex-1 items-center justify-center px-6 py-12 md:py-0">
        <div className="page-enter w-full max-w-[380px]">
          <div className="mb-10 flex justify-center md:hidden">
            <Logo />
          </div>

          <h2 className="font-serif text-[1.375rem] font-semibold tracking-[-0.01em] text-ink">
            {mode === "login" ? "欢迎回来" : "创建账号"}
          </h2>
          <p className="mt-1 text-sm text-slate">
            {mode === "login" ? "登录后开始提问" : "注册后即可免费使用"}
          </p>

          {/* 登录 / 注册 切换（底部划线式） */}
          <div className="tabs mt-8">
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

          <form onSubmit={onSubmit} className="card mt-6 border-l-[3px] border-l-vermilion p-8">
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
              <div className="mb-5">
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
              <p className="mb-4 rounded bg-[#fee2e2] px-3 py-2 text-sm text-error">{error}</p>
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
