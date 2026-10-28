// 服务/网络失败的可读分类（纯函数，便于测试）。
// 历史库里有 43 条 `服务暂时无响应，请稍后重试。`；客户端空答兜底是另一句。
// 两者此前都不被识别为错误态，渲染成普通回答；这里集中判据，MessageBubble 只消费。
export type ChatFailureKind = "service" | "generic" | null;

const SERVICE_FAILURES = [
  "服务暂时无响应，请稍后重试。",
  "服务暂时不可用，请稍后重试；紧急法律问题请咨询律师。",
];

export function chatFailureKind(content: string): ChatFailureKind {
  const t = (content || "").trim();
  if (!t) return null;
  if (SERVICE_FAILURES.some((s) => t === s || t.startsWith(s))) return "service";
  if (t.startsWith("出错了：")) return "generic";
  return null;
}
