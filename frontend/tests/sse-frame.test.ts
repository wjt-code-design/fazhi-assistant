import { describe, expect, it } from "vitest";
import { parseSSEFrames } from "@/lib/sse";

describe("parseSSEFrames", () => {
  it("单完整帧：返回帧体、缓冲清空", () => {
    const { frames, rest } = parseSSEFrames('data: {"content":"你好"}\n\n');
    expect(frames).toEqual(['{"content":"你好"}']);
    expect(rest).toBe("");
  });

  it("跨 chunk 残帧留在缓冲区，不丢不重", () => {
    const a = parseSSEFrames('data: {"content":"你');
    expect(a.frames).toEqual([]);
    expect(a.rest).toBe('data: {"content":"你');
    const b = parseSSEFrames(a.rest + '好"}\n\ndata: {"a":1}\n\n');
    expect(b.frames).toEqual(['{"content":"你好"}', '{"a":1}']);
    expect(b.rest).toBe("");
  });

  it("末帧无换行 → 视为残帧（行为与现状一致：不解析）", () => {
    const { frames, rest } = parseSSEFrames('data: {"content":"半截');
    expect(frames).toEqual([]);
    expect(rest).toBe('data: {"content":"半截');
  });

  it("非 data 行忽略（event:/注释），[DONE] 哨兵忽略", () => {
    const { frames } = parseSSEFrames(
      'event: ping\n\ndata: [DONE]\n\ndata: {"x":1}\n\n: comment\n\n'
    );
    expect(frames).toEqual(['{"x":1}']);
  });

  it("多帧一次喂入按序返回", () => {
    const { frames } = parseSSEFrames('data: {"n":1}\n\ndata: {"n":2}\n\ndata: {"n":3}\n\n');
    expect(frames).toEqual(['{"n":1}', '{"n":2}', '{"n":3}']);
  });

  it("data 前缀不匹配（无空格）忽略", () => {
    const { frames } = parseSSEFrames('data:{"noSpace":true}\n\n');
    expect(frames).toEqual([]);
  });
});
