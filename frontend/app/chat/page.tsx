"use client";
import { useEffect, useRef, useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { api, streamChat } from "@/lib/api";
import { Logo, Spinner, EmptyState } from "@/components/ui";

interface HistoryItem {
  id: number;
  question: string;
  answer: string;
  created_at: string;
}
interface Msg {
  role: "user" | "ai";
  content: string;
}

export default function ChatPage() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  // 未登录跳转
  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  // 加载我的历史
  useEffect(() => {
    if (user) {
      api.get<HistoryItem[]>("/api/conversations").then(setHistory).catch(() => {});
    }
  }, [user]);

  // 自动滚到底部
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (loading || !user) return null;

  async function send(e?: FormEvent) {
    e?.preventDefault();
    const q = input.trim();
    if (!q || streaming) return;
    setInput("");
    setActiveId(null);
    setMessages((m) => [
      ...m,
      { role: "user", content: q },
      { role: "ai", content: "" },
    ]);
    setStreaming(true);
    let acc = "";
    await streamChat(
      q,
      (chunk) => {
        acc += chunk;
        setMessages((m) => {
          const copy = [...m];
          copy[copy.length - 1] = { role: "ai", content: acc };
          return copy;
        });
      },
      (err) => {
        setMessages((m) => {
          const copy = [...m];
          copy[copy.length - 1] = { role: "ai", content: `出错了：${err}` };
          return copy;
        });
      }
    );
    setStreaming(false);
    api.get<HistoryItem[]>("/api/conversations").then(setHistory).catch(() => {});
  }

  function openHistory(item: HistoryItem) {
    setActiveId(item.id);
    setMessages([
      { role: "user", content: item.question },
      { role: "ai", content: item.answer },
    ]);
    setSidebarOpen(false);
  }

  function newChat() {
    setMessages([]);
    setActiveId(null);
    setSidebarOpen(false);
  }

  return (
    <div className="flex h-screen overflow-hidden">
      {/* 移动端遮罩 */}
      {sidebarOpen && (
        <div className="fade-in fixed inset-0 z-20 bg-ink/50 backdrop-blur-[2px] md:hidden" onClick={() => setSidebarOpen(false)} />
      )}

      {/* 侧栏（桌面常驻，移动抽屉） */}
      <aside
        className={`fixed inset-y-0 left-0 z-30 flex w-[280px] flex-col bg-ink text-white shadow-2xl transition-transform duration-300 ease-out md:static md:translate-x-0 md:shadow-none ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between px-5 py-5">
          <Logo dark size="sm" />
          <button className="rounded-md p-1 text-white/50 transition-colors hover:bg-white/10 hover:text-white md:hidden" onClick={() => setSidebarOpen(false)} aria-label="关闭菜单">
            ✕
          </button>
        </div>
        <div className="px-4">
          <button onClick={newChat} className="btn btn-ghost-dark w-full">
            <span className="text-base leading-none">＋</span> 新对话
          </button>
        </div>
        <div className="mt-6 flex-1 overflow-y-auto px-3 pb-4">
          <p className="px-2 pb-2 text-xs tracking-wide text-white/40">历史提问</p>
          {history.length === 0 && <p className="px-2 text-sm text-white/40">暂无记录</p>}
          {history.map((h) => (
            <div key={h.id} className={`chat-item ${activeId === h.id ? "active" : ""}`} onClick={() => openHistory(h)}>
              <p className="truncate text-sm text-white/85">{h.question}</p>
              <p className="mt-0.5 text-xs text-white/40">
                {new Date(h.created_at).toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" })}
              </p>
            </div>
          ))}
        </div>
        <div className="border-t border-white/10 px-5 py-4">
          {user.role === "admin" && (
            <button onClick={() => router.push("/admin")} className="mb-2 w-full text-left text-sm text-vermilion transition-colors hover:text-white">
              管理后台 →
            </button>
          )}
          <div className="flex items-center justify-between gap-2">
            <span className="flex min-w-0 items-center gap-2 text-sm text-white/70">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-vermilion/90 text-xs font-semibold text-white">
                {user.username.slice(0, 1).toUpperCase()}
              </span>
              <span className="truncate">{user.username}</span>
            </span>
            <button
              onClick={() => {
                logout();
                router.replace("/login");
              }}
              className="shrink-0 rounded-md px-2 py-1 text-xs text-white/50 transition-colors hover:bg-white/10 hover:text-white"
            >
              退出
            </button>
          </div>
        </div>
      </aside>

      {/* 主区域 */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="header-blur sticky top-0 z-10 flex items-center gap-3 border-b border-mist px-5 py-3.5">
          <button className="rounded-md p-1 text-xl leading-none text-ink transition-colors hover:bg-mist md:hidden" onClick={() => setSidebarOpen(true)} aria-label="打开菜单">
            ☰
          </button>
          <h1 className="font-serif text-lg font-semibold tracking-tight">法律咨询</h1>
        </header>

        {/* 消息流 */}
        <div className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
          <div className="mx-auto max-w-3xl">
            {messages.length === 0 && <EmptyState title="请输入您的法律问题" hint="例如：劳动合同试用期最长多久？" />}
            {messages.map((m, i) =>
              m.role === "user" ? (
                <div key={i} className="page-enter mb-6 flex items-end justify-end gap-2.5">
                  <div className="bubble-user max-w-[85%] px-4 py-3 text-[0.9375rem] leading-[1.7] md:max-w-[70%]">
                    {m.content}
                  </div>
                  <span className="mb-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-ink text-xs font-semibold text-white shadow-sm">
                    {user.username.slice(0, 1).toUpperCase()}
                  </span>
                </div>
              ) : (
                <div key={i} className="page-enter mb-6 flex items-start justify-start gap-2.5">
                  <span className="logo-seal mt-0.5 h-8 w-8 shrink-0 text-sm">§</span>
                  <div
                    className={`bubble-ai max-w-[85%] whitespace-pre-wrap px-5 py-4 text-[0.9375rem] leading-[1.75] text-ink md:max-w-[80%] ${
                      streaming && i === messages.length - 1 && m.content ? "streaming-cursor" : ""
                    }`}
                  >
                    {m.content ||
                      (streaming && i === messages.length - 1 ? (
                        <span className="text-slate">
                          正在检索法律条文
                          <span className="typing-dots">
                            <i /><i /><i />
                          </span>
                        </span>
                      ) : (
                        ""
                      ))}
                  </div>
                </div>
              )
            )}
            <div ref={bottomRef} />
          </div>
        </div>

        {/* 输入区 */}
        <form onSubmit={send} className="border-t border-mist bg-paper px-4 py-4 md:px-8">
          <div className="mx-auto flex max-w-3xl items-center gap-3">
            <input
              className="input flex-1 !rounded-full bg-parchment !py-3"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="请输入您的法律问题…"
              disabled={streaming}
            />
            <button
              type="submit"
              disabled={streaming || !input.trim()}
              className="btn btn-primary h-11 w-11 shrink-0 !rounded-full !p-0"
              aria-label="发送"
            >
              {streaming ? (
                <Spinner />
              ) : (
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="7" y1="17" x2="17" y2="7" />
                  <polyline points="7 7 17 7 17 17" />
                </svg>
              )}
            </button>
          </div>
          <p className="mx-auto mt-2 max-w-3xl text-center text-xs text-slate/70">回答仅供参考，不构成正式法律意见</p>
        </form>
      </div>
    </div>
  );
}
