// T2.2 自 chat/page.tsx 原样搬移（配额预警横幅 JSX 提取为组件），零行为变更。
import type { QuotaWarn } from "@/lib/types";

/** 配额预警横幅（B 更优版）：embedding 快用完/耗尽 或 rerank 已降级 → 顶部横幅。
 * 传入的 quotaWarn 为 null 或无任何告警位时返回 null（条件判断与原页一致）。 */
export function QuotaBanner({ quotaWarn }: { quotaWarn: QuotaWarn | null }) {
  if (
    !quotaWarn ||
    !(quotaWarn.embedding_depleted || quotaWarn.embedding_warn || quotaWarn.rerank_degraded)
  ) {
    return null;
  }
  return (
    <div
      className="border-b px-5 py-2 text-xs"
      style={
        quotaWarn.embedding_depleted
          ? { background: "#ef444422", color: "#b91c1c", borderColor: "#ef444455" }
          : { background: "#f59e0b22", color: "#92400e", borderColor: "#f59e0b55" }
      }
    >
      {quotaWarn.embedding_depleted
        ? "⚠ embedding 配额已耗尽，问答暂时不可用——请联系管理员换班（docs/换班手册.md）。"
        : quotaWarn.embedding_warn
          ? `⚠ embedding 配额接近耗尽（剩 ${quotaWarn.embedding_pct}%），建议尽快换班（docs/换班手册.md）。`
          : "⚠ rerank 模型已全部耗尽，自动降级本地精排（排序准度略降）。"}
    </div>
  );
}
