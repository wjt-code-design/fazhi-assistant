"use client";
import { useEffect, useRef, useState, FormEvent, ClipboardEvent, DragEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { streamChat, convApi, loadMediaSrc, ChatMeta, feedbackApi } from "@/lib/api";
import { Logo, Spinner, EmptyState } from "@/components/ui";

interface Msg {
  role: "user" | "assistant";
  content: string;
  imageDataURL?: string; // 本轮刚发送的本地预览
  imgRef?: string; // 历史：原图相对路径
  thumbRef?: string; // 历史：缩略图相对路径
}

interface ConvItem {
  id: number;
  title: string;
  preview: string;
  message_count: number;
  has_image: boolean;
  last_active_at?: string;
  created_at: string;
}

const MAX_IMAGE_MB = 5;
const ACCEPT_IMAGE = ["image/jpeg", "image/png"];

function ChatImage({ dataURL, imgRef, thumbRef }: { dataURL?: string; imgRef?: string; thumbRef?: string }) {
  const [src, setSrc] = useState<string | undefined>(dataURL);
  useEffect(() => {
    if (dataURL) {
      setSrc(dataURL);
      return;
    }
    const ref = thumbRef || imgRef;
    if (!ref) return;
    let alive = true;
    loadMediaSrc(ref).then((u) => {
      if (alive && u) setSrc(u);
    });
    return () => {
      alive = false;
    };
  }, [dataURL, imgRef, thumbRef]);
  if (!src) return null;
  return <img src={src} alt="附图" className="mt-1 max-h-56 rounded-lg border border-mist object-contain" />;
}

export default function ChatPage() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const [history, setHistory] = useState<ConvItem[]>([]);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [input, setInput] = useState("");
  const [pendingImage, setPendingImage] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [isNearBottom, setIsNearBottom] = useState(true);
  const fileRef = useRef<HTMLInputElement>(null);
  const [corrFor, setCorrFor] = useState<number | null>(null);
  const [corrText, setCorrText] = useState("");
  const [fbDone, setFbDone] = useState<Record<number, "up" | "down">>({});

  useEffect(() => {
    if (!loading) {
      if (!user) router.replace("/login");
    }
  }, [loading, user, router]);

  const loadHistory = () => {
    convApi.list().then(setHistory).catch(() => {});
  };
  useEffect(() => {
    if (user) loadHistory();
  }, [user]);

  // 自动滚动到底部：只在用户贴近底部时跟随（不打断向上阅读）；
  // 流式输出期间用即时滚动（避免 smooth 平滑动画"追着文字跑"的卡顿）
  useEffect(() => {
    const el = scrollRef.current;
    if (!el || !isNearBottom) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const behavior: ScrollBehavior = reduced || streaming ? "auto" : "smooth";
    el.scrollTo({ top: el.scrollHeight, behavior });
  }, [messages, isNearBottom, streaming]);

  if (loading || !user) return null;

  function newChat() {
    setMessages([]);
    setConversationId(null);
    setActiveId(null);
    setInput("");
    setPendingImage(null);
    setSidebarOpen(false);
    setIsNearBottom(true);
  }

  async function selectConv(item: ConvItem) {
    setActiveId(item.id);
    setConversationId(item.id);
    setPendingImage(null);
    setSidebarOpen(false);
    try {
      const det = await convApi.detail(item.id);
      setMessages(
        (det.messages || []).map((m: any) => ({
          role: m.role === "user" ? "user" : "assistant",
          content: m.content || "",
          imgRef: m.image_ref || undefined,
          thumbRef: m.thumb_ref || undefined,
        }))
      );
      setIsNearBottom(true);
    } catch {
      setMessages([]);
    }
  }

  function acceptImageFile(file: File) {
    if (!ACCEPT_IMAGE.includes(file.type)) {
      alert("仅支持 JPEG / PNG 图片");
      return;
    }
    if (file.size > MAX_IMAGE_MB * 1024 * 1024) {
      alert(`图片不能超过 ${MAX_IMAGE_MB}MB`);
      return;
    }
    const reader = new FileReader();
    reader.onload = () => setPendingImage(reader.result as string);
    reader.readAsDataURL(file);
  }

  function onPaste(e: ClipboardEvent) {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (const it of Array.from(items)) {
      if (it.kind === "file" && ACCEPT_IMAGE.includes(it.type)) {
        const f = it.getAsFile();
        if (f) {
          e.preventDefault();
          acceptImageFile(f);
          return;
        }
      }
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    const f = e.dataTransfer?.files?.[0];
    if (f && ACCEPT_IMAGE.includes(f.type)) acceptImageFile(f);
  }

  async function send(e?: FormEvent) {
    e?.preventDefault();
    const text = input.trim();
    if ((!text && !pendingImage) || streaming) return;
    const userMsg: Msg = {
      role: "user",
      content: text || "[图片]",
      imageDataURL: pendingImage || undefined,
    };
    const aiMsg: Msg = { role: "assistant", content: "" };
    setMessages((m) => [...m, userMsg, aiMsg]);
    const imageToSend = pendingImage;
    setInput("");
    setPendingImage(null);
    setStreaming(true);

    let acc = "";
    await streamChat(
      { conversationId, content: text, image: imageToSend || undefined },
      (chunk) => {
        acc += chunk;
        setMessages((m) => {
          const copy = [...m];
          copy[copy.length - 1] = { ...copy[copy.length - 1], content: acc };
          return copy;
        });
      },
      (meta: ChatMeta) => {
        if (meta.conversation_id != null) {
          setConversationId(meta.conversation_id);
          setActiveId(meta.conversation_id);
        }
      },
      (err) => {
        setMessages((m) => {
          const copy = [...m];
          copy[copy.length - 1] = { ...copy[copy.length - 1], content: `出错了：${err}` };
          return copy;
        });
      }
    );
    setStreaming(false);
    loadHistory();
  }

  async function sendFeedback(i: number, rating: "up" | "down", correction?: string) {
    const ai = messages[i];
    const prev = messages[i - 1];
    const question = prev && prev.role === "user" ? (prev.content === "[图片]" ? "[图片]" : prev.content) : "";
    try {
      await feedbackApi.post({
        conversation_id: conversationId,
        question: question || "(无)",
        answer: ai.content,
        rating,
        correction: correction || undefined,
      });
      setFbDone((s) => ({ ...s, [i]: rating }));
      setCorrFor(null);
      setCorrText("");
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="flex h-screen overflow-hidden">
      {sidebarOpen && (
        <div className="fade-in fixed inset-0 z-20 bg-ink/50 backdrop-blur-[2px] md:hidden" onClick={() => setSidebarOpen(false)} />
      )}

      {/* 侧栏：历史会话 */}
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
          <p className="px-2 pb-2 text-xs tracking-wide text-white/40">历史会话</p>
          {history.length === 0 && <p className="px-2 text-sm text-white/40">暂无记录</p>}
          {history.map((h) => (
            <div key={h.id} className={`chat-item ${activeId === h.id ? "active" : ""}`} onClick={() => selectConv(h)}>
              <p className="flex items-center gap-1.5 truncate text-sm text-white/85">
                {h.has_image && <span className="text-white/50">🖼</span>}
                {h.title || h.preview || "新对话"}
              </p>
              <p className="mt-0.5 truncate text-xs text-white/40">{h.preview}</p>
            </div>
          ))}
        </div>
        <div className="border-t border-white/10 px-5 py-4">
          {user.role === "admin" && (
            <button onClick={() => router.push("/admin")} className="mb-2 w-full text-left text-sm text-accent transition-colors hover:text-white">
              管理后台 →
            </button>
          )}
          <div className="flex items-center justify-between gap-2">
            <span className="flex min-w-0 items-center gap-2 text-sm text-white/70">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent/90 text-xs font-semibold text-white">
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
        <div
          ref={scrollRef}
          className="scroll-contain flex-1 overflow-y-auto px-4 py-6 md:px-8"
          onScroll={(e) => {
            const el = e.currentTarget;
            setIsNearBottom(el.scrollHeight - el.scrollTop - el.clientHeight < 80);
          }}
          onDrop={onDrop}
          onDragOver={(e) => e.preventDefault()}
        >
          <div className="mx-auto max-w-3xl">
            {messages.length === 0 && <EmptyState title="请输入您的法律问题" hint="支持文字、粘贴或拖拽图片；可连续追问" />}
            {messages.map((m, i) =>
              m.role === "user" ? (
                <div key={i} className="page-enter mb-6 flex items-end justify-end gap-2.5">
                  <div className="bubble-user max-w-[85%] px-4 py-3 text-[0.9375rem] leading-[1.7] md:max-w-[70%]">
                    {m.content && m.content !== "[图片]" && <span className="whitespace-pre-wrap">{m.content}</span>}
                    <ChatImage dataURL={m.imageDataURL} imgRef={m.imgRef} thumbRef={m.thumbRef} />
                  </div>
                  <span className="mb-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-ink text-xs font-semibold text-white shadow-sm">
                    {user.username.slice(0, 1).toUpperCase()}
                  </span>
                </div>
              ) : (
                <div key={i} className="page-enter mb-6 flex items-start justify-start gap-2.5">
                  <span className="logo-seal mt-0.5 h-8 w-8 shrink-0 text-sm">§</span>
                  <div className="max-w-[85%] md:max-w-[80%]">
                    <div
                      className={`bubble-ai whitespace-pre-wrap px-5 py-4 text-[0.9375rem] leading-[1.75] text-ink ${
                        streaming && i === messages.length - 1 && m.content ? "streaming-cursor" : ""
                      }`}
                    >
                      {m.content ||
                        (streaming && i === messages.length - 1 ? (
                          <span className="text-slate">
                            正在检索法律条文
                            <span className="typing-dots">
                              <i />
                              <i />
                              <i />
                            </span>
                          </span>
                        ) : (
                          ""
                        ))}
                    </div>
                    {!streaming && m.content && (
                      <div className="mt-2">
                        <div className="flex items-center gap-2 text-slate">
                          <button type="button" onClick={() => sendFeedback(i, "up")} disabled={!!fbDone[i]} className={`rounded px-1.5 text-sm transition-colors ${fbDone[i] === "up" ? "text-jade" : "hover:text-ink"}`} aria-label="有帮助" title="有帮助">👍</button>
                          <button type="button" onClick={() => setCorrFor(corrFor === i ? null : i)} disabled={!!fbDone[i]} className={`rounded px-1.5 text-sm transition-colors ${fbDone[i] === "down" ? "text-error" : "hover:text-ink"}`} aria-label="不准确" title="不准确 / 纠错">👎</button>
                          {fbDone[i] && <span className="text-xs text-jade">已记录，谢谢反馈</span>}
                        </div>
                        {corrFor === i && (
                          <div className="mt-2 space-y-2">
                            <textarea className="input min-h-[64px]" placeholder="可选：写出你认为正确的答案或指出错误…" value={corrText} onChange={(e) => setCorrText(e.target.value)} />
                            <div className="flex gap-2">
                              <button type="button" onClick={() => sendFeedback(i, "down", corrText)} className="btn btn-primary !px-3 !py-1 text-xs">提交纠错</button>
                              <button type="button" onClick={() => sendFeedback(i, "down", "")} className="btn btn-secondary !px-3 !py-1 text-xs">仅标记不准</button>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )
            )}
            <div ref={bottomRef} />
          </div>
        </div>

        {/* 输入区 */}
        <form onSubmit={send} className="border-t border-mist bg-paper px-4 py-4 md:px-8">
          <div className="mx-auto max-w-3xl">
            {pendingImage && (
              <div className="mb-2 inline-flex items-center gap-2 rounded-lg border border-mist bg-parchment p-1.5">
                <img src={pendingImage} alt="待发送" className="h-12 w-12 rounded object-cover" />
                <button type="button" onClick={() => setPendingImage(null)} className="rounded px-1.5 text-slate hover:text-error" aria-label="移除图片">
                  ✕
                </button>
              </div>
            )}
            <div className="flex items-center gap-2">
              <input ref={fileRef} type="file" accept="image/jpeg,image/png" className="hidden" onChange={(e) => e.target.files?.[0] && acceptImageFile(e.target.files[0])} />
              <button
                type="button"
                onClick={() => fileRef.current?.click()}
                disabled={streaming}
                className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-mist text-slate transition-colors hover:bg-mist hover:text-ink disabled:opacity-50"
                aria-label="上传图片"
                title="上传图片（JPEG/PNG，≤5MB）"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                  <circle cx="8.5" cy="8.5" r="1.5" />
                  <polyline points="21 15 16 10 5 21" />
                </svg>
              </button>
              <textarea
                className="input flex-1 !rounded-[6px] !py-3 resize-none max-h-[160px]"
                rows={2}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && e.ctrlKey) send();  // Enter 换行，Ctrl+Enter 发送
                }}
                onPaste={onPaste}
                placeholder="请输入您的法律问题…（Enter 换行，Ctrl+Enter 发送；可粘贴/拖拽图片，支持连续追问）"
                disabled={streaming}
              />
              <button
                type="submit"
                disabled={streaming || (!input.trim() && !pendingImage)}
                className="btn btn-primary h-11 w-11 shrink-0 !rounded-[6px] !p-0"
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
            <p className="mt-2 text-center text-xs text-slate/70">回答仅供参考，不构成正式法律意见</p>
          </div>
        </form>
      </div>
    </div>
  );
}
