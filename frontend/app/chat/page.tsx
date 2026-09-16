"use client";
// T2.2 拆分（区块渲染在 @/components/chat/*）+ T2.3 状态收敛（流式/会话/反馈/语音在 lib/hooks/*）。
// page 仅保留：页面级 UI 态、数据编排回调、effects 与组装 JSX。行为零变更。
import { useEffect, useRef, useState, FormEvent, ClipboardEvent, DragEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { chatFile, API_URL } from "@/lib/api";
import { usePointerGlow } from "@/lib/usePointerGlow";
import { buildScopeAnswer, SCOPE_MAX_SELECTION } from "@/lib/scope";
import type { QuotaWarn, FileInfo } from "@/lib/types";
import { useChatStream } from "@/lib/hooks/useChatStream";
import { useConversations } from "@/lib/hooks/useConversations";
import { useFeedback } from "@/lib/hooks/useFeedback";
import { useVoice } from "@/lib/hooks/useVoice";
import { useLawCards } from "@/lib/hooks/useLawCards";
import {
  MAX_IMAGE_MB,
  ACCEPT_IMAGE,
  MAX_FILE_MB,
  ACCEPT_FILE,
  DAILY_LAWS,
  dailyLawIndex,
  CODEX,
} from "@/lib/constants";
import { Sidebar } from "@/components/chat/Sidebar";
import { QuotaBanner } from "@/components/chat/QuotaBanner";
import { MessageList } from "@/components/chat/MessageList";
import { InputBar } from "@/components/chat/InputBar";
import { LawPanel } from "@/components/chat/LawPanel";

export default function ChatPage() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  // 能力发现（阶段B 诚实停用）：后端 /api/health 返回所配模型是否具备视觉/语音能力，
  // 缺失则隐藏对应入口（而非展示必然 501 的按钮）。加载失败/未加载时保持展示（fail-open，
  // 提交时仍有后端 501 兜底提示）。
  const [caps, setCaps] = useState<{ image_chat: boolean; voice_transcribe: boolean } | null>(null);
  // B1 方案 A：点选卡片 → 编号列表填入输入框（可手改），仍走现有发送按钮
  const [selectedScope, setSelectedScope] = useState<number[]>([]);
  const [input, setInput] = useState("");
  const [pendingImage, setPendingImage] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [isNearBottom, setIsNearBottom] = useState(true);
  const [fileInfo, setFileInfo] = useState<FileInfo | null>(null);
  const [fileContent, setFileContent] = useState<string | null>(null);
  const [quotaWarn, setQuotaWarn] = useState<QuotaWarn | null>(null);
  const [codexIdx, setCodexIdx] = useState(0); // 流式三态：法典速查字符轮换
  const [dailyIdx, setDailyIdx] = useState(dailyLawIndex()); // 每日法条轮播索引

  // ---------- T2.3 状态收敛 hooks ----------
  const { expandedLaw, toggleInlineLaw, clearExpandedLaw } = useLawCards();
  // useChatStream 需要会话切片的 setActiveId/loadHistory（原 doSend 内联调用）。
  // hooks 间不能相互引用未创建的值 → 以 ref 桥接、每渲染 effect 绑定；
  // doSend 仅在挂载后的用户动作中触发，绑定时序与原实现一致。
  const lateRef = useRef<{ sync: (id: number) => void; refresh: () => void } | null>(null);
  const stream = useChatStream({
    onConversationId: (id) => lateRef.current?.sync(id),
    onStreamEnd: () => lateRef.current?.refresh(),
  });
  const { messages, setMessages, streaming } = stream;
  const feedback = useFeedback({ messages, conversationId: stream.conversationId });
  const { fbDone, corrFor, corrText, setCorrFor, setCorrText, sendFeedback } = feedback;
  const conversations = useConversations({
    user,
    streaming,
    setMessages,
    setConversationId: stream.setConversationId,
    setPendingAgentRun: stream.setPendingAgentRun,
    setClarifyRounds: stream.setClarifyRounds,
    setSelectedScope,
    setInput,
    setPendingImage,
    setSidebarOpen,
    setIsNearBottom,
    clearExpandedLaw,
    resetFeedback: feedback.reset,
  });
  const { history, activeId, loadHistory, newChat, selectConv, deleteConv } = conversations;
  const { listening, transcribing, toggleVoice } = useVoice({ setInput });
  useEffect(() => {
    lateRef.current = { sync: conversations.setActiveId, refresh: loadHistory };
  });
  useEffect(() => {
    // 能力发现：一次性拉取后端能力位（失败静默——fail-open，提交时后端 501 兜底）
    fetch(`${API_URL}/api/health`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => (d?.capabilities ? setCaps(d.capabilities) : null))
      .catch(() => {});
  }, []);
  useEffect(() => {
    if (messages.length !== 0) return; // 只在空状态轮播；开始对话后停止，避免全局重渲染导致法条卡抖动
    // 真随机切换：从 [0, len-1] 中抽一条，且避开当前索引（n>=i 时 +1），避免连续重复
    const t = setInterval(
      () =>
        setDailyIdx((i) => {
          let n = Math.floor(Math.random() * (DAILY_LAWS.length - 1));
          if (n >= i) n++;
          return n;
        }),
      5000
    );
    return () => clearInterval(t);
  }, [messages.length]);
  // 法条速查面板开合（面板内部状态在 LawPanel 组件里）
  const [lawPanel, setLawPanel] = useState(false);
  usePointerGlow(scrollRef); // 指针光晕（仅 hover:hover）

  useEffect(() => {
    if (!loading) {
      if (!user) router.replace("/login");
    }
  }, [loading, user, router]);

  // 配额预警（B 更优版）：embedding 快用完/耗尽 + rerank 降级 → 顶部横幅（提前量）
  // 与能力发现一致用 API_URL 前缀（dev 直连 backend；相对路径在 next dev 会 404 → 横幅永不显示，P2-1）
  useEffect(() => {
    fetch(`${API_URL}/api/utility/quota`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setQuotaWarn(d))
      .catch(() => {});
  }, []);

  // 流式三态·检索期：法典速查字符轮换（streaming 且尚未输出时）
  useEffect(() => {
    if (!streaming) return;
    const t = setInterval(() => setCodexIdx((i) => (i + 1) % CODEX.length), 260);
    return () => clearInterval(t);
  }, [streaming]);

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

  async function handleFileUpload(file: File) {
    const ext = "." + (file.name.split(".").pop() || "").toLowerCase();
    if (!ACCEPT_FILE.includes(ext)) {
      alert("仅支持 txt / md / pdf / docx 文件");
      return;
    }
    if (file.size > MAX_FILE_MB * 1024 * 1024) {
      alert(`文件不能超过 ${MAX_FILE_MB}MB`);
      return;
    }
    try {
      const res = await chatFile(file);
      setFileInfo({ name: res.file_name, chars: res.chars, truncated: res.truncated });
      setFileContent(res.text);
      setInput(""); // 文件内容作为本轮发送内容，清空手输文本
    } catch (err) {
      alert(`文件解析失败：${err instanceof Error ? err.message : err}`);
    }
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

  // 核心发送逻辑已收敛至 lib/hooks/useChatStream（T2.3，逐行等价搬移）

  function send(e?: FormEvent) {
    e?.preventDefault();
    const text = input.trim();
    const contentToSend = fileContent ?? text;
    if (!contentToSend && !pendingImage) return;
    const display = fileContent
      ? `[文件：${fileInfo?.name ?? "已上传文件"}（${fileInfo?.chars ?? ""}字）]`
      : undefined;
    const imageToSend = pendingImage;
    const truncated = fileInfo?.truncated || undefined; // 文件上传超长截断信号穿透
    setInput("");
    setPendingImage(null);
    setFileContent(null);
    setFileInfo(null);
    stream.doSend(contentToSend, imageToSend, display, truncated);
  }

  // 空状态快捷提问（场景直达 / 每日法条）：直接发，不走输入框
  function quickSend(q: string) {
    if (streaming) return;
    setSidebarOpen(false);
    stream.doSend(q);
  }

  // B1 方案 A：点选卡片 → 编号列表填入输入框（可手改），仍走现有发送按钮。
  // 边界：达上限 5 个后拒绝切换（输入框不动）；清空选择 → 重置 selectedScope + 输入框。
  // 用组件作用域的 selectedScope 直接计算 next（避免 updater 内 setState，审查偏差修正）。
  function toggleScope(n: number) {
    const has = selectedScope.includes(n);
    if (!has && selectedScope.length >= SCOPE_MAX_SELECTION) return;
    const next = has ? selectedScope.filter((x) => x !== n) : [...selectedScope, n];
    setSelectedScope(next);
    setInput(next.length ? buildScopeAnswer(next) : "");
  }

  // ---------- 法条卡逻辑已收敛至 lib/hooks/useLawCards（T2.3，逐行等价搬移） ----------
  // 法条内联卡纯函数（escapeHtmlText/buildLawCardHtml/injectLawCardHtml）已迁至
  // components/chat/lawCardHtml.ts，供 MessageHtml memo 使用；removeUnprovidedHint 已删
  // （B1 后端保证库内不产矛盾句）。

  // sendFeedback 已收敛至 lib/hooks/useFeedback（T2.3，逐行等价搬移），经 feedback 解构使用

  return (
    <div className="app-shell flex overflow-hidden">
      <Sidebar
        open={sidebarOpen}
        history={history}
        activeId={activeId}
        streaming={streaming}
        user={user}
        onClose={() => setSidebarOpen(false)}
        onNewChat={newChat}
        onSelectConv={selectConv}
        onDeleteConv={(id) => void deleteConv(id)}
        onLogout={() => {
          logout();
          router.replace("/login");
        }}
        router={router}
      />

      {/* 主区域 */}
      <div className="relative flex min-w-0 flex-1 flex-col">
        <header className="header-blur sticky top-0 z-10 flex items-center gap-3 border-b border-mist px-5 py-3.5">
          <button
            className="rounded-md p-1 text-xl leading-none text-ink transition-colors hover:bg-mist md:hidden"
            onClick={() => setSidebarOpen(true)}
            aria-label="打开菜单"
          >
            ☰
          </button>
          <h1 className="font-serif text-lg font-semibold tracking-tight">法律咨询</h1>
        </header>

        <QuotaBanner quotaWarn={quotaWarn} />

        {/* 消息流 */}
        <div
          ref={scrollRef}
          className="scroll-contain pointer-glow flex-1 overflow-y-auto px-4 py-6 md:px-8"
          onScroll={(e) => {
            const el = e.currentTarget;
            setIsNearBottom(el.scrollHeight - el.scrollTop - el.clientHeight < 80);
          }}
          onDrop={onDrop}
          onDragOver={(e) => e.preventDefault()}
          onClick={(e) => {
            // 法条卡：点击 → 在该法条下一行内联展开 / 收起
            const ref = (e.target as Element).closest(".law-ref");
            if (!ref) return;
            const msgEl = ref.closest("[data-msg-index]");
            if (!msgEl) return; // 不在回答消息内（如每日法条）→ 交给原按钮行为
            const msgIndex = Number(msgEl.getAttribute("data-msg-index"));
            e.preventDefault();
            e.stopPropagation();
            void toggleInlineLaw(ref, msgIndex);
          }}
        >
          <MessageList
            messages={messages}
            username={user.username}
            streaming={streaming}
            expandedLaw={expandedLaw}
            fbDone={fbDone}
            corrFor={corrFor}
            corrText={corrText}
            codexIdx={codexIdx}
            selectedScope={selectedScope}
            history={history}
            dailyIdx={dailyIdx}
            onToggleScope={toggleScope}
            onClearScope={() => {
              setSelectedScope([]);
              setInput("");
            }}
            onFeedbackUp={(i) => void sendFeedback(i, "up")}
            onFeedbackDown={(i, correction) => void sendFeedback(i, "down", correction)}
            onCorrForChange={setCorrFor}
            onCorrTextChange={setCorrText}
            onQuickSend={quickSend}
            onSelectConv={selectConv}
            onOpenLawPanel={() => setLawPanel(true)}
          />
        </div>

        {/* 回到最新消息：向上翻阅历史时出现，一键平滑滚到底部 */}
        {!isNearBottom && messages.length > 0 && (
          <button
            type="button"
            onClick={() => {
              const el = scrollRef.current;
              if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
              setIsNearBottom(true);
            }}
            className="absolute bottom-28 right-5 z-20 flex items-center gap-1.5 rounded-full border border-white/70 bg-white/85 px-3.5 py-2 text-xs font-medium text-ink shadow-lg backdrop-blur-md transition-all duration-200 hover:-translate-y-0.5 hover:bg-white md:right-8"
            aria-label="回到最新消息"
          >
            <svg
              className="h-3.5 w-3.5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <line x1="12" y1="5" x2="12" y2="19" />
              <polyline points="19 12 12 19 5 12" />
            </svg>
            最新
          </button>
        )}

        <InputBar
          input={input}
          onInputChange={setInput}
          streaming={streaming}
          pendingImage={pendingImage}
          onRemoveImage={() => setPendingImage(null)}
          fileInfo={fileInfo}
          fileContent={fileContent}
          onRemoveFile={() => {
            setFileInfo(null);
            setFileContent(null);
          }}
          caps={caps}
          listening={listening}
          transcribing={transcribing}
          onToggleVoice={() => void toggleVoice()}
          onPickImageFile={acceptImageFile}
          onPickFile={(f) => void handleFileUpload(f)}
          onPaste={onPaste}
          onSubmit={send}
        />

        <LawPanel open={lawPanel} onClose={() => setLawPanel(false)} />
      </div>
    </div>
  );
}
