## torch 盲区消除（2026-09-29 补，执行计划 B 节第 4 项 / 待办 A-2）

**原先的状态是真的没数**：实装 `torch 2.6.0+cpu` 在扫描读数里是一条 `skip_reason`
（`Dependency not found on PyPI and could not be audited: torch (2.6.0+cpu)`）⇒ 扫描器**一条漏洞读数都没产生**。

**本轮做的不是换版本说话，是把本地标签摘掉**：`+cpu` 只是本地构建标签，上游 `2.6.0` 在 PyPI 上是有分发的，
扫描器失败的原因**是那个标签而不是这个版本**。所以拿实装版本本体去审：

```bash
# 用候选解释器； requirements 只钉实装的那个上游版本，--no-deps 防止解析器把依赖扩成另一棵树
printf 'torch==2.6.0\n' > /tmp/torch-pin.txt
python -m pip_audit -r /tmp/torch-pin.txt --no-deps --format json --timeout 90
# rc=1；Found 24 known vulnerabilities in 1 package
```

读数已入库：`C-torch-2.6.0-pinned-pip-audit.json`（横幅在 `.err.log`，按仓规 `.log` 不入库）。
**24 行 = 22 条唯一通报**（两条 PYSEC 各被给了两个不同 `fix_versions`，所以行数≠通报数，别混着报）。

**四条判据，逐条都有反例形状，别一步跳过去**：

1. **"在区间内"不等于适用**：22 条里若干条的公告正文把受影响版本写成 **2.7.0 / 2.8.0 / 2.10.0**
   （如 `CVE-2026-4538` 正文写 "identified in PyTorch 2.10.0"，且 `fix_versions` 为空 ⇒ pip-audit 因无上界而报它）。
   这与 §「pip-audit 只比本包版本」是同一族问题：**扫描器命中 ≠ 本版本适用**。
2. **构建变体是一根独立的判别轴**：`CVE-2025-2148 / 2149 / 2953` 正文写的是 `PyTorch 2.6.0+cu124`，
   受影响函数是 `profiler._call_end_callbacks_on_jit_fut`、`nnq_Sigmoid`（量化）、`mkldnn_max_pool2d`；
   本机是 **`+cpu`**（`torch.version.cuda = None`，实测）。⇒ 这三条**倾向不适用**，但这是**版本/构建证据，不是不可达证明**。
3. **调用面证据**：应用代码 **0 处 `import torch`**；torch 只经 `sentence-transformers`/`transformers`
   的模型加载与前向进来（B 档读数 `G3e SentenceTransformer` 两场均 1-CALLS，调用方唯一归到 `rag_chain.py:39`）。
   那 22 条点名的接口里，`torch.compile`/Inductor、`torch.jit.script`、量化、Conv2d、`to_sparse`、`linalg.lu`、
   `lstm_cell`、`nan_to_num`、`rot90`、`nn.Fold`、`PairwiseDistance` 等**均不在本应用的构造路径上**。
4. **`fix_versions` 为空的 4 条**（`CVE-2025-2148 / 2149 / 2998 / CVE-2026-4538`）**一律不得**读成"无补丁即永久有风险"，
   也不得读成"没有版本号所以不适用"。
   ⚠️ 这个"4"的判据不是"某行 `fix` 为空"：同一通报在 JSON 里可能有两条来源行，`CVE-2025-2953` 就是一条给 `[]`、
   一条给了修复版本 ⇒ **按单行判空会算成 5 条**。复算件（与运行时轴共用同一件）：
   `python b_no_fix_union.py --scan C-torch-2.6.0-pinned-pip-audit.json --selftest`，
   它同时打印"单行判空会多出 `2953`"这条能红的对照，并现算出本轴 **24 行 / 22 条唯一通报**。

**唯一一条与本环境暴露面直接相关的：`CVE-2026-24747`**（GHSA-63cw-57p8-fm3p，修复 **2.10.0**）
—— `weights_only` 反序列化器本身可被构造的 checkpoint 绕过。我做了**直接实测**（临时目录，不触网、不落仓）：

- `torch.load` 的 `pickle_module` 默认值是 **`None`** ⇒ `_default_to_weights_only(None) = True`，
  **torch 2.6.0+cpu 默认就是 `weights_only=True`**；
- 我写了一枚含 `__reduce__ → os.system` 的协议 4 pickle，调 `torch.load(p, map_location="cpu")`（不显式传 `weights_only`）
  ⇒ 抛 `UnpicklingError: Weights only load failed`，**副作用文件没有被创建**。

⇒ 三点结论，方向要摆对：
1. 默认防护**在本构建上确实是开的**，而且是**实测红的**（不是我读 release notes 读来的）；
2. 但这条通报声称绕过的**正是这个 `weights_only` 反序列化器** ⇒ **"默认开着"不是它的缓解证明**，别把 ① 当成已缓解；
3. 它的**前置条件是一份恶意/被改动的 checkpoint 文件** ⇒ 它**直接压在签字页第二栏 ⑤"模型文件完整性未验"上**。
   实测本机缓存 `models--BAAI--bge-base-zh-v1.5` 里**同时存在 `model.safetensors` 与 `pytorch_model.bin`**（两个快照目录），
   ⇒ pickle 加载路径**在缓存里是实体存在的**，不是假设。

**处置**：盲区已消除，但**不等于清零**。本阶段**不升级 torch**（要 2.10.0+ 才消 `CVE-2026-24747`，属 C 档另案、会牵动 BGE 向量空间）；
所以这一轴的正确状态是：**22 条逐条已有版本/构建/调用面证据，其中 1 条（24747）的实际风险取决于"模型文件完整性"这件尚未做的事**
⇒ 它既不能被本笔签字消案，也不该被读成"审过了、没事"。
