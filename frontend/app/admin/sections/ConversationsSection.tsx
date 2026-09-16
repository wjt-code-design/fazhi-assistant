"use client";
// T2.4 拆分：对话审查区块（自 app/admin/page.tsx 逐行搬移，零行为变更）。无子状态。
import { EmptyState } from "@/components/ui";
import { formatDateTime } from "@/lib/format";
import type { ConvRow } from "@/lib/types";

export function ConversationsSection({ convs }: { convs: ConvRow[] }) {
  return (
    <div className="glass-card overflow-x-auto rounded-xl">
      <table className="law-table">
        <thead>
          <tr>
            <th>用户</th>
            <th>提问</th>
            <th>回答摘要</th>
            <th>时间</th>
          </tr>
        </thead>
        <tbody>
          {convs.map((c) => (
            <tr key={c.id}>
              <td className="whitespace-nowrap font-medium">{c.username}</td>
              <td className="max-w-[200px] truncate">{c.question}</td>
              <td className="max-w-[320px] truncate text-slate">{c.answer}</td>
              <td className="whitespace-nowrap text-slate">{formatDateTime(c.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {convs.length === 0 && <EmptyState title="暂无对话记录" />}
    </div>
  );
}
