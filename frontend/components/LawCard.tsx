"use client";
import type { LawDetail } from "@/lib/api";

/** 法条原文卡：法条悬浮浮层 / 速查面板展开共用。数据来自后端 /api/law（不建前端库）。 */
export function LawCard({ law, compact = false }: { law: LawDetail; compact?: boolean }) {
  return (
    <div className="rounded-xl border border-white/60 bg-white/95 p-4 shadow-[var(--shadow-xl)]">
      <p className="font-serif text-sm font-semibold text-ink">
        《{law.source}》{law.article}
      </p>
      <p className={`mt-2 whitespace-pre-wrap text-[0.85rem] leading-relaxed text-ink/85 ${compact ? "line-clamp-4" : ""}`}>
        {law.content}
      </p>
      {law.status && <p className="mt-2 text-xs text-slate">状态：{law.status}</p>}
    </div>
  );
}
