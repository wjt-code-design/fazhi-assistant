"use client";
// T2.2 自 chat/page.tsx 原样搬移（单条消息渲染提取为组件），零行为变更：
// 原 `streaming && i === messages.length - 1` 以 isLast prop 等价传入。
import type { Msg, ExpandedLaw } from "@/lib/types";
import { SCOPE_MAX_SELECTION, buildScopeAnswer } from "@/lib/scope";
import { partialBanner } from "@/lib/coverage";
import { CODEX } from "@/lib/constants";
import { Spinner } from "@/components/ui";
import { ChatImage } from "./ChatImage";
import { MessageHtml } from "./MessageHtml";

// B3：reason_code → 可读提示（chat_integration error code；无 code 用通用文案）
function agentErrorHint(code?: string): string {
  switch (code) {
    case "ISSUE_CLAIMS_MISSING":
      return "模型未能生成可引用的法律依据，请换一种问法或简化问题。";
    case "UNKNOWN_MISSING_INFORMATION":
    case "MISSING_FACT":
      return "信息不足，建议补充时间、金额、主体等关键事实后重发。";
    case "UNSUPPORTED_CITATION":
    case "NON_CANONICAL_CITATION":
      return "未能从法律库引用到准确条文，建议换个表述重新提问。";
    default:
      return "";
  }
}

export function MessageBubble({
  m,
  i,
  username,
  streaming,
  isLast,
  expandedLaw,
  fbDone,
  corrFor,
  corrText,
  codexIdx,
  selectedScope,
  onToggleScope,
  onClearScope,
  onFeedbackUp,
  onFeedbackDown,
  onCorrForChange,
  onCorrTextChange,
}: {
  m: Msg;
  i: number;
  username: string;
  streaming: boolean;
  isLast: boolean;
  expandedLaw: ExpandedLaw | null;
  fbDone: Record<number, "up" | "down">;
  corrFor: number | null;
  corrText: string;
  codexIdx: number;
  selectedScope: number[];
  onToggleScope: (n: number) => void;
  onClearScope: () => void;
  onFeedbackUp: (i: number) => void;
  onFeedbackDown: (i: number, correction: string) => void;
  onCorrForChange: (i: number | null) => void;
  onCorrTextChange: (t: string) => void;
}) {
  // B3：错误态覆盖两类——agent 事件标注 error 的，或普通 RAG 失败（出错了：前缀，无 agentNote）
  const isErrorMsg =
    m.agentNote?.kind === "error" || (!m.agentNote && m.content.startsWith("出错了："));
  return m.role === "user" ? (
    <div key={i} className="page-enter mb-6 flex items-end justify-end gap-2.5">
      <div className="bubble-user max-w-[85%] px-4 py-3 text-sm leading-[1.7] md:max-w-[70%]">
        {m.content && m.content !== "[图片]" && (
          <span className="whitespace-pre-wrap">{m.content}</span>
        )}
        <ChatImage dataURL={m.imageDataURL} imgRef={m.imgRef} thumbRef={m.thumbRef} />
      </div>
      <span className="mb-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-semibold text-white shadow-sm">
        {username.slice(0, 1).toUpperCase()}
      </span>
    </div>
  ) : (
    <div
      key={i}
      data-msg-index={i}
      className="page-enter mb-6 flex items-start justify-start gap-2.5"
    >
      <span className="logo-seal mt-0.5 h-8 w-8 shrink-0 text-sm">§</span>
      <div className="max-w-[85%] md:max-w-[80%]">
        {/* T1（2026-09-16）：部分交付警示——结构化字段驱动，位于答案正文之前（A7）；
            full/unknown/用户消息不显示。实时与历史共用本组件（A6），文案单一来源在 lib/coverage.ts。 */}
        {(() => {
          const banner = partialBanner(m.coverage);
          if (!banner) return null;
          return (
            <div
              role="status"
              className="mb-2 flex items-start gap-2 rounded-lg border border-amber-500/50 bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-800"
            >
              <span aria-hidden>⚠</span>
              <span>
                部分交付：本次回答覆盖了部分法律争点，另有 {banner.uncoveredCount}{" "}
                个争点因现有依据不足未能给出结论（未覆盖争点及原因见本回答末尾说明）。
              </span>
            </div>
          );
        })()}
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
        {/* B2/B4：澄清标签 + 轮次 chip（无分母，后端未暴露总轮数） */}
        {m.agentNote?.kind === "clarification" && (
          <div className="mb-1.5 flex items-center gap-2">
            <span className="rounded-full border border-sea/60 px-2 py-0.5 text-xs font-medium text-sea">
              Agent 澄清
            </span>
            <span className="text-xs text-slate">第 {m.agentNote.round} 轮</span>
          </div>
        )}
        {/* B3：失败态徽标 + code 可读提示 */}
        {isErrorMsg && (
          <div className="mb-1.5 flex flex-col gap-1">
            <span className="flex items-center gap-2 rounded-full border border-error/40 px-2 py-0.5 text-xs font-medium text-error">
              <span className="h-1.5 w-1.5 rounded-full bg-error" /> 未能完成本次请求
            </span>
            {m.agentNote?.kind === "error" && agentErrorHint(m.agentNote.code) && (
              <span className="text-xs text-slate">{agentErrorHint(m.agentNote.code)}</span>
            )}
          </div>
        )}
        <div
          aria-live={streaming && isLast ? "polite" : undefined}
          className={`bubble-ai whitespace-pre-wrap px-5 py-4 text-sm leading-[1.75] text-ink [overflow-wrap:anywhere] ${
            m.agentNote?.kind === "clarification" ? "border border-sea/50" : ""
          } ${isErrorMsg ? "border border-error/40" : ""} ${
            streaming && isLast && m.content ? "streaming-cursor" : ""
          } ${streaming && isLast && m.content ? "streaming-aura" : ""} ${
            streaming && isLast && !m.content ? "overflow-hidden" : ""
          }`}
        >
          {m.scopeCandidates && m.scopeCandidates.length > 0 ? (
            // B1：范围选择候选卡片（替代提示文本展示；解析失败时 m.scopeCandidates 为 undefined 走原逻辑）
            <div className="scope-pick space-y-2">
              <p className="text-xs text-slate">
                本次请求分解出 {m.scopeCandidates.length} 个争点，单次最多处理 {SCOPE_MAX_SELECTION}{" "}
                个。点击选择（可多选），编号会自动填入输入框：
              </p>
              <div className="grid grid-cols-1 gap-1.5">
                {m.scopeCandidates.map((c) => (
                  <button
                    key={c.number}
                    type="button"
                    disabled={streaming}
                    onClick={() => onToggleScope(c.number)}
                    className={`scope-item flex items-start gap-2.5 rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
                      selectedScope.includes(c.number)
                        ? "border-sea bg-sea/10 text-ink"
                        : "border-mist bg-white/60 text-ink hover:border-sea"
                    } ${streaming ? "opacity-60" : ""}`}
                  >
                    <span
                      className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                        selectedScope.includes(c.number) ? "bg-ink text-white" : "bg-sea text-white"
                      }`}
                    >
                      {c.number}
                    </span>
                    <span className="leading-snug">{c.text}</span>
                  </button>
                ))}
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate">
                  已选 {selectedScope.length}/{SCOPE_MAX_SELECTION} 个
                  {selectedScope.length > 0 ? `（${buildScopeAnswer(selectedScope)}）` : ""}
                </span>
                {selectedScope.length > 0 && (
                  <button
                    type="button"
                    onClick={onClearScope}
                    className="text-slate underline decoration-dotted hover:text-error"
                  >
                    清空选择
                  </button>
                )}
              </div>
            </div>
          ) : m.content ? (
            // 流式期与完成期统一：实时语义标注（法条/时效/金额）+ Markdown 排版
            // （标题/表格/列表/加粗）；每帧基于当前累积内容重新生成完整 HTML，
            // 无半截标签累积，输出过程即规范格式。
            <MessageHtml content={m.content} expanded={expandedLaw} i={i} />
          ) : streaming && isLast ? (
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
        {/* ADR-012 阶段2C：参考条文折叠展示（SSE meta.sources 下发，流式结束后渲染） */}
        {!streaming && m.role === "assistant" && m.sources && m.sources.length > 0 && (
          <details className="mt-2 rounded-lg border border-mist bg-white/50 px-3 py-1.5">
            <summary className="cursor-pointer select-none text-xs text-slate hover:text-ink">
              参考条文（{m.sources.length}）
            </summary>
            <ul className="mt-1.5 flex flex-wrap gap-1.5 pb-1">
              {m.sources.map((s, si) => (
                <li
                  key={si}
                  className="rounded-full border border-sea/40 bg-sea/5 px-2.5 py-0.5 text-xs text-ink"
                >
                  《{s.source}》{s.article}
                </li>
              ))}
            </ul>
          </details>
        )}
        {!streaming && m.content && !m.agentNote && (
          <div className="mt-2">
            <div className="flex items-center gap-2 text-slate">
              <button
                type="button"
                onClick={() => onFeedbackUp(i)}
                disabled={!!fbDone[i]}
                className={`rounded px-1.5 text-sm transition-colors ${fbDone[i] === "up" ? "text-jade" : "hover:text-ink"}`}
                aria-label="有帮助"
                title="有帮助"
              >
                👍
              </button>
              <button
                type="button"
                onClick={() => onCorrForChange(corrFor === i ? null : i)}
                disabled={!!fbDone[i]}
                className={`rounded px-1.5 text-sm transition-colors ${fbDone[i] === "down" ? "text-error" : "hover:text-ink"}`}
                aria-label="不准确"
                title="不准确 / 纠错"
              >
                👎
              </button>
              {fbDone[i] && <span className="text-xs text-jade">已记录，谢谢反馈</span>}
            </div>
            {corrFor === i && (
              <div className="mt-2 space-y-2">
                <textarea
                  className="input min-h-[64px]"
                  placeholder="可选：写出你认为正确的答案或指出错误…"
                  value={corrText}
                  onChange={(e) => onCorrTextChange(e.target.value)}
                />
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => onFeedbackDown(i, corrText)}
                    className="btn btn-primary !px-3 !py-1 text-xs"
                  >
                    提交纠错
                  </button>
                  <button
                    type="button"
                    onClick={() => onFeedbackDown(i, "")}
                    className="btn btn-secondary !px-3 !py-1 text-xs"
                  >
                    仅标记不准
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
