"use client";
// T2.2 自 chat/page.tsx 原样搬移（侧栏区块提取为组件），零行为变更。
import { Logo } from "@/components/ui";
import type { ConversationItem } from "@/lib/types";
import type { AuthUser } from "@/lib/auth";

// 仅声明侧栏用到的导航能力；AppRouterInstance（next/navigation）结构上兼容
type Nav = { push: (href: string) => void; replace: (href: string) => void };

export function Sidebar({
  open,
  history,
  activeId,
  streaming,
  user,
  onClose,
  onNewChat,
  onSelectConv,
  onDeleteConv,
  onLogout,
  router,
}: {
  open: boolean;
  history: ConversationItem[];
  activeId: number | null;
  streaming: boolean;
  user: AuthUser;
  onClose: () => void;
  onNewChat: () => void;
  onSelectConv: (item: ConversationItem) => void;
  onDeleteConv: (id: number) => void;
  onLogout: () => void;
  router: Nav;
}) {
  return (
    <>
      {open && (
        <div
          className="fade-in fixed inset-0 z-20 bg-ink/50 backdrop-blur-[2px] md:hidden"
          onClick={onClose}
        />
      )}
      <aside
        className={`sidebar-glow sidebar-glass fixed inset-y-0 left-0 z-30 flex w-[280px] max-w-[85vw] flex-col text-ink transition-transform duration-300 ease-out md:relative md:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between px-3 py-5">
          <Logo size="sm" />
          <button
            className="rounded-md p-1 text-ink/50 transition-colors hover:bg-accent/10 hover:text-accent md:hidden"
            onClick={onClose}
            aria-label="关闭菜单"
          >
            ✕
          </button>
        </div>
        <div className="px-3">
          <button onClick={onNewChat} className="btn btn-primary w-full shadow-md shadow-accent/20">
            <span className="text-base leading-none">＋</span> 新对话
          </button>
        </div>
        <div className="mt-6 flex-1 overflow-y-auto px-3 pb-4">
          <p className="px-2 pb-2 text-xs tracking-wide text-slate">历史会话</p>
          {history.length === 0 && <p className="px-2 text-sm text-slate/70">暂无记录</p>}
          {history.map((h) => (
            <div
              key={h.id}
              className={`chat-item group relative ${activeId === h.id ? "active" : ""}`}
              onClick={() => onSelectConv(h)}
            >
              <p className="flex items-center gap-1.5 truncate pr-5 text-sm text-ink/90">
                {h.has_image && <span className="text-slate">🖼</span>}
                <span className="truncate">{h.title || h.preview || "新对话"}</span>
              </p>
              <p className="mt-0.5 truncate text-xs text-slate">{h.preview}</p>
              <button
                type="button"
                aria-label={`删除会话 ${h.title || h.preview || "新对话"}`}
                title="删除会话"
                className="absolute right-1.5 top-1/2 flex h-5 w-5 -translate-y-1/2 items-center justify-center rounded-full text-xs text-slate opacity-100 transition-opacity hover:bg-mist hover:text-ink md:opacity-0 md:group-hover:opacity-100"
                onClick={(e) => {
                  e.stopPropagation();
                  onDeleteConv(h.id);
                }}
              >
                ✕
              </button>
            </div>
          ))}
        </div>
        <div className="border-t border-mist px-3 py-4">
          {user.role === "admin" && (
            <button
              onClick={() => router.push("/admin")}
              disabled={streaming}
              className="mb-2 w-full text-left text-sm text-accent-deep transition-colors hover:text-accent disabled:cursor-not-allowed disabled:opacity-50"
            >
              管理后台 →
            </button>
          )}
          <div className="flex items-center justify-between gap-2">
            <span className="flex min-w-0 items-center gap-2 text-sm text-ink/70">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent/90 text-xs font-semibold text-white">
                {user.username.slice(0, 1).toUpperCase()}
              </span>
              <span className="truncate">{user.username}</span>
            </span>
            <button
              onClick={onLogout}
              className="shrink-0 rounded-md px-2 py-1 text-xs text-slate transition-colors hover:bg-mist hover:text-ink"
            >
              退出
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
