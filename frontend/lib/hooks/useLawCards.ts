"use client";
// 法条内联卡：run 证据快照 / 无 run 的当前条文，缓存随页面生命周期隔离。
import { useRef, useState } from "react";
import { lawApi, LawDetail } from "@/lib/api";
import { LAW_CACHE_MAX } from "@/lib/constants";
import type { ExpandedLaw } from "@/lib/types";

// 法条卡缓存：同「run+书名+条号」只请求一次后端。
// 带上限 + 最旧淘汰（与 mediaCache 策略一致，对抗审计 v2 #9 同族修复）：长会话不无界增长。
export function useLawCards() {
  // 缓存不跨组件生命周期/登录用户共享；run 是历史版本隔离键。
  const lawCache = useRef(new Map<string, Promise<LawDetail | null>>()).current;
  const requestVersion = useRef(0);
  const pendingTarget = useRef<string | null>(null);
  // 点击法条 → 卡片在该法条下一行内联展开（再点收起）
  const [expandedLaw, setExpandedLaw] = useState<ExpandedLaw | null>(null);

  // 从 .law-ref 的 data-source（书名，含省略书名号的独立条号）+ 文本条号 → 后端查原文。
  // 同版本条文只发一次请求；失败可重试，不回退到另一版本。
  function fetchLawRefCached(el: Element, runId?: string): Promise<LawDetail | null> {
    const src = el.getAttribute("data-source");
    const m = (el.textContent || "").match(
      /第\s*([零〇○一二三四五六七八九十百千万0-9０-９]+)\s*条(之[一二三四五六七八九十百千万0-9０-９]+)?/
    );
    if (!src || !m) return Promise.resolve(null);
    const article = `第${m[1]}条${m[2] || ""}`;
    // 历史快照与当前条文使用不同键。
    const key = JSON.stringify([runId || null, src, article]);
    let p = lawCache.get(key);
    if (!p) {
      // 库内 article 存完整「第X条」中文条号（精确匹配），必须拼回完整形式，否则数字/缺字 404
      // B3（2026-08-07）：后端 /api/law 已 _normalize_article 归一（〇零/阿拉伯/之条），直接传原文条号
      p = lawApi.detail(src, article, runId).catch(() => {
        lawCache.delete(key);
        return null;
      });
      // 带上限淘汰最旧（Map 插入序首键），与 LAW_CACHE_MAX 约束常驻
      if (lawCache.size >= LAW_CACHE_MAX) {
        const oldest = lawCache.keys().next().value;
        if (oldest !== undefined) lawCache.delete(oldest);
      }
      lawCache.set(key, p);
    }
    return p;
  }

  async function toggleInlineLaw(ref: Element, msgIndex: number, runId?: string) {
    // 未收录的条文（如司法解释）也弹卡提示，而不是点了没反应
    const src = ref.getAttribute("data-source") || "";
    const m = (ref.textContent || "").match(
      /第\s*([零〇○一二三四五六七八九十百千万0-9０-９]+)\s*条(之[一二三四五六七八九十百千万0-9０-９]+)?/
    );
    const article = m ? `第${m[1]}条${m[2] || ""}` : "";

    // 计算被点击法条在「同书名+条号」集合中的序号（文档顺序），
    // 使卡片精确落到点击的那一条，而非第一条（多次出现时）。
    let occurrence = 0;
    const msgEl = ref.closest("[data-msg-index]");
    if (msgEl) {
      const refs = msgEl.querySelectorAll(".law-ref");
      for (const r of Array.from(refs)) {
        if (r === ref) break;
        const rSrc = r.getAttribute("data-source") || "";
        const rm = (r.textContent || "").match(
          /第\s*([零〇○一二三四五六七八九十百千万0-9０-９]+)\s*条(之[一二三四五六七八九十百千万0-9０-９]+)?/
        );
        const rArt = rm ? `第${rm[1]}条${rm[2] || ""}` : "";
        if (rSrc === src && rArt === article) occurrence++;
      }
    }

    const targetKey = JSON.stringify([runId || null, msgIndex, src, article, occurrence]);
    let version = requestVersion.current;
    if (pendingTarget.current !== targetKey) {
      version = ++requestVersion.current;
      pendingTarget.current = targetKey;
    }
    const law = await fetchLawRefCached(ref, runId);
    if (version !== requestVersion.current) return;
    setExpandedLaw((prev) =>
      prev &&
      prev.msgIndex === msgIndex &&
      prev.source === src &&
      prev.article === article &&
      prev.occurrence === occurrence
        ? null // 再点同一条 → 收起
        : {
            msgIndex,
            source: src,
            article,
            content: law ? law.content : "",
            status: law?.status,
            isSnapshot: Boolean(runId),
            lawAsOf: law?.law_as_of,
            found: !!law,
            occurrence,
          }
    );
    if (pendingTarget.current === targetKey) pendingTarget.current = null;
  }

  return {
    expandedLaw,
    toggleInlineLaw,
    clearExpandedLaw: () => {
      requestVersion.current++;
      pendingTarget.current = null;
      lawCache.clear();
      setExpandedLaw(null);
    },
  };
}
