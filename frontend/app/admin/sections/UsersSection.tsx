"use client";
// T2.4 拆分：用户管理区块（自 app/admin/page.tsx 逐行搬移，零行为变更）。
// 开户/禁用/删除的子状态与函数随区块迁入；users 列表状态留页面（loader 与列表共享）。
import { useState } from "react";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { Badge, EmptyState } from "@/components/ui";
import type { UserRow } from "@/lib/types";

export function UsersSection({
  users,
  setUsers,
  currentUserId,
}: {
  users: UserRow[];
  setUsers: (list: UserRow[]) => void;
  currentUserId: number;
}) {
  // 创建账号（方案C 2026-08-08：公开注册关闭，管理员开户）
  const [newUser, setNewUser] = useState({ username: "", password: "" });
  const [userMsg, setUserMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [creating, setCreating] = useState(false);

  async function toggleUser(u: UserRow) {
    await api.patch(`/api/admin/users/${u.id}`, { is_active: !u.is_active });
    setUsers(users.map((x) => (x.id === u.id ? { ...x, is_active: !u.is_active } : x)));
  }

  async function deleteUser(u: UserRow) {
    if (!window.confirm(`确定删除账号「${u.username}」？将删除其全部对话与记录，不可恢复。`)) return;
    try {
      await api.delete(`/api/admin/users/${u.id}`);
      setUsers(users.filter((x) => x.id !== u.id));
    } catch (err) {
      alert(`删除失败：${err instanceof Error ? err.message : err}`);
    }
  }

  async function createUser() {
    if (newUser.username.trim().length < 3) {
      setUserMsg({ ok: false, text: "用户名至少 3 个字符" });
      return;
    }
    if (newUser.password.length < 8) {
      setUserMsg({ ok: false, text: "密码至少 8 位" });
      return;
    }
    setCreating(true);
    setUserMsg(null);
    try {
      await api.post("/api/admin/users", {
        username: newUser.username.trim(),
        password: newUser.password,
      });
      setUserMsg({ ok: true, text: "账号已创建，可登录使用" });
      setNewUser({ username: "", password: "" });
      api
        .get<UserRow[]>("/api/admin/users")
        .then(setUsers)
        .catch(() => {});
    } catch (err) {
      setUserMsg({ ok: false, text: err instanceof Error ? err.message : "创建失败" });
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="glass-card overflow-x-auto rounded-xl">
      <div className="flex flex-wrap items-center gap-2 border-b border-mist p-4">
        <h3 className="mr-1 text-sm font-semibold text-ink">创建账号（替代公开注册）</h3>
        <input
          className="input w-36"
          value={newUser.username}
          onChange={(e) => setNewUser({ ...newUser, username: e.target.value })}
          placeholder="用户名"
        />
        <input
          className="input w-44"
          type="password"
          value={newUser.password}
          onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
          placeholder="密码（≥8 位）"
        />
        <button type="button" className="btn btn-primary" onClick={createUser} disabled={creating}>
          {creating ? "创建中…" : "创建账号"}
        </button>
        {userMsg && (
          <span className={userMsg.ok ? "text-xs text-jade" : "text-xs text-error"}>
            {userMsg.text}
          </span>
        )}
      </div>
      <table className="law-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>用户名</th>
            <th>角色</th>
            <th>状态</th>
            <th>注册时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id}>
              <td>{u.id}</td>
              <td>
                <span className="flex items-center gap-2 font-medium">
                  <span className="flex h-7 w-7 items-center justify-center rounded-full bg-mist text-xs font-semibold text-ink">
                    {u.username.slice(0, 1).toUpperCase()}
                  </span>
                  {u.username}
                </span>
              </td>
              <td>
                {u.role === "admin" ? <Badge kind="accent">管理员</Badge> : <Badge>用户</Badge>}
              </td>
              <td>
                {u.is_active ? (
                  <Badge kind="success" dot>
                    正常
                  </Badge>
                ) : (
                  <Badge kind="error" dot>
                    已禁用
                  </Badge>
                )}
              </td>
              <td className="whitespace-nowrap text-slate">
                {u.created_at ? formatDateTime(u.created_at) : "-"}
              </td>
              <td>
                <div className="flex items-center justify-end gap-1.5">
                  {u.role !== "admin" && (
                    <button className="btn btn-ghost !px-3 !py-1 text-xs" onClick={() => toggleUser(u)}>
                      {u.is_active ? "禁用" : "启用"}
                    </button>
                  )}
                  {u.id !== currentUserId && (
                    <button className="btn btn-danger !px-3 !py-1 text-xs" onClick={() => deleteUser(u)}>
                      删除
                    </button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {users.length === 0 && <EmptyState title="暂无用户" />}
    </div>
  );
}
