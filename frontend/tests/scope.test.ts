import { describe, expect, it } from "vitest";
import { SCOPE_MAX_SELECTION, buildScopeAnswer, parseScopeCandidates } from "@/lib/scope";

describe("parseScopeCandidates", () => {
  const PROMPT =
    "本次请求分解出 6 个法律争点，超过单次可处理上限 5 个。请从中选择最多 5 个争点（输入编号，用逗号分隔，例如：1,3,5）：\n1. 争点甲\n2. 争点乙\n3. 争点丙";

  it("正常解析编号与文本", () => {
    expect(parseScopeCandidates(PROMPT)).toEqual([
      { number: 1, text: "争点甲" },
      { number: 2, text: "争点乙" },
      { number: 3, text: "争点丙" },
    ]);
  });

  it("无范围选择特征 → null", () => {
    expect(parseScopeCandidates("普通追问，不涉及分解")).toBeNull();
  });

  it("空输入 → null", () => {
    expect(parseScopeCandidates("")).toBeNull();
  });

  it("有前缀但无任何编号行 → null", () => {
    expect(parseScopeCandidates("本次请求分解出 2 个争点但没有列表")).toBeNull();
  });

  it("编号不从 1 开始 → null", () => {
    expect(parseScopeCandidates("本次请求分解出\n2. 乙\n3. 丙")).toBeNull();
  });

  it("编号不连续（乱序跳号）→ null", () => {
    expect(parseScopeCandidates("本次请求分解出\n1. 甲\n3. 丙")).toBeNull();
  });

  it("编号行容忍前导空白", () => {
    const r = parseScopeCandidates("本次请求分解出\n  1. 甲\n\t2. 乙");
    expect(r).toEqual([
      { number: 1, text: "甲" },
      { number: 2, text: "乙" },
    ]);
  });
});

describe("buildScopeAnswer", () => {
  it("升序 + 英文逗号分隔", () => {
    expect(buildScopeAnswer([3, 1, 2])).toBe("1,2,3");
  });

  it("去重", () => {
    expect(buildScopeAnswer([2, 2, 1])).toBe("1,2");
  });

  it("空数组 → 空串", () => {
    expect(buildScopeAnswer([])).toBe("");
  });

  it("上限常量与后端契约一致（5 选）", () => {
    expect(SCOPE_MAX_SELECTION).toBe(5);
  });
});
