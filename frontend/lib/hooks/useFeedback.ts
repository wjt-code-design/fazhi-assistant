"use client";
// T2.3 状态收敛：👍/👎 反馈与纠错态。函数体为 chat 页原实现逐行搬移，零行为变更；
// messages/conversationId 经参数注入（每渲染重建闭包，语义与原页面级函数一致）。
import { useState } from "react";
import { feedbackApi } from "@/lib/api";
import type { Msg } from "@/lib/types";

export function useFeedback(deps: { messages: Msg[]; conversationId: number | null }) {
  const [corrFor, setCorrFor] = useState<number | null>(null);
  const [corrText, setCorrText] = useState("");
  const [fbDone, setFbDone] = useState<Record<number, "up" | "down">>({});

  async function sendFeedback(i: number, rating: "up" | "down", correction?: string) {
    const ai = deps.messages[i];
    const prev = deps.messages[i - 1];
    const question =
      prev && prev.role === "user" ? (prev.content === "[图片]" ? "[图片]" : prev.content) : "";
    try {
      await feedbackApi.post({
        conversation_id: deps.conversationId,
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

  /** 切换会话时的重置（与 f0f9cc9 修复的三入口逻辑同源，勿"顺手优化"） */
  function reset() {
    setFbDone({});
    setCorrFor(null);
    setCorrText("");
  }

  return { fbDone, corrFor, corrText, setCorrFor, setCorrText, sendFeedback, reset };
}
