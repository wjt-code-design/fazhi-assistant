export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const TOKEN_KEY = "alh_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  // FormData 由浏览器自动设置 multipart 边界，不能手动写 Content-Type
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!res.ok) {
    let detail = `请求失败（HTTP ${res.status}）`;
    try {
      const data = await res.json();
      if (data.detail) {
        detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
      }
    } catch {
      /* 忽略解析错误，使用默认提示 */
    }
    throw new ApiError(res.status, detail);
  }
  const text = await res.text();
  return text ? (JSON.parse(text) as T) : ({} as T);
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "POST",
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "PATCH",
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  upload: <T>(path: string, formData: FormData) =>
    request<T>(path, { method: "POST", body: formData }),
};

// ==================== 流式问答（多轮 + 多模态） ====================
export interface ChatPayload {
  conversationId?: number | null;
  content?: string;
  image?: string; // data URL
  truncated?: boolean; // 客户端已截断（文件上传超长）——穿透给合同评估/analysis_runs
}
export interface ChatMeta {
  conversation_id?: number;
  sources?: { source: string; article: string }[];
}

// 文件→文本（合同评估/普通问答输入，二期）：复用后端 knowledge_service 解析
export interface ChatFileResult {
  file_name: string;
  ext: string;
  chars: number;
  truncated: boolean;
  text: string;
}
export function chatFile(file: File): Promise<ChatFileResult> {
  const fd = new FormData();
  fd.append("file", file);
  return api.upload<ChatFileResult>("/api/chat/file", fd);
}

// 合同评估分析进度（SSE step 事件）：确定性骨架已完成的步骤回放
export interface AnalysisStep {
  label: string;
  detail: string;
}

export async function streamChat(
  payload: ChatPayload,
  onChunk: (text: string) => void,
  onMeta: (meta: ChatMeta) => void,
  onError: (msg: string) => void,
  onSteps?: (steps: AnalysisStep[]) => void
): Promise<void> {
  const token = getToken();
  const body: Record<string, unknown> = {};
  if (payload.content !== undefined) body.content = payload.content;
  if (payload.conversationId != null) body.conversation_id = payload.conversationId;
  if (payload.image) body.image = payload.image;
  if (payload.truncated) body.truncated = payload.truncated;

  const res = await fetch(`${API_URL}/api/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });

  if (!res.ok || !res.body) {
    let detail = `请求失败（HTTP ${res.status}）`;
    try {
      const d = await res.json();
      if (d.detail) detail = d.detail;
    } catch {
      /* ignore */
    }
    onError(detail);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data: ") || line.includes("[DONE]")) continue;
      try {
        const p = JSON.parse(line.slice(6));
        if (p.error) onError(p.error);
        else if (typeof p.content === "string") onChunk(p.content);
        else if (p.type === "step" && Array.isArray(p.steps) && onSteps) onSteps(p.steps);
        if (p.conversation_id !== undefined || p.sources !== undefined) {
          onMeta({ conversation_id: p.conversation_id, sources: p.sources });
        }
      } catch {
        /* ignore malformed chunk */
      }
    }
  }
}

// ==================== 会话 ====================
export const convApi = {
  list: () => api.get<any[]>("/api/conversations"),
  detail: (id: number) => api.get<any>(`/api/conversations/${id}`),
  create: () => api.post<{ id: number }>("/api/conversations"),
  rename: (id: number, title: string) =>
    api.patch<any>(`/api/conversations/${id}?title=${encodeURIComponent(title)}`),
  remove: (id: number) => api.delete<any>(`/api/conversations/${id}`),
};

// ==================== 管理员扩展 ====================
export const adminApi = {
  stats: () => api.get<any>("/api/admin/stats"),
  addKnowledge: (b: {
    title: string;
    article: string;
    content: string;
    effective_from?: string;
    effective_to?: string;
    status?: string;
  }) => api.post<any>("/api/admin/knowledge", b),
  knowledgeTest: (query: string) => api.post<any[]>("/api/admin/knowledge/test", { query }),
  previewChunk: (text: string) => api.post<any>("/api/admin/knowledge/preview-chunk", { text }),
  qaCandidates: (status?: string) =>
    api.get<any[]>(`/api/admin/qa/candidates${status ? `?status=${status}` : ""}`),
  qaDecision: (id: number, decision: "approved" | "rejected") =>
    api.post<any>(`/api/admin/qa/${id}/decision`, { decision }),
  llmSwitch: (b: { model?: string }) =>
    api.post<any>("/api/admin/llm", b),
  llmStatus: () => api.get<any>("/api/admin/llm-status"),
  audit: (limit?: number) =>
    api.get<any[]>(`/api/admin/audit${limit ? `?limit=${limit}` : ""}`),
};

export const feedbackApi = {
  post: (b: {
    conversation_id?: number | null;
    question: string;
    answer: string;
    rating: "up" | "down";
    correction?: string;
  }) => api.post<{ id: number }>("/api/feedback", b),
};

// ==================== 法条（法条悬浮卡 / 速查面板，P1） ====================
export interface LawDetail {
  source: string;
  article: string;
  content: string;
  status?: string;
  effective_from?: string;
  effective_to?: string;
}
export interface LawItem {
  source: string;
  article: string;
  preview: string;
  content: string;
  status?: string;
}
export const lawApi = {
  detail: (source: string, article: string) =>
    api.get<LawDetail>(`/api/law?source=${encodeURIComponent(source)}&article=${encodeURIComponent(article)}`),
  search: (q: string) => api.get<LawItem[]>(`/api/law/search?q=${encodeURIComponent(q)}`),
};

// ==================== 受鉴权媒体（历史图片，Blob 缓存） ====================
const mediaCache = new Map<string, string>();
export async function loadMediaSrc(ref: string): Promise<string | null> {
  if (!ref) return null;
  const hit = mediaCache.get(ref);
  if (hit) return hit;
  const token = getToken();
  const res = await fetch(`${API_URL}/api/media/${ref}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) return null;
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  mediaCache.set(ref, url);
  return url;
}
