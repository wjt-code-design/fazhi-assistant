// T1（2026-09-16）覆盖状态展示：实时 SSE 与历史会话**共用**的纯函数（防两套文案漂移）。
// 结构化字段驱动——禁止解析答案正文判断覆盖（交接书 A6/A7）。

export interface UncoveredIssueInfo {
  issue_id: string;
  reason_code: string;
}

export interface CoverageInfo {
  status: "full" | "partial";
  uncovered: UncoveredIssueInfo[];
}

/** 后端 /api/conversations/{id} 消息的覆盖投影字段（MessageOut） */
export interface HistoryCoverageFields {
  coverage_status?: "full" | "partial" | "unknown" | null;
  uncovered_issues?: UncoveredIssueInfo[] | null;
}

/**
 * partial 提示数据：partial 且列表非空 → { uncoveredCount }；
 * full / 未定义 / 异常形态（partial 空列表，契约禁止）→ null（不显示提示）。
 */
export function partialBanner(coverage?: CoverageInfo): { uncoveredCount: number } | null {
  if (!coverage || coverage.status !== "partial") return null;
  if (!coverage.uncovered || coverage.uncovered.length === 0) return null;
  return { uncoveredCount: coverage.uncovered.length };
}

/**
 * 历史消息覆盖投影 → 展示用 CoverageInfo。
 * unknown / 缺字段 → null（旧消息不显示提示，也绝不显示为 full——A5）。
 * 注：旧消息缺 coverage 是预期态而非异常，静默归 null 不做诊断输出（warn 会成为预期噪音）。
 */
export function coverageFromMessage(m: HistoryCoverageFields): CoverageInfo | null {
  const status = m.coverage_status;
  if (status !== "full" && status !== "partial") return null;
  const uncovered = Array.isArray(m.uncovered_issues) ? m.uncovered_issues : [];
  if (status === "full" && uncovered.length > 0) return null; // 异常形态防御
  if (status === "partial" && uncovered.length === 0) return null; // 异常形态防御
  return { status, uncovered };
}

/**
 * final SSE 事件原始载荷 → ChatMeta 覆盖字段（api.ts 调用，行为与原内联三元链逐字等价）。
 * 未知形态（非 "full"/"partial"、列表非数组）→ undefined，不猜测——解析判定收口在纯函数
 * （与 partialBanner/coverageFromMessage 同一测试覆盖面），api.ts 只做透传。
 */
export function coverageFromFinalEvent(raw: {
  coverage_status?: unknown;
  uncovered_issues?: unknown;
}): {
  coverage_status: "full" | "partial" | undefined;
  uncovered_issues: UncoveredIssueInfo[] | undefined;
} {
  const status = raw.coverage_status;
  return {
    coverage_status: status === "full" || status === "partial" ? status : undefined,
    uncovered_issues: Array.isArray(raw.uncovered_issues)
      ? (raw.uncovered_issues as UncoveredIssueInfo[])
      : undefined,
  };
}
