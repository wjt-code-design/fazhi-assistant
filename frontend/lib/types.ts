// 集中类型定义（T2.0）：自 chat/admin 页面原样迁移，字段与语义零变更。
// SSE 契约类型（ChatMeta/AnalysisStep）仍由 lib/api.ts 持有，此处按 type 引用。
import type { AnalysisStep } from "./api";
import type { CoverageInfo } from "./coverage";
import type { ScopeCandidate } from "./scope";

export interface Msg {
  role: "user" | "assistant";
  content: string;
  imageDataURL?: string; // 本轮刚发送的本地预览
  imgRef?: string; // 历史：原图相对路径
  thumbRef?: string; // 历史：缩略图相对路径
  sources?: { source: string; article: string }[]; // 参考条文（ADR-012 阶段2C：回答下方折叠展示）
  steps?: AnalysisStep[]; // 合同评估分析进度（SSE step 事件）
  scopeCandidates?: ScopeCandidate[]; // 范围选择候选（卡片渲染用）；随消息存，天然随新会话/切换重置
  agentNote?: { kind: "clarification"; round: number } | { kind: "error"; code?: string };
  // T1（2026-09-16）：结构化覆盖状态（partial 顶部提示用）；实时由 SSE final 帧写入、历史由消息投影映射
  coverage?: CoverageInfo;
}

// 侧栏历史会话项（convApi.list 返回元素）
export interface ConversationItem {
  id: number;
  title: string;
  preview: string;
  message_count: number;
  has_image: boolean;
  last_active_at?: string;
  created_at: string;
}

// convApi.detail 返回的历史消息（后端字段），映射为 Msg 展示（P3-4 收紧 any）
export interface HistoryMsg {
  role?: string;
  content?: string;
  image_ref?: string;
  thumb_ref?: string;
  // T1（2026-09-16）：覆盖投影（assistant 消息为 full/partial/unknown；用户消息 null）
  coverage_status?: "full" | "partial" | "unknown" | null;
  uncovered_issues?: { issue_id: string; reason_code: string }[] | null;
}

export interface ConversationDetail {
  messages?: HistoryMsg[];
}

// 配额预警（B 更优版，grilling）：/api/utility/quota 公开接口的响应
export interface QuotaWarn {
  embedding_warn?: boolean;
  embedding_depleted?: boolean;
  embedding_pct?: number;
  embedding_model?: string;
  rerank_degraded?: boolean;
}

export interface FileInfo {
  name: string;
  chars: number;
  truncated: boolean;
}

export interface PendingAgentRun {
  runId: string;
  stateVersion: number;
}

export interface ExpandedLaw {
  msgIndex: number;
  source: string;
  article: string;
  content: string;
  status?: string;
  found: boolean;
  occurrence: number;
}

export type DailyLaw = { src: string; art: string; text: string; q: string };

// ==================== admin ====================

export type AdminSection = "stats" | "users" | "knowledge" | "upload" | "conversations" | "audit";

export interface Stats {
  user_count: number;
  conversation_count: number;
  knowledge_count: number;
  knowledge_expired?: number;
  llm_model: string;
  qa_pending?: number;
}

export interface UserRow {
  id: number;
  username: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface KnowledgeDoc {
  id: string;
  content: string;
  metadata: {
    source?: string;
    article?: string;
    origin?: string;
    status?: string;
    effective_from?: string;
    effective_to?: string;
  };
}

export interface KnowledgePage {
  items: KnowledgeDoc[];
  total: number;
}

export interface ConvRow {
  id: number;
  username: string;
  question: string;
  answer: string;
  created_at: string;
}

export interface QaCandidate {
  id: number;
  question: string;
  answer: string;
  grounded_score: number;
  evidence: string;
  status: string;
  created_at?: string;
}

export interface KnowledgeHit {
  chunk: string;
  source: string;
  article: string;
  origin: string;
  status?: string;
  effective_from?: string;
  effective_to?: string;
  score: number;
}

export interface AuditRow {
  id: number;
  admin: string;
  action: string;
  target: string;
  detail: string;
  created_at?: string;
}

// ==================== api 端点响应（T2.5 消灭 any）====================

// 切分预览（字段取自 admin 页 preview state 原定义）
export interface ChunkPreviewResult {
  mode: string;
  count: number;
  chunks: { article: string; chapter: string; chars: number; content: string }[];
}

// qa 决策（backend main.py admin_qa_decision 核实：返回 {id, status}；前端不消费字段）
export interface QaDecisionResult {
  id: number;
  status: string;
}

// 以下端点前端均不消费响应字段（llm-switch 返回 registry 配置快照，形状随配置演进），
// 用开放记录保住调用点行为，同时消除 any。
export type LlmSwitchResult = Record<string, unknown>;
export type LlmStatusResult = Record<string, unknown>;
export type KnowledgeAddResult = Record<string, unknown>;
