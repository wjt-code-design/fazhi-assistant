# 模型链依赖升级预检（只读元数据）

任务于 2026-10-03 启动，跨日于 2026-10-04 完成；本文件保留约定的 `20261003` 名称。下列取得时间均为 **Asia/Shanghai（UTC+08:00）**。

**结论：ST 5.6.0／Transformers 5.10.0 在官方 PyPI 均存在，但 Transformers 5.10.0 已撤回，禁止列入下载目标。相邻未撤回 5.10.1 可保留为待验证候选；其默认依赖要求升级 huggingface-hub。ST 5.6.0 的官方源码仍保留本地自定义代码信任绕过，与审计“5.6.0 修复线”存在实质矛盾，安全关闭尚未成立。**

本轮只读既有证据、官方 PyPI JSON、上游发行说明和带版本标签的源码；未下载 wheel／sdist／模型，未运行 pip install／download／dry-run resolver，未加载模型。旧源码、venv、主仓代码、真实库、`.env`、模型缓存及 Git 未修改。`metadata-only` **不等于完整依赖解析、安装、功能或安全验证通过**。模型来源继续 **PARTIAL**；正式采纳／D2 留待 Owner，**2026-10-05 复审不顺延**。

证据保全限制：本模型链研究的原始 PyPI JSON／官方源码未另存文件，取得时间与内容保留在当轮工具输出中；本文的 wheel SHA 是上游公告值，不是实物校验。后续冻结候选前须另存新的原始响应、实际取证时间和 hash，不能事后补造旧快照。主审已复核公告／标签源码矛盾；合并下一步边界见 [剩余依赖预检与执行边界](C:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/superpowers/plans/2026-10-04-remaining-dependency-preflight.md)。

## 1. 已查版本与声明

| 官方元数据 | 实际取得时间 | Requires-Python | wheel 标签／撤回状态 |
| --- | --- | --- | --- |
| [ST 5.6.0 JSON](https://pypi.org/pypi/sentence-transformers/5.6.0/json) | 2026-10-04T00:02:40+08:00 | `>=3.10` | `py3-none-any`；`yanked=false` |
| [Transformers 5.10.0 JSON](https://pypi.org/pypi/transformers/5.10.0/json) | 2026-10-04T00:02:41+08:00 | `>=3.10.0` | `py3-none-any`；**`yanked=true`** |
| [Transformers 5.10.1 JSON](https://pypi.org/pypi/transformers/5.10.1/json) | 2026-10-04T00:05:11+08:00 | `>=3.10.0` | `py3-none-any`；`yanked=false` |

已装 Windows amd64／Python 3.11.0 满足上述 Python 声明，通用 wheel 标签可匹配该平台；这只确认发行文件的标签与 Python 条件，未核对全部传递二进制依赖。5.10.0 撤回原因是发布时使用过旧 main、遗漏修复并存在模型可用性疑问；[上游 5.10.1 发行说明](https://github.com/huggingface/transformers/releases/tag/v5.10.1)也确认错误分支导致撤回。官方[发行列表 JSON](https://pypi.org/pypi/transformers/json)于 00:03:48 查询到相邻 5.10.1，本轮只展开此一个替代版本。

**ST 5.6.0 默认 Requires-Dist（无 extras）**，逐项来自上述 ST JSON：

```text
transformers<6.0.0,>=4.41.0
huggingface-hub>=0.23.0
torch>=1.11.0
numpy>=1.20.0
scikit-learn>=0.22.0
scipy>=1.0.0
typing_extensions>=4.5.0
tqdm>=4.0.0
```

`Provides-Extra`：`image,audio,video,train,onnx,onnx-gpu,openvino,dev`。可选分支分别声明 Transformers 的 vision／audio／video extras，train 的 datasets／accelerate，ONNX／OpenVINO 的 optimum 包；dev 还带训练与测试工具。本轮不启用这些 extras。

**Transformers 5.10.0 与 5.10.1 默认 Requires-Dist 相同（无 extras）**，逐项来自各自的版本 JSON：

```text
huggingface-hub<2.0,>=1.5.0
numpy>=1.17
packaging>=20.0
pyyaml>=5.1
regex>=2025.10.22
tokenizers<=0.23.0,>=0.22.0
typer
safetensors>=0.4.3
tqdm>=4.27
```

两者 `Provides-Extra` 均为 `torch,vision,audio,video,timm,quality,docs,kernels,sentencepiece,tiktoken,mistral-common,chat-template,sklearn,accelerate,retrieval,sagemaker,deepspeed,optuna,integrations,ray,codecarbon,serving,num2words,benchmark,ja,testing,deepspeed-testing,all,dev`。相关 `torch` extra 额外要求 `torch>=2.4`、`accelerate>=1.1.0`；默认发行并不要求 accelerate。本轮不启用 TF extras，未审查未选 extras 的完整闭包。

## 2. 所查 wheel 元数据（仅公告值，未下载校验文件）

所有 size 均为字节；SHA-256 是 PyPI JSON 的 `digests.sha256`，不是本轮计算得到的 wheel 文件哈希。

| 文件名与官方 URL | bytes | SHA-256 | yanked／原因 |
| --- | ---: | --- | --- |
| [sentence_transformers-5.6.0-py3-none-any.whl](https://files.pythonhosted.org/packages/76/c1/dc1582b79e9a2eb0cddf9559cd9bcdff084f541d6fe881fdd9d98630dba7/sentence_transformers-5.6.0-py3-none-any.whl) | 596411 | `d2075b5e687a1611005e20ab04a6846994d51adfcf39610aed066af3c0c0b81f` | false／null |
| [transformers-5.10.0-py3-none-any.whl](https://files.pythonhosted.org/packages/d9/19/448dd8054ac95d61718105bea048ded00a60551824e08b4280cd31770039/transformers-5.10.0-py3-none-any.whl) | 10923423 | `eae143e46d8e521da604bc4fdc45af7dd90e96eacbbc27f68d2754150aa5175a` | **true／旧分支、遗漏修复；记录供追溯，排除下载** |
| [transformers-5.10.1-py3-none-any.whl](https://files.pythonhosted.org/packages/e3/8c/3119596c7fcd9b8b8d924d5b5ba1bfdfafd6d8738bdd81ca09c60b4a38b3/transformers-5.10.1-py3-none-any.whl) | 11003770 | `ccb919ea1b77338b44d0d45d23f7472081906b1bb6ed8e5f5cf4d692d1da03d4` | false／null |

对应 upload UTC：ST `2026-06-16T14:01:55.103031Z`，TF 5.10.0 `2026-06-03T15:16:02.505003Z`，TF 5.10.1 `2026-06-03T15:37:00.433138Z`。这些是发行时间，不能代替本轮取证时间。

## 3. 兼容冲突与安全限制

已验联合根的 [installed-audit.json](C:/Users/33393/Desktop/fazhi-joint-candidate-20261003-ac701f4a880441b5a453b1b7cbb06f01/evidence/installed-audit.json) SHA-256：`e017d4ea084899c31137f8d58df6e57bda38dad536941dc83d9e6b16ca5a0d5a`。以下已装版本取自该只读审计；torch 的实装 `2.6.0+cpu` 由审计跳过原因确认。

| 当前值 | 新声明比较 | 本轮判断 |
| --- | --- | --- |
| ST 2.7.0 要求 TF `<5` | TF 修复线进入 5.x | 不能保留旧 ST 并单升 TF；需成组验证 |
| huggingface-hub 0.36.2 | TF 5.10.x 要求 `>=1.5.0,<2.0` | **明确形式冲突，必须调查精确 1.x 候选** |
| tokenizers 0.22.2 | `>=0.22.0,<=0.23.0` | 形式满足；暂保留，API／本地模型行为待验 |
| torch 2.6.0+cpu | ST `>=1.11.0`，TF[torch] `>=2.4` | 形式满足；无需仅为声明兼容换 CPU torch |
| numpy 1.26.4 | ST `>=1.20.0`，TF `>=1.17` | 形式满足；不因本轮默认声明升级 |

审计中的 packaging 23.2、PyYAML 6.0.3、regex 2026.9.10、scikit-learn 1.9.1、scipy 1.17.1、tqdm 4.70.1、typer 0.27.2、typing-extensions 4.16.0、safetensors 0.8.0 也分别满足这里列出的直接声明。以上为声明比较推断，未执行解析器，未验证它们各自的传递依赖和运行路径。

**torch 未被原审计覆盖。** 原条目只有 `name,skip_reason`，原因是 `Dependency not found on PyPI and could not be audited: torch (2.6.0+cpu)`；不存在可当作“0 漏洞”的 `vulns` 结果。本轮未发现要求更换 torch 的声明，因此没有扩大 CPU 版本搜索；后续须独立核对该 CPU 构建的上游风险、平台 wheel 和实际加载边界。不能推断 CPU 没有漏洞。

**ST 修复口径冲突必须阻断安全通过声明。** 原审计 `PYSEC-2026-4164`／`GHSA-jhr6-gm9c-rqjv` 列修复 5.6.0；[GitHub 公告](https://github.com/advisories/GHSA-jhr6-gm9c-rqjv)也列 patched 5.6.0。但[官方 5.6.0 发行说明](https://github.com/huggingface/sentence-transformers/releases/tag/v5.6.0)只说发出弃用警告、v6.0 才要求显式信任；[5.6.0 官方源码 misc.py 第131行](https://github.com/huggingface/sentence-transformers/blob/v5.6.0/sentence_transformers/util/misc.py#L131)仍保留本地路径条件，在调用动态模块加载后才发 `FutureWarning`（第135／151行）。源码于 `2026-10-04T00:06:07+08:00` 从[官方 raw 文件](https://raw.githubusercontent.com/huggingface/sentence-transformers/v5.6.0/sentence_transformers/util/misc.py)只读取得。**警告不构成拒绝执行，本轮没有运行攻击探针；仍需核对真正关闭此行为的精确发行，不能仅信 fix_versions。**

Transformers 原审计还保留空 fix 列表：`PYSEC-2025-217`（X-CLIP checkpoint conversion）、`PYSEC-2026-2290`（同 ID 的另一行又列 5.5.0）、`PYSEC-2026-4174`（custom generation 信任检查前写入）。[chat-template 路径穿越公告](https://github.com/advisories/GHSA-xrqw-3rrv-vx5w)列修复 5.10.0；[custom generation 公告](https://github.com/advisories/GHSA-x9r9-c232-4q39)列 affected `>=4.49.0,<=5.8.1`、patched `None`。5.10.1 不在该公告明列 affected 区间，但这不能代替修复代码／项目调用面核对。空 fix 列表既不证明新版本受影响，也不证明风险关闭；需逐项复核并保留重复记录差异。

## 4. 最小拟变更集合与追加调查

仅用于下一轮讨论的最小集合：`sentence-transformers==5.6.0`、`transformers==5.10.1`、`huggingface-hub>=1.5.0,<2.0` 中一个经核对的精确版本。**这不是已批准的下载单或安全候选通过结论**；ST 信任门禁冲突须先决定正确修复目标，再冻结最终精确集合。本轮不扩查 ST 6.x，不把 5.10.0 放入候选。

- 必须追加：hub 的精确版本、Requires-Python／Requires-Dist、撤回、Windows wheel 公告 SHA，以及 0.x→1.x API／缓存行为；该部分未核对。
- 暂保留后验证：tokenizers 0.22.2、numpy 1.26.4、torch 2.6.0+cpu；另查项目本地模型是否需要 sentencepiece 等可选包，避免启用 all／dev／训练 extras 引入无关依赖。
- 尚未核对：完整解析闭包、额外包 Windows wheel、TF 4→5／ST 2→5 项目 API 迁移、本地 BGE 配置和池化一致性、逐条安全适用性、CPU torch 完整审计。源码标签与 PyPI wheel 内容的一致性也未经解包验证。

## 5. 后续独立验证 DoD（本轮未执行）

1. 先解决 ST 公告／源码矛盾并冻结精确候选；全部发行未撤回、官方文件／SHA 可复核，完整声明闭包可解析。任何下载或执行只进入新的仓外隔离环境；不覆写既有联合候选或旧快照。
2. 独立安装后验证实际版本、`pip check`、项目必要回归，记录 resolver 新增／改变的每一包；将 Python／Windows amd64／CPU 路径与支持范围写清。重做逐项安全审计，CPU torch 的跳过必须有独立补证或明确限制。
3. 模型来源 **PARTIAL** 的缺项继续保留；不能以依赖升版或局部权重哈希顶替精确 revision 全文件来源。本轮未重复既有 HF 模型来源补证失败请求。CPU 加载须限定既有冻结缓存、禁网、不执行未知自定义模型代码；若门禁不成立，先停止加载验证并记录原因。
4. 只用已批准 **1528 条公开法规库副本**；新进程复开并核对 ID／正文／metadata、QA=0、输入向量指纹和索引读回阈值。输入 bytes 严格一致；索引读回绝对差≤`1e-6`、余弦误差≤`1e-10`，不能改向量凑哈希。
5. 同一 BGE CPU 模型按原规则每部法规固定两条、共 **8 条**重算，逐条余弦≥`0.99999`；**768 维相同不等于空间一致**。阈值与样本规则来自[原模型空间验收 §4](C:/Users/33393/Desktop/ai-legal-helper/docs/work-report-20261002-rerank-acceptance.md:45)，不是本轮新运行结果。保持原检索题集／判据，验证离线烟测与法名＋条号联合召回；数值失败时提出隔离重建索引分案，不写原库。
6. 验前／验后保护指纹覆盖旧源码、旧 venv、既有证据、原库、`.env`、模型缓存、HEAD／refs。保留失败与差异，不以 mock、维度或旧轮次成功替代本轮结果；不自动增加真实 rerank／云端请求。最终依赖变更与 D2 分别交 Owner，复审仍为 **2026-10-05**。

可复核元数据的最小只读命令为 `Invoke-RestMethod -Uri 'https://pypi.org/pypi/<包名>/<精确版本>/json'`；本文使用的是返回中的 `info.requires_python`、`info.requires_dist`、`info.provides_extra` 与 `urls`。PyPI 是实时来源，日后状态改变应另存新取证记录，不能改写本文旧取得时间或将公告 SHA 当作已下载验签。
