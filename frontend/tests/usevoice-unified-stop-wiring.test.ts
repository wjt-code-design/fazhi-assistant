import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

// R14（改前失败）：Web Speech 兜底识别的停止路径必须可达。
// 病根：`useVoice.toggleVoice` 的 `if (listening)` 分支只停 `wavRecRef` 就 return；
// 走浏览器兜底识别时 `wavRecRef` 是 null、`recRef` 有值，于是识别根本没停，
// 且 `legacyWebSpeech()` 里那个"停止"分支永远到不了。卸载清理也只处理 WAV。
//
// 诚实边界：同 R13——本仓前端测试无 jsdom / @testing-library，这里钉的是**接线**
// （"两处都停 recRef"），不是原生 API 的真实行为；真机行为需人工验收一次。
const HOOK = fileURLToPath(new URL("../lib/hooks/useVoice.ts", import.meta.url));

function slice(src: string, startMarker: string, endMarker: string): string {
  const start = src.indexOf(startMarker);
  const end = src.indexOf(endMarker, start + 1);
  expect(start).toBeGreaterThan(-1);
  expect(end).toBeGreaterThan(start);
  return src.slice(start, end);
}

describe("useVoice：Web Speech 停止路径统一", () => {
  it("卸载清理里也停 recRef（Web Speech）", () => {
    const src = readFileSync(HOOK, "utf8");
    const cleanup = slice(src, "useEffect(() => {", "}, []);");
    expect(cleanup).toContain("recRef.current");
    expect(cleanup).toContain("rec.stop()");
  });

  it("toggleVoice 的 listening 分支里停 recRef，而不是只停 wavRecRef", () => {
    const src = readFileSync(HOOK, "utf8");
    const toggle = slice(src, "async function toggleVoice", "async function transcribeAndFill");
    const listeningBlock = toggle.slice(toggle.indexOf("if (listening) {"));
    expect(listeningBlock).toContain("recRef.current = null");
    expect(listeningBlock).toContain("rec.stop()");
  });
});
