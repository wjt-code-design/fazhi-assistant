"use client";
import { memo, useEffect, useRef, useState, FormEvent, ClipboardEvent, DragEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { streamChat, convApi, loadMediaSrc, chatFile, ChatMeta, AnalysisStep, feedbackApi, lawApi, LawDetail, LawItem, transcribeApi } from "@/lib/api";
import { Logo, Spinner } from "@/components/ui";
import { renderAnswer } from "@/lib/annotate";
import { startWavRecorder } from "@/lib/recorder";
import { LawCard } from "@/components/LawCard";
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
// 空状态：每日法条（前端硬编码高频常识，按日期轮换；点击提问走正常管线）
const DAILY_LAWS = [
  { src: "劳动合同法", art: "第十九条", text: "试用期最长不得超过六个月", q: "劳动合同试用期最长是多久？" },
  { src: "民法典", art: "第五百八十五条", text: "违约金过分高于损失可请求法院调减", q: "违约金太高可以要求降低吗？" },
  { src: "民法典", art: "第一百八十八条", text: "普通诉讼时效为三年", q: "普通诉讼时效是几年？" },
  { src: "劳动法", art: "第四十四条", text: "安排延长工作时间应支付加班费", q: "加班费怎么计算？" },
  { src: "民法典", art: "第一百四十八条", text: "受欺诈方有权请求撤销违背真实意思的法律行为", q: "被欺诈签订的合同可以撤销吗？" },
  { src: "民法典", art: "第一千零七十九条", text: "感情确已破裂且调解无效的应准予离婚", q: "什么情况下法院会判决离婚？" },
  { src: "消费者权益保护法", art: "第二十四条", text: "商品不符合质量要求的消费者可要求退货", q: "网购商品质量不好可以退货吗？" },
  { src: "刑法", art: "第二十条", text: "正当防卫不负刑事责任", q: "什么是正当防卫？" },
  { src: "道路交通安全法", art: "第七十六条", text: "交强险限额内先行赔偿交通事故损失", q: "交通事故赔偿顺序是怎样的？" },
  { src: "民法典", art: "第一千一百六十五条", text: "因过错侵害他人民事权益应承担侵权责任", q: "侵权责任的构成要件是什么？" },
];
function dailyLawIndex() {
  const d = new Date();
  const dayKey = d.getFullYear() * 10000 + (d.getMonth() + 1) * 100 + d.getDate();
  return dayKey % DAILY_LAWS.length;
}
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

// ---- 法条内联卡（纯函数，模块级：供 MessageHtml memo 使用，避免组件内重建失效） ----
function escapeHtmlText(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function buildLawCardHtml(exp: {
  source: string;
  article: string;
  content: string;
  status?: string;
  found: boolean;
}): string {
  const title = `<p class="law-title font-serif text-sm">《${escapeHtmlText(exp.source)}》${escapeHtmlText(exp.article)}</p>`;
  if (!exp.found) {
    // 知识库未收录（如司法解释）：仍弹卡，给出可操作提示
    return (
      `<div class="law-glass law-inline-card rounded-xl px-4 py-4">` +
      title +
      `<p class="mt-2 text-[0.85rem] leading-relaxed text-slate/85">知识库暂未收录该条文原文。</p>` +
      `</div>`
    );
  }
  const content = escapeHtmlText(exp.content).replace(/\n/g, "<br/>");
  const status = exp.status ? `<p class="mt-2 text-xs text-slate">状态：${escapeHtmlText(exp.status)}</p>` : "";
  return (
    `<div class="law-glass law-inline-card rounded-xl px-4 py-4">` +
    title +
    `<p class="mt-2 whitespace-pre-wrap text-[0.85rem] leading-relaxed text-ink/90 font-normal">${content}</p>` +
    `${status}</div>`
  );
}

/** 在回答 HTML 中定位「对应 data-source + 条号」的法条引用，在其第 occurrence 次出现后追加卡片 */
function injectLawCardHtml(html: string, exp: {
  source: string;
  article: string;
  content: string;
  status?: string;
  found: boolean;
}, occurrence = 0): string {
  const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const src = esc(exp.source);
  const art = esc(exp.article.replace(/^第|条$/g, ""));
  const re = new RegExp(`(<span class="law-ref" data-source="${src}"[^>]*>[^<]*${art}[^<]*<\\/span>)`, "g");
  const card = buildLawCardHtml(exp);
  let count = 0;
  let injected = false;
  const out = html.replace(re, (full) => {
    const isTarget = count === occurrence;
    count++;
    if (isTarget) {
      injected = true;
      return full + card;
    }
    return full;
  });
  return injected ? out : out + card; // 兜底：计数越界则追加到末尾
}

interface ExpandedLaw {
  msgIndex: number;
  source: string;
  article: string;
  content: string;
  status?: string;
  found: boolean;
  occurrence: number;
}

/** 消息 HTML 渲染（React.memo）：流式时只有 content 变化的最后一条会重排 renderAnswer，
 * 已完成消息不重复跑语义标注正则（F1 性能优化，2026-08-07）。 */
const MessageHtml = memo(function MessageHtml({ content, expanded, i }: {
  content: string;
  expanded: ExpandedLaw | null;
  i: number;
}) {
  let html = renderAnswer(content);
  if (expanded && expanded.msgIndex === i) {
    html = injectLawCardHtml(html, expanded, expanded.occurrence);
  }
  return <div className="whitespace-normal" dangerouslySetInnerHTML={{ __html: html }} />;
});

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
  const [dailyIdx, setDailyIdx] = useState(dailyLawIndex()); // 每日法条轮播索引
  useEffect(() => {
    if (messages.length !== 0) return; // 只在空状态轮播；开始对话后停止，避免全局重渲染导致法条卡抖动
    const t = setInterval(() => setDailyIdx((i) => (i + 1) % DAILY_LAWS.length), 5000);
    return () => clearInterval(t);
  }, [messages.length]);
  const dailyLaw = DAILY_LAWS[dailyIdx];
  // 法条速查面板 + 法条内联展开卡（P1）
  const [lawPanel, setLawPanel] = useState(false);
  const [lawQ, setLawQ] = useState("");
  const [lawResults, setLawResults] = useState<LawItem[]>([]);
  const [lawDetail, setLawDetail] = useState<LawDetail | null>(null);
  // 点击法条 → 卡片在该法条下一行内联展开（再点收起）
  const [expandedLaw, setExpandedLaw] = useState<{
    msgIndex: number;
    source: string;
    article: string;
    content: string;
    status?: string;
    found: boolean; // 知识库是否收录了原文（未收录也弹卡提示）
    occurrence: number; // 同「书名+条号」在该消息内第几次出现（0 起），用于卡片精确落到点击的那一条
  } | null>(null);
  usePointerGlow(scrollRef); // 指针光晕（仅 hover:hover）

  // 语音（M2）：Qwen livetranslate 后端转写，Web Speech 兜底
  const [transcribing, setTranscribing] = useState(false);
  const wavRecRef = useRef<{ stop: () => Promise<Blob> } | null>(null);
  const voiceTimeoutRef = useRef<number | null>(null);

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

  // 卸载清理：语音超时
  useEffect(() => {
    return () => {
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
    setExpandedLaw(null);
  }

  async function selectConv(item: ConvItem) {
    setActiveId(item.id);
    setConversationId(item.id);
    setPendingImage(null);
    setSidebarOpen(false);
    setExpandedLaw(null);
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
        setExpandedLaw(null);
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

  // ---------- 法条卡：点击 → 内联展开（卡片出现在法条下一行，再点收起） ----------
  // 从 .law-ref 的 data-source（书名，含省略书名号的独立条号）+ 文本条号 → 后端查原文。
  // 带模块级缓存：同条文只发一次请求；失败返回 null（前端降级纯文本）。
  function fetchLawRefCached(el: Element): Promise<LawDetail | null> {
    const src = el.getAttribute("data-source");
    const m = (el.textContent || "").match(
      /第\s*([零〇○一二三四五六七八九十百千万0-9０-９]+)\s*条(之[一二三四五六七八九十百千万0-9０-９]+)?/
    );
    if (!src || !m) return Promise.resolve(null);
    const article = `第${m[1]}条${m[2] || ""}`;
    const key = `${src}\u0000${article}`;
    let p = lawCache.get(key);
    if (!p) {
      // 库内 article 存完整「第X条」中文条号（精确匹配），必须拼回完整形式，否则数字/缺字 404
      // B3（2026-08-07）：后端 /api/law 已 _normalize_article 归一（〇零/阿拉伯/之条），直接传原文条号
      p = lawApi.detail(src, article).catch(() => null);
      lawCache.set(key, p);
    }
    return p;
  }

  // 法条内联卡纯函数（escapeHtmlText/buildLawCardHtml/injectLawCardHtml）已上移模块级，
  // 供 MessageHtml memo 使用；removeUnprovidedHint 已删（B1 后端保证库内不产矛盾句）。

  async function toggleInlineLaw(ref: Element, msgIndex: number) {
    // 未收录的条文（如司法解释）也弹卡提示，而不是点了没反应
    const src = ref.getAttribute("data-source") || "";
    const m = (ref.textContent || "").match(/第\s*([零〇○一二三四五六七八九十百千万0-9０-９]+)\s*条(之[一二三四五六七八九十百千万0-9０-９]+)?/);
    const article = m ? `第${m[1]}条${m[2] || ""}` : "";

    // 计算被点击法条在「同书名+条号」集合中的序号（文档顺序），
    // 使卡片精确落到点击的那一条，而非第一条（多次出现时）。
    let occurrence = 0;
    const msgEl = ref.closest("[data-msg-index]");
    if (msgEl) {
      const refs = msgEl.querySelectorAll(".law-ref");
      for (const r of Array.from(refs)) {
        if (r === ref) break;
        const rSrc = r.getAttribute("data-source") || "";
        const rm = (r.textContent || "").match(/第\s*([零〇○一二三四五六七八九十百千万0-9０-９]+)\s*条(之[一二三四五六七八九十百千万0-9０-９]+)?/);
        const rArt = rm ? `第${rm[1]}条${rm[2] || ""}` : "";
        if (rSrc === src && rArt === article) occurrence++;
      }
    }

    const law = await fetchLawRefCached(ref);
    setExpandedLaw((prev) =>
      prev && prev.msgIndex === msgIndex && prev.source === src && prev.article === article && prev.occurrence === occurrence
        ? null // 再点同一条 → 收起
        : {
            msgIndex,
            source: src,
            article,
            content: law ? law.content : "",
            status: law?.status,
            found: !!law,
            occurrence,
          }
    );
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

      {/* 侧栏：历史会话（樱花海主题色玻璃卡） */}
      <aside
        className={`sidebar-glow sidebar-glass fixed inset-y-0 left-0 z-30 flex w-[280px] max-w-[85vw] flex-col text-ink transition-transform duration-300 ease-out md:relative md:translate-x-0 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between px-3 py-5">
          <Logo size="sm" />
          <button className="rounded-md p-1 text-ink/50 transition-colors hover:bg-accent/10 hover:text-accent md:hidden" onClick={() => setSidebarOpen(false)} aria-label="关闭菜单">
            ✕
          </button>
        </div>
        <div className="px-3">
          <button onClick={newChat} className="btn btn-primary w-full shadow-md shadow-accent/20">
            <span className="text-base leading-none">＋</span> 新对话
          </button>
        </div>
        <div className="mt-6 flex-1 overflow-y-auto px-3 pb-4">
          <p className="px-2 pb-2 text-xs tracking-wide text-slate">历史会话</p>
          {history.length === 0 && <p className="px-2 text-sm text-slate/70">暂无记录</p>}
          {history.map((h) => (
            <div
              key={h.id}
              className={`chat-item group relative ${activeId === h.id ? "active" : ""}`}
              onClick={() => selectConv(h)}
            >
              <p className="flex items-center gap-1.5 truncate pr-5 text-sm text-ink/90">
                {h.has_image && <span className="text-slate">🖼</span>}
                <span className="truncate">{h.title || h.preview || "新对话"}</span>
              </p>
              <p className="mt-0.5 truncate text-xs text-slate">{h.preview}</p>
              <button
                type="button"
                aria-label={`删除会话 ${h.title || h.preview || "新对话"}`}
                title="删除会话"
                className="absolute right-1.5 top-1/2 flex h-5 w-5 -translate-y-1/2 items-center justify-center rounded-full text-xs text-slate opacity-100 transition-opacity hover:bg-mist hover:text-ink md:opacity-0 md:group-hover:opacity-100"
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
        <div className="border-t border-mist px-3 py-4">
          {user.role === "admin" && (
            <button onClick={() => router.push("/admin")} className="mb-2 w-full text-left text-sm text-accent-deep transition-colors hover:text-accent">
              管理后台 →
            </button>
          )}
          <div className="flex items-center justify-between gap-2">
            <span className="flex min-w-0 items-center gap-2 text-sm text-ink/70">
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
              className="shrink-0 rounded-md px-2 py-1 text-xs text-slate transition-colors hover:bg-mist hover:text-ink"
            >
              退出
            </button>
          </div>
        </div>
      </aside>

      {/* 主区域 */}
      <div className="relative flex min-w-0 flex-1 flex-col">
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
          <div className="mx-auto max-w-[44rem]">
            {messages.length === 0 && (
              <div className="fade-in pt-6">
                {/* 欢迎语 */}
                <p className="mb-6 text-center font-serif text-lg font-semibold tracking-tight text-ink md:mb-7 md:text-[1.4rem]">
                  你好，{user.username}，今天想咨询什么？
                </p>
                {/* 场景直达卡：移动端 2 列，避免单列堆得太高 */}
                <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
                  {SCENES.map((s) => (
                    <button
                      key={s.title}
                      type="button"
                      onClick={() => quickSend(s.q)}
                      className="glass-card group rounded-xl border border-transparent px-3 py-3 text-left transition-all duration-200 hover:-translate-y-0.5 hover:border-accent/40 md:px-4 md:py-4"
                    >
                      <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent/10 text-xl transition-colors group-hover:bg-accent/20 md:h-11 md:w-11 md:text-2xl">{s.icon}</span>
                      <p className="mt-1.5 text-sm font-medium text-ink md:mt-2">{s.title}</p>
                      <p className="mt-0.5 text-[11px] leading-snug text-slate md:text-xs">{s.desc}</p>
                    </button>
                  ))}
                </div>
                {/* 每日法条：轮播展示（5 秒切换），标题与内容居中，卡片高度固定 */}
                <div className="glass-card relative mb-6 overflow-hidden rounded-xl border-l-[3px] border-l-accent px-5 py-4">
                  <span className="section-mark absolute -right-1 -top-3 text-6xl text-accent opacity-20">§</span>
                  <p className="text-center text-xs tracking-wide text-accent-deep">每日法条</p>
                    <button
                    key={dailyIdx}
                    type="button"
                    onClick={() => quickSend(dailyLaw.q)}
                    className="fade-in mt-1.5 flex h-[3.5rem] w-full flex-col items-center justify-center overflow-hidden text-center text-sm leading-relaxed text-ink transition-colors hover:text-accent"
                  >
                    <span className="line-clamp-2">
                      <span className="law-ref" data-source={dailyLaw.src}>
                        《{dailyLaw.src}》{dailyLaw.art}
                      </span>
                      <span className="mx-1">—</span>
                      {dailyLaw.text}
                    </span>
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
                <div key={i} data-msg-index={i} className="page-enter mb-6 flex items-start justify-start gap-2.5">
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
                        // 流式期与完成期统一：实时语义标注（法条/时效/金额）+ Markdown 排版
                        // （标题/表格/列表/加粗）；每帧基于当前累积内容重新生成完整 HTML，
                        // 无半截标签累积，输出过程即规范格式。
                        <MessageHtml content={m.content} expanded={expandedLaw} i={i} />
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
          </div>
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
            <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19" />
              <polyline points="19 12 12 19 5 12" />
            </svg>
            最新
          </button>
        )}

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
            <div className="flex items-center gap-1.5 md:gap-2">
              <input ref={imageInputRef} type="file" accept="image/jpeg,image/png" className="hidden" onChange={(e) => e.target.files?.[0] && acceptImageFile(e.target.files[0])} />
              <button
                type="button"
                onClick={() => imageInputRef.current?.click()}
                disabled={streaming}
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-mist text-slate transition-colors hover:bg-mist hover:text-ink disabled:opacity-50 md:h-10 md:w-10"
                aria-label="上传图片"
                title="上传图片（JPEG/PNG，≤5MB）"
              >
                <svg className="h-[17px] w-[17px] md:h-[18px] md:w-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
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
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-mist text-slate transition-colors hover:bg-mist hover:text-ink disabled:opacity-50 md:h-10 md:w-10"
                aria-label="上传文件"
                title="上传文件（txt/md/pdf/docx，≤10MB）"
              >
                <svg className="h-[17px] w-[17px] md:h-[18px] md:w-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
                  <polyline points="13 2 13 9 20 9" />
                </svg>
              </button>
              <button
                type="button"
                onClick={toggleVoice}
                disabled={streaming || transcribing}
                className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full border transition-colors disabled:opacity-50 md:h-10 md:w-10 ${
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
                  <svg className="h-[17px] w-[17px] md:h-[18px] md:w-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                    <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                    <line x1="12" y1="19" x2="12" y2="23" />
                    <line x1="8" y1="23" x2="16" y2="23" />
                  </svg>
                )}
              </button>
              <textarea
                className="input min-w-0 flex-1 !rounded-[6px] !py-2 !text-[15px] resize-none max-h-[120px] md:!text-base"
                rows={2}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && e.ctrlKey) send();  // Enter 换行，Ctrl+Enter 发送
                }}
                onPaste={onPaste}
                placeholder="请输入法律问题…"
                disabled={streaming}
              />
              <button
                type="submit"
                disabled={streaming || (!input.trim() && !pendingImage && !fileContent)}
                className="btn btn-primary h-9 w-9 shrink-0 !rounded-[6px] !p-0 shadow-md shadow-accent/25 md:h-10 md:w-10"
                aria-label="发送"
              >
                {streaming ? (
                  <Spinner />
                ) : (
                  <svg className="h-4 w-4 md:h-[17px] md:w-[17px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
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
