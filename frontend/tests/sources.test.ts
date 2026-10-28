import { describe, expect, it } from "vitest";

import { sourceTitle } from "@/lib/sources";

describe("sourceTitle", () => {
  it("拼出状态、施行日、失效日", () => {
    expect(
      sourceTitle({ status: "现行", effective_from: "2021-01-01", effective_to: "2099-12-31" })
    ).toBe("状态：现行；施行：2021-01-01；失效：2099-12-31");
  });

  it("只有施行日", () => {
    expect(sourceTitle({ effective_from: "2021-01-01" })).toBe("施行：2021-01-01");
  });

  it("没有版本字段时明确说未标注", () => {
    expect(sourceTitle({})).toBe("版本日期未标注");
  });
});
