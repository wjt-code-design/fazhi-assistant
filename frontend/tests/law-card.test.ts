import { describe, expect, it } from "vitest";
import { buildLawCardHtml } from "@/components/chat/lawCardHtml";

describe("law card version labeling", () => {
  const card = { source: "民法典", article: "第675条", content: "证据片段", found: true };
  it("labels snapshots, cutoff and escapes snapshot text", () => {
    const html = buildLawCardHtml({ ...card, isSnapshot: true, lawAsOf: "2020-01-01<script>" });
    expect(html).toContain("非完整条文");
    expect(html).toContain("2020-01-01&lt;script&gt;");
    expect(html).not.toContain("<script>");
  });
  it("does not pretend legacy cards are historical snapshots", () => {
    expect(buildLawCardHtml(card)).toContain("未关联该次答复的历史版本");
  });
  it("distinguishes missing snapshot from missing current statute", () => {
    expect(buildLawCardHtml({ ...card, found: false, isSnapshot: true })).toContain("未改用当前版本");
  });
});
