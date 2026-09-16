// 争点范围选择：解析后端澄清 prompt → 候选卡片数据；再把选中编号拼回后端接受的回答文本。
// 契约来自 backend/agent/controller.py _scope_selection_question（2026-09-13 固定）：
//   "本次请求分解出 N 个法律争点，超过单次可处理上限 5 个。请从中选择最多 5 个争点（输入编号，用逗号分隔，例如：1,3,5）：\n1. 争点甲\n2. 争点乙"
// 解析失败返回 null → 调用方降级为纯文本追问（不做卡片，行为不变）。

export interface ScopeCandidate {
  number: number;
  text: string;
}

export const SCOPE_MAX_SELECTION = 5;

/** 仅当 prompt 命中范围选择特征（前缀 + 至少一条 "N. " 行）时解析；否则返回 null。 */
export function parseScopeCandidates(prompt: string): ScopeCandidate[] | null {
  if (!prompt.includes("本次请求分解出")) return null;
  const lines = prompt.split("\n");
  const candidates: ScopeCandidate[] = [];
  for (const line of lines) {
    const m = line.match(/^\s*(\d+)\.\s*(.+?)\s*$/);
    if (!m) continue;
    const n = Number(m[1]);
    // 要求编号从 1 连续递增（防乱序行混入）
    if (candidates.length === 0 && n !== 1) return null;
    if (candidates.length > 0 && n !== candidates[candidates.length - 1].number + 1) return null;
    candidates.push({ number: n, text: m[2] });
  }
  if (candidates.length === 0) return null;
  return candidates;
}

/** 升序 + 英文逗号分隔；参数由调用方保证 1-5 个、均在候选范围内。 */
export function buildScopeAnswer(selected: number[]): string {
  // 目标低于 es2015 时不可遍历 Set（且 Set 迭代需要 downlevelIteration），用数组去重
  const deduped: number[] = [];
  for (const n of selected) {
    if (!deduped.includes(n)) deduped.push(n);
  }
  return deduped.sort((a, b) => a - b).join(",");
}