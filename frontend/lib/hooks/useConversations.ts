"use client";
// T2.3 状态收敛：历史会话列表 + 当前选中 + 切换/新建/删除。
// 函数体为 chat 页原实现逐行搬移，零行为变更；三个入口重置的状态集合本就不同
// （执行书 T2.3：保留现有重置逻辑，勿"顺手优化"）——跨切片 setter 全部经 opts 注入。
import { useEffect, useState, type Dispatch, type SetStateAction } from "react";
import { convApi } from "@/lib/api";
import { coverageFromMessage } from "@/lib/coverage";
import type { AuthUser } from "@/lib/auth";
import type { ConversationItem, HistoryMsg, Msg, PendingAgentRun } from "@/lib/types";

export function useConversations(opts: {
  user: AuthUser | null;
  streaming: boolean;
  setMessages: Dispatch<SetStateAction<Msg[]>>;
  setConversationId: Dispatch<SetStateAction<number | null>>;
  setPendingAgentRun: Dispatch<SetStateAction<PendingAgentRun | null>>;
  setClarifyRounds: Dispatch<SetStateAction<number>>;
  setSelectedScope: Dispatch<SetStateAction<number[]>>;
  setInput: Dispatch<SetStateAction<string>>;
  setPendingImage: Dispatch<SetStateAction<string | null>>;
  setSidebarOpen: Dispatch<SetStateAction<boolean>>;
  setIsNearBottom: Dispatch<SetStateAction<boolean>>;
  clearExpandedLaw: () => void;
  resetFeedback: () => void;
}) {
  const [history, setHistory] = useState<ConversationItem[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);

  const loadHistory = () => {
    convApi
      .list()
      .then(setHistory)
      .catch(() => {});
  };
  useEffect(() => {
    if (opts.user) loadHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opts.user]);

  function newChat() {
    if (opts.streaming) return; // 流式期间禁止切会话，防消息污染/conversationId 错位（对抗审计 2026-08-07）
    opts.setMessages([]);
    opts.setConversationId(null);
    opts.setPendingAgentRun(null);
    opts.setClarifyRounds(0);
    opts.setSelectedScope([]);
    setActiveId(null);
    opts.setInput("");
    opts.setPendingImage(null);
    opts.setSidebarOpen(false);
    opts.setIsNearBottom(true);
    opts.clearExpandedLaw();
    opts.resetFeedback();
  }

  async function selectConv(item: ConversationItem) {
    if (opts.streaming) return; // 流式期间禁止切换会话，防消息污染/conversationId 错位（对抗审计 2026-08-07）
    setActiveId(item.id);
    opts.setConversationId(item.id);
    opts.setPendingAgentRun(null);
    opts.setClarifyRounds(0);
    opts.setSelectedScope([]);
    opts.setPendingImage(null);
    opts.setSidebarOpen(false);
    opts.clearExpandedLaw();
    opts.resetFeedback();
    try {
      const det = await convApi.detail(item.id);
      opts.setMessages(
        (det.messages || []).map((m: HistoryMsg) => ({
          role: m.role === "user" ? "user" : "assistant",
          content: m.content || "",
          imgRef: m.image_ref || undefined,
          thumbRef: m.thumb_ref || undefined,
          // T1（2026-09-16）：历史覆盖投影（unknown/缺字段 → undefined，不显示提示、绝不显示为 full）
          coverage: coverageFromMessage(m) || undefined,
        }))
      );
      opts.setIsNearBottom(true);
    } catch {
      opts.setMessages([]);
    }
  }

  // 删除历史对话（M5）：后端 DELETE /api/conversations/{id} 已就绪，前端接线
  async function deleteConv(id: number) {
    if (opts.streaming) return; // 流式期间禁止删除会话，防消息污染/conversationId 错位（对抗审计 2026-08-07）
    if (!window.confirm("确定删除这个对话吗？删除后不可恢复。")) return;
    try {
      await convApi.remove(id);
      if (activeId === id) {
        opts.setMessages([]);
        opts.setConversationId(null);
        opts.setPendingAgentRun(null);
        opts.setClarifyRounds(0);
        opts.setSelectedScope([]);
        setActiveId(null);
        opts.clearExpandedLaw();
        opts.resetFeedback();
      }
      loadHistory();
    } catch {
      alert("删除失败，请重试");
    }
  }

  return { history, activeId, setActiveId, loadHistory, newChat, selectConv, deleteConv };
}
