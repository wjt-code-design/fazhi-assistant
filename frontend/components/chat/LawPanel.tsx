"use client";
// T2.2 自 chat/page.tsx 原样搬移（法条速查面板区块提取为组件），零行为变更：
// 面板专属状态（关键词/结果/详情）随区块迁入本组件——仅面板内使用，页面不再持有。
import { useState } from "react";
import { lawApi, LawDetail, LawItem } from "@/lib/api";
import { LawCard } from "@/components/LawCard";

export function LawPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [lawQ, setLawQ] = useState("");
  const [lawResults, setLawResults] = useState<LawItem[]>([]);
  const [lawDetail, setLawDetail] = useState<LawDetail | null>(null);

  async function doLawSearch() {
    const q = lawQ.trim();
    if (!q) return;
    try {
      setLawResults(await lawApi.search(q));
      setLawDetail(null);
    } catch {
      setLawResults([]);
    }
  }

  async function openLawDetail(item: LawItem) {
    try {
      setLawDetail(await lawApi.detail(item.source, item.article));
    } catch {
      setLawDetail(null);
    }
  }

  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-ink/30 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="glass-card w-full max-w-xl rounded-2xl p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h3 className="font-serif text-lg font-semibold text-ink">法条速查</h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded px-2 text-slate transition-colors hover:text-ink"
            aria-label="关闭"
          >
            ✕
          </button>
        </div>
        <div className="mt-3 flex gap-2">
          <input
            className="input flex-1"
            value={lawQ}
            onChange={(e) => setLawQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && doLawSearch()}
            placeholder="输入关键词或法条号，如「试用期」「民法典 585」"
          />
          <button type="button" onClick={doLawSearch} className="btn btn-primary shrink-0">
            搜索
          </button>
        </div>
        {lawResults.length > 0 && (
          <div className="mt-3 max-h-64 space-y-2 overflow-y-auto">
            {lawResults.map((r, i) => (
              <button
                key={`${r.source}-${r.article}-${i}`}
                type="button"
                onClick={() => openLawDetail(r)}
                className="block w-full rounded-lg border border-mist bg-white/70 px-3 py-2 text-left transition-colors hover:border-accent"
              >
                <p className="text-sm font-medium text-ink">
                  《{r.source}》{r.article}
                </p>
                <p className="mt-0.5 line-clamp-2 text-xs text-slate">{r.preview}</p>
              </button>
            ))}
          </div>
        )}
        {lawDetail && (
          <div className="mt-3">
            <LawCard law={lawDetail} />
          </div>
        )}
      </div>
    </div>
  );
}
