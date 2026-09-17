"use client";
// T2.2 自 chat/page.tsx 原样搬移，零行为变更。
import { memo } from "react";
import { renderAnswer } from "@/lib/annotate";
import type { ExpandedLaw } from "@/lib/types";
import { injectLawCardHtml } from "./lawCardHtml";

/** 消息 HTML 渲染（React.memo）：流式时只有 content 变化的最后一条会重排 renderAnswer，
 * 已完成消息不重复跑语义标注正则（F1 性能优化，2026-08-07）。
 * 自定义比较（对抗审计 v2 #10）：expanded 是对象，浅比较会被引用击穿（点法条卡→全量重标注）。
 * 改为按内容字段比较：仅当 content 变、或卡片注入状态变、或卡片内容字段（source/article/occurrence）
 * 变时才重渲染；点任意法条卡不再触发全部历史消息重跑 renderAnswer。 */
export const MessageHtml = memo(
  function MessageHtml({
    content,
    expanded,
    i,
  }: {
    content: string;
    expanded: ExpandedLaw | null;
    i: number;
  }) {
    let html = renderAnswer(content);
    if (expanded && expanded.msgIndex === i) {
      html = injectLawCardHtml(html, expanded, expanded.occurrence);
    }
    return <div className="whitespace-normal" dangerouslySetInnerHTML={{ __html: html }} />;
  },
  (prev, next) => {
    const prevHit = prev.expanded?.msgIndex === prev.i;
    const nextHit = next.expanded?.msgIndex === next.i;
    if (prevHit !== nextHit) return false; // 卡片注入状态变化（注入/收起）→ 重渲染
    if (prevHit && nextHit) {
      const pe = prev.expanded!;
      const ne = next.expanded!;
      return (
        prev.content === next.content &&
        prev.i === next.i &&
        pe.source === ne.source &&
        pe.article === ne.article &&
        pe.occurrence === ne.occurrence &&
        pe.found === ne.found
      );
    }
    return prev.content === next.content && prev.i === next.i;
  }
);
