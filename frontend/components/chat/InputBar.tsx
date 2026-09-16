"use client";
// T2.2 自 chat/page.tsx 原样搬移（输入区区块提取为组件），零行为变更。
// hidden file input 与触发它的按钮同属本组件，refs 随迁（点击自身隐藏 input 的行为不变）。
import { useRef, type FormEvent, type ClipboardEvent } from "react";
import { Spinner } from "@/components/ui";
import type { FileInfo } from "@/lib/types";

export function InputBar({
  input,
  onInputChange,
  streaming,
  pendingImage,
  onRemoveImage,
  fileInfo,
  fileContent,
  onRemoveFile,
  caps,
  listening,
  transcribing,
  onToggleVoice,
  onPickImageFile,
  onPickFile,
  onPaste,
  onSubmit,
}: {
  input: string;
  onInputChange: (v: string) => void;
  streaming: boolean;
  pendingImage: string | null;
  onRemoveImage: () => void;
  fileInfo: FileInfo | null;
  fileContent: string | null;
  onRemoveFile: () => void;
  caps: { image_chat: boolean; voice_transcribe: boolean } | null;
  listening: boolean;
  transcribing: boolean;
  onToggleVoice: () => void;
  onPickImageFile: (f: File) => void;
  onPickFile: (f: File) => void;
  onPaste: (e: ClipboardEvent) => void;
  onSubmit: (e?: FormEvent) => void;
}) {
  const imageInputRef = useRef<HTMLInputElement>(null); // 图片选择
  const fileInputRef = useRef<HTMLInputElement>(null); // 文件（txt/pdf/docx）选择
  return (
    <form
      onSubmit={(e) => onSubmit(e)}
      className="border-t border-white/40 bg-white/45 px-4 py-4 backdrop-blur-md md:px-8 pb-safe"
    >
      <div className="mx-auto max-w-[44rem]">
        {pendingImage && (
          <div className="mb-2 inline-flex items-center gap-2 rounded-lg border border-mist bg-parchment p-1.5">
            <img src={pendingImage} alt="待发送" className="h-12 w-12 rounded object-cover" />
            <button
              type="button"
              onClick={onRemoveImage}
              className="rounded px-1.5 text-slate hover:text-error"
              aria-label="移除图片"
            >
              ✕
            </button>
          </div>
        )}
        {fileInfo && (
          <div className="mb-2 inline-flex items-center gap-2 rounded-lg border border-mist bg-parchment px-2.5 py-1.5 text-sm text-ink">
            <span className="text-slate">📄</span>
            <span className="max-w-[220px] truncate">{fileInfo.name}</span>
            <span className="text-slate/70">
              已解析 {fileInfo.chars} 字{fileInfo.truncated ? "（超长已截断）" : ""}
            </span>
            <button
              type="button"
              onClick={onRemoveFile}
              className="rounded px-1 text-slate hover:text-error"
              aria-label="移除文件"
            >
              ✕
            </button>
          </div>
        )}
        <div className="flex items-center gap-1.5 md:gap-2">
          {caps?.image_chat !== false && (
            <>
              <input
                ref={imageInputRef}
                type="file"
                accept="image/jpeg,image/png"
                capture="environment"
                className="hidden"
                onChange={(e) => e.target.files?.[0] && onPickImageFile(e.target.files[0])}
              />
              <button
                type="button"
                onClick={() => imageInputRef.current?.click()}
                disabled={streaming}
                className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-mist text-slate transition-colors hover:bg-mist hover:text-ink disabled:opacity-50"
                aria-label="上传图片"
                title="上传图片（JPEG/PNG，≤5MB）"
              >
                <svg
                  className="h-[17px] w-[17px] md:h-[18px] md:w-[18px]"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                  <circle cx="8.5" cy="8.5" r="1.5" />
                  <polyline points="21 15 16 10 5 21" />
                </svg>
              </button>
            </>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept=".txt,.md,.pdf,.docx"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && onPickFile(e.target.files[0])}
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={streaming}
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-mist text-slate transition-colors hover:bg-mist hover:text-ink disabled:opacity-50"
            aria-label="上传文件"
            title="上传文件（txt/md/pdf/docx，≤10MB）"
          >
            <svg
              className="h-[17px] w-[17px] md:h-[18px] md:w-[18px]"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
              <polyline points="13 2 13 9 20 9" />
            </svg>
          </button>
          {caps?.voice_transcribe !== false && (
            <button
              type="button"
              onClick={onToggleVoice}
              disabled={streaming || transcribing}
              className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-full border transition-colors disabled:opacity-50 ${
                listening
                  ? "border-error bg-error/10 text-error"
                  : transcribing
                    ? "border-accent bg-accent/10 text-accent"
                    : "border-mist text-slate hover:bg-mist hover:text-ink"
              }`}
              aria-label={listening ? "停止录音" : transcribing ? "语音转写中" : "语音输入"}
              title={
                listening
                  ? "停止录音"
                  : transcribing
                    ? "正在转写…"
                    : "语音输入（按住说话，松手转写）"
              }
            >
              {transcribing ? (
                <Spinner />
              ) : listening ? (
                <span className="h-3.5 w-3.5 animate-pulse rounded-full bg-error" />
              ) : (
                <svg
                  className="h-[17px] w-[17px] md:h-[18px] md:w-[18px]"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                  <line x1="12" y1="19" x2="12" y2="23" />
                  <line x1="8" y1="23" x2="16" y2="23" />
                </svg>
              )}
            </button>
          )}
          <textarea
            className="input min-w-0 flex-1 !rounded-[6px] !py-2 !text-[15px] resize-none max-h-[120px] md:!text-base"
            rows={2}
            value={input}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={(e) => {
              // Enter 发送 / Shift+Enter 换行；isComposing 防中文输入法候选态回车误发
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                onSubmit();
              }
            }}
            onPaste={onPaste}
            placeholder="请输入法律问题…（Enter 发送 · Shift+Enter 换行）"
            disabled={streaming}
          />
          <button
            type="submit"
            disabled={streaming || (!input.trim() && !pendingImage && !fileContent)}
            className="btn btn-primary h-11 w-11 shrink-0 !rounded-[6px] !p-0 shadow-md shadow-accent/25"
            aria-label="发送"
            title="发送（Enter）"
          >
            {streaming ? (
              <Spinner />
            ) : (
              <svg
                className="h-4 w-4 md:h-[17px] md:w-[17px]"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <line x1="7" y1="17" x2="17" y2="7" />
                <polyline points="7 7 17 7 17 17" />
              </svg>
            )}
          </button>
        </div>
        <p className="mt-2 text-center text-xs text-slate/70">
          回答仅供参考，不构成正式法律意见；法律可能修订，请以最新规定为准
        </p>
      </div>
    </form>
  );
}
