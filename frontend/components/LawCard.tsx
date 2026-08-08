"use client";
import type { LawDetail } from "@/lib/api";

/** 法条原文卡：法条悬浮浮层 / 速查面板展开共用。数据来自后端 /api/law（不建前端库）。 */
export function LawCard({ law, compact = false }: { law: LawDetail; compact?: boolean }) {
  return (
    <div className="law-glass rounded-xl px-4 py-4 shadow-[var(--shadow-xl)]">
      <p className="law-title font-serif text-sm">
        《{law.source}》{law.article}
      </p>
      <p className={`mt-2 whitespace-pre-wrap pl-0.5 text-[0.85rem] leading-relaxed text-ink/90 font-normal ${compact ? "line-clamp-4" : ""}`}>
        {law.content}
      </p>
      {law.status && <p className="mt-2 text-xs text-slate">状态：{law.status}</p>}
    </div>
  );
}
