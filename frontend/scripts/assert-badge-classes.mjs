// 断言生产构建的 CSS 产物里四个徽章类名在册（缺陷 J3 的回归腿）。
// 用法：node scripts/assert-badge-classes.mjs [.next 目录]
// 判据设计：四个 badge-* 各 ≥1 才算绿；同时必须存在阳性对照 .badge{ 与 .upload-zone，
// 否则"全 0"可能只是因为 glob 没找到 CSS 文件（那会把这条腿变成恒真）。
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

const root = process.argv[2] || ".next";
const cssDir = join(root, "static", "css");

let files = [];
try {
  files = readdirSync(cssDir).filter((f) => f.endsWith(".css"));
} catch (e) {
  console.log(`FAIL: 读不到 ${cssDir} —— ${e.code || e.message}`);
  process.exit(2);
}
if (files.length === 0) {
  console.log("FAIL: css 目录为空（构建未产出样式表？）");
  process.exit(2);
}

const all = files
  .map((f) => readFileSync(join(cssDir, f), "utf8"))
  .join("\n");

const count = (needle) => all.split(needle).length - 1;

const TARGETS = [".badge-success", ".badge-error", ".badge-neutral", ".badge-accent"];
const CONTROLS = [".badge{", ".upload-zone"];

const got = {};
for (const t of TARGETS) got[t] = count(t);
const ctl = {};
for (const c of CONTROLS) ctl[c] = count(c);

console.log("css_files=" + files.length, "bytes=" + all.length);
console.log("controls:", JSON.stringify(ctl));
console.log("targets:", JSON.stringify(got));

// 对照必须为正：否则本条断言恒真，没有价值
const ctlBad = Object.entries(ctl).filter(([, v]) => v < 1).map(([k]) => k);
if (ctlBad.length) {
  console.log("VERDICT=INERT missing_controls=" + ctlBad.join(","));
  process.exit(2);
}

const missing = TARGETS.filter((t) => got[t] < 1);
if (missing.length) {
  console.log("VERDICT=DEFECT_PRESENT missing=" + missing.join(","));
  process.exit(1);
}
console.log("VERDICT=OK");
