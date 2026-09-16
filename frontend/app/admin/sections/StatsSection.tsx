"use client";
// T2.4 拆分：系统统计区块（自 app/admin/page.tsx 逐行搬移，零行为变更）。
// 模型热切换的 sub-state（textModel/switching）随区块迁入；切换成功后经 onStats 回写页面 stats。
import { useState } from "react";
import { adminApi } from "@/lib/api";
import { Badge, Spinner, StatCard, SectionTitle } from "@/components/ui";
import type { Stats } from "@/lib/types";

export function StatsSection({ stats, onStats }: { stats: Stats; onStats: (s: Stats) => void }) {
  const [textModel, setTextModel] = useState("");
  const [switching, setSwitching] = useState(false);

  async function applySwitch() {
    const model = textModel.trim();
    if (!model) return;
    setSwitching(true);
    try {
      await adminApi.llmSwitch({ model });
      const s = await adminApi.stats();
      onStats(s);
      setTextModel("");
    } catch {
      /* ignore */
    } finally {
      setSwitching(false);
    }
  }

  return (
    <div>
      <SectionTitle>运行概览</SectionTitle>
      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3">
        <div className="sm:col-span-2">
          <StatCard
            label="累计提问（对话数）"
            value={stats.conversation_count}
            icon={
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
            }
          />
        </div>
        <StatCard
          label="注册用户"
          value={stats.user_count}
          icon={
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
              <circle cx="9" cy="7" r="4" />
              <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
              <path d="M16 3.13a4 4 0 0 1 0 7.75" />
            </svg>
          }
        />
        <StatCard
          label="知识库条目"
          value={stats.knowledge_count}
          icon={
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
              <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
            </svg>
          }
        />
        <div className="stat-card sm:col-span-2">
          <div className="stat-value text-accent">§</div>
          <div className="stat-label">基于公开法律条文 · 可通过「文件上传」持续扩充</div>
        </div>
      </div>
      <div className="glass-card mt-4 space-y-3 rounded-xl px-5 py-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="stat-label">当前模型（仅管理员可见）</div>
            <div className="mt-1 font-serif text-base font-semibold text-ink">{stats.llm_model}</div>
            <p className="mt-1 text-xs text-slate">
              知识库共 {stats.knowledge_count} 条 · 已废止 {stats.knowledge_expired ?? 0} 条
            </p>
          </div>
          <Badge kind="accent" dot>
            待审沉淀 {stats.qa_pending ?? 0}
          </Badge>
        </div>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_auto]">
          <input
            className="input"
            placeholder="新模型名，如 qwen3.5-omni-plus-2026-03-15"
            value={textModel}
            onChange={(e) => setTextModel(e.target.value)}
          />
          <button className="btn btn-primary" onClick={applySwitch} disabled={switching}>
            {switching ? <Spinner /> : "应用切换"}
          </button>
        </div>
        <p className="text-xs text-slate">
          在线热切换（运行期生效，重启回配置默认，仅同提供商模型 id）；换提供商/网关请改
          backend/.env 并重启。
        </p>
      </div>
    </div>
  );
}
