// 展示层日期时间格式化（T1.7）：统一 admin 页的 zh-CN 本地化时间显示。
// 行为与原内联写法逐点对齐：空值 → "-"；非法值交给 toLocaleString 输出 "Invalid Date"。

/** ISO 字符串 → zh-CN 本地日期时间；空值返回 "-"。 */
export function formatDateTime(iso?: string): string {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("zh-CN");
}
