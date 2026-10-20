import { execFileSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

// R10（改前失败）：service worker 的缓存名必须**构建期嵌入**稳定构建号。
// 改前 public/sw.js 只把 CACHE 顶层默认成 dev，靠 install 事件 fetch build-id.txt 去改；
// Worker 被回收重启不会重跑 install ⇒ CACHE 退回 dev 名，版本化失效。
// 现在构建脚本必须由 sw.template.js 生成 public/sw.js 并把占位符替换成真实构建号。
const SCRIPT = fileURLToPath(new URL("../scripts/write-build-id.mjs", import.meta.url));

function runScript(buildId: string): { dir: string; sw: string; bridge: string } {
  const dir = mkdtempSync(join(tmpdir(), "fazhi-swbid-"));
  mkdirSync(join(dir, ".next"), { recursive: true });
  mkdirSync(join(dir, "public"), { recursive: true });
  writeFileSync(join(dir, ".next", "BUILD_ID"), `${buildId}\n`);
  execFileSync(process.execPath, [SCRIPT], { cwd: dir });
  return {
    dir,
    sw: readFileSync(join(dir, "public", "sw.js"), "utf8"),
    bridge: readFileSync(join(dir, "public", "build-id.txt"), "utf8"),
  };
}

describe("write-build-id：构建号构建期嵌入 sw.js", () => {
  it("把模板占位符替换成真实构建号，产物缓存名随构建号变化", () => {
    const { sw } = runScript("test-build-42");
    // 精确钉住 CACHE 那一行：产物里它就是版本化名字（不靠 install 事件或网络去改）
    expect(sw).toContain('const CACHE = "fazhi-shell-test-build-42";');
    expect(sw).not.toContain("__BUILD_ID__");
  });

  it("不同构建号 → 不同缓存名（activate 才能清旧壳）", () => {
    const a = runScript("bid-a").sw;
    const b = runScript("bid-b").sw;
    expect(a).toContain("fazhi-shell-bid-a");
    expect(b).toContain("fazhi-shell-bid-b");
    expect(a).not.toEqual(b);
  });

  it("桥接文件 build-id.txt 仍按历史约定写出", () => {
    const { bridge } = runScript("test-build-42");
    expect(bridge.trim()).toBe("test-build-42");
  });
});
