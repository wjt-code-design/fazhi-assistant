"use client";
import { useState } from "react";

export default function Home() {
  const [q, setQ] = useState("");
  const [a, setA] = useState("");
  const [loading, setLoading] = useState(false);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  async function ask() {
    if (!q.trim() || loading) return;
    setLoading(true);
    setA("");
    try {
      const res = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      if (!res.ok || !res.body) {
        setA(`请求失败（HTTP ${res.status}），请稍后重试`);
        return;
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let acc = "";
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        // stream:true 避免汉字在网络包裹边界被切断而变乱码
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n"); // 按完整 SSE 事件切分
        buffer = parts.pop() ?? ""; // 留下尚未凑齐的半截，等下个包裹
        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith("data: ") || line.includes("[DONE]")) continue;
          const payload = JSON.parse(line.slice(6)); // 与后端 JSON 封装对应
          if (payload.error) {
            acc += `\n[出错了] ${payload.error}`;
          } else if (payload.content) {
            acc += payload.content;
          }
          setA(acc);
        }
      }
    } catch {
      setA("网络异常，请确认后端服务已启动");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-2xl font-bold mb-6 text-gray-800">AI 法律咨询小助手</h1>
        <div className="bg-white rounded-lg shadow p-6 mb-4 min-h-[200px] whitespace-pre-wrap text-gray-700 leading-relaxed">
          {a || (loading ? "思考中..." : "请输入您的法律问题")}
        </div>
        <div className="flex gap-2">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !loading && ask()}
            placeholder="例如：劳动合同试用期最长多久？"
            className="flex-1 border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={ask}
            disabled={loading}
            className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50"
          >
            提问
          </button>
        </div>
        <p className="mt-4 text-xs text-gray-400 text-center">
          本工具基于公开法律条文生成，仅供参考，不构成正式法律意见。具体问题请咨询执业律师。
        </p>
      </div>
    </main>
  );
}
