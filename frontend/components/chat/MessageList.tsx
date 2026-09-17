"use client";
// T2.2 自 chat/page.tsx 原样搬移（空态区块 + 消息循环提取为组件），零行为变更。
// 外层滚动容器（scrollRef/onScroll/onDrop/法条卡点击委托）留在 page——其绑定逻辑属页面编排。
import type { Msg, ConversationItem } from "@/lib/types";
import { SCENES, DAILY_LAWS } from "@/lib/constants";
import { MessageBubble } from "./MessageBubble";

export function MessageList({
  messages,
  username,
  streaming,
  expandedLaw,
  fbDone,
  corrFor,
  corrText,
  codexIdx,
  selectedScope,
  history,
  dailyIdx,
  onToggleScope,
  onClearScope,
  onFeedbackUp,
  onFeedbackDown,
  onCorrForChange,
  onCorrTextChange,
  onQuickSend,
  onSelectConv,
  onOpenLawPanel,
}: {
  messages: Msg[];
  username: string;
  streaming: boolean;
  expandedLaw: import("@/lib/types").ExpandedLaw | null;
  fbDone: Record<number, "up" | "down">;
  corrFor: number | null;
  corrText: string;
  codexIdx: number;
  selectedScope: number[];
  history: ConversationItem[];
  dailyIdx: number;
  onToggleScope: (n: number) => void;
  onClearScope: () => void;
  onFeedbackUp: (i: number) => void;
  onFeedbackDown: (i: number, correction: string) => void;
  onCorrForChange: (i: number | null) => void;
  onCorrTextChange: (t: string) => void;
  onQuickSend: (q: string) => void;
  onSelectConv: (item: ConversationItem) => void;
  onOpenLawPanel: () => void;
}) {
  const dailyLaw = DAILY_LAWS[dailyIdx];
  return (
    <div className="mx-auto max-w-[44rem]">
      {messages.length === 0 && (
        <div className="fade-in pt-6">
          {/* 欢迎语 */}
          <p className="mb-6 text-center font-serif text-lg font-semibold tracking-tight text-ink md:mb-7 md:text-[1.4rem]">
            你好，{username}，今天想咨询什么？
          </p>
          {/* 场景直达卡：移动端 2 列，避免单列堆得太高 */}
          <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
            {SCENES.map((s) => (
              <button
                key={s.title}
                type="button"
                onClick={() => onQuickSend(s.q)}
                className="glass-card group rounded-xl border border-transparent px-3 py-3 text-left transition-all duration-200 hover:-translate-y-0.5 hover:border-accent/40 md:px-4 md:py-4"
              >
                <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent/10 text-xl transition-colors group-hover:bg-accent/20 md:h-11 md:w-11 md:text-2xl">
                  {s.icon}
                </span>
                <p className="mt-1.5 text-sm font-medium text-ink md:mt-2">{s.title}</p>
                <p className="mt-0.5 text-[11px] leading-snug text-slate md:text-xs">{s.desc}</p>
              </button>
            ))}
          </div>
          {/* 每日法条：轮播展示（5 秒切换），标题与内容居中，卡片高度固定 */}
          <div className="glass-card relative mb-6 overflow-hidden rounded-xl border-l-[3px] border-l-accent px-5 py-4">
            <span className="section-mark absolute -right-1 -top-3 text-6xl text-accent opacity-20">
              §
            </span>
            <p className="text-center text-xs tracking-wide text-accent-deep">每日法条</p>
            <button
              key={dailyIdx}
              type="button"
              onClick={() => onQuickSend(dailyLaw.q)}
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
                    onClick={() => onSelectConv(h)}
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
              onClick={onOpenLawPanel}
              className="rounded-full border border-mist bg-white/60 px-4 py-2 text-xs text-slate transition-colors hover:border-accent hover:text-accent"
            >
              § 法条速查
            </button>
          </div>
        </div>
      )}
      {messages.map((m, i) => (
        <MessageBubble
          key={i}
          m={m}
          i={i}
          username={username}
          streaming={streaming}
          isLast={i === messages.length - 1}
          expandedLaw={expandedLaw}
          fbDone={fbDone}
          corrFor={corrFor}
          corrText={corrText}
          codexIdx={codexIdx}
          selectedScope={selectedScope}
          onToggleScope={onToggleScope}
          onClearScope={onClearScope}
          onFeedbackUp={onFeedbackUp}
          onFeedbackDown={onFeedbackDown}
          onCorrForChange={onCorrForChange}
          onCorrTextChange={onCorrTextChange}
        />
      ))}
    </div>
  );
}
