"use client";
import { useEffect, useRef, useState, ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { api, adminApi } from "@/lib/api";
import { Logo, Spinner, StatCard, Badge, SectionTitle, EmptyState, Skeleton } from "@/components/ui";

type Section = "stats" | "users" | "knowledge" | "upload" | "conversations" | "audit";
interface Stats {
  user_count: number;
  conversation_count: number;
  knowledge_count: number;
  knowledge_expired?: number;
  llm_model: string;
  qa_pending?: number;
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
  metadata: { source?: string; article?: string; origin?: string; status?: string; effective_from?: string; effective_to?: string };
}
interface KnowledgePage {
  items: KnowledgeDoc[];
  total: number;
}
const K_PAGE_SIZE = 50;
interface ConvRow {
  id: number;
  username: string;
  question: string;
  answer: string;
  created_at: string;
}
interface QaCandidate {
  id: number;
  question: string;
  answer: string;
  grounded_score: number;
  evidence: string;
  status: string;
  created_at?: string;
}
interface KnowledgeHit {
  chunk: string;
  source: string;
  article: string;
  origin: string;
  status?: string;
  effective_from?: string;
  effective_to?: string;
  score: number;
}
interface AuditRow {
  id: number;
  admin: string;
  action: string;
  target: string;
  detail: string;
  created_at?: string;
}
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

/** 条文时效状态徽章（阶段5） */
function StatusBadge({ status }: { status?: string }) {
  if (status === "已废止") return <Badge kind="error">已废止</Badge>;
  if (status === "即将施行") return <Badge kind="accent">即将施行</Badge>;
  return <Badge kind="success">现行</Badge>;
}

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
  const [uploadMsg, setUploadMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const [candidates, setCandidates] = useState<QaCandidate[]>([]);
  const [expandedCands, setExpandedCands] = useState<Set<number>>(new Set()); // 受控沉淀待审展开的候选 id
  const [testQuery, setTestQuery] = useState("");
  const [testResults, setTestResults] = useState<KnowledgeHit[] | null>(null);
  const [testing, setTesting] = useState(false);
  const [switching, setSwitching] = useState(false);
  const [textModel, setTextModel] = useState("");
  const [audit, setAudit] = useState<AuditRow[]>([]);
  const [addForm, setAddForm] = useState({
    title: "",
    article: "",
    content: "",
    status: "现行",
    effective_from: "",
    effective_to: "",
  });
  const [addMsg, setAddMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [adding, setAdding] = useState(false);
  const [previewText, setPreviewText] = useState("");
  const [preview, setPreview] = useState<{
    mode: string;
    count: number;
    chunks: { article: string; chapter: string; chars: number; content: string }[];
  } | null>(null);
  const [previewing, setPreviewing] = useState(false);

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

  async function toggleUser(u: UserRow) {
    await api.patch(`/api/admin/users/${u.id}`, { is_active: !u.is_active });
    setUsers((list) => list.map((x) => (x.id === u.id ? { ...x, is_active: !u.is_active } : x)));
  }

  function toggleExpandCand(id: number) {
    setExpandedCands((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function deleteUser(u: UserRow) {
    if (!window.confirm(`确定删除账号「${u.username}」？将删除其全部对话与记录，不可恢复。`)) return;
    try {
      await api.delete(`/api/admin/users/${u.id}`);
      setUsers((list) => list.filter((x) => x.id !== u.id));
    } catch (err) {
      alert(`删除失败：${err instanceof Error ? err.message : err}`);
    }
  }

  async function deleteKnowledge(id: string) {
    await api.delete(`/api/admin/knowledge/${id}`);
    setKnowledge((list) => list.filter((x) => x.id !== id));
  }

  async function submitAdd() {
    if (!addForm.title.trim() || !addForm.content.trim()) {
      setAddMsg({ ok: false, text: "法律名称与条文内容必填" });
      return;
    }
    setAdding(true);
    setAddMsg(null);
    try {
      await adminApi.addKnowledge({
        title: addForm.title.trim(),
        article: addForm.article.trim(),
        content: addForm.content.trim(),
        effective_from: addForm.effective_from || undefined,
        effective_to: addForm.effective_to || undefined,
        status: addForm.status,
      });
      setAddMsg({ ok: true, text: `已入库「${addForm.title.trim()}」，稍后即可被检索引用。` });
      setAddForm({ title: "", article: "", content: "", status: "现行", effective_from: "", effective_to: "" });
      const k = await api.get<KnowledgePage>(
        `/api/admin/knowledge?limit=${K_PAGE_SIZE}&offset=${kPage * K_PAGE_SIZE}`
      );
      setKnowledge(k.items);
      setKnowledgeTotal(k.total);
    } catch (e) {
      setAddMsg({ ok: false, text: e instanceof Error ? e.message : "添加失败" });
    } finally {
      setAdding(false);
    }
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

  async function runPreview() {
    if (!previewText.trim()) return;
    setPreviewing(true);
    try {
      setPreview(await adminApi.previewChunk(previewText));
    } catch {
      setPreview(null);
    } finally {
      setPreviewing(false);
    }
  }

  async function runKnowledgeTest() {
    const q = testQuery.trim();
    if (!q) return;
    setTesting(true);
    try {
      const r = await adminApi.knowledgeTest(q);
      setTestResults(r);
    } catch {
      setTestResults([]);
    } finally {
      setTesting(false);
    }
  }

  async function decideCand(id: number, decision: "approved" | "rejected") {
    await adminApi.qaDecision(id, decision);
    setCandidates((list) => list.filter((c) => c.id !== id));
  }

  async function applySwitch() {
    const model = textModel.trim();
    if (!model) return;
    setSwitching(true);
    try {
      await adminApi.llmSwitch({ model });
      const s = await adminApi.stats();
      setStats(s);
      setTextModel("");
    } catch {
      /* ignore */
    } finally {
      setSwitching(false);
    }
  }

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

            {/* ===== 系统统计 ===== */}
            {!loadingData && section === "stats" && stats && (
              <div>
                <SectionTitle>运行概览</SectionTitle>
                <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3">
                  <div className="sm:col-span-2">
                    <StatCard
                      label="累计提问（对话数）"
                      value={stats.conversation_count}
                      icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>}
                    />
                  </div>
                  <StatCard
                    label="注册用户"
                    value={stats.user_count}
                    icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>}
                  />
                  <StatCard
                    label="知识库条目"
                    value={stats.knowledge_count}
                    icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>}
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
                    <Badge kind="accent" dot>待审沉淀 {stats.qa_pending ?? 0}</Badge>
                  </div>
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_auto]">
                    <input className="input" placeholder="新模型名，如 qwen3.5-omni-plus-2026-03-15" value={textModel} onChange={(e) => setTextModel(e.target.value)} />
                    <button className="btn btn-primary" onClick={applySwitch} disabled={switching}>
                      {switching ? <Spinner /> : "应用切换"}
                    </button>
                  </div>
                  <p className="text-xs text-slate">在线热切换（运行期生效，重启回配置默认，仅同提供商模型 id）；换提供商/网关请改 backend/.env 并重启。</p>
                </div>
              </div>
            )}

            {/* ===== 用户管理 ===== */}
            {!loadingData && section === "users" && (
              <div className="glass-card overflow-x-auto rounded-xl">
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
                        <td>{u.role === "admin" ? <Badge kind="accent">管理员</Badge> : <Badge>用户</Badge>}</td>
                        <td>{u.is_active ? <Badge kind="success" dot>正常</Badge> : <Badge kind="error" dot>已禁用</Badge>}</td>
                        <td className="whitespace-nowrap text-slate">
                          {u.created_at ? new Date(u.created_at).toLocaleString("zh-CN") : "-"}
                        </td>
                        <td>
                          <div className="flex items-center justify-end gap-1.5">
                            {u.role !== "admin" && (
                              <button className="btn btn-ghost !px-3 !py-1 text-xs" onClick={() => toggleUser(u)}>
                                {u.is_active ? "禁用" : "启用"}
                              </button>
                            )}
                            {u.id !== user.id && (
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
            )}

            {/* ===== 知识库 ===== */}
            {!loadingData && section === "knowledge" && (
              <div className="space-y-3">
                {/* 手动添加条文（阶段5：含时效字段） */}
                <div className="glass-card rounded-xl px-5 py-4">
                  <SectionTitle>手动添加条文</SectionTitle>
                  <p className="mt-2 text-sm text-slate">逐条录入条文原文与时效信息（YYYY-MM-DD），用于快速补充知识库。</p>
                  <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-[1fr_160px_1fr_1fr]">
                    <input
                      className="input"
                      placeholder="法律名称，如 劳动法"
                      value={addForm.title}
                      onChange={(e) => setAddForm((f) => ({ ...f, title: e.target.value }))}
                    />
                    <input
                      className="input"
                      placeholder="条号，如 第三条"
                      value={addForm.article}
                      onChange={(e) => setAddForm((f) => ({ ...f, article: e.target.value }))}
                    />
                    <select
                      className="input"
                      value={addForm.status}
                      onChange={(e) => setAddForm((f) => ({ ...f, status: e.target.value }))}
                    >
                      <option value="现行">现行</option>
                      <option value="已废止">已废止</option>
                      <option value="即将施行">即将施行</option>
                    </select>
                    <div className="flex gap-2">
                      <input
                        type="date"
                        className="input"
                        value={addForm.effective_from}
                        onChange={(e) => setAddForm((f) => ({ ...f, effective_from: e.target.value }))}
                        title="施行日期"
                      />
                      <input
                        type="date"
                        className="input"
                        value={addForm.effective_to}
                        onChange={(e) => setAddForm((f) => ({ ...f, effective_to: e.target.value }))}
                        title="废止日期"
                      />
                    </div>
                  </div>
                  <textarea
                    className="input mt-3 min-h-[96px]"
                    placeholder="条文原文（请粘贴权威原文，一字不差）"
                    value={addForm.content}
                    onChange={(e) => setAddForm((f) => ({ ...f, content: e.target.value }))}
                  />
                  <div className="mt-3 flex items-center gap-3">
                    <button className="btn btn-primary" onClick={submitAdd} disabled={adding}>
                      {adding ? <Spinner /> : "添加入库"}
                    </button>
                    {addMsg && (
                      <span className={`text-sm ${addMsg.ok ? "text-jade" : "text-error"}`}>{addMsg.text}</span>
                    )}
                  </div>
                </div>

                <p className="text-sm text-slate">
                  共 <span className="font-serif font-semibold text-ink">{knowledgeTotal}</span> 条知识片段（含种子条文与上传内容，分页显示）
                </p>
                {knowledge.map((k) => (
                  <div key={k.id} className="card card-hover law-border-l px-5 py-4">
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-serif font-semibold text-ink">{k.metadata?.source || "未命名"}</span>
                          {k.metadata?.article && <span className="text-sm text-slate">{k.metadata.article}</span>}
                          <StatusBadge status={k.metadata?.status} />
                          {k.metadata?.origin === "upload" ? (
                            <Badge kind="accent">上传</Badge>
                          ) : k.metadata?.origin === "import" ? (
                            <Badge kind="neutral">导入</Badge>
                          ) : (
                            <Badge>种子</Badge>
                          )}
                        </div>
                        {(k.metadata?.effective_from || k.metadata?.effective_to) && (
                          <p className="mt-1 text-xs text-slate">
                            {k.metadata?.effective_from ? `${k.metadata.effective_from} 起` : ""}
                            {k.metadata?.effective_to ? `  ${k.metadata.effective_to} 止` : ""}
                          </p>
                        )}
                        <p className="mt-2 line-clamp-2 text-sm leading-relaxed text-slate">{k.content}</p>
                      </div>
                      <button className="btn btn-danger shrink-0 !px-3 !py-1 text-xs" onClick={() => deleteKnowledge(k.id)}>
                        删除
                      </button>
                    </div>
                  </div>
                ))}
                {knowledge.length === 0 && <EmptyState title="知识库为空" hint="通过「文件上传」添加法律条文，问答时即可检索引用" />}
                {knowledgeTotal > K_PAGE_SIZE && (
                  <div className="mt-4 flex items-center justify-between">
                    <span className="text-sm text-slate">
                      第 {kPage * K_PAGE_SIZE + 1}–{Math.min((kPage + 1) * K_PAGE_SIZE, knowledgeTotal)} 条 / 共 {knowledgeTotal} 条
                    </span>
                    <div className="flex gap-2">
                      <button className="btn btn-outline" disabled={kPage === 0} onClick={() => setKPage((p) => Math.max(0, p - 1))}>
                        上一页
                      </button>
                      <button
                        className="btn btn-outline"
                        disabled={(kPage + 1) * K_PAGE_SIZE >= knowledgeTotal}
                        onClick={() => setKPage((p) => p + 1)}
                      >
                        下一页
                      </button>
                    </div>
                  </div>
                )}

                {/* 检索测试 */}
                <div className="glass-card mt-4 rounded-xl px-5 py-4">
                  <SectionTitle>检索测试</SectionTitle>
                  <p className="mt-2 text-sm text-slate">输入一个问题，查看当前知识库会命中哪些片段及相关度（验证上传/种子是否生效）。</p>
                  <div className="mt-3 flex gap-2">
                    <input
                      className="input flex-1"
                      placeholder="例如：试用期最长多久"
                      value={testQuery}
                      onChange={(e) => setTestQuery(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && runKnowledgeTest()}
                    />
                    <button className="btn btn-primary" onClick={runKnowledgeTest} disabled={testing}>
                      {testing ? <Spinner /> : "测试"}
                    </button>
                  </div>
                  {testResults && (
                    <div className="mt-3 space-y-2">
                      {testResults.length === 0 && <p className="text-sm text-slate">无命中。</p>}
                      {testResults.map((h, i) => (
                        <div key={i} className="rounded-lg border border-mist bg-parchment px-3 py-2">
                          <div className="flex items-center gap-2 text-xs text-slate">
                            <Badge kind="accent">相关度 {h.score}</Badge>
                            <StatusBadge status={h.status} />
                            <span>《{h.source}》{h.article}</span>
                            <span className="text-slate/70">· {h.origin}</span>
                          </div>
                          <p className="mt-1 line-clamp-2 text-sm text-ink">{h.chunk}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* 受控沉淀待审 */}
                <div className="glass-card mt-4 rounded-xl px-5 py-4">
                  <SectionTitle>受控沉淀 · 待审</SectionTitle>
                  <p className="mt-2 text-sm text-slate">高有据且带引用的问答会自动进入此处，采纳后写入"已确认问答"，今后相似问题可直接复用。</p>
                  {candidates.filter((c) => c.status === "pending").length === 0 && <p className="mt-3 text-sm text-slate">暂无待审候选。</p>}
                  <div className="mt-3 space-y-2">
                    {candidates
                      .filter((c) => c.status === "pending")
                      .map((c) => (
                        <div key={c.id} className="rounded-lg border border-mist bg-parchment px-3 py-3">
                          <div className="flex items-center gap-2 text-xs text-slate">
                            <Badge kind="accent">有据分 {c.grounded_score}</Badge>
                            {c.grounded_score >= 0.89 && <Badge kind="success" dot>自动收录</Badge>}
                          </div>
                          <p className="mt-1 text-sm font-medium text-ink">问：{c.question}</p>
                          <button
                            type="button"
                            title={expandedCands.has(c.id) ? "点击收起" : "点击展开查看全文"}
                            className={`mt-1 block w-full cursor-pointer text-left text-sm text-slate transition-colors hover:text-ink ${expandedCands.has(c.id) ? "" : "line-clamp-3"}`}
                            onClick={() => toggleExpandCand(c.id)}
                          >
                            答：{c.answer}
                          </button>
                          <button
                            type="button"
                            className="mt-1 text-xs text-slate/60 transition-colors hover:text-accent"
                            onClick={() => toggleExpandCand(c.id)}
                          >
                            {expandedCands.has(c.id) ? "收起 ▲" : "展开全文 ▼"}
                          </button>
                          <div className="mt-2 flex gap-2">
                            <button className="btn btn-primary !px-3 !py-1 text-xs" onClick={() => decideCand(c.id, "approved")}>
                              采纳入库
                            </button>
                            <button className="btn btn-secondary !px-3 !py-1 text-xs" onClick={() => decideCand(c.id, "rejected")}>
                              否决
                            </button>
                          </div>
                        </div>
                      ))}
                  </div>
                </div>
              </div>
            )}

            {/* ===== 文件上传 ===== */}
            {!loadingData && section === "upload" && (
              <div>
                <SectionTitle>上传法律知识文件</SectionTitle>
                <p className="mt-3 max-w-2xl text-sm leading-relaxed text-slate">
                  支持 .txt / .md / .pdf / .docx。文件内容会被切分并加入知识库，此后的提问即可检索并引用其中内容（RAG
                  知识库扩充，非模型训练）。
                </p>
                <div className="upload-zone mt-6" onClick={() => fileRef.current?.click()}>
                  <input
                    ref={fileRef}
                    type="file"
                    accept=".txt,.md,.pdf,.docx"
                    className="hidden"
                    onChange={(e) => onUpload(e.target.files)}
                  />
                  <p className="font-serif text-5xl text-accent">§</p>
                  <p className="mt-3 font-medium text-ink">
                    {uploading ? (
                      <span className="inline-flex items-center gap-2">
                        正在入库 <Spinner className="text-accent" />
                      </span>
                    ) : (
                      "点击选择文件"
                    )}
                  </p>
                  <p className="mt-1 text-xs text-slate">单个文件 · 建议纯文本法律条文</p>
                  <div className="mt-4 flex items-center justify-center gap-2">
                    {[".txt", ".md", ".pdf", ".docx"].map((ext) => (
                      <span key={ext} className="rounded-md border border-mist bg-parchment px-2 py-0.5 text-xs text-slate">
                        {ext}
                      </span>
                    ))}
                  </div>
                </div>
                {uploadMsg && (
                  <p
                    className={`scale-in mt-4 flex items-start gap-2 rounded-lg border px-4 py-3 text-sm ${
                      uploadMsg.ok
                        ? "border-jade/40 bg-[var(--jade-tint)] text-jade"
                        : "border-error/40 bg-[var(--error-tint)] text-error"
                    }`}
                  >
                    <svg className="mt-0.5 shrink-0" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      {uploadMsg.ok ? <path d="M20 6L9 17l-5-5"/> : <><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></>}
                    </svg>
                    {uploadMsg.text}
                  </p>
                )}

                {/* 切分预览（阶段6）：结构化切分不写库，核对条号边界 */}
                <div className="glass-card mt-4 rounded-xl px-5 py-4">
                  <SectionTitle>切分预览</SectionTitle>
                  <p className="mt-2 text-sm text-slate">
                    粘贴文档正文，预览结构化切分结果（按「第X条」边界、章节前缀、目录页跳过）。确认无误再上传正式入库。
                  </p>
                  <textarea
                    className="input mt-3 min-h-[120px]"
                    placeholder="粘贴法律文档正文…"
                    value={previewText}
                    onChange={(e) => setPreviewText(e.target.value)}
                  />
                  <div className="mt-3 flex items-center gap-3">
                    <button className="btn btn-primary" onClick={runPreview} disabled={previewing || !previewText.trim()}>
                      {previewing ? <Spinner /> : "预览切分"}
                    </button>
                    {preview && (
                      <span className={`text-sm ${preview.mode === "structured" ? "text-jade" : "text-slate"}`}>
                        {preview.mode === "structured"
                          ? `结构化切分：${preview.count} 个片段`
                          : `未识别到条号边界，回退段落切分：${preview.count} 个片段`}
                      </span>
                    )}
                  </div>
                  {preview && preview.chunks.length > 0 && (
                    <div className="mt-3 space-y-2">
                      {preview.chunks.map((c, i) => (
                        <div key={i} className="rounded-lg border border-mist bg-parchment px-3 py-2">
                          <div className="flex items-center gap-2 text-xs text-slate">
                            {c.article && <Badge kind="accent">{c.article}</Badge>}
                            {c.chapter && <span>{c.chapter}</span>}
                            <span>{c.chars} 字</span>
                          </div>
                          <p className="mt-1 line-clamp-2 text-sm text-ink">{c.content}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* ===== 对话审查 ===== */}
            {!loadingData && section === "conversations" && (
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

            {/* ===== 操作日志 ===== */}
            {!loadingData && section === "audit" && (
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
                        <td><Badge kind="accent">{a.action}</Badge></td>
                        <td className="max-w-[180px] truncate text-slate">{a.target}</td>
                        <td className="max-w-[260px] truncate text-slate">{a.detail}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {audit.length === 0 && <EmptyState title="暂无操作记录" />}
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
