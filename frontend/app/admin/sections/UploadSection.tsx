"use client";
// T2.4 拆分：文件上传区块（自 app/admin/page.tsx 逐行搬移，零行为变更）。
// 上传/切分预览的子状态（uploadMsg/uploading/preview 等）与 fileRef 随区块迁入。
import { useRef, useState } from "react";
import { api, adminApi } from "@/lib/api";
import { Badge, SectionTitle, Spinner } from "@/components/ui";
import type { ChunkPreviewResult } from "@/lib/types";

export function UploadSection() {
  const [uploadMsg, setUploadMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const [previewText, setPreviewText] = useState("");
  const [preview, setPreview] = useState<ChunkPreviewResult | null>(null);
  const [previewing, setPreviewing] = useState(false);

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
      setUploadMsg({
        ok: true,
        text: `已入库「${res.filename}」，切分为 ${res.added_chunks} 个知识片段，稍后即可被检索引用。`,
      });
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

  return (
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
            <span
              key={ext}
              className="rounded-md border border-mist bg-parchment px-2 py-0.5 text-xs text-slate"
            >
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
          <svg
            className="mt-0.5 shrink-0"
            width="15"
            height="15"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            {uploadMsg.ok ? (
              <path d="M20 6L9 17l-5-5" />
            ) : (
              <>
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </>
            )}
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
          <button
            className="btn btn-primary"
            onClick={runPreview}
            disabled={previewing || !previewText.trim()}
          >
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
  );
}
