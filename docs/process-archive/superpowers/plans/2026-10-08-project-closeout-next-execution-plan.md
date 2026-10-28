# 项目收尾工作后续执行书（2026-10-08）

> **For agentic workers:** 使用 executing-plans 按 A→B→C→D→E 执行并逐项复核。默认单助手，不自行开并行写主仓任务。复选框是执行记录，不因文档生成就勾选。只收到本文件也能知道起点、任务、输出、禁止项和停点；链接用于读取证据，不是新的授权。

**Goal:** 补齐本地整合后的依赖路线、原有前端修改验证和真实模型实验准备，形成可核查的收尾候选与明确审批项；本书不默认发布。

**Architecture:** 保留既有应用和单 worker 边界。只读主仓/共享环境/封口记录，输出新独立目录；先证实约束和真实缺口，再请求必要修复，不造通用发布平台，不因 diff 小跳过安全或无障碍。

**Tech Stack:** Windows / PowerShell、Git、Python 3.11、FastAPI、SQLite/Chroma、Next.js 14.1.0、React 18.2.0、现有 Vitest；服务器尚未选定。

## Global Constraints

- 主仓 C:/Users/33393/Desktop/ai-legal-helper；GitHub 为 https://github.com/wjt-code-design/fazhi-assistant。主仓本地 HEAD 应为 0b543960c7172ce1ffea57616952e4d5525190c4，master，暂存区为空；不是旧起点 902e2d1。
- 上一阶段 C:/Users/33393/Desktop/fazhi-main-integration-20261007 及旧候选 C:/Users/33393/Desktop/fazhi-closeout-auditfix-20261007 全部只读。不得重跑旧 round-11、扫描器或 freeze，不复用/覆盖运行编号，不改旧失败来凑通过。
- 只读 Python：C:/Users/33393/Desktop/fazhi-next-local-20261004-356fb810b3144d158e5dd18b9e276499/joint/venv/Scripts/python.exe。读取分发元数据可；不 import 后端主入口/模型加载器，不升级或向该环境安装包。
- 本书默认 A–E：只读风险调查、在新私有前端副本内的离线 SSR/现有测试/类型检查、公开样本与审批材料编写、证据自审。不自动授权产品修改、浏览器服务、依赖安装、真实模型调用或发布。
- 不读真实 .env、密钥值/片段/长度/哈希、数据库、私有语料或模型权重，不拷贝它们到候选。没有凭据不是让用户发 key 到聊天的理由。
- 不 stage/commit/merge/fetch/push/PR，不触发 CI、不清理未跟踪文件。不改主仓原有六处修改。本执行书和前轮修订报告均未提交。
- 不启动/重启/停止既有服务或容器，不动 3021，也不占用其他会话端口。默认测试不启动服务；浏览器阶段必须另批独占地址和全假传输方案。
- 新网络行为仅限官方公开公告、版本/源码与小元数据；不下 wheel/权重。相同失败先分析，完全相同最多重试一次；重命令失败不自动循环。
- 结构性根因确认就重规划，不等三次失败；同一 bug 三次修复仍不过必须停止。正确性、安全、数据保护、无障碍、明确需求优先；必要重构可另提，不为未来假设提前搭架子。
- 不因升级复杂默认接受漏洞，不虚构精确安全版本、预算、gold 或平台。行为/接口/数据格式/外发/授权改变，使用中文纯文本 grilling；不弹选择卡片。
- 若有其他会话写主仓，先对齐所有权；输入漂移时暂停依赖该输入的裁定，不替他人还原文件。

## 0. 当前状态：先纠正这些旧说法

已完成的是受限本地整合与提交。旧门禁：后端 1852 通过/10 skip/18 slow 排除、86.11% 综合覆盖率；前端 83 项/类型/构建；round-11 取消/存储/摘要和 shutdown-control-13 收尾通过。这些是历史证据，执行本书必须另记新检查，不能贴数字称本轮全量通过。

原有六处未提交残余：

| 路径（相对于主仓） | 当前增/删 | 任务 |
|---|---|---|
| docs/process-archive/superpowers/plans/2026-09-29-local-candidate-decision-and-release-prep.md | 1/1 | 历史入口横幅仍不适合作最新结论；只审，不代改 |
| frontend/app/admin/sections/KnowledgeSection.tsx | 29/4 | 六值状态徽章与录入选项 |
| frontend/app/admin/sections/UploadSection.tsx | 16/1 | 上传区键盘/读屏可达 |
| frontend/app/chat/page.tsx | 6/0 | 图片能力门；不是未提交的取消接线 |
| frontend/app/globals.css | 11/0 | 焦点与 h4 样式 |
| frontend/components/chat/InputBar.tsx | 7/2 | 移动布局；已有 md:!text-base，别虚报桌面字号问题 |

四个非重叠文件字节、两个重叠文件有序 residual 已独立复核保留；五个前端当前字节等于历史 working-view。类型/构建证据不能替代对应交互验证。

依赖实装仍有 Chroma 0.4.24、core 0.1.53、LangSmith 0.1.147、splitters 0.0.2、langchain-openai 0.1.7、torch 2.6.0+cpu 风险。PyPI 用 fixed_in；LangSmith 使用 pip 行。补丁字段为空不是“永久无解”；ST 6.0.0/TF 5.17.0 未声明 torch 上界；2.13.0 不是已验证全清目标。

rerank 旧主/备用 key 已有 Owner 轮换确认，10-02 系统来源七请求成功的限定验收已完成；授权已用完。不得再写“未轮换/未配置”，也不得推广为普通入口、其他凭据或历史风险均关闭。

本地 Docker 8088 不是生产现网；旧镜像观察不保证当前 HEAD 能力。阿里云教程不是用户已选服务器。BGE 精确 revision 来源仍 PARTIAL。

当前修订证据入口：

- [汇总](C:/Users/33393/Desktop/fazhi-release-preflight-20261008-02b95968ef4541858da309bc26aaf703/reports/results.md)
- [残余审查](C:/Users/33393/Desktop/fazhi-release-preflight-20261008-02b95968ef4541858da309bc26aaf703/reports/residual-changes-review.md)
- [依赖/来源分案](C:/Users/33393/Desktop/fazhi-release-preflight-20261008-02b95968ef4541858da309bc26aaf703/reports/risk-followup.md)
- [独立复算](C:/Users/33393/Desktop/fazhi-release-preflight-20261008-02b95968ef4541858da309bc26aaf703/evidence/review-20261008-01/evidence-recalculation.json)
- [冻结清单核对](C:/Users/33393/Desktop/fazhi-release-preflight-20261008-02b95968ef4541858da309bc26aaf703/evidence/review-20261008-01/sealed-manifests-check.json)
- [本轮收尾核对](C:/Users/33393/Desktop/fazhi-release-preflight-20261008-02b95968ef4541858da309bc26aaf703/evidence/review-20261008-01/completion-check.json)
- [历史封口](C:/Users/33393/Desktop/fazhi-main-integration-20261007/evidence/delivery-closure.json)
- [rerank 当前历史记录](C:/Users/33393/Desktop/ai-legal-helper/docs/work-report-20261002-rerank-acceptance.md)

不要修改上述证据。原助手原稿另保存在 C:/Users/33393/Desktop/fazhi-release-preflight-20261008-02b95968ef4541858da309bc26aaf703/evidence/review-20261008-01/original-reports，仅作历史，不执行其已撤回的建议。

## A. 起点核对、输入保护与独立输出

**输入：** 本书起点、当前 Git、当前分发元数据、上列原始记录。
**创建：** 新独立根的 reports/a-baseline.md、evidence/input-before.json；不回填旧执行书复选框。
**接口：** 输出实际 root、HEAD、六 residual 的文件 SHA/bytes、分发清单、原始清单指纹；供 B/C/E 使用。

- [ ] 读 Git 四项；必须与本书起点一致：

~~~powershell
git -C C:/Users/33393/Desktop/ai-legal-helper rev-parse HEAD
git -C C:/Users/33393/Desktop/ai-legal-helper branch --show-current
git -C C:/Users/33393/Desktop/ai-legal-helper diff --cached --name-only
git -C C:/Users/33393/Desktop/ai-legal-helper status --short --untracked-files=no
~~~

- [ ] 明确没有并行写输入的任务；若不确定，纯文本询问 Owner 是否有写主仓/共享环境会话。检测到漂移则记录实际变化并暂停，不恢复六 residual。
- [ ] 用纯元数据命令保存精确分发清单，不读取环境变量：

~~~powershell
& 'C:/Users/33393/Desktop/fazhi-next-local-20261004-356fb810b3144d158e5dd18b9e276499/joint/venv/Scripts/python.exe' -I -B -c "import importlib.metadata as m,json;print(json.dumps(sorted((d.metadata['Name'],d.version) for d in m.distributions()),ensure_ascii=False))"
~~~

- [ ] 新建唯一目录，仅创建一次；新 shell 继续使用记录的实际路径，不再生成新目录：

~~~powershell
$closeoutTaskRoot = 'C:/Users/33393/Desktop/fazhi-project-closeout-' + (Get-Date -Format 'yyyyMMdd') + '-' + [guid]::NewGuid().ToString('N')
New-Item -ItemType Directory -Path $closeoutTaskRoot -ErrorAction Stop
New-Item -ItemType Directory -Path ($closeoutTaskRoot + '/reports') -ErrorAction Stop
New-Item -ItemType Directory -Path ($closeoutTaskRoot + '/evidence') -ErrorAction Stop
~~~

- [ ] 对六 residual 和实际会读取的源码/声明/旧证据建立明确路径清单，逐文件 Get-FileHash SHA256 + bytes 记录到 input-before.json。后续新增读取路径在使用前补记录，不把目录 mtime 当全树保护。
- [ ] 所有人工文件用 apply_patch；命令原始输出/退出码可由执行工具采集到私有 evidence。不要将可能含凭据的完整环境或请求头收进日志。

**A 验收：** 起点吻合、输入保护可复核、输出路径唯一；否则不开始候选裁定。本书默认未授权提交，暂存区必须保持空。

## B. 只读依赖适用性与精确一致闭包预检（优先主线）

**输入：** A；backend/requirements.txt、requirements-dev.txt；复算 JSON 的 requires/ghsa_rows/torch_archive_groups；官方公告与精确版本元数据/源码。
**创建：** reports/b-dependency-route.md、evidence/dependency-constraints.json；官方公开响应保存 evidence/advisories，不复用旧目录。
**接口：** 每簇输出适用对象/入口/外部输入、证据 URL/取得时点/生态、精确候选约束和缺口；不得只产出“建议升级”。

- [ ] 先核实际 Requires-Dist，不 import 产品码：

~~~powershell
& 'C:/Users/33393/Desktop/fazhi-next-local-20261004-356fb810b3144d158e5dd18b9e276499/joint/venv/Scripts/python.exe' -I -B -c "import importlib.metadata as m,json;names=['langchain-core','langsmith','langchain-openai','langchain-chroma','langchain-huggingface','langchain-text-splitters','sentence-transformers','transformers','torch'];print(json.dumps({n:{'version':m.version(n),'requires':m.requires(n)} for n in names},ensure_ascii=False))"
~~~

- [ ] Chroma 两条（GHSA-36p7-vc44-83pf、GHSA-2wm9-hf6c-p5cr）分别核对受影响入口与当前调用链。直接使用 backend/rag_chain.py、knowledge_service.py 中持久化 Chroma；不访问真实 CHROMA_DIR。无 HttpClient 命中只作静态事实，不作为缓解证明。
- [ ] LangChain 全家族核：core、LangSmith、openai/chroma/huggingface 适配与 splitters，连带 Chroma 本体、OpenAI SDK、索引兼容。当前 metadata 的上界相交不能代替候选 metadata 相交。
- [ ] LangSmith pip 修复线依次 0.7.31、0.8.0、0.8.18；不能用 npm 0.5.19/0.6.0。从复算 JSON 列全部相关通报逐项处理，不仅取最高数。
- [ ] torch 22 簇分别核适用性；4 簇空补丁不当永久风险，18 簇最高记录线 2.13.0 不当验证目标。+cpu 需要构建来源/修复映射，不要求为审计改实装标签。ST/TF 当前 torch 下限不是上限。
- [ ] ST 6.0.0 / TF 5.17.0：核当前精确源码的动态模块加载与默认信任调用链，区分旧对象异议、公告区间与当前实验缺口。只输出无害 marker 正控/否定实验方案，本书默认不运行模型加载器。
- [ ] 开发与 optional MCP：核 requirements-dev.txt 实装/声明和 .github/workflows/ci.yml 的 runtime-only 审计范围；MCP 声明/实装缺口写成能力选择，不默认安装或启用。
- [ ] 凭据/历史：只用既有脱敏记录核 10-02 rerank 轮换与限定成功，不重开“未配置”旧结论；普通入口、ADMIN_PASSWORD 及历史安全明确保持未证，本书不扩大扫描。
- [ ] 对存在于官方索引的精确候选核 Python3.11/目标平台、Requires-Dist 与每条修复区间，形成一个可解释的一致集合；缺来源/版本/构建/约束即登记不能证明，不自动换另一组无限试。
- [ ] 对比两条路线：受影响家族整体升级 vs 继续当前受限使用并补适用性/隔离证据。给事实/迁移面/残余风险，不能因后一条改动小就推荐风险接受；未确认安全路线即停止安装准备。
- [ ] 记录 BGE 精确 revision 小元数据缺口；当前本地一致性不等于来源证明。本书不授权再下权重或读取模型载荷。若仅查官方树，单请求连接 8 秒、总 20 秒、响应上限 1 MiB，失败原样记录，不改 refs/main/镜像来源凑闭合。

**B 验收：** 所有上述对象的风险/约束/证据缺口可追溯。精确一致集合若没有证实，则明确“安装准备停止，路线未闭合”；这是一份合格的调查结论，不是安全通过。默认不 pip install/--no-deps、不接受风险、不改 requirements。

## C. 六处残余：隔离离线补证，不先改产品

**输入：** A 的当前前端字节，不用仅 HEAD 归档替代残余视图。
**创建：** 新根 frontend/ 副本、frontend/tests/closeout.status-ssr.test.ts、frontend/vitest.closeout.config.ts，reports/c-residual-validation.md。
**原文件责任：** 只读主仓六 residual；新的测试/配置仅写新根，不修改旧 working-view/source。

- [ ] 用 rg --files 定位 frontend 下 app、components、lib、tests、scripts 与配置/包锁。只复制这些源码/清单；排除 .env*、node_modules、.next、证据/浏览器目录。逐文件显式 Copy-Item；不复制整个主仓或旧依赖根。核当前五文件字节等于 A 记录。
- [ ] 复用主仓现有 frontend/node_modules，只在新根创建 Junction；不 npm install、不复制/升级依赖。先确认 Node 与该 vitest/tsc 可用，缺任一就报告阻塞，不 npx 自动联网补装：

~~~powershell
Get-Command node -ErrorAction Stop
Test-Path -LiteralPath 'C:/Users/33393/Desktop/ai-legal-helper/frontend/node_modules/vitest/vitest.mjs'
Test-Path -LiteralPath 'C:/Users/33393/Desktop/ai-legal-helper/frontend/node_modules/typescript/bin/tsc'
# $closeoutTaskRoot 为 A 实际生成的目录；frontend 必须已由显式源码复制创建。
$closeoutFrontendRoot = $closeoutTaskRoot + '/frontend'
if (Test-Path -LiteralPath ($closeoutFrontendRoot + '/node_modules')) { throw 'Unexpected existing dependency path' }
New-Item -ItemType Junction -Path ($closeoutFrontendRoot + '/node_modules') -Value 'C:/Users/33393/Desktop/ai-legal-helper/frontend/node_modules' -ErrorAction Stop
~~~

- [ ] 新建 vitest.closeout.config.ts；自动 JSX 解析、别名与 cache 都指新根，不让测试写到旧输入：

~~~typescript
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";
export default defineConfig({
  cacheDir: fileURLToPath(new URL("./.closeout-vite-cache", import.meta.url)),
  esbuild: { jsx: "automatic" },
  resolve: { alias: { "@": fileURLToPath(new URL(".", import.meta.url)) } },
  test: { environment: "node", include: ["tests/**/*.test.ts"] },
});
~~~

- [ ] 使用现有 react-dom/server，真实渲染 KnowledgeSection，不导出内部组件只为测试，不从实现 switch 自动生成期望。新建 tests/closeout.status-ssr.test.ts：

~~~typescript
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { KnowledgeSection } from "../app/admin/sections/KnowledgeSection";
import { UploadSection } from "../app/admin/sections/UploadSection";

vi.mock("@/lib/api", () => ({
  api: new Proxy({}, { get: () => () => { throw new Error("Network forbidden"); } }),
  adminApi: new Proxy({}, { get: () => () => { throw new Error("Network forbidden"); } }),
}));
beforeEach(() => vi.stubGlobal("fetch", () => { throw new Error("Network forbidden"); }));
afterEach(() => vi.unstubAllGlobals());
const rows = [
  ["现行", "success"], ["已修改", "accent"], ["已废止", "error"],
  ["即将施行", "accent"], ["未生效", "accent"], ["未验证", "neutral"],
  ["未知测试状态", "neutral"], [undefined, "neutral"],
] as const;
function render(status: string | undefined) {
  return renderToStaticMarkup(createElement(KnowledgeSection, {
    knowledge: [{ id: "public-fixture", content: "无害公开测试正文", metadata: { status } }],
    setKnowledge: () => {}, knowledgeTotal: 1, setKnowledgeTotal: () => {},
    kPage: 1, setKPage: () => {}, candidates: [], setCandidates: () => {},
  }));
}
for (const [status, kind] of rows) {
  it("status " + String(status), () => {
    expect(render(status)).toContain(
      '<span class="badge badge-' + kind + '">' + (status || "未标注") + "</span>"
    );
  });
}
it("offers all six statuses", () => {
  const html = render("未验证");
  for (const status of ["现行", "已修改", "已废止", "即将施行", "未生效", "未验证"]) {
    expect(html).toContain('value="' + status + '"');
  }
});
it("upload exposes keyboard semantics", () => {
  const html = renderToStaticMarkup(createElement(UploadSection));
  expect(html).toContain('role="button"');
  expect(html).toContain('tabindex="0"');
  expect(html).toContain('aria-label="上传法律知识文件（回车选择文件）"');
});
~~~

- [ ] 在新 frontend 目录执行定向与回归；每条保存 cwd/起止/原始输出/退出码：

~~~powershell
# 命令的工作目录必须是 $closeoutFrontendRoot，不是主仓或旧封口根。
node 'C:/Users/33393/Desktop/ai-legal-helper/frontend/node_modules/vitest/vitest.mjs' run --config vitest.closeout.config.ts tests/closeout.status-ssr.test.ts
node 'C:/Users/33393/Desktop/ai-legal-helper/frontend/node_modules/vitest/vitest.mjs' run --config vitest.closeout.config.ts
node 'C:/Users/33393/Desktop/ai-legal-helper/frontend/node_modules/typescript/bin/tsc' --noEmit --incremental false
~~~

- [ ] 验证断言能红：另建 frontend/controls/closeout.status-negative.test.ts，故意给“未验证”期望 badge-success：

~~~typescript
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { KnowledgeSection } from "../app/admin/sections/KnowledgeSection";
vi.mock("@/lib/api", () => ({
  api: new Proxy({}, { get: () => () => { throw new Error("Network forbidden"); } }),
  adminApi: new Proxy({}, { get: () => () => { throw new Error("Network forbidden"); } }),
}));
beforeEach(() => vi.stubGlobal("fetch", () => { throw new Error("Network forbidden"); }));
afterEach(() => vi.unstubAllGlobals());
it("intentional wrong badge oracle", () => {
  const html = renderToStaticMarkup(createElement(KnowledgeSection, {
    knowledge: [{ id: "public-fixture", content: "无害公开测试正文", metadata: { status: "未验证" } }],
    setKnowledge: () => {}, knowledgeTotal: 1, setKnowledgeTotal: () => {},
    kPage: 1, setKPage: () => {}, candidates: [], setCandidates: () => {},
  }));
  expect(html).toContain('<span class="badge badge-success">未验证</span>');
});
~~~

另建 vitest.closeout.negative.config.ts，使对照不进入默认绿色集合：

~~~typescript
import { defineConfig } from "vitest/config";
import base from "./vitest.closeout.config";
export default defineConfig({
  ...base,
  test: { ...base.test, include: ["controls/closeout.status-negative.test.ts"] },
});
~~~

~~~powershell
node 'C:/Users/33393/Desktop/ai-legal-helper/frontend/node_modules/vitest/vitest.mjs' run --config vitest.closeout.negative.config.ts controls/closeout.status-negative.test.ts
~~~

预期非零必须来自 badge 文本/样式期望不符；“未找到用例”、编译/导入失败不算红测控制成功。保留日志，不改产品来演戏，不删除/改写失败证据。
- [ ] 报告 SSR 的局限：不执行键盘事件、不测 CSS 计算宽度、不证明页面图片 guard 外发路径。不得给十个静态断言包装成全部交互通过。
- [ ] 浏览器仍缺项明确列出：六徽章未知值；上传 Tab/Enter/Space 一次触发/无滚页/可见焦点；图片能力 true/false 下选择/拖放/粘贴各入口零未批准外发；390px 与 >=768px 输入/按钮可达、长输入无横向溢出。提出新独占页面/假 API 方案，未另批不启动服务或点击真实上传。
- [ ] 文档横幅按当前报告说明列“需另批修订”；不将旧 §16 当当前签字入口，不修改主仓此文件。
- [ ] 若真实缺陷复现，只交付失败用例、根因和修改责任。实际产品补丁进入 F0 审批，不因测试失败顺手重构。

**C 验收：** 当前源码绑定、离线断言/回归/类型检查都有退出码和局限；失败如实保留。SSR 通过不解除浏览器交互缺口。环境/依赖缺失则停止 C 的执行部分，不另装依赖。

## D. 真实模型 / 法律质量分案准备（不调用）

**输入：** A/B/C；backend/settings.py、llm_registry.py；10-02 历史 rerank 报告；新公开样本与官方法律来源。
**创建：** reports/d-model-validation-proposal.md、evidence/public-case-proposal.json。
**接口：** 角色/精确模型/端点确定来源、公开外发字段、gold、预算、缓存、成功/停止条件，供 Owner 一次明确裁定；未确认值必须列为执行前阻塞，不造默认值。

- [ ] 提案只覆盖主文本 RAG 质量与已承诺入口；Agent/图片/语音各由 Owner 选是否纳入，不默认开 agent/shadow/流量。llm_registry 的默认模型不是已确认实配，LLM_MODELS_JSON 可覆盖。
- [ ] 先准备六类公开案例：明确现行法条、历史基准日、同句多个事件日期歧义、非法日期、未收录/无证据、来源版本冲突。每案的事实/基准日/法名条号/正文版本/应答或拒答由官方来源和独立法律审查核对。六类是提案覆盖，不是批准调用数。
- [ ] 公共样本 gold 在生成前冻结并哈希，不由待测模型给答案再自评。待核法律结论不充当 gold；若无合格独立审查，则质量门保持未关闭。
- [ ] 把数据库、答案缓存、模型缓存、运行日志分别定位新独立路径；真实库不作为数据源。可先只提交 fixture 提案，不调用产品加载器。
- [ ] 给待批准预算表：总发送次数（含路由回退/SDK retry/Agent）、输入/输出 token 及费用上限、一次性轮次/超时/失败停点；精确模型确定后查官方价格，估算和实账分开。数字未批准之前新增调用上限为 0。
- [ ] 实验要求假传输先证明外发白名单、重定向/重试/回退计账、预算熔断、缓存绕过与脱敏有效；不把 HTTP200 或历史 rerank 七次成功当新法律质量证明。
- [ ] 质量判据由独立 gold 确定：条款/日期/版本逐项匹配，无证据不得硬答。关键法律错误、未批准外发、预算超限、鉴权或控制失败即停；不自动换模型/加轮/降门槛。
- [ ] 对 missing inputs 交付一个整齐审批表，由 Owner 指定实际角色/端点、数值预算、外发字段与样本/gold 认可。不要索要 key；另批后用安全来源就地注入，不打印。

**D 验收：** 实验协议结构完整、可读的公开样本提案及执行前输入明确；如果 gold/角色/数值预算缺任何一项，标“真实执行未就绪”，不能勾真实质量通过。

## E. 综合自审与交付（本书默认终点）

**输入：** A/B/C/D 实际结果，不沿用假定通过。
**创建：** reports/results.md、reports/work-report.md、evidence/input-after.json、evidence/closure.json。
**接口：** Owner 能区分本地准备完成与发布门未完成，并只选择下一项真实操作。

- [ ] 复量 HEAD/分支/暂存区/六 residual 字节、A 的选定输入与分发清单，逐一 before/after 比较。包括复用的 package/锁文件与工具版本；不能把包计数相同当包版本相同。
- [ ] 证据区分本次实跑、历史转录、未执行；记录所有失败/skip、排除项、原始退出码、工具/数据来源和断言控制。路径链接存在不等于测试通过。
- [ ] 自审 five-question：范围自然；与“直接升级/直接接受风险”相比为何先证闭包；无缓存污染/模型自评；事实出处可核；DoD 能复验。风险决定测试深度，不用一个 check 抵全验收。
- [ ] 汇总原六处建议：可另批何种提交单元/还缺哪些证据。若想只提交注释，必须审精准 hunk，整文件含行为修改不能冒充注释提交。
- [ ] 四门逐项标记未执行与输入：G1 真实法律质量；G2 目标平台可搬运包（Windows EPERM 未解决）；G3 远端历史/凭据/CI；G4 真实库恢复/迁移/部署。别把 A–E 文档结束当项目上线完成。
- [ ] 只推荐一个有实际推进条件的下一步，按已证风险和依赖排序，不按 diff 大小：B 缺证且可只读补齐则明确那一个补证；可靠闭包已证则可请求一案隔离升级；C 发现更高影响阻断或信任门可先独立验证，则请求对应定向案。证据已穷尽就交付具体裁定问题，不无限重复预检，不一次申请全部发布权限。
- [ ] 交付新根完整路径、实际发生的操作、输入保护结果、失败与未闭合项；到此停止，不自动进入 F。

**本地准备完成条件：** A 起点/保护一致；B 逐对象有证据或明确不可证明的缺口；C 有实际验证结果及浏览器未验边界；D 有协议和审批表；E 无虚假通过。它不是“依赖安全/六残余可提交/法律质量/项目发布通过”。C 工具执行被阻塞或输入保护失败，必须标本书部分完成。

## F. 后续审批分支（不是默认执行范围）

| 分支 | 进入前必须批准 / 具备 | 完成判据与停止条件 |
|---|---|---|
| F0 定向产品修复/文档改正 | 已复现失败、明确文件/行为/范围、独立期望、回归范围；Owner 另批 | 在独立候选先红后绿，覆盖相关正常/边界/失败；不改真实库。若结构性根因则重规划，不能反复小补丁 |
| F1a 当前信任门否定测试 | ST/TF 精确对象与源码预期、无害 marker 正控/拒绝实验、禁网/私有路径与允许的只读依赖使用另批；不要求 LangChain 升级闭包先完成 | 观测 import/执行前拒绝，而不是只有警告；对照不可观测或发生未批准执行即停。默认不下权重、不升级依赖，不以版本比较代替实验 |
| F1b 依赖升级 | B 已证该升级案精确闭包；Python/CPU 构建/来源、允许下载项/安装私有环境与实验边界另批 | 新环境不得动共享 venv；完整回归与索引兼容用公开隔离库，不用 --no-deps 凑绿。无可靠目标即停止 |
| F2 浏览器残余验收 | 独占私有端口/页面、全假 API、无真实 upload/LLM、可复核样本；Owner 另批 | C 浏览器矩阵实测，网络白名单零越界、截图/数值/事件计数绑定字节；只关自己的服务，原服务不动 |
| F3 真实模型一次性轮次 | D gold/角色/端点/预算/外发/凭据来源与质量门批准 | 实际目标路径与发送数可证明、独立 gold 判定、失败止损；不以 fallback 或缓存命中充目标通过 |
| F4 本地整合/提交 | F0/F1b/F2 对应验证完成，精确暂存路径/hunk/提交范围批准 | 提交前 fresh 验证与 index 审核，用户原改动保护；不自动 push。新分支默认 codex/ 前缀，主仓不 reset |
| F5 历史凭据/远端对齐/push/CI | 扫描范围与凭据源单独批准，ADMIN_PASSWORD 等历史处置明确；远端 URL/提交图/分支/CI 触发单独批准 | 不强推、不默认覆盖共同历史；已轮换 rerank 事实不重开旧问题，普通入口继承另证；CI runtime/dev 覆盖分开 |
| F6 目标平台/恢复/部署 | Owner 选服务器/OS/架构/域名；完整包、恢复演练、回滚、TLS/访问控制/监控、真实数据与时窗单独批准 | 先恢复验证再发布；Windows 退出0不能消除 standalone EPERM；教程不是平台选择。暂未选服务器时该分支不执行 |

风险接受另须 Owner 对“当前对象、实际受限用途、未覆盖风险、失效触发、复审时点”逐项裁定；助手不能因 F1 复杂代签。用户泛称“继续”不能替代真实外发/数据/发布新边界的确认。

## 给执行助手的建议与作者自审

- 先做 B 主线，不等服务器；C 离线静态验证可在 B 的某案受阻时独立推进，不能跳过 A 保护。
- 默认一个会话即可；只有用户另要求并行，才把 B/C 各自报告交不同助手，任何共享输入只读，E 由一个整合人负责。
- 不先加 jsdom/Testing Library/发布框架，不先拆 UI；确有能力缺口再提出理由和批准请求。
- 不清理旧目录来“整理项目”；先保护完整证据链。任何 Junction 不作递归删除目标，避免误删实际依赖。
- 本书自审：选择“先证路线/补针对性证据”而非直接跨代升级或默认接受风险；覆盖六 residual、十个风险分案类别、模型 gold/预算、四发布门；未知执行输入被列为硬停点，不虚构占位预算/服务器；没有修改业务接口、数据格式或自动发布权限。
- 本书命令与新 SSR 示例是后续执行步骤，本次仅核对当前源码接口，尚未实际运行；执行助手应保存真实结果。不能把作者自审当测试已通过。
