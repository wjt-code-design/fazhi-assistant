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
}
export interface ChatMeta {
  conversation_id?: number;
  sources?: { source: string; article: string }[];
}

export async function streamChat(
  payload: ChatPayload,
  onChunk: (text: string) => void,
  onMeta: (meta: ChatMeta) => void,
  onError: (msg: string) => void
): Promise<void> {
  const token = getToken();
  const body: Record<string, unknown> = {};
  if (payload.content !== undefined) body.content = payload.content;
  if (payload.conversationId != null) body.conversation_id = payload.conversationId;
  if (payload.image) body.image = payload.image;

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
  knowledgeTest: (query: string) => api.post<any[]>("/api/admin/knowledge/test", { query }),
  qaCandidates: (status?: string) =>
    api.get<any[]>(`/api/admin/qa/candidates${status ? `?status=${status}` : ""}`),
  qaDecision: (id: number, decision: "approved" | "rejected") =>
    api.post<any>(`/api/admin/qa/${id}/decision`, { decision }),
  llmSwitch: (b: { model?: string }) =>
    api.post<any>("/api/admin/llm", b),
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
