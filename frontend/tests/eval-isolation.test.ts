import { describe, expect, it } from "vitest";

import { evalNoCurateHeader } from "@/lib/evalIsolation";

const storage = (value: string | null) => ({ getItem: () => value });

describe("evalNoCurateHeader", () => {
  it("标记为 1 时带评测隔离头", () => {
    expect(evalNoCurateHeader(storage("1"))).toEqual({ "X-Eval-No-Curate": "1" });
  });

  it("标记为 0 / 空时不应带头", () => {
    expect(evalNoCurateHeader(storage("0"))).toEqual({});
    expect(evalNoCurateHeader(storage(null))).toEqual({});
  });

  it("存储抛错时静默降级", () => {
    const bad = {
      getItem() {
        throw new Error("denied");
      },
    };
    expect(evalNoCurateHeader(bad)).toEqual({});
  });

  it("无存储时返回空（node/SSR）", () => {
    expect(evalNoCurateHeader(null)).toEqual({});
  });
});
