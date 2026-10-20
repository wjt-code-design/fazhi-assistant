import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

// R13（改前失败）：Admin 上传失败后必须也能重选同一个文件。
// 病根：`UploadSection.onUpload` 只在**成功分支**清空 `fileRef.current.value`，
// 失败时保留原选择 ⇒ 用户再选同一文件时浏览器认为 value 未变、不触发 change，看起来"点了没反应"。
//
// 诚实边界：本仓前端测试环境是 node，没有 jsdom / @testing-library（未装、且本轮不新增依赖），
// 所以这里钉的是**接线**（"清空动作落在 finally 里"），不是 DOM 行为本身；
// 真正的浏览器行为需人工在 admin 页验收一次。
const COMPONENT = fileURLToPath(new URL("../app/admin/sections/UploadSection.tsx", import.meta.url));

function onUploadBody(): string {
  const src = readFileSync(COMPONENT, "utf8");
  const start = src.indexOf("async function onUpload");
  const end = src.indexOf("async function runPreview");
  expect(start).toBeGreaterThan(-1);
  expect(end).toBeGreaterThan(start);
  return src.slice(start, end);
}

describe("UploadSection.onUpload：失败后也要清空 file input", () => {
  it("清空动作落在 finally 里，而不是成功分支", () => {
    const body = onUploadBody();
    const resetMatches = body.match(/fileRef\.current\.value = ""/g) ?? [];
    expect(resetMatches.length).toBe(1);

    const finallyIdx = body.indexOf("} finally {");
    const resetIdx = body.indexOf('fileRef.current.value = ""');
    expect(finallyIdx).toBeGreaterThan(-1);
    expect(resetIdx).toBeGreaterThan(finallyIdx);
  });
});
