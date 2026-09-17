"use client";
// T2.4 拆分：操作日志区块（自 app/admin/page.tsx 逐行搬移，零行为变更）。无子状态。
import { Badge, EmptyState } from "@/components/ui";
import type { AuditRow } from "@/lib/types";

export function AuditSection({ audit }: { audit: AuditRow[] }) {
  return (
    <div className="glass-card overflow-x-auto rounded-xl">
      <table className="law-table">
        <thead>
          <tr>
            <th>时间</th>
            <th>管理员</th>
            <th>操作</th>
            <th>对象</th>
            <th>详情</th>
          </tr>
        </thead>
        <tbody>
          {audit.map((a) => (
            <tr key={a.id}>
              <td className="whitespace-nowrap text-slate">
                {a.created_at ? new Date(a.created_at).toLocaleString("zh-CN") : "-"}
              </td>
              <td className="font-medium">{a.admin}</td>
              <td>
                <Badge kind="accent">{a.action}</Badge>
              </td>
              <td className="max-w-[180px] truncate text-slate">{a.target}</td>
              <td className="max-w-[260px] truncate text-slate">{a.detail}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {audit.length === 0 && <EmptyState title="暂无操作记录" />}
    </div>
  );
}
