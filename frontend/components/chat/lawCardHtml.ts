// 法条内联卡（T2.2 自 chat/page.tsx 原样搬移，纯函数，零行为变更）：
// escapeHtmlText/buildLawCardHtml/injectLawCardHtml 模块级——供 MessageHtml memo 使用，避免组件内重建失效。

/** HTML 文本转义（卡片内容用） */
export function escapeHtmlText(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

export function buildLawCardHtml(exp: {
  source: string;
  article: string;
  content: string;
  status?: string;
  found: boolean;
}): string {
  const title = `<p class="law-title font-serif text-sm">《${escapeHtmlText(exp.source)}》${escapeHtmlText(exp.article)}</p>`;
  if (!exp.found) {
    // 知识库未收录（如司法解释）：仍弹卡，给出可操作提示
    return (
      `<div class="law-glass law-inline-card rounded-xl px-4 py-4">` +
      title +
      `<p class="mt-2 text-[0.85rem] leading-relaxed text-slate/85">知识库暂未收录该条文原文。</p>` +
      `</div>`
    );
  }
  const content = escapeHtmlText(exp.content).replace(/\n/g, "<br/>");
  const status = exp.status
    ? `<p class="mt-2 text-xs text-slate">状态：${escapeHtmlText(exp.status)}</p>`
    : "";
  return (
    `<div class="law-glass law-inline-card rounded-xl px-4 py-4">` +
    title +
    `<p class="mt-2 whitespace-pre-wrap text-[0.85rem] leading-relaxed text-ink/90 font-normal">${content}</p>` +
    `${status}</div>`
  );
}

/** 在回答 HTML 中定位「对应 data-source + 条号」的法条引用，在其第 occurrence 次出现后追加卡片 */
export function injectLawCardHtml(
  html: string,
  exp: {
    source: string;
    article: string;
    content: string;
    status?: string;
    found: boolean;
  },
  occurrence = 0
): string {
  const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const src = esc(exp.source);
  const art = esc(exp.article.replace(/^第|条$/g, ""));
  const re = new RegExp(
    `(<span class="law-ref" data-source="${src}"[^>]*>[^<]*${art}[^<]*<\\/span>)`,
    "g"
  );
  const card = buildLawCardHtml(exp);
  let count = 0;
  let injected = false;
  const out = html.replace(re, (full) => {
    const isTarget = count === occurrence;
    count++;
    if (isTarget) {
      injected = true;
      return full + card;
    }
    return full;
  });
  return injected ? out : out + card; // 兜底：计数越界则追加到末尾
}
