"use client";
// T2.4 拆分：知识库区块（自 app/admin/page.tsx 逐行搬移，零行为变更）。
// 含手动添加条文、受控沉淀待审、分页列表、检索测试四个子块；
// 子状态（addForm/candidates/expandedCands/testQuery/testResults 等）随区块迁入；
// knowledge/knowledgeTotal/kPage/candidates 初值由页面 loader 管理，经 props 注入。
import { useState } from "react";
import { api, adminApi } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { Badge, EmptyState, SectionTitle, Spinner } from "@/components/ui";
import type { KnowledgeDoc, KnowledgeHit, QaCandidate } from "@/lib/types";

const K_PAGE_SIZE = 50;

/** 条文时效状态徽章（阶段5） */
function StatusBadge({ status }: { status?: string }) {
  if (status === "已废止") return <Badge kind="error">已废止</Badge>;
  if (status === "即将施行") return <Badge kind="accent">即将施行</Badge>;
  return <Badge kind="success">现行</Badge>;
}

export function KnowledgeSection({
  knowledge,
  setKnowledge,
  knowledgeTotal,
  setKnowledgeTotal,
  kPage,
  setKPage,
  candidates,
  setCandidates,
}: {
  knowledge: KnowledgeDoc[];
  setKnowledge: (list: KnowledgeDoc[]) => void;
  knowledgeTotal: number;
  setKnowledgeTotal: (n: number) => void;
  kPage: number;
  setKPage: (updater: (p: number) => number) => void;
  candidates: QaCandidate[];
  setCandidates: (list: QaCandidate[]) => void;
}) {
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
  const [expandedCands, setExpandedCands] = useState<Set<number>>(new Set()); // 受控沉淀待审展开的候选 id
  const [testQuery, setTestQuery] = useState("");
  const [testResults, setTestResults] = useState<KnowledgeHit[] | null>(null);
  const [testing, setTesting] = useState(false);

  async function deleteKnowledge(id: string) {
    await api.delete(`/api/admin/knowledge/${id}`);
    setKnowledge(knowledge.filter((x) => x.id !== id));
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
      setAddForm({
        title: "",
        article: "",
        content: "",
        status: "现行",
        effective_from: "",
        effective_to: "",
      });
      const k = await api.get<{ items: KnowledgeDoc[]; total: number }>(
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

  function toggleExpandCand(id: number) {
    setExpandedCands((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function decideCand(id: number, decision: "approved" | "rejected") {
    await adminApi.qaDecision(id, decision);
    setCandidates(candidates.filter((c) => c.id !== id));
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

  return (
    <div className="space-y-3">
      {/* 手动添加条文（阶段5：含时效字段） */}
      <div className="glass-card rounded-xl px-5 py-4">
        <SectionTitle>手动添加条文</SectionTitle>
        <p className="mt-2 text-sm text-slate">
          逐条录入条文原文与时效信息（YYYY-MM-DD），用于快速补充知识库。
        </p>
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
            <span className={`text-sm ${addMsg.ok ? "text-jade" : "text-error"}`}>
              {addMsg.text}
            </span>
          )}
        </div>
      </div>

      {/* 受控沉淀待审 */}
      <div className="glass-card mt-4 rounded-xl px-5 py-4">
        <SectionTitle>受控沉淀 · 待审</SectionTitle>
        <p className="mt-2 text-sm text-slate">
          高有据且带引用的问答会自动进入此处，采纳后写入&quot;已确认问答&quot;，今后相似问题可直接复用。
        </p>
        {candidates.filter((c) => c.status === "pending").length === 0 && (
          <p className="mt-3 text-sm text-slate">暂无待审候选。</p>
        )}
        <div className="mt-3 space-y-2">
          {candidates
            .filter((c) => c.status === "pending")
            .map((c) => (
              <div key={c.id} className="rounded-lg border border-mist bg-parchment px-3 py-3">
                <div className="flex items-center gap-2 text-xs text-slate">
                  <Badge kind="accent">有据分 {c.grounded_score}</Badge>
                  {c.grounded_score >= 0.89 && (
                    <Badge kind="success" dot>
                      自动收录
                    </Badge>
                  )}
                </div>
                <p className="mt-1 text-sm font-medium text-ink">问：{c.question}</p>
                <button
                  type="button"
                  title={expandedCands.has(c.id) ? "点击收起" : "点击展开查看全文"}
                  className={`mt-1 w-full cursor-pointer text-left text-sm text-slate transition-colors hover:text-ink ${
                    expandedCands.has(c.id) ? "" : "line-clamp-3"
                  }`}
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
                  <button
                    className="btn btn-primary !px-3 !py-1 text-xs"
                    onClick={() => decideCand(c.id, "approved")}
                  >
                    采纳入库
                  </button>
                  <button
                    className="btn btn-secondary !px-3 !py-1 text-xs"
                    onClick={() => decideCand(c.id, "rejected")}
                  >
                    否决
                  </button>
                </div>
              </div>
            ))}
        </div>
      </div>

      <p className="text-sm text-slate">
        共 <span className="font-serif font-semibold text-ink">{knowledgeTotal}</span>{" "}
        条知识片段（含种子条文与上传内容，分页显示）
      </p>
      {knowledge.map((k) => (
        <div key={k.id} className="card card-hover law-border-l px-5 py-4">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-serif font-semibold text-ink">
                  {k.metadata?.source || "未命名"}
                </span>
                {k.metadata?.article && (
                  <span className="text-sm text-slate">{k.metadata.article}</span>
                )}
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
            <button
              className="btn btn-danger shrink-0 !px-3 !py-1 text-xs"
              onClick={() => deleteKnowledge(k.id)}
            >
              删除
            </button>
          </div>
        </div>
      ))}
      {knowledge.length === 0 && (
        <EmptyState title="知识库为空" hint="通过「文件上传」添加法律条文，问答时即可检索引用" />
      )}
      {knowledgeTotal > K_PAGE_SIZE && (
        <div className="mt-4 flex items-center justify-between">
          <span className="text-sm text-slate">
            第 {kPage * K_PAGE_SIZE + 1}–{Math.min((kPage + 1) * K_PAGE_SIZE, knowledgeTotal)} 条 /
            共 {knowledgeTotal} 条
          </span>
          <div className="flex gap-2">
            <button
              className="btn btn-outline"
              disabled={kPage === 0}
              onClick={() => setKPage((p) => Math.max(0, p - 1))}
            >
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
        <p className="mt-2 text-sm text-slate">
          输入一个问题，查看当前知识库会命中哪些片段及相关度（验证上传/种子是否生效）。
        </p>
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
                  <span>
                    《{h.source}》{h.article}
                  </span>
                  <span className="text-slate/70">· {h.origin}</span>
                </div>
                <p className="mt-1 line-clamp-2 text-sm text-ink">{h.chunk}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
