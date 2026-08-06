"use client";
import { useEffect, useLayoutEffect, useRef, useState, FormEvent, ClipboardEvent, DragEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { streamChat, convApi, loadMediaSrc, chatFile, ChatMeta, AnalysisStep, feedbackApi, lawApi, LawDetail, LawItem, transcribeApi } from "@/lib/api";
import { Logo, Spinner } from "@/components/ui";
import { annotate, stripMarkdown } from "@/lib/annotate";
import { startWavRecorder } from "@/lib/recorder";
import { LawCard } from "@/components/LawCard";
import { useHoverCapable } from "@/lib/usePointer";
import { usePointerGlow } from "@/lib/usePointerGlow";

interface Msg {
  role: "user" | "assistant";
  content: string;
  imageDataURL?: string; // 本轮刚发送的本地预览
  imgRef?: string; // 历史：原图相对路径
  thumbRef?: string; // 历史：缩略图相对路径
  sources?: { source: string; article: string }[]; // 参考条文（ADR-012 阶段2C：回答下方折叠展示）
  steps?: AnalysisStep[]; // 合同评估分析进度（SSE step 事件）
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

// 配额预警（B 更优版，grilling）：/api/utility/quota 公开接口的响应
interface QuotaWarn {
  embedding_warn?: boolean;
  embedding_depleted?: boolean;
  embedding_pct?: number;
  embedding_model?: string;
  rerank_degraded?: boolean;
}

const MAX_IMAGE_MB = 5;
const ACCEPT_IMAGE = ["image/jpeg", "image/png"];
const MAX_FILE_MB = 10; // 与后端 _MAX_UPLOAD_BYTES 一致
const ACCEPT_FILE = [".txt", ".md", ".pdf", ".docx"];

interface FileInfo {
  name: string;
  chars: number;
  truncated: boolean;
}

// 空状态：场景直达卡
const SCENES = [
  { icon: "📄", title: "审合同", desc: "贴 / 传 / 拍合同", q: "请帮我审查这份合同的风险点" },
  { icon: "📚", title: "法考答题", desc: "刷题对答案", q: "帮我解答一道法考选择题" },
  { icon: "💰", title: "被拖欠工资", desc: "劳动维权", q: "公司拖欠我三个月工资，该怎么维权？" },
  { icon: "⚖️", title: "离婚财产分割", desc: "婚姻家事", q: "离婚时财产分割有哪些规定？" },
];
// 空状态：每日法条（前端硬编码高频常识，随机一条；点击提问走正常管线）
const DAILY_LAWS = [
  { src: "劳动合同法", art: "第十九条", text: "试用期最长不得超过六个月", q: "劳动合同试用期最长是多久？" },
  { src: "民法典", art: "第五百八十五条", text: "违约金过分高于损失可请求法院调减", q: "违约金太高可以要求降低吗？" },
  { src: "民法典", art: "第一百八十八条", text: "普通诉讼时效为三年", q: "普通诉讼时效是几年？" },
  { src: "劳动法", art: "第四十四条", text: "安排延长工作时间应支付加班费", q: "加班费怎么计算？" },
];
// 流式三态：法典速查字符（检索期轮换）
const CODEX = ["§", "¶", "†", "‡"];

// 法条卡缓存：同「书名+条号」只请求一次后端（防 hover 重复请求 / 乱序覆盖）
const lawCache = new Map<string, Promise<LawDetail | null>>();

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
  const imageInputRef = useRef<HTMLInputElement>(null); // 图片选择
  const fileInputRef = useRef<HTMLInputElement>(null); // 文件（txt/pdf/docx）选择
  const [fileInfo, setFileInfo] = useState<FileInfo | null>(null);
  const [fileContent, setFileContent] = useState<string | null>(null);
  const [listening, setListening] = useState(false); // 语音输入（Web Speech API）录音中
  const recRef = useRef<{ stop: () => void } | null>(null);
  const [corrFor, setCorrFor] = useState<number | null>(null);
  const [corrText, setCorrText] = useState("");
  const [fbDone, setFbDone] = useState<Record<number, "up" | "down">>({});
  const [quotaWarn, setQuotaWarn] = useState<QuotaWarn | null>(null);
  const [codexIdx, setCodexIdx] = useState(0); // 流式三态：法典速查字符轮换
  const [dailyLaw] = useState(() => DAILY_LAWS[Math.floor(Math.random() * DAILY_LAWS.length)]); // 每日法条（固定一次）
  // 法条速查面板 + 法条悬浮卡（P1）
  const [lawPanel, setLawPanel] = useState(false);
  const [lawQ, setLawQ] = useState("");
  const [lawResults, setLawResults] = useState<LawItem[]>([]);
  const [lawDetail, setLawDetail] = useState<LawDetail | null>(null);
  const [lawPopup, setLawPopup] = useState<{
    law: LawDetail;
    left: number;
    top: number;
    width: number;
    flipped: boolean;
  } | null>(null);
  const popupNodeRef = useRef<HTMLDivElement>(null);
  const popupRefEl = useRef<Element | null>(null); // 当前 hover 的 .law-ref
  const openTimer = useRef<number | null>(null); // hover 进入延迟
  const hideTimer = useRef<number | null>(null); // 离开宽限
  const popupSeq = useRef(0); // 请求序号，防乱序覆盖
  const hoverCapable = useHoverCapable(); // 桌面纯鼠标 → hover；触屏/Mac 触控板 → click
  usePointerGlow(scrollRef); // 指针光晕（仅 hover:hover）

  // 语音（M2）：Qwen livetranslate 后端转写，Web Speech 兜底
  const [transcribing, setTranscribing] = useState(false);
  const wavRecRef = useRef<{ stop: () => Promise<Blob> } | null>(null);
  const voiceTimeoutRef = useRef<number | null>(null);

  // 浮层渲染后量高：下方空间不足则翻到 ref 上方（上下自适应）。
  // 注意：必须放在上方 `if (loading || !user) return null;` 之前——hook 不能被提前 return 跳过，
  // 否则认证通过后 hook 数变化，React 抛「Rendered more hooks than during the previous render」。
  useLayoutEffect(() => {
    const node = popupNodeRef.current;
    if (!lawPopup || !node || lawPopup.flipped) return;
    const c = scrollRef.current;
    if (!c) return;
    const h = node.offsetHeight;
    const spaceBelow = c.clientHeight - lawPopup.top;
    if (spaceBelow < h + 8 && popupRefEl.current) {
      const cr = c.getBoundingClientRect();
      const refTop = popupRefEl.current.getBoundingClientRect().top - cr.top + c.scrollTop;
      setLawPopup((p) => (p ? { ...p, top: Math.max(8, refTop - h - 8), flipped: true } : p));
    }
  }, [lawPopup]);

  useEffect(() => {
    if (!loading) {
      if (!user) router.replace("/login");
    }
  }, [loading, user, router]);

  // 配额预警（B 更优版）：embedding 快用完/耗尽 + rerank 降级 → 顶部横幅（提前量）
  useEffect(() => {
    fetch("/api/utility/quota")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setQuotaWarn(d))
      .catch(() => {});
  }, []);

  const loadHistory = () => {
    convApi.list().then(setHistory).catch(() => {});
  };
  useEffect(() => {
    if (user) loadHistory();
  }, [user]);

  // 流式三态·检索期：法典速查字符轮换（streaming 且尚未输出时）
  useEffect(() => {
    if (!streaming) return;
    const t = setInterval(() => setCodexIdx((i) => (i + 1) % CODEX.length), 260);
    return () => clearInterval(t);
  }, [streaming]);

  // 卸载清理：法条卡定时器 + 语音超时
  useEffect(() => {
    return () => {
      if (openTimer.current) clearTimeout(openTimer.current);
      if (hideTimer.current) clearTimeout(hideTimer.current);
      if (voiceTimeoutRef.current) clearTimeout(voiceTimeoutRef.current);
    };
  }, []);

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
    clearLawPopup();
  }

  async function selectConv(item: ConvItem) {
    setActiveId(item.id);
    setConversationId(item.id);
    setPendingImage(null);
    setSidebarOpen(false);
    clearLawPopup();
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

  // 删除历史对话（M5）：后端 DELETE /api/conversations/{id} 已就绪，前端接线
  async function deleteConv(id: number) {
    if (!window.confirm("确定删除这个对话吗？删除后不可恢复。")) return;
    try {
      await convApi.remove(id);
      if (activeId === id) {
        setMessages([]);
        setConversationId(null);
        setActiveId(null);
        clearLawPopup();
      }
      loadHistory();
    } catch {
      alert("删除失败，请重试");
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

  async function toggleVoice() {
    // 语音转文字（M2）：优先后端 Qwen livetranslate 语音模型转写（麦克风录音→WAV→上传，
    // 识别质量优于浏览器 Web Speech）；失败/无麦克风权限 → 回退浏览器 Web Speech。
    if (listening) {
      const w = wavRecRef.current;
      wavRecRef.current = null;
      if (voiceTimeoutRef.current) clearTimeout(voiceTimeoutRef.current);
      setListening(false);
      if (w) {
        const blob = await w.stop();
        void transcribeAndFill(blob);
      }
      return;
    }
    if (window.AudioContext) {
      try {
        // getUserMedia 缺失会在此抛错，被 catch 兜底回退 Web Speech
        wavRecRef.current = await startWavRecorder();
        // 60s 自动停止并转写
        voiceTimeoutRef.current = window.setTimeout(() => {
          const w = wavRecRef.current;
          if (w) {
            wavRecRef.current = null;
            setListening(false);
            void w.stop().then(transcribeAndFill).catch(() => {});
          }
        }, 60000);
        setListening(true);
        return;
      } catch {
        // 麦克风权限拒绝等 → 回退 Web Speech
      }
    }
    legacyWebSpeech();
  }

  async function transcribeAndFill(blob: Blob) {
    setTranscribing(true);
    try {
      const r = await transcribeApi.post(blob);
      setInput((prev) => (prev ? prev + r.text : r.text));
    } catch (err) {
      alert(`语音转写失败（${err instanceof Error ? err.message : err}），已回退浏览器识别`);
      legacyWebSpeech();
    } finally {
      setTranscribing(false);
    }
  }

  function legacyWebSpeech() {
    // 兜底：浏览器 Web Speech API（zh-CN 连续识别）
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) {
      alert("当前浏览器不支持语音输入，请用 Chrome 或 Edge");
      return;
    }
    if (listening) {
      recRef.current?.stop();
      setListening(false);
      return;
    }
    const rec = new SR();
    rec.lang = "zh-CN";
    rec.continuous = true;
    rec.interimResults = true;
    recRef.current = rec;
    rec.onresult = (e: any) => {
      let text = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        text += e.results[i][0].transcript;
      }
      setInput((prev) => (prev ? prev + text : text));
    };
    rec.onend = () => setListening(false);
    rec.onerror = () => {
      setListening(false);
      alert("语音识别失败，请检查麦克风权限后重试");
    };
    rec.start();
    setListening(true);
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

  // 核心发送：普通 send 与空状态快捷提问共用（streamChat 回调原样，零逻辑改动）
  async function doSend(contentText: string, image?: string | null, display?: string, truncated?: boolean) {
    if ((!contentText && !image) || streaming) return;
    const userMsg: Msg = {
      role: "user",
      content: display || contentText || "[图片]",
      imageDataURL: image || undefined,
    };
    const aiMsg: Msg = { role: "assistant", content: "" };
    setMessages((m) => [...m, userMsg, aiMsg]);
    setStreaming(true);

    let acc = "";
    await streamChat(
      {
        conversationId,
        content: contentText,
        image: image || undefined,
        truncated,
      },
      (chunk) => {
        acc += chunk;
        setMessages((m) => {
          const copy = [...m];
          copy[copy.length - 1] = { ...copy[copy.length - 1], content: acc };
          return copy;
        });
      },
      (meta: ChatMeta) => {
        setMessages((m) => {
          const copy = [...m];
          const last = copy[copy.length - 1];
          if (last && meta.sources?.length) {
            copy[copy.length - 1] = { ...last, sources: meta.sources };
          }
          return copy;
        });
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
      },
      (steps) => {
        // 合同评估分析进度（SSE step 事件）：更新最后一条 AI 消息的步骤区
        setMessages((m) => {
          const copy = [...m];
          const last = copy[copy.length - 1];
          if (last && last.role === "assistant") {
            copy[copy.length - 1] = { ...last, steps };
          }
          return copy;
        });
      }
    );
    setStreaming(false);
    loadHistory();
  }

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
    doSend(contentToSend, imageToSend, display, truncated);
  }

  // 空状态快捷提问（场景直达 / 每日法条）：直接发，不走输入框
  function quickSend(q: string) {
    if (streaming) return;
    setSidebarOpen(false);
    doSend(q);
  }

  // 法条悬浮卡：从 .law-ref 的 data-source（书名，含省略书名号的独立条号）+ 文本条号 → 后端查原文。
  // 带模块级缓存：同条文只发一次请求；失败返回 null（前端降级纯文本）。
  function fetchLawRefCached(el: Element): Promise<LawDetail | null> {
    const src = el.getAttribute("data-source");
    const m = (el.textContent || "").match(/第\s*([一二三四五六七八九十百千零0-9]+)\s*条/);
    if (!src || !m) return Promise.resolve(null);
    const key = `${src}\u0000${m[1]}`;
    let p = lawCache.get(key);
    if (!p) {
      // 库内 article 存完整「第X条」中文条号（精确匹配），必须拼回完整形式，否则数字/缺字 404
      p = lawApi.detail(src, `第${m[1]}条`).catch(() => null);
      lawCache.set(key, p);
    }
    return p;
  }

  // ---------- 法条悬浮卡：位置计算 + hover 防抖/宽限（absolute 锚定在滚动容器内，随内容滚动） ----------
  function placeLawPopup(ref: Element, law: LawDetail) {
    const c = scrollRef.current;
    if (!c) return;
    const cr = c.getBoundingClientRect();
    const rr = ref.getBoundingClientRect();
    const pad = 12;
    const width = Math.min(320, c.clientWidth - pad * 2); // 窄屏自适应
    const gap = 8;
    const left = Math.max(pad, Math.min(rr.left - cr.left + c.scrollLeft, c.clientWidth - width - pad));
    setLawPopup({
      law,
      left,
      top: rr.bottom - cr.top + c.scrollTop + gap, // 默认放 ref 下方
      width,
      flipped: false,
    });
  }

  function clearLawPopup() {
    setLawPopup(null);
  }

  function scheduleLawOpen(ref: Element) {
    if (openTimer.current) clearTimeout(openTimer.current);
    if (hideTimer.current) clearTimeout(hideTimer.current);
    openTimer.current = window.setTimeout(() => {
      void openLawPopup(ref);
    }, 150); // 进入延迟：快速划过不弹
  }

  async function openLawPopup(ref: Element) {
    const seq = ++popupSeq.current;
    const law = await fetchLawRefCached(ref);
    if (seq !== popupSeq.current || popupRefEl.current !== ref) return; // 已移走 / 有更新目标
    if (law) placeLawPopup(ref, law);
    else clearLawPopup();
  }

  function scheduleLawHide() {
    if (openTimer.current) clearTimeout(openTimer.current);
    if (hideTimer.current) clearTimeout(hideTimer.current);
    hideTimer.current = window.setTimeout(() => {
      clearLawPopup();
    }, 300); // 离开宽限：移到浮层上不关闭
  }

  async function toggleLawPopup(ref: Element) {
    // 触屏/Mac 触控板：click toggle（同条再点收起）
    const law = await fetchLawRefCached(ref);
    if (!law) return;
    if (lawPopup && lawPopup.law.source === law.source && lawPopup.law.article === law.article) {
      clearLawPopup();
    } else {
      placeLawPopup(ref, law);
    }
  }

  async function doLawSearch() {
    const q = lawQ.trim();
    if (!q) return;
    try {
      setLawResults(await lawApi.search(q));
      setLawDetail(null);
    } catch {
      setLawResults([]);
    }
  }

  async function openLawDetail(item: LawItem) {
    try {
      setLawDetail(await lawApi.detail(item.source, item.article));
    } catch {
      setLawDetail(null);
    }
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
    <div className="app-shell flex overflow-hidden">
      {sidebarOpen && (
        <div className="fade-in fixed inset-0 z-20 bg-ink/50 backdrop-blur-[2px] md:hidden" onClick={() => setSidebarOpen(false)} />
      )}

      {/* 侧栏：历史会话 */}
      <aside
        className={`sidebar-glow relative fixed inset-y-0 left-0 z-30 flex w-[280px] max-w-[85vw] flex-col bg-ink text-white shadow-2xl transition-transform duration-300 ease-out md:static md:translate-x-0 md:shadow-none ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between px-3 py-5">
          <Logo dark size="sm" />
          <button className="rounded-md p-1 text-white/50 transition-colors hover:bg-white/10 hover:text-white md:hidden" onClick={() => setSidebarOpen(false)} aria-label="关闭菜单">
            ✕
          </button>
        </div>
        <div className="px-3">
          <button onClick={newChat} className="btn btn-ghost-dark w-full">
            <span className="text-base leading-none">＋</span> 新对话
          </button>
        </div>
        <div className="mt-6 flex-1 overflow-y-auto px-3 pb-4">
          <p className="px-2 pb-2 text-xs tracking-wide text-white/40">历史会话</p>
          {history.length === 0 && <p className="px-2 text-sm text-white/40">暂无记录</p>}
          {history.map((h) => (
            <div
              key={h.id}
              className={`chat-item group relative ${activeId === h.id ? "active" : ""}`}
              onClick={() => selectConv(h)}
            >
              <p className="flex items-center gap-1.5 truncate pr-5 text-sm text-white/85">
                {h.has_image && <span className="text-white/50">🖼</span>}
                <span className="truncate">{h.title || h.preview || "新对话"}</span>
              </p>
              <p className="mt-0.5 truncate text-xs text-white/40">{h.preview}</p>
              <button
                type="button"
                aria-label={`删除会话 ${h.title || h.preview || "新对话"}`}
                title="删除会话"
                className="absolute right-1.5 top-1/2 flex h-5 w-5 -translate-y-1/2 items-center justify-center rounded-full text-xs text-white/40 opacity-0 transition-opacity hover:bg-white/15 hover:text-white group-hover:opacity-100"
                onClick={(e) => {
                  e.stopPropagation();
                  void deleteConv(h.id);
                }}
              >
                ✕
              </button>
            </div>
          ))}
        </div>
        <div className="border-t border-white/10 px-3 py-4">
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

        {/* 配额预警横幅（B 更优版）：embedding 快用完/耗尽 或 rerank 已降级 */}
        {quotaWarn && (quotaWarn.embedding_depleted || quotaWarn.embedding_warn || quotaWarn.rerank_degraded) && (
          <div
            className="border-b px-5 py-2 text-xs"
            style={
              quotaWarn.embedding_depleted
                ? { background: "#ef444422", color: "#b91c1c", borderColor: "#ef444455" }
                : { background: "#f59e0b22", color: "#92400e", borderColor: "#f59e0b55" }
            }
          >
            {quotaWarn.embedding_depleted
              ? "⚠ embedding 配额已耗尽，问答暂时不可用——请联系管理员换班（docs/换班手册.md）。"
              : quotaWarn.embedding_warn
                ? `⚠ embedding 配额接近耗尽（剩 ${quotaWarn.embedding_pct}%），建议尽快换班（docs/换班手册.md）。`
                : "⚠ rerank 模型已全部耗尽，自动降级本地精排（排序准度略降）。"}
          </div>
        )}

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
          onPointerOver={(e) => {
            // 法条悬浮卡：桌面 hover（防抖 + 宽限，ref 与浮层同组不闪烁）
            if (!hoverCapable) return;
            if ((e.target as Element).closest("[data-law-popup]")) {
              if (hideTimer.current) clearTimeout(hideTimer.current);
              return;
            }
            const ref = (e.target as Element).closest(".law-ref");
            if (!ref) {
              scheduleLawHide();
              return;
            }
            if (ref !== popupRefEl.current) {
              popupRefEl.current = ref;
              scheduleLawOpen(ref);
            } else if (hideTimer.current) {
              clearTimeout(hideTimer.current);
            }
          }}
          onPointerLeave={() => {
            if (hoverCapable) scheduleLawHide();
          }}
          onClick={(e) => {
            // 法条卡：触屏/Mac 触控板 click toggle；桌面纯鼠标只走 hover，点击不误关
            if (hoverCapable) return;
            const ref = (e.target as Element).closest(".law-ref");
            if (!ref) {
              clearLawPopup();
              return;
            }
            void toggleLawPopup(ref);
          }}
        >
          <div className="mx-auto max-w-[44rem]">
            {messages.length === 0 && (
              <div className="fade-in pt-6">
                {/* 欢迎语 */}
                <p className="mb-7 text-center font-serif text-xl font-semibold tracking-tight text-ink md:text-[1.4rem]">
                  你好，{user.username}，今天想咨询什么？
                </p>
                {/* 场景直达卡 */}
                <div className="mb-6 grid grid-cols-1 gap-3 min-[400px]:grid-cols-2 md:grid-cols-4">
                  {SCENES.map((s) => (
                    <button
                      key={s.title}
                      type="button"
                      onClick={() => quickSend(s.q)}
                      className="glass-card group rounded-xl px-4 py-4 text-left transition-transform duration-200 hover:-translate-y-0.5"
                    >
                      <span className="text-xl">{s.icon}</span>
                      <p className="mt-2 text-sm font-medium text-ink">{s.title}</p>
                      <p className="mt-0.5 text-xs text-slate">{s.desc}</p>
                    </button>
                  ))}
                </div>
                {/* 每日法条 */}
                <div className="glass-card mb-6 rounded-xl px-5 py-4">
                  <p className="text-xs tracking-wide text-slate">每日法条</p>
                  <button
                    type="button"
                    onClick={() => quickSend(dailyLaw.q)}
                    className="mt-1.5 block text-left text-sm leading-relaxed text-ink transition-colors hover:text-accent"
                  >
                    <span className="law-ref" data-source={dailyLaw.src}>
                      《{dailyLaw.src}》{dailyLaw.art}
                    </span>{" "}
                    — {dailyLaw.text}
                  </button>
                </div>
                {/* 用法引导 */}
                <p className="mb-6 text-center text-xs tracking-wide text-slate/80">
                  ① 贴文字 / 传文件 / 拍照　→　② 逐条追问　→　③ 查看参考条文
                </p>
                {/* 最近会话 */}
                {history.length > 0 && (
                  <div className="mb-6">
                    <p className="mb-2 text-center text-xs text-slate">最近会话</p>
                    <div className="flex flex-wrap justify-center gap-2">
                      {history.slice(0, 3).map((h) => (
                        <button
                          key={h.id}
                          type="button"
                          onClick={() => selectConv(h)}
                          className="max-w-[220px] truncate rounded-full border border-mist bg-white/60 px-3 py-1.5 text-xs text-ink transition-colors hover:border-accent hover:text-accent"
                        >
                          {h.title || h.preview || "新对话"}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                {/* 法条速查（P1 搜索面板） */}
                <div className="text-center">
                  <button
                    type="button"
                    onClick={() => setLawPanel(true)}
                    className="rounded-full border border-mist bg-white/60 px-4 py-2 text-xs text-slate transition-colors hover:border-accent hover:text-accent"
                  >
                    § 法条速查
                  </button>
                </div>
              </div>
            )}
            {messages.map((m, i) =>
              m.role === "user" ? (
                <div key={i} className="page-enter mb-6 flex items-end justify-end gap-2.5">
                  <div className="bubble-user max-w-[85%] px-4 py-3 text-sm leading-[1.7] md:max-w-[70%]">
                    {m.content && m.content !== "[图片]" && <span className="whitespace-pre-wrap">{m.content}</span>}
                    <ChatImage dataURL={m.imageDataURL} imgRef={m.imgRef} thumbRef={m.thumbRef} />
                  </div>
                  <span className="mb-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-semibold text-white shadow-sm">
                    {user.username.slice(0, 1).toUpperCase()}
                  </span>
                </div>
              ) : (
                <div key={i} className="page-enter mb-6 flex items-start justify-start gap-2.5">
                  <span className="logo-seal mt-0.5 h-8 w-8 shrink-0 text-sm">§</span>
                  <div className="max-w-[85%] md:max-w-[80%]">
                    {m.steps && m.steps.length > 0 && (
                      <div className="mb-2 flex flex-wrap gap-1.5">
                        {m.steps.map((s, si) => (
                          <span
                            key={si}
                            className="inline-flex items-center gap-1 rounded-full border border-mist bg-parchment px-2.5 py-1 text-xs text-slate"
                          >
                            <span className="text-emerald-600">✓</span>
                            <span className="font-medium text-ink">{s.label}</span>
                            <span>{s.detail}</span>
                          </span>
                        ))}
                      </div>
                    )}
                    <div
                      className={`bubble-ai whitespace-pre-wrap px-5 py-4 text-sm leading-[1.75] text-ink [overflow-wrap:anywhere] ${
                        streaming && i === messages.length - 1 && m.content ? "streaming-cursor" : ""
                      } ${streaming && i === messages.length - 1 && m.content ? "streaming-aura" : ""} ${
                        streaming && i === messages.length - 1 && !m.content ? "overflow-hidden" : ""
                      }`}
                    >
                      {m.content ? (
                        streaming && i === messages.length - 1 ? (
                          // 流式期：纯文本（不标注，防半截标签）
                          <span className="whitespace-pre-wrap">{m.content}</span>
                        ) : (
                          // 完成/历史：先清 markdown 残留（禁 * - 字符），再语义标注（法条/时效/金额；引号内不标）
                          <span
                            className="whitespace-pre-wrap"
                            dangerouslySetInnerHTML={{ __html: annotate(stripMarkdown(m.content)) }}
                          />
                        )
                      ) : streaming && i === messages.length - 1 ? (
                        // 检索期三态：合同模式=分析中（step 胶囊已是进度）；普通问答=法典速查+扫描光
                        m.steps && m.steps.length > 0 ? (
                          <span className="flex items-center gap-2 text-slate">
                            正在生成风险评估报告
                            <span className="typing-dots">
                              <i />
                              <i />
                              <i />
                            </span>
                          </span>
                        ) : (
                          <span className="flex items-center gap-2 text-slate">
                            <span className="codex-char text-accent">{CODEX[codexIdx]}</span>
                            正在检索法律条文
                            <span className="scan-beam" />
                          </span>
                        )
                      ) : (
                        ""
                      )}
                    </div>
                    {!streaming && m.sources && m.sources.length > 0 && (
                      <details className="mt-1.5 text-xs">
                        <summary className="cursor-pointer select-none text-slate transition-colors hover:text-ink">
                          参考条文（{m.sources.length}）
                        </summary>
                        <div className="mt-1.5 space-y-1">
                          {m.sources.map((s, si) => (
                            <div key={si} className="rounded bg-mist px-2.5 py-1.5 font-mono text-[0.78rem] text-ink/80">
                              {s.source} {s.article}
                            </div>
                          ))}
                        </div>
                      </details>
                    )}
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

            {/* 法条悬浮卡浮层：absolute 锚定在滚动容器内（随内容滚动，位置上下自适应 + 玻璃卡） */}
            {lawPopup && (
              <div
                ref={popupNodeRef}
                data-law-popup
                className="law-popup"
                style={{ left: lawPopup.left, top: lawPopup.top, width: lawPopup.width }}
                onPointerEnter={() => {
                  if (hideTimer.current) clearTimeout(hideTimer.current);
                }}
                onPointerLeave={() => {
                  if (hoverCapable) scheduleLawHide();
                }}
              >
                <LawCard law={lawPopup.law} compact />
              </div>
            )}
          </div>
        </div>

        {/* 输入区 */}
        <form onSubmit={send} className="border-t border-white/40 bg-white/45 px-4 py-4 backdrop-blur-md md:px-8 pb-safe">
          <div className="mx-auto max-w-[44rem]">
            {pendingImage && (
              <div className="mb-2 inline-flex items-center gap-2 rounded-lg border border-mist bg-parchment p-1.5">
                <img src={pendingImage} alt="待发送" className="h-12 w-12 rounded object-cover" />
                <button type="button" onClick={() => setPendingImage(null)} className="rounded px-1.5 text-slate hover:text-error" aria-label="移除图片">
                  ✕
                </button>
              </div>
            )}
            {fileInfo && (
              <div className="mb-2 inline-flex items-center gap-2 rounded-lg border border-mist bg-parchment px-2.5 py-1.5 text-sm text-ink">
                <span className="text-slate">📄</span>
                <span className="max-w-[220px] truncate">{fileInfo.name}</span>
                <span className="text-slate/70">已解析 {fileInfo.chars} 字{fileInfo.truncated ? "（超长已截断）" : ""}</span>
                <button type="button" onClick={() => { setFileInfo(null); setFileContent(null); }} className="rounded px-1 text-slate hover:text-error" aria-label="移除文件">
                  ✕
                </button>
              </div>
            )}
            <div className="flex items-center gap-2">
              <input ref={imageInputRef} type="file" accept="image/jpeg,image/png" className="hidden" onChange={(e) => e.target.files?.[0] && acceptImageFile(e.target.files[0])} />
              <button
                type="button"
                onClick={() => imageInputRef.current?.click()}
                disabled={streaming}
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-mist text-slate transition-colors hover:bg-mist hover:text-ink disabled:opacity-50"
                aria-label="上传图片"
                title="上传图片（JPEG/PNG，≤5MB）"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                  <circle cx="8.5" cy="8.5" r="1.5" />
                  <polyline points="21 15 16 10 5 21" />
                </svg>
              </button>
              <input ref={fileInputRef} type="file" accept=".txt,.md,.pdf,.docx" className="hidden" onChange={(e) => e.target.files?.[0] && handleFileUpload(e.target.files[0])} />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={streaming}
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-mist text-slate transition-colors hover:bg-mist hover:text-ink disabled:opacity-50"
                aria-label="上传文件"
                title="上传文件（txt/md/pdf/docx，≤10MB）"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
                  <polyline points="13 2 13 9 20 9" />
                </svg>
              </button>
              <button
                type="button"
                onClick={toggleVoice}
                disabled={streaming || transcribing}
                className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full border transition-colors disabled:opacity-50 ${
                  listening
                    ? "border-error bg-error/10 text-error"
                    : transcribing
                      ? "border-accent bg-accent/10 text-accent"
                      : "border-mist text-slate hover:bg-mist hover:text-ink"
                }`}
                aria-label={listening ? "停止录音" : transcribing ? "语音转写中" : "语音输入"}
                title={listening ? "停止录音" : transcribing ? "正在转写…" : "语音输入（按住说话，松手转写）"}
              >
                {transcribing ? (
                  <Spinner />
                ) : listening ? (
                  <span className="h-3.5 w-3.5 animate-pulse rounded-full bg-error" />
                ) : (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                    <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                    <line x1="12" y1="19" x2="12" y2="23" />
                    <line x1="8" y1="23" x2="16" y2="23" />
                  </svg>
                )}
              </button>
              <textarea
                className="input min-w-0 flex-1 !rounded-[6px] !py-2 resize-none max-h-[120px]"
                rows={2}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && e.ctrlKey) send();  // Enter 换行，Ctrl+Enter 发送
                }}
                onPaste={onPaste}
                placeholder="请输入您的法律问题…（可上传文件/图片审合同，支持语音输入、连续追问）"
                disabled={streaming}
              />
              <button
                type="submit"
                disabled={streaming || (!input.trim() && !pendingImage && !fileContent)}
                className="btn btn-primary h-10 w-10 shrink-0 !rounded-[6px] !p-0"
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
            <p className="mt-2 text-center text-xs text-slate/70">
              回答仅供参考，不构成正式法律意见；法律可能修订，请以最新规定为准
            </p>
          </div>
        </form>

        {/* 法条速查面板（P1） */}
        {lawPanel && (
          <div
            className="fixed inset-0 z-40 flex items-center justify-center bg-ink/30 p-4 backdrop-blur-sm"
            onClick={() => setLawPanel(false)}
          >
            <div className="glass-card w-full max-w-xl rounded-2xl p-5" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center justify-between">
                <h3 className="font-serif text-lg font-semibold text-ink">法条速查</h3>
                <button type="button" onClick={() => setLawPanel(false)} className="rounded px-2 text-slate transition-colors hover:text-ink" aria-label="关闭">
                  ✕
                </button>
              </div>
              <div className="mt-3 flex gap-2">
                <input
                  className="input flex-1"
                  value={lawQ}
                  onChange={(e) => setLawQ(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && doLawSearch()}
                  placeholder="输入关键词或法条号，如「试用期」「民法典 585」"
                />
                <button type="button" onClick={doLawSearch} className="btn btn-primary shrink-0">
                  搜索
                </button>
              </div>
              {lawResults.length > 0 && (
                <div className="mt-3 max-h-64 space-y-2 overflow-y-auto">
                  {lawResults.map((r, i) => (
                    <button
                      key={`${r.source}-${r.article}-${i}`}
                      type="button"
                      onClick={() => openLawDetail(r)}
                      className="block w-full rounded-lg border border-mist bg-white/70 px-3 py-2 text-left transition-colors hover:border-accent"
                    >
                      <p className="text-sm font-medium text-ink">
                        《{r.source}》{r.article}
                      </p>
                      <p className="mt-0.5 line-clamp-2 text-xs text-slate">{r.preview}</p>
                    </button>
                  ))}
                </div>
              )}
              {lawDetail && (
                <div className="mt-3">
                  <LawCard law={lawDetail} />
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
