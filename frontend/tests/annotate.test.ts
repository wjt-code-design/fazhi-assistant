import { describe, expect, it } from "vitest";
import { annotate, renderAnswer } from "@/lib/annotate";

// 执行书 T0.3 用例方向逐条落地。annotate.ts 一行不改（V5 行为锁定），以下断言全部锁定现状行为。

describe("法条引用标注", () => {
  it("完整《书名》第X条 → law-ref，data-source 为书名", () => {
    const html = renderAnswer("《民法典》第五百七十七条");
    expect(html).toContain('class="law-ref"');
    expect(html).toContain('data-source="民法典"');
    expect(html).toContain("《民法典》第五百七十七条");
  });

  it("常见法律名省略书名号（刑法第23条）→ 补《》渲染", () => {
    const html = renderAnswer("刑法第23条");
    expect(html).toContain('data-source="刑法"');
    expect(html).toContain("《刑法》第23条");
  });

  it("跨句独立条号不标注（书名延续断开）", () => {
    const html = renderAnswer("本案依据《劳动法》。第九条为合同条款。");
    // 《劳动法》后无条号不构成 law-ref；句号后的独立"第九条"也不标注
    expect(html).not.toContain('class="law-ref"');
  });

  it("同句连续条号（顿号连接）归属上一书名", () => {
    const html = renderAnswer("《民法典》第715条、第716条");
    expect(html).toContain('data-source="民法典"');
    expect(html).toContain("第716条");
    // 两处都应是 law-ref
    const count = (html.match(/class="law-ref"/g) || []).length;
    expect(count).toBe(2);
  });

  it("支持之条与全角数字", () => {
    const html = renderAnswer("《刑法》第１７条之一");
    expect(html).toContain('class="law-ref"');
    expect(html).toContain("之一");
  });
});

describe("语义高亮", () => {
  it("时限（中文数字/阿拉伯数字）→ hl-time", () => {
    expect(renderAnswer("诉讼时效三年")).toContain('class="hl-time"');
    expect(renderAnswer("期限3年")).toContain('class="hl-time"');
  });

  it("金额 → hl-money", () => {
    expect(renderAnswer("补偿2万元")).toContain('class="hl-money"');
    expect(renderAnswer("定金500元")).toContain('class="hl-money"');
  });

  it("倍数/百分比 → hl-num", () => {
    expect(renderAnswer("赔偿三倍")).toContain('class="hl-num"');
    expect(renderAnswer("按日0.05%")).toContain('class="hl-num"');
  });
});

describe("Markdown 排版", () => {
  it("标题 # → answer-h1", () => {
    const html = renderAnswer("# 标题");
    expect(html).toContain('class="answer-h1"');
    expect(html).toContain("<h1");
  });

  it("表格 | a | b | → answer-table", () => {
    const html = renderAnswer("| 甲 | 乙 |\n| --- | --- |\n| 1 | 2 |");
    expect(html).toContain('class="answer-table"');
    expect(html).toContain("<th>甲</th>");
    expect(html).toContain("<td>1</td>");
  });

  it("无序列表 - 项 → answer-ul；有序列表 1. 项 → answer-ol", () => {
    expect(renderAnswer("- 甲\n- 乙")).toContain('class="answer-ul"');
    expect(renderAnswer("1. 甲\n2. 乙")).toContain('class="answer-ol"');
  });

  it("水平线 --- → answer-hr；加粗/斜体/行内代码", () => {
    expect(renderAnswer("甲\n\n---\n\n乙")).toContain('class="answer-hr"');
    expect(renderAnswer("**重点**")).toContain("<strong>重点</strong>");
    expect(renderAnswer("*斜体*")).toContain("<em>斜体</em>");
    expect(renderAnswer("`code`")).toContain("<code>code</code>");
  });
});

describe("安全与已知缺陷", () => {
  it("XSS：script 标签被转义，不原样输出", () => {
    const html = renderAnswer("<script>alert(1)</script>");
    expect(html).not.toContain("<script>");
    expect(html).toContain("&lt;script&gt;");
  });

  it("中文引号「」内的时间/金额同样高亮（highlightInsideQuote 路径）", () => {
    const html = renderAnswer("合同写明「三年」内交付");
    expect(html).toContain('class="hl-time"');
    // 引号本身保留
    expect(html).toContain("「");
  });

  // KNOWN-DEFECT 批次2后修复：全局删星号（annotate.ts:278）
  // 现状：正文中未被 Markdown 消费的 * 被无差别删除。此处锁定现状，勿"顺手修"。
  it("锁定现状：正文星号被全局删除", () => {
    const html = renderAnswer("0.05%*本金");
    expect(html).not.toContain("*");
    // 乘号消失属已知缺陷，修复前该断言即回归信号
  });
});

describe("annotate 与 renderAnswer 分层", () => {
  it("annotate 只做行内标注，不产生块级结构", () => {
    const html = annotate("# 标题\n正文");
    expect(html).not.toContain("answer-h1"); // 块级结构由 formatMarkdown 负责
    expect(html).toContain("# 标题");
  });
});
