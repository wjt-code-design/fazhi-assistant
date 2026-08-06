// 语义标注 A 路径（法智前端美化批3 + B1/B2）：
// 对回答文本渲染——法条引用 / 期限时效 / 关键金额 / 倍数高亮。
// 每次渲染都重跑（含流式期，由调用方 memo 保证只在消息变化时重算）；先 escape 防 XSS；
// 引号内「原文摘录」（合同报告 R_n 里的引号）也做金额/时限/倍数高亮，统一格式。

// 引号模式：双引号 / 中文引号「」“” / 单引号
const QUOTE_RE = /"[^"]*"|「[^」]*」|“[^”]*”|'[^']*'/g;

// 引号占位符：NUL 字符（正常回答文本中不会出现），引号内内容标注阶段一律不碰
const PH = "\u0000";

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// B1/B2（2026-08-07）："未检索到/建议核对"矛盾句删除与币种 $/¥→元 归一已上移到后端生成层
// （output_normalize.money_normalize / strip_unprovided_notes，带库证据、确定性），
// 前端不再做正则兜底——原 fixCurrencyTypos/stripUnprovidedHint 猜形状、变体一变就失效。

/** 对引号内部文本做语义高亮（金额/时限/倍数/百分比），还原占位符时调用 */
function highlightInsideQuote(q: string): string {
  const open = q[0];
  const close = q[q.length - 1];
  const inner = q.slice(1, -1);
  const h = inner
    .replace(
      /(\d+(?:\.\d+)?)\s*[-~～至到]\s*(\d+(?:\.\d+)?)\s*(年|日)/g,
      '<span class="hl-time">$1</span>-<span class="hl-time">$2</span>$3'
    )
    .replace(/(\d+(?:\.\d+)?)\s*[-~～至到]\s*(\d+(?:\.\d+)?)(个月)/g, '<span class="hl-time">$1</span>-<span class="hl-time">$2</span>$3')
    .replace(/(\d+(?:\.\d+)?|[一二三四五六七八九十百千万零]+)\s*(年|日)/g, '<span class="hl-time">$1</span>$2')
    .replace(/(\d+(?:\.\d+)?|[一二三四五六七八九十百千万零]+)(个月)/g, '<span class="hl-time">$1</span>$2')
    .replace(
      /(\d+(?:\.\d+)?)\s*[-~～至到]\s*(\d+(?:\.\d+)?)\s*(?:万元|万|元)/g,
      '<span class="hl-money">$1</span>-<span class="hl-money">$2$3</span>'
    )
    .replace(
      /(¥\s*[\d,]+(?:\.\d+)?|\d+(?:\.\d+)?\s*(?:万元|万|元)|[一二三四五六七八九十百千万零]+元)/g,
      '<span class="hl-money">$1</span>'
    )
    .replace(/([二三四五六七八九]|\d+(?:\.\d+)?)\s*倍/g, '<span class="hl-num">$1倍</span>')
    .replace(/\d+(?:\.\d+)?\s*%/g, '<span class="hl-num">$&</span>');
  return open + h + close;
}

export function annotate(raw: string): string {
  const text = escapeHtml(raw);
  const quotes: string[] = [];

  // 1) 引号内先暂存为占位符——引号内永不标注（保持现有行为）
  const tmp = text.replace(QUOTE_RE, (m) => {
    quotes.push(m);
    return `${PH}${quotes.length - 1}${PH}`;
  });

  // 2) 法条匹配最先执行：单个带 alternation 的全局正则，一次从左到右处理，保证顺序正确。
  //    - 完整《书名》第X条 必然标注。
  //    - 独立「第X条」仅当紧跟上一处法条引用、且中间只隔连续符号（、，,）时才视为
  //      「省略书名的连续条号」，如《民法典》第四百九十七条、第五百六十三条。
  //    - 跨句 / 跨表格单元的独立「第X条」（如合同条款「第九条 争议解决」）一律不标注，
  //      并断开书名延续，避免误亮成法条。
  // 字符集对齐后端 _ART_FULL_RE（retrieval.py）：补 万/〇/○/全角０-９；支持"之条"（第X条之三）。
  const LAW =
    /《([^》]+)》\s*第\s*([零〇○一二三四五六七八九十百千万0-9０-９]+)\s*条(之[一二三四五六七八九十百千万0-9０-９]+)?|第\s*([零〇○一二三四五六七八九十百千万0-9０-９]+)\s*条(之[一二三四五六七八九十百千万0-9０-９]+)?/g;
  let lastBook = "";
  let lastLawEnd = -1; // 上一处法条引用在原文中的结束偏移
  const lawMarked = tmp.replace(
    LAW,
    (full, book, clause, zhi, standalone, szhi, offset) => {
      if (book) {
        // 组1（书名）存在 → 完整匹配，记录书名与结束位置；之条拼回
        lastBook = book;
        lastLawEnd = offset + full.length;
        return `<span class="law-ref" data-source="${book}">《${book}》第${clause}条${zhi || ""}</span>`;
      }
      if (standalone && lastBook && lastLawEnd >= 0) {
        // 组4（独立条号）存在：与上一处法条引用之间只允许连续符号/空白 → 归属上一个书名
        const gap = tmp.slice(lastLawEnd, offset);
        if (/^[、，,、\s]*$/.test(gap)) {
          lastLawEnd = offset + full.length;
          return `<span class="law-ref" data-source="${lastBook}">第${standalone}条${szhi || ""}</span>`;
        }
        // 上下文已断开（跨句/跨单元）→ 不标注，并清掉书名延续
        lastBook = "";
        lastLawEnd = -1;
      }
      return full;
    }
  );

  // 3) 对引号外部分标注：期限时效（含范围 + 中文数字）→ 金额（含范围 + 中文数字）→ 倍数/百分比
  //    月份（个月）只高亮数字、单位不加填充色；年/日整体高亮。
  const marked = lawMarked
    .replace(
      /(\d+(?:\.\d+)?)\s*[-~～至到]\s*(\d+(?:\.\d+)?)\s*(年|日)/g,
      '<span class="hl-time">$1</span>-<span class="hl-time">$2</span>$3'
    )
    .replace(/(\d+(?:\.\d+)?)\s*[-~～至到]\s*(\d+(?:\.\d+)?)(个月)/g, '<span class="hl-time">$1</span>-<span class="hl-time">$2</span>$3')
    .replace(/(\d+(?:\.\d+)?|[一二三四五六七八九十百千万零]+)\s*(年|日)/g, '<span class="hl-time">$1</span>$2')
    .replace(/(\d+(?:\.\d+)?|[一二三四五六七八九十百千万零]+)(个月)/g, '<span class="hl-time">$1</span>$2')
    .replace(
      /(\d+(?:\.\d+)?)\s*[-~～至到]\s*(\d+(?:\.\d+)?)\s*(?:万元|万|元)/g,
      '<span class="hl-money">$1</span>-<span class="hl-money">$2$3</span>'
    )
    .replace(
      /(¥\s*[\d,]+(?:\.\d+)?|\d+(?:\.\d+)?\s*(?:万元|万|元)|[一二三四五六七八九十百千万零]+元)/g,
      '<span class="hl-money">$1</span>'
    )
    .replace(/([二三四五六七八九]|\d+(?:\.\d+)?)\s*倍/g, '<span class="hl-num">$1倍</span>')
    .replace(/\d+(?:\.\d+)?\s*%/g, '<span class="hl-num">$&</span>');

  // 4) 引号内容还原，并对引号内原文摘录做同样的语义高亮，保证格式统一
  return marked.replace(new RegExp(`${PH}(\\d+)${PH}`, "g"), (_, i) => highlightInsideQuote(quotes[Number(i)]));
}

// ==================== 回答排版器 ====================
// 把模型输出的 Markdown 排版成整齐的 HTML（标题 / 表格 / 列表 / 加粗），
// 使 `#`、`*`、`-`、`|` 等符号不再原样出现在回答里，只保留文字、数字与序号。
// 输入为 annotate() 的输出（已转义 + 语义高亮 span），行级结构在行间处理，安全。

/** 行内格式化：**加粗** / *斜体* / `代码` */
function inlineMarkdown(s: string): string {
  return s
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*\n]+)\*/g, "<em>$1</em>")
    .replace(/`([^`\n]+)`/g, "<code>$1</code>");
}

/** 取表格一行去掉首尾 `|` 后的单元格 */
function tableCells(row: string): string[] {
  return row
    .split("|")
    .slice(1, -1)
    .map((c) => c.trim());
}

function buildTable(rows: string[]): string {
  const head = tableCells(rows[0]).map((c) => `<th>${inlineMarkdown(c)}</th>`).join("");
  // 跳过 | :--- | 分隔行
  let bodyStart = 1;
  if (rows[1] && /^[\s:|-]+$/.test(rows[1].replace(/\|/g, ""))) bodyStart = 2;
  const body = rows
    .slice(bodyStart)
    .map((r) => `<tr>${tableCells(r).map((c) => `<td>${inlineMarkdown(c)}</td>`).join("")}</tr>`)
    .join("");
  return `<div class="answer-table-wrap"><table class="answer-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

function formatMarkdown(html: string): string {
  const lines = html.split("\n");
  const out: string[] = [];
  let para: string[] = [];
  const flushPara = () => {
    if (para.length) {
      out.push(`<p class="answer-p">${para.join("<br/>")}</p>`);
      para = [];
    }
  };
  const isTableRow = (l: string) => {
    const t = l.trim();
    return t.startsWith("|") && t.endsWith("|") && t.length > 2;
  };

  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const t = line.trim();

    if (!t) {
      flushPara();
      i++;
      continue;
    }
    // 水平分隔线 --- / *** / ___
    if (/^([-*_])\1{2,}$/.test(t)) {
      flushPara();
      out.push('<hr class="answer-hr"/>');
      i++;
      continue;
    }
    // 标题 # ## ###
    const h = t.match(/^(#{1,4})\s+(.*)$/);
    if (h) {
      flushPara();
      const level = h[1].length;
      out.push(`<h${level} class="answer-h${level}">${inlineMarkdown(h[2])}</h${level}>`);
      i++;
      continue;
    }
    // 表格
    if (isTableRow(line)) {
      flushPara();
      const rows: string[] = [];
      while (i < lines.length && isTableRow(lines[i])) {
        rows.push(lines[i]);
        i++;
      }
      out.push(buildTable(rows));
      continue;
    }
    // 无序列表
    const ul = t.match(/^[-*•·]\s+(.*)$/);
    if (ul) {
      flushPara();
      const items: string[] = [];
      while (i < lines.length) {
        const it = lines[i].trim().match(/^[-*•·]\s+(.*)$/);
        if (it) {
          items.push(`<li>${inlineMarkdown(it[1])}</li>`);
          i++;
        } else break;
      }
      out.push(`<ul class="answer-ul">${items.join("")}</ul>`);
      continue;
    }
    // 有序列表
    const ol = t.match(/^\d+[.、]\s+(.*)$/);
    if (ol) {
      flushPara();
      const items: string[] = [];
      while (i < lines.length) {
        const it = lines[i].trim().match(/^\d+[.、]\s+(.*)$/);
        if (it) {
          items.push(`<li>${inlineMarkdown(it[1])}</li>`);
          i++;
        } else break;
      }
      out.push(`<ol class="answer-ol">${items.join("")}</ol>`);
      continue;
    }
    // 普通段落行（连续行合并为一段，行间 <br/>）
    para.push(inlineMarkdown(t));
    i++;
  }
  flushPara();

  // 清残留 markdown 符号：* 已全部转换/移除；行首 # 已在标题处理；--- 已转分隔线
  return out.join("\n").replace(/\*/g, "");
}

/** 完整回答渲染：语义标注（法条/时效/金额）+ Markdown 排版，输出可直接插入的 HTML */
export function renderAnswer(raw: string): string {
  // B1/B2（2026-08-07）：币种 $/¥→元 与"未检索到/建议核对"矛盾句已由后端生成层归一，
  // 前端只做展示排版，不再猜形状正则兜底。
  return formatMarkdown(annotate(raw));
}
