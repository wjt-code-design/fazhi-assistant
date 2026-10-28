// 评测隔离（2026-10-27）：前端验收/自动化测试可在 localStorage 置位，
// 让浏览器发出的 /api/chat 自动带 X-Eval-No-Curate: 1，避免测试会话沉淀候选。
// 普通用户不置位 ⇒ 不带头，行为不变。
export const EVAL_NO_CURATE_KEY = "alh_eval_no_curate";

type StorageLike = { getItem(key: string): string | null };

export function evalNoCurateHeader(storage?: StorageLike | null): Record<string, string> {
  const s =
    storage === undefined ? (typeof window !== "undefined" ? window.localStorage : null) : storage;
  try {
    return s?.getItem(EVAL_NO_CURATE_KEY) === "1" ? { "X-Eval-No-Curate": "1" } : {};
  } catch {
    return {};
  }
}
