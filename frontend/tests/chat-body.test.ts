import { describe, expect, it } from "vitest";

import { buildChatBody } from "@/lib/api";

describe("buildChatBody", () => {
  it("携带法律基准日时写 law_as_of", () => {
    const body = buildChatBody({ content: "诉讼时效几年？", lawAsOf: "2020-01-01" });
    expect(body.law_as_of).toBe("2020-01-01");
    expect(body.content).toBe("诉讼时效几年？");
  });

  it("未选基准日时不写该键（现行）", () => {
    const body = buildChatBody({ content: "诉讼时效几年？" });
    expect("law_as_of" in body).toBe(false);
  });

  it("映射会话/图片/截断/Agent 字段", () => {
    const body = buildChatBody({
      conversationId: 7,
      content: "q",
      image: "data:image/png;base64,xx",
      truncated: true,
      agentRunId: "run-1",
      agentStateVersion: 2,
    });
    expect(body).toMatchObject({
      conversation_id: 7,
      image: "data:image/png;base64,xx",
      truncated: true,
      agent_run_id: "run-1",
      agent_state_version: 2,
    });
  });
});
