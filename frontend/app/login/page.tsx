"use client";
import { useState, FormEvent, CSSProperties } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { Logo, Spinner } from "@/components/ui";

// 钤印入典：点印章进登录/直进（防登录疲劳）。短期（JWT 7 天内）已登录 → 直进跳过密码。
function SealGate({ onSeal, disabled, sealing }: { onSeal?: () => void; disabled?: boolean; sealing?: boolean }) {
  return (
    <button
      type="button"
      onClick={onSeal}
      disabled={disabled}
      aria-label="钤印入典"
      className="group flex flex-col items-center gap-7 focus:outline-none"
    >
      <span
        className="flex h-24 w-24 items-center justify-center rounded-2xl border border-white/70 bg-white/55 font-serif text-5xl text-accent-deep shadow-[var(--glow)] backdrop-blur-md transition-transform duration-300 group-hover:-rotate-3 group-hover:scale-105"
        style={sealing ? ({ animation: "sealPress .4s cubic-bezier(.34,1.56,.64,1)" } as CSSProperties) : ({ animation: "glowBreathe 2.6s ease-in-out infinite" } as CSSProperties)}
      >
        §
      </span>
      <span className="text-sm tracking-[0.45em] text-slate">钤 印 入 典</span>
    </button>
  );
}

export default function LoginPage() {
  const router = useRouter();
  const { user, loading, login, register } = useAuth();
  const [sealed, setSealed] = useState(false);
  const [sealing, setSealing] = useState(false);
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // 钤印入典：印章下压回弹后分支——token 有效直进（跳过密码），否则表单自墨心凝结
  async function handleSeal() {
    if (sealing) return;
    setSealing(true);
    await new Promise((r) => setTimeout(r, 400));
    if (user) {
      router.replace(user.role === "admin" ? "/admin" : "/chat");
    } else {
      setSealed(true);
    }
    setSealing(false);
  }

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

  // 四角装饰（<860px 隐藏）
  const corners = (
    <>
      <div className="pointer-events-none absolute left-8 top-8 hidden items-center md:flex">
        <Logo />
      </div>
      <p className="pointer-events-none absolute right-8 top-8 hidden font-serif text-xs tracking-[0.3em] text-slate/70 md:block" style={{ writingMode: "vertical-rl" }}>
        法智 · 樱花法典
      </p>
      <p className="pointer-events-none absolute bottom-8 left-8 hidden font-serif text-xs tracking-[0.25em] text-slate/50 md:block">
        01 · 贴文 / 传件 / 拍照　02 · 逐条追问　03 · 参考条文
      </p>
      <p className="pointer-events-none absolute bottom-8 right-8 hidden font-serif text-xs tracking-[0.2em] text-slate/60 md:block">
        以事实为依据 · 以法律为准绳
      </p>
    </>
  );

  if (loading) {
    return (
      <main className="relative flex min-h-screen items-center justify-center overflow-hidden px-6 py-12">
        {corners}
        <SealGate disabled />
      </main>
    );
  }

  if (!sealed) {
    return (
      <main className="relative flex min-h-screen items-center justify-center overflow-hidden px-6 py-12">
        {corners}
        <SealGate onSeal={handleSeal} sealing={sealing} />
      </main>
    );
  }

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden px-6 py-12">
      {corners}
      <div className="w-full max-w-[min(340px,92vw)]" style={{ animation: "condenseIn .9s var(--ease-out)" }}>
        <div className="glass-card mb-8 rounded-2xl p-8">
          <h2 className="page-enter font-serif text-[1.5rem] font-semibold tracking-[-0.01em] text-ink">
            {mode === "login" ? "欢迎回来" : "创建账号"}
          </h2>
          <p className="page-enter mt-1.5 text-sm text-slate">
            {mode === "login" ? "登录后开始提问" : "注册后即可免费使用"}
          </p>

          <div className="page-enter tabs mt-8">
            <button type="button" className={`tab flex-1 ${mode === "login" ? "active" : ""}`} onClick={() => { setMode("login"); setError(""); }}>
              登录
            </button>
            <button type="button" className={`tab flex-1 ${mode === "register" ? "active" : ""}`} onClick={() => { setMode("register"); setError(""); }}>
              注册
            </button>
          </div>

          <form onSubmit={onSubmit} className="mt-6">
            <div className="mb-5">
              <label htmlFor="username" className="field-label">用户名</label>
              <input id="username" className="input" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="3-32 个字符" autoComplete="username" required />
            </div>
            <div className="mb-5">
              <label htmlFor="password" className="field-label">密码</label>
              <input id="password" type="password" className="input" value={password} onChange={(e) => setPassword(e.target.value)} placeholder={mode === "register" ? "至少 8 位" : "请输入密码"} autoComplete={mode === "login" ? "current-password" : "new-password"} required />
            </div>
            {mode === "register" && (
              <div className="mb-5 fade-in">
                <label htmlFor="confirm" className="field-label">确认密码</label>
                <input id="confirm" type="password" className="input" value={confirm} onChange={(e) => setConfirm(e.target.value)} placeholder="再次输入密码" autoComplete="new-password" required />
              </div>
            )}
            {error && (
              <p className="scale-in mb-4 flex items-center gap-2 rounded-lg border border-error/40 bg-[var(--error-tint)] px-3.5 py-2.5 text-sm text-error">
                <svg className="shrink-0" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" /></svg>
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
      </div>
    </main>
  );
}
