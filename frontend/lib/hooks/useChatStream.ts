"use client";
// T2.3 状态收敛：流式会话核心态（messages/streaming/conversationId/agent 续跑/澄清计数）。
// doSend 为 chat 页原函数逐行搬移，零逻辑改动；跨切片副作用经 opts 回调注入
// （activeId 同步 / 流结束后刷新历史），调用时序与原实现一致。
import { useState } from "react";
import { streamChat, ChatMeta } from "@/lib/api";
import { parseScopeCandidates, ScopeCandidate } from "@/lib/scope";
import type { Msg, PendingAgentRun } from "@/lib/types";

export function useChatStream(opts: {
  /** SSE meta 帧带回 conversation_id 时同步侧栏高亮（原 setActiveId） */
  onConversationId: (id: number) => void;
  /** 一轮流式（成功/失败）结束后刷新历史列表（原 loadHistory） */
  onStreamEnd: () => void;
}) {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [pendingAgentRun, setPendingAgentRun] = useState<PendingAgentRun | null>(null);
  // 本轮 Agent 澄清计数（B4：无分母，后端未暴露总轮数；newChat/selectConv 重置）
  const [clarifyRounds, setClarifyRounds] = useState(0);
  const [streaming, setStreaming] = useState(false);

  // 核心发送：普通 send 与空状态快捷提问共用（streamChat 回调原样，零逻辑改动）
  async function doSend(
    contentText: string,
    image?: string | null,
    display?: string,
    truncated?: boolean
  ) {
    if ((!contentText && !image) || streaming) return;
    const userMsg: Msg = {
      role: "user",
      content: display || contentText || "[图片]",
      imageDataURL: image || undefined,
    };
    const aiMsg: Msg = { role: "assistant", content: "" };
    setMessages((m) => [...m, userMsg, aiMsg]);
    setStreaming(true);
    const resumeAgent = pendingAgentRun;

    let acc = "";
    try {
      await streamChat(
        {
          conversationId,
          content: contentText,
          image: image || undefined,
          truncated,
          agentRunId: resumeAgent?.runId,
          agentStateVersion: resumeAgent?.stateVersion,
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
          // B2/B4/B3 标注计算放 updater 外（避免 updater 内 setState，审查偏差修正）；
          // 每轮 doSend 最多一条澄清事件 → clarifyRounds 闭包语义 = 当前已确认轮次
          let patchNote: Msg["agentNote"] | undefined;
          let patchScope: ScopeCandidate[] | undefined;
          let patchCoverage: Msg["coverage"] | undefined;
          if (meta.agent_event === "clarification") {
            patchNote = { kind: "clarification", round: clarifyRounds + 1 };
            setClarifyRounds(clarifyRounds + 1);
            // B1：解析候选（失败降级纯文本——不做卡片，pending 逻辑不变）
            if (meta.prompt) patchScope = parseScopeCandidates(meta.prompt) || undefined;
          } else if (meta.agent_event === "error") {
            patchNote = { kind: "error", code: meta.error_code };
            setClarifyRounds(0);
          } else if (meta.agent_event === "final") {
            patchNote = undefined;
            setClarifyRounds(0);
            // T1（2026-09-16）：结构化覆盖随 final 帧写入（partial → 顶部提示；full/缺省 → 无提示）
            if (meta.coverage_status === "partial" && meta.uncovered_issues?.length) {
              patchCoverage = { status: "partial", uncovered: meta.uncovered_issues };
            } else if (meta.coverage_status === "full") {
              patchCoverage = { status: "full", uncovered: [] };
            }
          }
          setMessages((m) => {
            const copy = [...m];
            const last = copy[copy.length - 1];
            if (!last) return copy;
            const patch: Partial<Msg> = {};
            if (meta.sources?.length) patch.sources = meta.sources;
            if (meta.agent_event === "clarification") patch.scopeCandidates = patchScope;
            if (meta.agent_event !== undefined) patch.agentNote = patchNote;
            if (patchCoverage) patch.coverage = patchCoverage;
            copy[copy.length - 1] = { ...last, ...patch };
            return copy;
          });
          if (meta.conversation_id != null) {
            setConversationId(meta.conversation_id);
            opts.onConversationId(meta.conversation_id);
          }
          if (
            meta.agent_event === "clarification" &&
            meta.agent_run_id &&
            meta.agent_state_version !== undefined
          ) {
            setPendingAgentRun({
              runId: meta.agent_run_id,
              stateVersion: meta.agent_state_version,
            });
          } else if (meta.agent_event === "final" || meta.agent_event === "error") {
            setPendingAgentRun(null);
          }
        },
        (err) => {
          // 失败标注：保留已有 agentNote（error code 在其中；普通 RAG 路径 undefined）
          setClarifyRounds(0);
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
        },
        () => {
          // 后端重试将零重答：清空已发的半截内容重新累积，防拼接乱码（对抗审计 2026-08-07）
          acc = "";
          setMessages((m) => {
            const copy = [...m];
            copy[copy.length - 1] = { ...copy[copy.length - 1], content: "" };
            return copy;
          });
        }
      );
      // G-5 降级兜底：流正常结束但回答为空（技术故障 fail-closed 空响应）→ 明确提示而非空白。
      // clarification 必有 content 写入，不受影响；此处仅覆盖"零内容完成"。
      setMessages((m) => {
        const copy = [...m];
        const last = copy[copy.length - 1];
        if (last?.role === "assistant" && last.content.trim() === "") {
          copy[copy.length - 1] = {
            ...last,
            content: "服务暂时不可用，请稍后重试；紧急法律问题请咨询律师。",
          };
        }
        return copy;
      });
    } catch (e) {
      // 网络错误/流中断会让 streamChat reject——必须恢复 streaming 状态并提示，
      // 否则 UI 永久卡在"正在生成"（对抗审计 2026-08-07）
      setMessages((m) => {
        const copy = [...m];
        copy[copy.length - 1] = {
          ...copy[copy.length - 1],
          content: `出错了：${e instanceof Error ? e.message : String(e)}`,
        };
        return copy;
      });
    } finally {
      setStreaming(false);
    }
    opts.onStreamEnd();
  }

  return {
    messages,
    setMessages,
    streaming,
    setStreaming,
    conversationId,
    setConversationId,
    pendingAgentRun,
    setPendingAgentRun,
    clarifyRounds,
    setClarifyRounds,
    doSend,
  };
}
