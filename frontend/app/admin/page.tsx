"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { Logo, Spinner, StatCard, Badge, SectionTitle, EmptyState } from "@/components/ui";

type Section = "stats" | "users" | "knowledge" | "upload" | "conversations";

interface Stats {
  user_count: number;
  conversation_count: number;
  knowledge_count: number;
}
interface UserRow {
  id: number;
  username: string;
  role: string;
  is_active: boolean;
  created_at: string;
}
interface KnowledgeDoc {
  id: string;
  content: string;
  metadata: { source?: string; article?: string; origin?: string };
}
interface ConvRow {
  id: number;
  username: string;
  question: string;
  answer: string;
  created_at: string;
}

const NAV: { key: Section; label: string }[] = [
  { key: "stats", label: "系统统计" },
  { key: "users", label: "用户管理" },
  { key: "knowledge", label: "知识库" },
  { key: "upload", label: "文件上传" },
  { key: "conversations", label: "对话审查" },
];

export default function AdminPage() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const [section, setSection] = useState<Section>("stats");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const [stats, setStats] = useState<Stats | null>(null);
  const [users, setUsers] = useState<UserRow[]>([]);
  const [knowledge, setKnowledge] = useState<KnowledgeDoc[]>([]);
  const [convs, setConvs] = useState<ConvRow[]>([]);
  const [loadingData, setLoadingData] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

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
      knowledge: () => api.get<KnowledgeDoc[]>("/api/admin/knowledge").then(setKnowledge),
      conversations: () => api.get<ConvRow[]>("/api/admin/conversations").then(setConvs),
      upload: () => Promise.resolve(),
    };
    loaders[section]()
      .catch(() => {})
      .finally(() => setLoadingData(false));
  }, [section, user]);

  if (loading || !user || user.role !== "admin") return null;

  async function toggleUser(u: UserRow) {
    await api.patch(`/api/admin/users/${u.id}`, { is_active: !u.is_active });
    setUsers((list) => list.map((x) => (x.id === u.id ? { ...x, is_active: !u.is_active } : x)));
  }

  async function deleteKnowledge(id: string) {
    await api.delete(`/api/admin/knowledge/${id}`);
    setKnowledge((list) => list.filter((x) => x.id !== id));
  }

  async function onUpload(files: FileList | null) {
    if (!files || files.length === 0) return;
    setUploading(true);
    setUploadMsg(null);
    try {
      const fd = new FormData();
      fd.append("file", files[0]);
      const res = await api.upload<{ filename: string; added_chunks: number }>(
        "/api/admin/knowledge/upload",
        fd
      );
      setUploadMsg({ ok: true, text: `已入库「${res.filename}」，切分为 ${res.added_chunks} 个知识片段，稍后即可被检索引用。` });
      if (fileRef.current) fileRef.current.value = "";
    } catch (e) {
      setUploadMsg({ ok: false, text: e instanceof Error ? e.message : "上传失败" });
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="flex h-screen overflow-hidden">
      {sidebarOpen && (
        <div className="fixed inset-0 z-20 bg-ink/40 md:hidden" onClick={() => setSidebarOpen(false)} />
      )}

      {/* 侧导航 */}
      <aside
        className={`fixed inset-y-0 left-0 z-30 flex w-[240px] flex-col border-r border-mist bg-white transition-transform duration-200 md:static md:translate-x-0 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between px-5 py-5">
          <Logo size="sm" />
          <button className="text-slate md:hidden" onClick={() => setSidebarOpen(false)} aria-label="关闭菜单">
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
              {n.label}
            </button>
          ))}
        </nav>
        <div className="border-t border-mist px-5 py-4">
          <button onClick={() => router.push("/chat")} className="mb-2 w-full text-left text-sm text-vermilion hover:underline">
            ← 返回问答
          </button>
          <div className="flex items-center justify-between">
            <span className="truncate text-sm text-slate">{user.username}</span>
            <button
              onClick={() => {
                logout();
                router.replace("/login");
              }}
              className="text-xs text-slate hover:text-ink"
            >
              退出
            </button>
          </div>
        </div>
      </aside>

      {/* 内容区 */}
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="h-[2px] bg-vermilion" />
        <header className="flex items-center gap-3 border-b border-mist bg-white px-5 py-3.5 md:px-8">
          <button className="text-xl leading-none text-ink md:hidden" onClick={() => setSidebarOpen(true)} aria-label="打开菜单">
            ☰
          </button>
          <h1 className="font-serif text-lg font-semibold tracking-tight">
            {NAV.find((n) => n.key === section)?.label}
          </h1>
          <Badge kind="accent">管理员</Badge>
        </header>

        <main className="flex-1 overflow-y-auto px-5 py-8 md:px-8">
          <div key={section} className="page-enter mx-auto max-w-5xl">
            {loadingData && (
              <div className="space-y-4">
                <div className="skeleton h-28" />
                <div className="skeleton h-28" />
                <div className="skeleton h-28" />
              </div>
            )}

            {/* ===== 系统统计 ===== */}
            {!loadingData && section === "stats" && stats && (
              <div>
                <SectionTitle>运行概览</SectionTitle>
                <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-3">
                  <div className="md:col-span-2">
                    <StatCard label="累计提问（对话数）" value={stats.conversation_count} />
                  </div>
                  <StatCard label="注册用户" value={stats.user_count} />
                  <StatCard label="知识库条目" value={stats.knowledge_count} />
                  <div className="stat-card md:col-span-2">
                    <div className="stat-value text-vermilion">§</div>
                    <div className="stat-label">基于公开法律条文 · 可通过"文件上传"持续扩充</div>
                  </div>
                </div>
              </div>
            )}

            {/* ===== 用户管理 ===== */}
            {!loadingData && section === "users" && (
              <div className="card overflow-x-auto">
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
                        <td className="font-medium">{u.username}</td>
                        <td>{u.role === "admin" ? <Badge kind="accent">管理员</Badge> : <Badge>用户</Badge>}</td>
                        <td>{u.is_active ? <Badge kind="success">正常</Badge> : <Badge kind="error">已禁用</Badge>}</td>
                        <td className="whitespace-nowrap text-slate">
                          {u.created_at ? new Date(u.created_at).toLocaleString("zh-CN") : "-"}
                        </td>
                        <td>
                          {u.role !== "admin" && (
                            <button className="btn btn-danger !px-3 !py-1 text-xs" onClick={() => toggleUser(u)}>
                              {u.is_active ? "禁用" : "启用"}
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {users.length === 0 && <EmptyState title="暂无用户" />}
              </div>
            )}

            {/* ===== 知识库 ===== */}
            {!loadingData && section === "knowledge" && (
              <div className="space-y-3">
                <p className="text-sm text-slate">共 {knowledge.length} 条知识片段（含种子条文与上传内容）</p>
                {knowledge.map((k) => (
                  <div key={k.id} className="card card-hover law-border-l px-5 py-4">
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-serif font-semibold text-ink">{k.metadata?.source || "未命名"}</span>
                          {k.metadata?.article && <span className="text-sm text-slate">{k.metadata.article}</span>}
                          {k.metadata?.origin === "upload" ? <Badge kind="accent">上传</Badge> : <Badge>种子</Badge>}
                        </div>
                        <p className="mt-2 line-clamp-2 text-sm leading-relaxed text-slate">{k.content}</p>
                      </div>
                      <button className="btn btn-danger shrink-0 !px-3 !py-1 text-xs" onClick={() => deleteKnowledge(k.id)}>
                        删除
                      </button>
                    </div>
                  </div>
                ))}
                {knowledge.length === 0 && <EmptyState title="知识库为空" />}
              </div>
            )}

            {/* ===== 文件上传 ===== */}
            {!loadingData && section === "upload" && (
              <div>
                <SectionTitle>上传法律知识文件</SectionTitle>
                <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate">
                  支持 .txt / .md / .pdf。文件内容会被切分并加入知识库，此后的提问即可检索并引用其中内容（RAG
                  知识库扩充，非模型训练）。
                </p>
                <div className="upload-zone mt-6" onClick={() => fileRef.current?.click()}>
                  <input
                    ref={fileRef}
                    type="file"
                    accept=".txt,.md,.pdf"
                    className="hidden"
                    onChange={(e) => onUpload(e.target.files)}
                  />
                  <p className="font-serif text-5xl text-vermilion">§</p>
                  <p className="mt-3 font-medium text-ink">
                    {uploading ? (
                      <>
                        正在入库 <Spinner className="ml-1 text-vermilion" />
                      </>
                    ) : (
                      "点击选择文件"
                    )}
                  </p>
                  <p className="mt-1 text-xs text-slate">单个文件 · 建议纯文本法律条文</p>
                </div>
                {uploadMsg && (
                  <p
                    className={`mt-4 rounded px-4 py-3 text-sm ${
                      uploadMsg.ok ? "bg-[#d1fae5] text-jade" : "bg-[#fee2e2] text-error"
                    }`}
                  >
                    {uploadMsg.text}
                  </p>
                )}
              </div>
            )}

            {/* ===== 对话审查 ===== */}
            {!loadingData && section === "conversations" && (
              <div className="card overflow-x-auto">
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
                        <td className="whitespace-nowrap text-slate">
                          {new Date(c.created_at).toLocaleString("zh-CN")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {convs.length === 0 && <EmptyState title="暂无对话记录" />}
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
