"use client";
// T2.3 状态收敛：流式会话核心态（messages/streaming/conversationId/agent 续跑/澄清计数）。
// doSend 复用原 streamChat 回调；当前请求身份隔离主动取消后的迟到回调；副作用经 opts 注入
// 正常结束/失败在收尾刷新历史；主动停止立即刷新，旧请求不重复收尾。
import { useEffect, useRef, useState, type SetStateAction } from "react";
import { convApi, streamChat, ChatMeta } from "@/lib/api";
import { parseScopeCandidates, ScopeCandidate } from "@/lib/scope";
import type { Msg, PendingAgentRun } from "@/lib/types";

export function useChatStream(opts: {
  /** SSE meta 帧带回 conversation_id 时同步侧栏高亮（原 setActiveId） */
  onConversationId: (id: number) => void;
  /** 一轮流式（成功/失败/主动停止）结束后刷新历史列表 */
  onStreamEnd: () => void;
}) {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [conversationId, setConversationIdState] = useState<number | null>(null);
  const [pendingAgentRun, setPendingAgentRun] = useState<PendingAgentRun | null>(null);
  // 本轮 Agent 澄清计数（B4：无分母，后端未暴露总轮数；newChat/selectConv 重置）
  const [clarifyRounds, setClarifyRounds] = useState(0);
  const [streaming, setStreaming] = useState(false);
  const activeRequest = useRef<AbortController | null>(null);
  const conversationIdRef = useRef<number | null>(null);
  const viewVersion = useRef(0);
  const pendingCreation = useRef<Promise<number> | null>(null);

  useEffect(
    () => () => {
      viewVersion.current += 1;
      pendingCreation.current = null;
      activeRequest.current?.abort();
      activeRequest.current = null;
    },
    []
  );

  // 外部 setter 表示切换/新建视图；内部建号和 meta 同步不经过此失效入口。
  function setConversationId(value: SetStateAction<number | null>) {
    viewVersion.current += 1;
    pendingCreation.current = null;
    activeRequest.current?.abort();
    activeRequest.current = null;
    setStreaming(false);
    conversationIdRef.current =
      typeof value === "function" ? value(conversationIdRef.current) : value;
    setConversationIdState(conversationIdRef.current);
  }

  function stop() {
    const controller = activeRequest.current;
    if (!controller) return;
    controller.abort();
    activeRequest.current = null;
    setStreaming(false);
    setPendingAgentRun(null);
    setClarifyRounds(0);
    setMessages((m) => {
      const last = m[m.length - 1];
      if (last?.role !== "assistant") return m;
      return [
        ...m.slice(0, -1),
        {
          ...last,
          content: last.content.trim()
            ? `${last.content}\n\n（已停止生成，以上为未完成回答。）`
            : "已停止生成。",
          coverage: undefined,
          agentNote: undefined,
          scopeCandidates: undefined,
        },
      ];
    });
    opts.onStreamEnd();
  }

  // ref 同步挡住重复发送；state 仅负责输入栏的可用状态。
  async function doSend(
    contentText: string,
    image?: string | null,
    display?: string,
    truncated?: boolean
  ) {
    if ((!contentText && !image) || activeRequest.current) return;
    const controller = new AbortController();
    activeRequest.current = controller;
    const isCurrent = () => activeRequest.current === controller && !controller.signal.aborted;
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
      let targetConversationId = conversationIdRef.current;
      if (targetConversationId === null) {
        if (!pendingCreation.current) {
          const version = viewVersion.current;
          // 停止只取消本轮回答；同视图重问共享创建，原生超时防止创建永久挂起。
          const creation = convApi
            .create(AbortSignal.timeout(180_000))
            .then(({ id }) => {
              if (!Number.isSafeInteger(id) || id <= 0) {
                throw new Error("创建对话失败：无效的对话编号");
              }
              if (viewVersion.current === version) {
                conversationIdRef.current = id;
                setConversationIdState(id);
                opts.onConversationId(id);
              }
              return id;
            })
            .finally(() => {
              if (pendingCreation.current === creation) pendingCreation.current = null;
            });
          pendingCreation.current = creation;
        }
        targetConversationId = await pendingCreation.current;
      }
      if (!isCurrent()) return;
      await streamChat(
        {
          conversationId: targetConversationId,
          content: contentText,
          image: image || undefined,
          truncated,
          agentRunId: resumeAgent?.runId,
          agentStateVersion: resumeAgent?.stateVersion,
        },
        (chunk) => {
          if (!isCurrent()) return;
          acc += chunk;
          setMessages((m) => {
            if (controller.signal.aborted) return m;
            const copy = [...m];
            copy[copy.length - 1] = { ...copy[copy.length - 1], content: acc };
            return copy;
          });
        },
        (meta: ChatMeta) => {
          if (!isCurrent()) return;
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
            if (controller.signal.aborted) return m;
            const copy = [...m];
            const last = copy[copy.length - 1];
            if (!last) return copy;
            const patch: Partial<Msg> = {};
            if (meta.agent_run_id) patch.agentRunId = meta.agent_run_id;
            if (meta.sources?.length) patch.sources = meta.sources;
            if (meta.agent_event === "clarification") patch.scopeCandidates = patchScope;
            if (meta.agent_event !== undefined) patch.agentNote = patchNote;
            if (patchCoverage) patch.coverage = patchCoverage;
            copy[copy.length - 1] = { ...last, ...patch };
            return copy;
          });
          if (meta.conversation_id != null) {
            conversationIdRef.current = meta.conversation_id;
            setConversationIdState(meta.conversation_id);
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
          if (!isCurrent()) return;
          // 失败标注：保留已有 agentNote（error code 在其中；普通 RAG 路径 undefined）
          setClarifyRounds(0);
          setMessages((m) => {
            if (controller.signal.aborted) return m;
            const copy = [...m];
            copy[copy.length - 1] = { ...copy[copy.length - 1], content: `出错了：${err}` };
            return copy;
          });
        },
        (steps) => {
          if (!isCurrent()) return;
          // 合同评估分析进度（SSE step 事件）：更新最后一条 AI 消息的步骤区
          setMessages((m) => {
            if (controller.signal.aborted) return m;
            const copy = [...m];
            const last = copy[copy.length - 1];
            if (last && last.role === "assistant") {
              copy[copy.length - 1] = { ...last, steps };
            }
            return copy;
          });
        },
        () => {
          if (!isCurrent()) return;
          // 后端重试将零重答：清空已发的半截内容重新累积，防拼接乱码（对抗审计 2026-08-07）
          acc = "";
          setMessages((m) => {
            if (controller.signal.aborted) return m;
            const copy = [...m];
            copy[copy.length - 1] = { ...copy[copy.length - 1], content: "" };
            return copy;
          });
        },
        controller.signal
      );
      if (!isCurrent()) return;
      // G-5 降级兜底：流正常结束但回答为空（技术故障 fail-closed 空响应）→ 明确提示而非空白。
      // clarification 必有 content 写入，不受影响；此处仅覆盖"零内容完成"。
      setMessages((m) => {
        if (controller.signal.aborted) return m;
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
      if (!isCurrent()) return;
      // 网络错误/流中断会让 streamChat reject——必须恢复 streaming 状态并提示，
      // 否则 UI 永久卡在"正在生成"（对抗审计 2026-08-07）
      setMessages((m) => {
        if (controller.signal.aborted) return m;
        const copy = [...m];
        copy[copy.length - 1] = {
          ...copy[copy.length - 1],
          content: `出错了：${e instanceof Error ? e.message : String(e)}`,
        };
        return copy;
      });
    } finally {
      if (activeRequest.current === controller) {
        activeRequest.current = null;
        setStreaming(false);
        opts.onStreamEnd();
      }
    }
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
    stop,
  };
}
