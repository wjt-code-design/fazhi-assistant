// 参考条目的版本提示（纯函数）：状态 / 施行日 / 失效日。
// 后端 meta.sources 已带 effective_from/effective_to/status；前端此前只显示法名与条号。
export interface SourceVersionMeta {
  source?: string;
  article?: string;
  effective_from?: string;
  effective_to?: string;
  status?: string;
}

export function sourceTitle(s: SourceVersionMeta): string {
  const parts: string[] = [];
  if (s.status) parts.push(`状态：${s.status}`);
  if (s.effective_from) parts.push(`施行：${s.effective_from}`);
  if (s.effective_to) parts.push(`失效：${s.effective_to}`);
  return parts.length ? parts.join("；") : "版本日期未标注";
}
