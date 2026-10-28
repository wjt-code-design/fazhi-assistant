// 历史会话的纯函数：搜索过滤 + 导出 Markdown（便于单测与复用）。
import type { ConversationItem, Msg } from "./types";

export function filterHistory(items: ConversationItem[], query: string): ConversationItem[] {
  const q = query.trim().toLowerCase();
  if (!q) return items;
  return items.filter((h) => `${h.title || ""} ${h.preview || ""}`.toLowerCase().includes(q));
}

export function conversationToMarkdown(messages: Msg[], title?: string): string {
  const head = (title || "").trim() || "法智对话";
  const lines: string[] = [`# ${head}`, ""];
  for (const m of messages) {
    lines.push(m.role === "user" ? "## 我" : "## 法智", "", m.content || "", "");
  }
  return lines.join("\n");
}
