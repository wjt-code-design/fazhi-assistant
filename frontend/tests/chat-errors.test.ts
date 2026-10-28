import { describe, expect, it } from "vitest";

import { chatFailureKind } from "@/lib/chatErrors";

describe("chatFailureKind", () => {
  it("识别历史占位消息（服务无响应）", () => {
    expect(chatFailureKind("服务暂时无响应，请稍后重试。")).toBe("service");
  });

  it("识别客户端空答兜底（服务不可用）", () => {
    expect(chatFailureKind("服务暂时不可用，请稍后重试；紧急法律问题请咨询律师。")).toBe("service");
  });

  it("识别普通 RAG/网络错误", () => {
    expect(chatFailureKind("出错了：Failed to fetch")).toBe("generic");
  });

  it("正常回答不误判", () => {
    expect(chatFailureKind("根据《劳动合同法》第十九条，试用期最长六个月。")).toBe(null);
  });

  it("空内容不误判", () => {
    expect(chatFailureKind("")).toBe(null);
    expect(chatFailureKind("   ")).toBe(null);
  });

  it("已停止生成的半截回答不误判为失败", () => {
    expect(
      chatFailureKind("根据《民法典》第六百五十八条…\n\n（已停止生成，以上为未完成回答。）")
    ).toBe(null);
  });
});
