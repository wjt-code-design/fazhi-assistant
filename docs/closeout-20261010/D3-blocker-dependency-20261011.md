# D-3 阻塞登记：两条依赖红线（2026-10-11，停于装包前）

> 依据 `dispatch-D3-langchain-migration-20261011.md` §5 停止条件 3（命中 ×2）。**本步未装包、未改窗、未建副本树、未动任何工作区。**
> §1 三条现量已核：审计 24/15/13/38 两轴相同、五行窗原文一致、61 行 import / 16 符号 / 39 文件、envB Py3.11.0/164 行、候选树 HEAD `9e3cfc5` porcelain=0、基线 1925/0/10/18/cov 86.35% —— **全部与本票一致，无差异项**。
> 本页数字口径：pip **纯净 dry-run**（`--dry-run --ignore-installed`，全新解析、不落任何 site-packages）与 PyPI 元数据（`requires_dist`），判定一律 `packaging.SpecifierSet` 区间运算。证据与复算命令见 §6。

## 0 一句话

**「五窗到 1.x」与「不动 chromadb」在依赖声明层不可同时成立**（唯一绕行=一个未声明组合）；**「13 条清零」要求 openai SDK 从 1.109.1 抬到 ≥2.26**（major）。两条都命中停止条件 3，停下登记，待裁（§4 四选一，每条一词）。

## 1 阻塞 B1-a：langchain-chroma × chromadb

- langchain-chroma **14 个稳定版本全扫**（逐版 core 钉 × chromadb 钉，机器生成）：
  - 能配 core 1.x 的版本：`0.2.3 / 0.2.4 / 0.2.5 / 0.2.6 / 1.0.0 / 1.1.0`
  - 其中**同时能配 chromadb 0.4.24** 的：**只有 0.2.3**（其余都钉 `chromadb>=1.0.9…1.3.5`）
  - `1.1.0` 钉 `chromadb>=1.3.5,<2`；与 `requirements.txt:10` 原行 `chromadb>=0.4,<0.5` **无交集**
- pip 纯净解析实测：五窗 `<2` + `chromadb` 原窗 ⇒ **rc=1 ResolutionImpossible**，原文：
  `langchain-chroma 1.1.0 depends on chromadb<2.0.0 and >=1.3.5`（完整冲突段见 `evidence/d3-dryrun-minA-resolution-impossible.txt`）
- ⇒ 五窗真 1.x = 必须动 chromadb 窗 + chromadb 0.4→1.5.9 的 major 迁移（与 §4 红线「不动 chromadb」及 D-2 撞面）；不动的唯一绕行 = `langchain-chroma==0.2.3`（**未受上游声明的组合**：0.2.3 的开发基线是 core 0.3.52，pip 可解≠被承诺）

## 2 阻塞 B1-b：openai SDK 轴

- 族通报 `langchain-openai PYSEC-2026-76`：fix=1.1.14；**1.1.14 起钉 `openai>=2.26,<3`**；`1.1.9` 及以前钉 `openai>=1.109.1,<3`。
- ⇒ 保持 openai SDK 1.109.1（envB 现装）⇒ langchain-openai 最多 1.1.9 ⇒ **76 清不掉**（最多 12/13）。
- ⇒ 13/13 清零 ⇔ openai SDK 1.109.1→≥2.26（major）。五窗全 1.x 纯净解析还会拿到 **SDK 3.28.0**（跨两个 major；可钉 `<3` 停 2.x 线）。
- SDK 2.54.0 对项目直连面（`OpenAI`/`AsyncOpenAI`/`APITimeoutError`/`APIStatusError`/`APIConnectionError`）已在 wheel 内核实全部仍在（5/5）。

## 3 顺带实测（非阻塞，备核）

- **langsmith 真·最新 = 0.14.7**（远超 4 条修复线 ≥0.8.18）。⚠️ 我早前粗扫按上传序取 latest 有错（报出 0.9.8/0.10.12），已用纯净解析改正；如你见过我用旧数，以本页为准。
- langchain-core 1.6.9 引入**新传递依赖 `langchain-protocol`**（解析到 0.0.19）。
- API 面（静态、未装包）：**16/16 符号在 1.x 全候选未改名**（`evidence/d3_api_freeze.json`，行号与 import 均现扫）。热点三条：`llm_registry.py:398` 注入 `client/async_client` 字段（1.x 字段仍在）；`self.llm.copy(update=…)` 为 pydantic v1 风格调用（装包后必测的第一适配点，代码注释在原位）；`HuggingFaceEmbeddings` 配 st 6.1.0 属未声明组合（hf 1.2.3 的 full extra 声明 st `<6.0`，运行时按需 import sentence_transformers）。
- 纯净全新解析下 numpy 到 2.4.6（envB 是 1.26.4）——「全新装」与「原地升级」两种语义读数不同，执行时两种都报。

## 4 四条路线（pip 纯净解析实测；每条一词可答）

| 路线 | requirements 窗改动 | 纯净解析装出（关键件） | 13 条 | 代价 |
|---|---|---|---|---|
| **A** | 五窗 `<2` + chromadb 放开 | core 1.6.9 / openai 1.7.0 / chroma 1.1.0 / hf 1.2.3 / splitters 1.1.3 / **chromadb 1.5.9** / **openai-sdk 3.28.0** / langsmith 0.14.7 | 理论 13/13（待实测复核） | chromadb major 迁移（红线）+ SDK 跨 2 major |
| **B** | core`>=1,<2`；openai`>=1.1,<1.1.10`；chroma`==0.2.3`；hf`>=1,<2`；splitters`>=1,<2`；+新钉 `openai>=1.109.1,<2` | core 1.6.9 / openai 1.1.9 / chroma 0.2.3 / hf 1.2.3 / splitters 1.1.3 / **chromadb 0.4.24 不动** / **openai-sdk 1.109.1 不动** | 12/13（76 留） | 1 个未声明组合（chroma 0.2.3 × core 1.6.9） |
| **B+** | 同 B，但 openai`>=1.1.14,<2`；+新钉 `openai>=2.26,<3` | core 1.6.9 / openai 1.7.0 / chroma 0.2.3 / hf 1.2.3 / splitters 1.1.3 / **chromadb 0.4.24 不动** / openai-sdk 2.54.0 | 理论 13/13（待实测复核） | 1 个未声明组合 + SDK major（1→2） |
| **C** | 暂缓 D-3 | — | 0 | 迁移轴整体留给 D-2 统筹 |

**推荐：B+（先冒烟定生死）。** 理由：四条里唯一能「不动 chromadb 红线 + 13/13」的路线；B 系的未声明组合只有 1 个，且静态面已预验：chroma 0.2.3 的 `vectorstores.py` 对 core 的 4 个 import（`Document`/`Embeddings`/`utils.xor_args`/`vectorstores.VectorStore`）在 core 1.6.9 全部仍在（5/5，含成色复核）。
若你选 B+：执行第一步 = 副本树冒烟（新建 `candidate-envC-1x` 装 B+ 组合，跑三个引用测试文件 + 迁移敏感用例：llm copy 适配点、Chroma 读写、splitter）；**冒烟红 ⇒ 停回来再裁**（退 A 或 C，B 作次选）。
次选：**B**（不接受 SDK major 时）；都不接受 ⇒ **C**。

## 5 本步自查出的我自己的错（防后人踩）

1. 首版 wheel 扫描器与自检正则两次写窄（定义候选路径、`>=1.x` 匹配），制造过假阴/假阳 ⇒ 全部改用 `SpecifierSet` 区间判定 + 全包扫描重做；本页数字以重做版为准。
2. "latest 版本"粗扫按上传序排序有误（langsmith 报 0.9.8）⇒ 改为 pip 纯净解析（0.14.7）为准。
3. 一次含 torch 的全量 dry-run 解析缓慢转后台且输出未能读取 ⇒ **未引用其结果**；代之以 5 份最小集纯净 dry-run（A/B/B+/Bwin/A2 全部落盘）。

## 6 复算入口

- 矩阵重建：`python evidence/d3_dependency_matrix_gen.py evidence/d3_dependency_matrix.json`（stdout 打四象限）
- 冻结表重建：`python evidence/d3_api_freeze_gen.py mig-20261011/wheels "<候选树>/backend" candidate-envB/Lib/site-packages evidence/d3_api_freeze.json`
- 分母三口径：`node evidence/audit_axes.js evidence/audit-cand-runtime.json`
- dry-run 程序（pip 22.3；任意实验集可复跑）：
  `"C:/Users/33393/AppData/Local/Programs/Python/Python311/python.exe" -m pip install --dry-run --ignore-installed --report <rep.json> -r <set.txt>`
  - 实验集与结果：`evidence/d3-dryrun-sets.txt`、`d3-dryrun-minA-resolution-impossible.txt`、`d3-dryrun-min{A2/ B/Bplus/Bwin}*.txt`、`d3-dryrun-rep-*.json`

## 7 与票面差异（现量更正，2026-10-11）

- dispatch-D3 §2.2 的「必须手工带的那一只（不在 git 里）：`dispatch-output/task1/hidden_runner.py`」**现量为误**：该文件**已被跟踪**（`git ls-files -- dispatch-output/task1/` 列出；引入提交 `fdf802d`"盲测集改运行期读取……纯 tracked 树可收集"），`git check-ignore -v` 无命中（exit=1），`git archive HEAD` 自带。按 tracked 快照建树无需手工步骤；本会话两种口径各做一遍（幂等，同 sha），树完整性 2676/2676 tracked、0 缺失、0 多余。独立复核票若读到同句，请按现量改。
