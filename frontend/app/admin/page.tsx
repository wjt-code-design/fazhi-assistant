"use client";
// T2.4 拆分：AdminPage 收敛为侧导航 + loader + 组装；六个区块渲染与子状态迁至 ./sections/*。
// 数据加载沿用原 loaders 模式（本页 useEffect），列表状态留页面经 props 注入，行为零变更。
import { useEffect, useState, ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { api, adminApi } from "@/lib/api";
import { Logo, Badge, Skeleton } from "@/components/ui";
import type {
  AdminSection as Section,
  Stats,
  UserRow,
  KnowledgeDoc,
  KnowledgePage,
  ConvRow,
  QaCandidate,
  AuditRow,
} from "@/lib/types";
import { StatsSection } from "./sections/StatsSection";
import { UsersSection } from "./sections/UsersSection";
import { KnowledgeSection } from "./sections/KnowledgeSection";
import { UploadSection } from "./sections/UploadSection";
import { ConversationsSection } from "./sections/ConversationsSection";
import { AuditSection } from "./sections/AuditSection";

const K_PAGE_SIZE = 50;
const ICONS: Record<Section, ReactNode> = {
  stats: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
  ),
  users: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
  ),
  knowledge: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
  ),
  upload: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
  ),
  conversations: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
  ),
  audit: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
  ),
};

const NAV: { key: Section; label: string }[] = [
  { key: "stats", label: "系统统计" },
  { key: "users", label: "用户管理" },
  { key: "knowledge", label: "知识库" },
  { key: "upload", label: "文件上传" },
  { key: "conversations", label: "对话审查" },
  { key: "audit", label: "操作日志" },
];

export default function AdminPage() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const [section, setSection] = useState<Section>("stats");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [stats, setStats] = useState<Stats | null>(null);
  const [users, setUsers] = useState<UserRow[]>([]);
  const [knowledge, setKnowledge] = useState<KnowledgeDoc[]>([]);
  const [knowledgeTotal, setKnowledgeTotal] = useState(0);
  const [kPage, setKPage] = useState(0);
  const [convs, setConvs] = useState<ConvRow[]>([]);
  const [loadingData, setLoadingData] = useState(false);
  const [candidates, setCandidates] = useState<QaCandidate[]>([]);
  const [audit, setAudit] = useState<AuditRow[]>([]);

  // 仅管理员可进
  useEffect(() => {
    if (!loading) {
      if (!user) router.replace("/login");
      else if (user.role !== "admin") router.replace("/chat");
    }
  }, [loading, user, router]);

  // 按当前区块加载数据
  useEffect(() => {
    if (!user || user.role !== "admin") return;
    setLoadingData(true);
    const loaders: Record<Section, () => Promise<unknown>> = {
      stats: () => api.get<Stats>("/api/admin/stats").then(setStats),
      users: () => api.get<UserRow[]>("/api/admin/users").then(setUsers),
      knowledge: async () => {
        const k = await api.get<KnowledgePage>(
          `/api/admin/knowledge?limit=${K_PAGE_SIZE}&offset=${kPage * K_PAGE_SIZE}`
        );
        setKnowledge(k.items);
        setKnowledgeTotal(k.total);
        // 待审列表显式取 pending——无 status 时按 created_at 倒序限 200，已决项会淹没待审项
        const c = await adminApi.qaCandidates("pending").catch(() => [] as QaCandidate[]);
        setCandidates(c);
      },
      conversations: () => api.get<ConvRow[]>("/api/admin/conversations").then(setConvs),
      audit: () => adminApi.audit().then(setAudit),
      upload: () => Promise.resolve(),
    };
    loaders[section]()
      .catch(() => {})
      .finally(() => setLoadingData(false));
  }, [section, user, kPage]);

  if (loading || !user || user.role !== "admin") return null;

  return (
    <div className="flex h-screen overflow-hidden">
      {sidebarOpen && (
        <div className="fade-in fixed inset-0 z-20 bg-ink/50 backdrop-blur-[2px] md:hidden" onClick={() => setSidebarOpen(false)} />
      )}

      {/* 侧导航（樱花海主题色玻璃卡） */}
      <aside
        className={`sidebar-glow sidebar-glass fixed inset-y-0 left-0 z-30 flex w-[240px] flex-col transition-transform duration-300 ease-out md:relative md:translate-x-0 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between px-5 py-5">
          <Logo size="sm" />
          <button className="rounded-md p-1 text-slate transition-colors hover:bg-mist md:hidden" onClick={() => setSidebarOpen(false)} aria-label="关闭菜单">
            ✕
          </button>
        </div>
        <nav className="flex-1 space-y-1 px-3">
          {NAV.map((n) => (
            <button
              key={n.key}
              className={`nav-item ${section === n.key ? "active" : ""}`}
              onClick={() => {
                setSection(n.key);
                setSidebarOpen(false);
              }}
            >
              <span className={section === n.key ? "text-accent" : "text-slate/70"}>{ICONS[n.key]}</span>
              {n.label}
            </button>
          ))}
        </nav>
        <div className="border-t border-mist px-5 py-4">
          <button onClick={() => router.push("/chat")} className="mb-2 w-full text-left text-sm text-accent transition-opacity hover:opacity-75">
            ← 返回问答
          </button>
          <div className="flex items-center justify-between gap-2">
            <span className="flex min-w-0 items-center gap-2 text-sm text-slate">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-semibold text-white">
                {user.username.slice(0, 1).toUpperCase()}
              </span>
              <span className="truncate">{user.username}</span>
            </span>
            <button
              onClick={() => {
                logout();
                router.replace("/login");
              }}
              className="shrink-0 rounded-md px-2 py-1 text-xs text-slate transition-colors hover:bg-mist hover:text-ink"
            >
              退出
            </button>
          </div>
        </div>
      </aside>

      {/* 内容区 */}
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="grad-bar h-[3px]" />
        <header className="header-blur sticky top-0 z-10 flex items-center gap-3 border-b border-mist px-5 py-3.5 md:px-8">
          <button className="rounded-md p-1 text-xl leading-none text-ink transition-colors hover:bg-mist md:hidden" onClick={() => setSidebarOpen(true)} aria-label="打开菜单">
            ☰
          </button>
          <h1 className="font-serif text-lg font-semibold tracking-tight">
            {NAV.find((n) => n.key === section)?.label}
          </h1>
          <Badge kind="accent" dot>管理员</Badge>
        </header>

        <main className="flex-1 overflow-y-auto px-5 py-8 md:px-8">
          <div key={section} className="page-enter mx-auto max-w-5xl">
            {loadingData && (
              <div className="space-y-4">
                <Skeleton className="h-28" />
                <Skeleton className="h-28" />
                <Skeleton className="h-28" />
              </div>
            )}

            {!loadingData && section === "stats" && stats && (
              <StatsSection stats={stats} onStats={setStats} />
            )}
            {!loadingData && section === "users" && (
              <UsersSection users={users} setUsers={setUsers} currentUserId={user.id} />
            )}
            {!loadingData && section === "knowledge" && (
              <KnowledgeSection
                knowledge={knowledge}
                setKnowledge={setKnowledge}
                knowledgeTotal={knowledgeTotal}
                setKnowledgeTotal={setKnowledgeTotal}
                kPage={kPage}
                setKPage={setKPage}
                candidates={candidates}
                setCandidates={setCandidates}
              />
            )}
            {!loadingData && section === "upload" && <UploadSection />}
            {!loadingData && section === "conversations" && <ConversationsSection convs={convs} />}
            {!loadingData && section === "audit" && <AuditSection audit={audit} />}
          </div>
        </main>
      </div>
    </div>
  );
}
