# T7 依赖升级分案（pypdf / FastAPI·Starlette / Chroma）— 2026-09-27

写给的后续独立任务：每节自带"风险与证据 → 最小升级候选 → 与现有上限的冲突 → 必跑的兼容性检查 → 失败回退"，
可按节拆票执行。**本文件只记账，不改 `requirements*.txt`、不动 venv、不动真实库**（当日纪律：T7 本轮不升级依赖）。

> **E 修订记录（2026-09-27）**：修正三处自相矛盾/不成立处 —— §1 检查 3 的"应为 24/24 基线"、§1 的失败回退两条互斥路径、§2 的失败回退（"删显式 starlette 行重装 ⇒ 回 0.36.3"不可复现）。改后仍**只记账**：任何具体升级留待单独授权。
> 事实基线（上面那条 `HEAD 7eda4bb`）仍有效：`7eda4bb..6f95d3a` 这 4 笔的 30 个文件**未碰** `requirements*/venv/pip/lock`（`git diff --name-only 7eda4bb..6f95d3a | grep -iE "requirement|venv|pip|lock"` 为空）。

事实基线（09-27 实测，HEAD `7eda4bb` + 工作区）：

- 声明区间（`backend/requirements.txt`）：`pypdf>=4.0,<6.0`（:24）、`fastapi>=0.110,<0.111`（:3）、
  `chromadb>=0.4,<0.5`（:11）、`uvicorn[standard]>=0.27,<0.28`（:4）；**starlette 无直接声明行**（fastapi 传递依赖）。
- 本机实装（backend venv，`pip show`）：pypdf **6.14.2**（越 `<6.0`）、fastapi 0.110.3（在区间内）、
  starlette **0.36.3**、chromadb 0.4.24（在区间内）、uvicorn **0.52.1**（越 `<0.28`）——
  与汇报 §9.11"本机 uvicorn/pypdf 越出声明依赖区间"一致。
- `pip check` 当场两条红：①fastapi 0.110.3 要求 `starlette>=0.37.2,<0.38.0` 但实装 0.36.3；
  ②sse-starlette 3.4.8（由 `mcp` 传递引入，backend 代码未 import，后端 SSE 走 `fastapi` 的 `StreamingResponse`）
  要求 `starlette>=0.49.1` 但实装 0.36.3 ⇒ **venv 现状已经不是自洽安装**。
- 审计双模式（pip-audit 2.10.1；完整读数在本会话对账回执，未落盘为仓库文件，此处录要点）：`pip-audit -r requirements.txt` 审的是"按区间新解析出的安装集"（pypdf 解析到
  5.9.0），**不是**本机实装集；要看实装面须另跑不带 `-r` 的环境模式。两者退出码都是 1。
- CI（`.github/workflows/ci.yml:45-46`）每次 push/PR 跑 `pip-audit -r requirements.txt` ⇒ 按该解析集读数推断
  **CI 的 pip-audit 步必红**（推断，未查实际 CI 运行记录）
  （pypdf 解析版 5.9.0 有 41 行通报，全部只在 6.x 修复）；与 §9 记的"pip-audit rc=1 ＝ 在册已批的风险接受到期"同源。

未核项（写明，不许当已核）：允许 starlette≥1.3.1 的 fastapi 具体版本未核（PyPI 最新 0.141.1，其 starlette 上限待该任务
实查）；chromadb 0.5/1.x 是否修复 PYSEC-2026-3813/3814 未核（审计库对 0.4.24 未给修复版本）；`langchain-chroma>=0.1,<0.2`
对 chromadb 的实际兼容上限未核。以下凡"未核"处不得编造版本号。

---

## 1. pypdf（建议第一个做：改动面最小、风险面最实）

**当前风险与证据**
- requirements 解析版 5.9.0：41 行通报（PYSEC-2026-1827~1833/3004~3016/3655/3656/3910~3913 + CVE-2026-57204），
  修复版本散布 6.0.0→6.16.1 ⇒ **在 `<6.0` 区间内无任何可清账的版本**。
- 实装 6.14.2 仍余 6 条（修复 6.15.0/6.16.0/6.16.1）⇒ 清全部当前通报需 **≥6.16.1**（PyPI 在售，最新 6.19.0）。
- 可达性（在册记录 `backend/scripts/gen_r8_disposition.py:76`）：用户上传 PDF 经
  `knowledge_service.parse_uploaded`（`backend/knowledge_service.py:111-113`，`PdfReader(io.BytesIO(raw))`）
  —— chat_file 合同评估 + admin_upload 知识库两条路径；多条属畸形文件处理类（需主动上传恶意 PDF，仅文本提取）。
  缓解已在册：10MB 上限、仅文本提取（不渲染不执行）、上传需登录会话；此前按"中-高保守取值"风险接受、已到期。

**最小升级候选**：`pypdf>=6.16.1,<7.0`（一行改动；6.16.1 为当前通报的最低全清版本）。

**与现有上限的冲突**：仅 `<6.0` 本身；无其他声明包钉 pypdf（chromadb 不依赖它）。
注意 venv 里那颗 6.14.2 本来就越界——本票顺手把实装拉回声明区间内，是收编不是越权。

**必跑的兼容性检查**
1. 上传路径：admin 上传 PDF 端点 + chat_file 用样例 PDF 各一次，比对提取文本与旧版逐字一致（含中文样例）。
2. 畸形/损坏 PDF 负例：上传损坏文件应被友好拒绝或跳过，不得 500（通报集中在畸形文件处理）。
3. `pytest` 全量 + `smoke_citation_fast.py` 24 项。
   ⚠️（E 更正）：**不得写"应为 24/24 基线"**——该门禁在**原配置（真实 rerank）**下的现量是 **23/24、rc=1**，
   红点恒为既有检索缺口 `retrieve("周末加班，加班费怎么算？")` 期望 `劳动法 × 第四十四条`
   （`progress-handoff-report-20260925.md:921`）。pypdf 是纯解析库、改不到检索面 ⇒ 升级后应与此**读数相同**；
   拿"24/24"当验收基线会把**既有**红点误算成新回归。（历史另有"离线 24/24"，那是副本+离线嵌入口径，与本门禁不同轴，不可互顶。）
4. `ruff`/`mypy` 原门槛。

**失败回退**（E 更正：原文"还原到 `>=4.0,<6.0` 并重装"与"回到 6.14.2 实装"**互斥**——`<6.0` 解析所得是 5.x，永远装不回 6.14.2；须按想退到哪一侧**二选一**）：
① 退到**声明自洽的低侧**：还原该行为 `>=4.0,<6.0` 并按区间重装（解析得 **5.9.0**、携 41 行在册通报，等于退回原风险接受）；
② 退到**今天实装**：显式钉 `pypdf==6.14.2`（或改声明为 `>=6.14.2,<7.0`），承认区间越界、续登在册风险接受。
无数据面（pypdf 纯解析库，无持久化格式）。

---

## 2. FastAPI / Starlette（分两步走；第一步只清一条，第二步未核）

**当前风险与证据**
- starlette 0.36.3（实装）/0.37.2（CI 解析版）同携 **7 条**通报：PYSEC-2026-1943（修 0.40.0）、
  -1941（修 0.47.2）、-161（修 1.0.1）、-2280/-2281（修 1.1.0）、-248/-249（修 1.3.0/1.3.1）
  ⇒ **清全部需 starlette≥1.3.1**（PyPI 在售至 1.7.0）。fastapi 本体 0.110.3 无通报。
- 可达性：starlette 是对外 HTTP 面（FastAPI 应用全量端点 + SSE 流式出口）。
- **先修"环境不自洽"本身就是风险**：实装 starlette 0.36.3 低于 fastapi 0.110.3 自己的下限 0.37.2，
  且 sse-starlette 3.4.8（mcp 传递）要 ≥0.49.1——今天任何一次重装都会把 starlette 拉到别的版本，
  与其漂着不如按票钉死。

**最小升级候选（两步，各自独立可回退）**
1. 第一步（低风险）：`fastapi>=0.115,<0.116`（0.115.14 为该系末版）+ 显式加 `starlette>=0.40,<0.42`
   ⇒ 清掉 PYSEC-2026-1943；同时消除"实装低于 fastapi 下限"的自相矛盾。
   （0.115 允许的 starlette 区间以该任务实装 `pip check` 为准，此处只给方向。）
2. 第二步（未核，先查再动）：清余下 6 条需 starlette ≥1.3.1 ⇒ 对应 fastapi 版本**未核**
   （PyPI 最新 0.141.1；查清其 starlette 上限后才许开票）。
3. 相邻决定（不捆进本票）：uvicorn 实装 0.52.1 越 `<0.28`、本身无通报——上限是陈旧值，改区间是独立一句话决定，
   与 fastapi 升级分开裁。

**与现有上限的冲突**：`fastapi<0.111` 是主要约束；starlette 无声明行反而是个坑——建议本票给它补显式行，
否则 CI 解析与实装会继续漂。次要约束面：chromadb 0.4.24 自己依赖 fastapi（其上限未核），
`opentelemetry-instrumentation-fastapi`（chromadb 传递）与 `slowapi 0.1.9`（限流中间件包着 starlette）都要过一遍。

**必跑的兼容性检查**
1. **SSE 逐帧形状**：E7/E8/E9/E17/E18 各出口的帧序与文案（`tests/test_time_unverified_note.py` 20 条 +
   `tests/test_stream_exit_law_version_gate.py` 是主回归面，帧序断言最脆）。
2. slowapi 限流在升版后仍生效（429 路径一条用例）。
3. python-multipart 上传、FileResponse、pydantic v2 校验面（`schemas.py` 全量）。
4. chromadb 0.4.24 与新 fastapi 共存：`pip check` 干净 + 服务能起（uvicorn 现装版跑通冒烟）。
5. `pytest` 全量 + smoke 24 项 + ruff/mypy。

**失败回退**（E 更正：原文"删显式 starlette 行重装 ⇒ 回 0.36.3/0.110.3 组合"**不可复现**——
fastapi 0.110.3 自身要求 `starlette>=0.37.2,<0.38.0`，删行重装会拉到 0.37.x；而 sse-starlette 3.4.8 又要 `>=0.49.1`，
两条传递约束互斥 ⇒ 结果由 pip 解析顺序决定、非定值，且必然仍不满足 `pip check`）：
退不回"自洽态"，只能退到"今天这条**已红**的非自洽态"。故回退须**显式钉死目标组合**（如 `fastapi==0.110.3` + `starlette==0.36.3`，
并标注"已知不自洽、仅为行为对照"）。第二步若 fastapi 侧无兼容版，停在第一步并按 gen_r8_disposition 形状续登风险接受。

---

## 3. Chroma（唯一没有"升级即清账"证据的一条；数据面风险最高）

**当前风险与证据**
- 实装 0.4.24（区间内、也是 0.4.x 末版）：PYSEC-2026-3813、PYSEC-2026-3814 两条，**审计库未给修复版本**
  ⇒ 升到 0.5.23/0.6.3/1.5.9 是否清账**未核**，须先在沙箱装新版重跑 pip-audit 验证，再谈升级。
- 可达性：`rag_chain.py:119-123`/`knowledge_service.py:42` 用 `PersistentClient`（**内嵌进程内，无网络监听面**）
  ⇒ 通报的远程可达性低；但要按票面口径写清"内嵌 ≠ 无风险"。
- 真实数据面：`backend/chroma_db/`（10266 块，mtime 09-21 02:06 在册）——大版本升级可能触发持久化格式迁移，
  **不可逆**；这是与"T7 不动真实数据"红线的正面冲突，也是本节排最后的理由。

**最小升级候选**：无现成答案（未核）。候选动作序列：①沙箱 venv 装 0.5.23 → 重跑 pip-audit 看两条是否消失 →
②不清再试 1.x；③清了才进"兼容性检查"阶段。每步都先 `chroma_db` 整目录冷备份（复用 `scripts/backup_data.py`，
落点另盘），**绝不指真实库做试验**。

**与现有上限的冲突**：`chromadb<0.5`、`langchain-chroma<0.2`（其对 chromadb 的实际上限未核）、
`chroma-hnswlib` 原生扩展随版走；0.5/1.x 的 embedding function 与 collection API 有破坏性变更史，
`rebuild_embeddings.py`/`switch_embedding.py`/`restore_drill.py` 一并受波及。

**必跑的兼容性检查**
1. 副本库打开读回：集合名、块数 10266、`origin/effective_from` 等元数据键逐字段一致。
2. 检索对照：`smoke_citation_fast.py` 24 项（副本、离线口径）+ 一组固定探针的 top-6 位次前后逐位对照
   （可复用 version-safety-review-20260927 §1.2 的 A/B 法）。
3. 导入预检 `--dry-run`（三条候选）读数仍为"替换 2、新增 3、跳过 0"。
4. 全量 pytest + ruff/mypy。

**失败回退**：换回备份的 `chroma_db` 目录 + 还原 `chromadb>=0.4,<0.5` 重装 0.4.24；
若 0.5/1.x 数据格式已被真实库误触迁移 ⇒ 只能整目录回滚到冷备份，**这也是每步先备份的原因**。
两条通报清不掉时，按 gen_r8_disposition 形状登记"无可用修复 + 内嵌面可达性低"的风险接受。

---

## 4. 三条的共同前置（任何一票开工前）

1. **先立可复现基线**：当前 venv 两处越区间 + `pip check` 两条红 ⇒ 所有升级任务必须从
   `pip install -r requirements-dev.txt` 新建 venv 起步（对齐 CI 解析集），不许在漂移的 venv 上做升级对照。
2. 审计口径固定写两行：`-r` 模式（CI 口径）+ 环境模式（实装口径），退出码都记。
3. 每票独立分支/相邻 commit，不与代码轮混；不改 `.env`、不碰真实库、不 push（与本仓 09-26 以来纪律同）。
