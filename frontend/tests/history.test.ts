import { describe, expect, it } from "vitest";

import { conversationToMarkdown, filterHistory } from "@/lib/history";
import type { ConversationItem, Msg } from "@/lib/types";

const item = (id: number, title: string, preview = ""): ConversationItem => ({
  id,
  title,
  preview,
  message_count: 2,
  has_image: false,
  created_at: "2026-10-27 00:00:00",
});

describe("filterHistory", () => {
  const rows = [item(1, "拖欠工资", "公司不发工资"), item(2, "离婚冷静期", "协议离婚")];

  it("空查询返回全部", () => {
    expect(filterHistory(rows, "  ")).toHaveLength(2);
  });

  it("按标题/预览过滤且忽略大小写", () => {
    expect(filterHistory(rows, "工资").map((x) => x.id)).toEqual([1]);
    expect(filterHistory(rows, "离婚").map((x) => x.id)).toEqual([2]);
  });

  it("无命中返回空数组", () => {
    expect(filterHistory(rows, "专利")).toEqual([]);
  });
});

describe("conversationToMarkdown", () => {
  it("输出标题与双方内容", () => {
    const messages: Msg[] = [
      { role: "user", content: "公司拖欠工资怎么维权？" },
      { role: "assistant", content: "可以申请劳动仲裁。" },
    ];
    const md = conversationToMarkdown(messages, "拖欠工资");
    expect(md).toContain("# 拖欠工资");
    expect(md).toContain("## 我");
    expect(md).toContain("公司拖欠工资怎么维权？");
    expect(md).toContain("## 法智");
    expect(md).toContain("可以申请劳动仲裁。");
  });

  it("无标题用默认标题", () => {
    expect(conversationToMarkdown([], "")).toContain("# 法智对话");
  });
});
