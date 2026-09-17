import { describe, expect, it } from "vitest";
import {
  coverageFromFinalEvent,
  coverageFromMessage,
  partialBanner,
  type CoverageInfo,
  type HistoryCoverageFields,
} from "@/lib/coverage";

describe("partialBanner（T1 部分交付提示，实时/历史共用）", () => {
  it("partial + 非空列表 → 返回提示数据（条数 = 未覆盖争点数）", () => {
    const coverage: CoverageInfo = {
      status: "partial",
      uncovered: [
        { issue_id: "i1", reason_code: "UNKNOWN_EVIDENCE_ID" },
        { issue_id: "i2", reason_code: "ISSUE_CLAIMS_MISSING" },
      ],
    };
    expect(partialBanner(coverage)).toEqual({ uncoveredCount: 2 });
  });

  it("full → null（不显示提示）", () => {
    expect(partialBanner({ status: "full", uncovered: [] })).toBeNull();
  });

  it("undefined（用户消息/无覆盖信息）→ null", () => {
    expect(partialBanner(undefined)).toBeNull();
  });

  it("partial 但列表为空（异常形态，契约禁止）→ null 防御", () => {
    expect(partialBanner({ status: "partial", uncovered: [] })).toBeNull();
  });
});

describe("coverageFromMessage（历史消息投影映射，unknown 不得变 full）", () => {
  it("full + 空列表 → full", () => {
    const m: HistoryCoverageFields = { coverage_status: "full", uncovered_issues: [] };
    expect(coverageFromMessage(m)).toEqual({ status: "full", uncovered: [] });
  });

  it("partial + 非空列表 → partial + 条目透传", () => {
    const m: HistoryCoverageFields = {
      coverage_status: "partial",
      uncovered_issues: [{ issue_id: "i1", reason_code: "UNKNOWN_EVIDENCE_ID" }],
    };
    expect(coverageFromMessage(m)).toEqual({
      status: "partial",
      uncovered: [{ issue_id: "i1", reason_code: "UNKNOWN_EVIDENCE_ID" }],
    });
  });

  it("unknown → null（旧消息不显示提示，也绝不显示为 full）", () => {
    expect(coverageFromMessage({ coverage_status: "unknown", uncovered_issues: [] })).toBeNull();
  });

  it("缺字段（用户消息/旧后端）→ null", () => {
    expect(coverageFromMessage({})).toBeNull();
  });
});

describe("coverageFromFinalEvent（final SSE 载荷解析，api.ts 判定收口）", () => {
  it("full → coverage_status=full + 空列表透传", () => {
    expect(coverageFromFinalEvent({ coverage_status: "full", uncovered_issues: [] })).toEqual({
      coverage_status: "full",
      uncovered_issues: [],
    });
  });

  it("partial + 非空列表 → 原样透传", () => {
    const list = [{ issue_id: "i1", reason_code: "ISSUE_CLAIMS_MISSING" }];
    expect(coverageFromFinalEvent({ coverage_status: "partial", uncovered_issues: list })).toEqual({
      coverage_status: "partial",
      uncovered_issues: list,
    });
  });

  it("未知状态值（契约外字符串）→ undefined（不猜测）", () => {
    expect(coverageFromFinalEvent({ coverage_status: "unknown", uncovered_issues: [] })).toEqual({
      coverage_status: undefined,
      uncovered_issues: [],
    });
  });

  it("字段缺失 / 列表非数组 → undefined（不猜测）", () => {
    expect(coverageFromFinalEvent({})).toEqual({
      coverage_status: undefined,
      uncovered_issues: undefined,
    });
    expect(coverageFromFinalEvent({ coverage_status: "partial", uncovered_issues: "bad" })).toEqual({
      coverage_status: "partial",
      uncovered_issues: undefined,
    });
  });
});
