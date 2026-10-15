# D-3 冒烟回报：19 条红已全部归因；语义对照受控零漂移（2026-10-11）

> 依据 `dispatch-D3-langchain-migration-20261011.md` 与我（B+）推荐里写明的「冒烟红 ⇒ 停回来再裁」。**本步未改任何被测文件**；所有结论均为 envC(tree-x1) vs envB(tree-old) 双栈实测。
> 环境：`candidate-envC-1x`（Py3.11.0，core 1.6.9 / lc-openai 1.7.0 / lc-chroma 0.2.3 / lc-hf 1.2.3 / lc-splitters 1.1.3 / chromadb 0.4.24 不动 / openai-sdk 2.54.0）＋ tree-x1；对照 envB＋tree-old（HEAD `9e3cfc5` 同字节树）。

## 0 一句话

**19 条红 = 6 簇，全部定性为「测试夹具/断言对 1.x 新行为的适配」与「测试生命周期假设与 1.x 进程级 lru_cache 的边界」，无一指向生产字节不可迁移；受控语义对照 28/28 零漂移。请裁 §4 四项拟改是否放行（C1）或退 A/C。**

## 1 冒烟盘点

| 腿 | 读数 |
|---|---|
| 冒烟探针（8 步：import/copy 适配点/RunnableSerializable/callbacks/messages+parser/HF 构造/Chroma 端到端/splitter） | **8/8 OK**（log：`mig-20261011/smoke-probe-x1.log`） |
| 产品离线默认核（干净环境 import rag_chain → HF_HUB_OFFLINE=1 / HF_ENDPOINT=镜像） | **OK**（`defaultcheck.py`；注意本机 `env` 命令被 `~/.local/bin/env` 劫持会吞输出——勿用 `env -u` 包装） |
| 10 只迁移敏感 pytest（envC+tree-x1） | **19 failed / 239 passed / 3 skipped**（`smoke-pytest-x1.log`） |
| 同 10 只（envB+tree-old，对照） | **258 passed / 3 skipped / rc=0**（`smoke-pytest-old.log`） |

## 2 十九条第逐条映射（簇分六类）

| # | 用例（文件::名，略参） | 簇 | 已抓的 E 签 | 状态 |
|---|---|---|---|---|
| 1 | stream_cancellation::test_make_chain_close_reaches_owned_provider_response | 簇1 Field | `'FieldInfo' object has no attribute 'append'` @289 | 已证（E1 探针复现） |
| 2 | ::test_make_chain_task_cancel…[before-content] | 簇1 | 同上 | 已证 |
| 3 | ::test_make_chain_task_cancel…[after-content] | 簇1 | 同上 | 已证 |
| 4 | ::test_real_http_cancel_disconnects_peer…[before-content] | 簇3 metadata | `assert model.metadata == {"model":"same"}` @636（实差 lc_versions） | 已证 |
| 5 | ::test_real_http_cancel_disconnects_peer…[after-content] | 簇3 | 同上 | 已证 |
| 6 | ::test_factory_preserves_config_callbacks_and_original_client | 簇1 | FieldInfo 组 | 待修后复跑闭环 |
| 7 | ::test_per_chunk_parser_awaits…[async-handler-list] | 簇1 | FieldInfo 组 | 已证 |
| 8 | ::test_per_chunk_parser_awaits…[async-manager] | 簇1 | FieldInfo 组 | 已证 |
| 9 | ::test_concurrent_streams_keep_responses_request_local | 簇1 | FieldInfo 组 | 已证 |
| 10 | ::test_cleanup_error_does_not_mask… | 簇1 | FieldInfo 组 | 已证 |
| 11 | ::test_cleanup_error_preserves_original_provider_exception | 簇1+簇2 连锁 | FieldInfo → 异常路径错乱 → `NameError: _ERROR_NO_RESPONSE`（裸名） | 已证（连锁机理） |
| 12 | ::test_real_main_stream_close…[partial-output-ordinary] | 簇1 系 | — | 待修后复跑闭环 |
| 13 | ::test_real_main_stream_close…[partial-output-contract] | 簇1 系 | — | 待修后复跑闭环 |
| 14 | ::test_asgi_disconnect…[ordinary] | 簇1 系 | — | 待修后复跑闭环 |
| 15 | ::test_asgi_disconnect…[contract] | 簇1 系 | — | 待修后复跑闭环 |
| 16 | cancel_boundaries::test_d2_disconnect…[disconnect-while-prebody-work-in-flight] | 簇1 连锁 | `pre-body wait thread never finished…`（astream 早炸所致） | 已证连锁 |
| 17 | llm_lifecycle::test_registry_aclose_closes_real_installed_sdk_roots | 簇5 lru_cache | `assert not sync_root.is_closed()` 首查即 True；**单跑绿/与「#18 前序」双跑红** | 已证（P2 复刻） |
| 18 | llm_lifecycle::test_discarded_request_variant_leaves_shared_roots_open | 簇5 | 同上（单跑绿、有 aclose 前序则红） | 已证（P2 复刻） |
| 19 | llm_lifecycle::test_variant_and_model_reload_reuse_roots_and_keep_request_params | 簇4 extra_body | `model_kwargs.get("extra_body") is None`（1.x 已搬顶层字段） | 已证（源码+警告） |

**簇 1（根因钉死）**：测试两个文件用 `from pydantic.v1 import Field`（test_stream_cancellation.py:34、test_cancel_boundaries.py:31——全仓仅此 2 处）。0.1.x 的 `RunnableSerializable` 是 pydantic v1 模型（认 v1 Field）；**1.x 是 v2 模型**——v1 FieldInfo 不被收集，被当成"普通默认值"：
- 证据（E1 探针，直接加载测试的 `_LLM` 实测）：`vars(llm)['configs']` 里躺着 **v1 FieldInfo**、`model_fields['configs'].default_factory=None`；append 即炸。对照 envB：全正常（list）。
- 对照探针 M（同构类但用 `from pydantic import Field`）：1.6.9 下 default_factory 生效、append OK。

**簇 3（lc_versions）**：1.x `BaseLanguageModel.model_post_init`（langchain_core 1.6.9 `language_models/base.py:222-251`）**无条件**往 `metadata["lc_versions"]` 种子 core(+openai) 版本。生产无 `llm.metadata` 消费方（全仓 grep：仅 Document.metadata）。

**簇 4（extra_body）**：1.x 构造时把 `model_kwargs["extra_body"]` 提升为模型顶层字段（`ChatOpenAI(..., extra_body={...})`）+ UserWarning"should be specified explicitly"。**生产不读 `model_kwargs`**（全仓 grep 零消费）。

**簇 5（lru_cache 污染，本票最深水）**：
- 1.x 新增 `langchain_openai/chat_models/_client_utils.py:481-530`：`_cached_sync_httpx_client`/`_cached_async_httpx_client` 为 **`@lru_cache` 进程级缓存**（键=base_url+timeout+socket_options），构造 ChatOpenAI 时默认取用；且 1.x 把 `client` 改为 **Completions 访问器**、真根挪到新增的 **`root_client`/`root_async_client`**（base.py:793-799、1500-1544）。
- `LLMRegistry.aclose()`（llm_registry.py:531-563）关闭 `llm.client._client`（=共享的 OpenAI root）⇒ **lru_cache 里的 httpx 被连坐关闭且缓存不失效** ⇒ **同参数的下一个 llm 出生即 `is_closed()`**。
- P2 探针（逐段打点）复刻：「aclose 后新开 registry → 新 root 是**新对象**但 `is_closed=True`」。
- **生产不可达论证**：aclose 只在 `main.lifespan` 进程退出前一次性调用（幂等标记）；`reload()` 走 share 复用**不 close**（llm_registry.py:515-528）；`variant()` 同 share；`_load()` 重建不 close。⇒ 生产不存在"close 后继续构造"的序列。**测试的暴露面=测试自己在同进程多 registry 生命周期。**

## 3 语义对照（本票真目标）

**方法**：`mig-20261011/semantic_compare.py`（同一器三腿：A=`vector_top` 分数榜 / B=`hybrid_retrieve(k=4,cutoff=2026-10-11)` / C=引用配对链（ok/article_missing/source_missing 三态探针）+ D=切分），语料=data 在册 10 条（laws.json 7 + candidate-20260925 3；laws_extra.json 全占位符按 import_laws 护栏跳过——两侧同口径），query=eval_set.json 28 条；**离线、零 LLM、六根 BASE_URL 全 127.0.0.1、QUOTA/CHROMA/DATABASE 全隔离**。

| 读数 | 结果 |
|---|---|
| 分数逐位（BGE 余弦，抽样） | 两树**完全相同**（如 `0.3952403059400056`） |
| 27/28 query（vector+hybrid+citation）| 完全相同 |
| **id=4（刑法第十三条…）第 4 位** | **三跑三值**（一百八十八/二十条/二十五条）；**同栈两跑也变**（old↔old2 27/28；x1↔x1-2 27/28）⇒ **进程级非确定性** |
| **PYTHONHASHSEED=0 双树终拍** | **28/28 完全相同**、切分全部相同 ⇒ **非确定源=Python hash 随机化；受控条件下零漂移** |
| 切分（split_law_document + 10 条 split_article_text 的 meta/len/sha1） | 全部相同 |

⇒ 判定：**无"召回或引用配对变化"（停止条件 2 不成立）**；id=4 抖动在旧栈同样存在（**非迁移引入**）。若要把"逐位可复现"升级为正式判据，需以固定 `PYTHONHASHSEED` 口径复测（本页已给）。

## 4 拟改清单（改前/改后；票面 §3 要求"单独列出交 Owner"——**未动手**）

| # | 文件:行（2026-10-11 现量） | 改前 | 改后（拟） | 理由 |
|---|---|---|---|---|
| R1 | test_stream_cancellation.py:34、test_cancel_boundaries.py:31 | `from pydantic.v1 import Field` | `from pydantic import Field` | 簇1 根因；不改任何断言；全仓仅此 2 处 |
| R2 | test_stream_cancellation.py:636 | `assert model.tags == [...] and model.metadata == {"model": "same"}` | 保留 tags 断言；metadata 改为剔除 `lc_versions` 后相等 **＋增钉** `set(model.metadata["lc_versions"]) ⊇ {langchain-core, langchain-openai}` | 簇3；1.x 设计行为；新版不弱化（等价 + 增钉） |
| R3 | test_llm_lifecycle.py:295-297、326（4 行） | `v.model_kwargs.get("extra_body") == …` | 改读 1.x 顶层字段（`v.extra_body` / variant 对照同改） | 簇4；生产零消费；完整修法以修后复跑为准 |
| R4 | test_llm_lifecycle.py（`_fresh_registry()` 或各 aclose 用例收尾） | （无） | 加 `_cached_sync_httpx_client.cache_clear()`＋`_cached_async_httpx_client.cache_clear()`（from `langchain_openai.chat_models._client_utils`） | 簇5；模拟"新进程"隔离；该文件本就以"钉私有接缝"为风格（现有 `test_installed_chatopenai_accepts_client_injection_and_sdk_close_api` 即先例） |

**修后复跑计划**：冒烟 10 只（预期全绿；含 6/12-15 的闭环）→ 若全绿再跑全量（与在册旧窗阅读数对照）→ 残留任何红逐条再归因，绝不静默。

## 5 生产影响评估（三处 1.x 行为面）

| 行为 | 生产可达性 | 消费方 |
|---|---|---|
| lru_cache 共享 httpx（close 连坐） | **不可达**（aclose 仅进程退出一次性；reload/variant 走 share 不 close） | — |
| `metadata.lc_versions` 种子 | 可达（每个 ChatOpenAI 构造都种） | **无**（grep 零消费；LangSmith 未接） |
| `extra_body` 挪顶层字段 | 可达（warning 但语义保留，构造 repr 显示 extra_body 已生效） | 无（model_kwargs 零消费） |

**版本契约面**：测试文件内原有的"版本契约"用例（钉注入/关闭私有接缝）在 1.x 下**仍然通过**——注入语义（client/sync_root.chat.completions、`_client is root`）未破。

## 6 我的自审事故（本轮，防后人踩）

1. 探针三次自伤：`__version__` 属性不存在×2（改用 importlib.metadata）、`-z` 参数次序错致 git 静默失败（改写后没收 returncode）、极简探针缺抽象方法。
2. `env -u` 包装被 `~/.local/bin/env` 劫持吞输出 ⇒ 一度误判"命令没跑"。
3. 首版 Chroma 端到端探针用 `TemporaryDirectory`，Windows 文件锁使**清理阶段**抛 `NotADirectoryError`，**险些误读为 API 断裂**（功能段实为通过；改固定目录复跑 8/8）。
4. 一度把 id=4 的 hybrid 差异当"停止条件2 的漂移候选"，单栈复跑后翻案为 hash 随机（**报告口径以复跑矩阵为准**）。
5. 本机 `python`（PATH 上）非任何 venv——本页所有读数均标了所用解释器。

## 7 待裁（每条一词可答）

- **C1（推荐）**：放行 §4 的 R1–R4 四项测试适配改动 → 我修改后按 §4 复跑计划闭环，继续 B+ 迁移的后续腿（旧树全量基线复跑、新树全套、pip-audit 三口径、负向自证、报告）。
- **C2**：退 A（连 chromadb 一起抬）——**不推荐**：19 红中没有一条能被 A 消解（Field/断言/lru_cache 与 chromadb 无关），且引入 chromadb 大迁移。
- **C3**：退 C（暂缓整个迁移）。

## 8 复算入口

- 冒烟：`candidate-envC-1x/Scripts/python.exe mig-20261011/smoke_probe.py`；pytest 集与命令见 `smoke-pytest-x1.log` 头部；对照 `smoke-pytest-old.log`。
- 簇1 复现：`probe_fake_llm.py`（两栈各跑一次，`tree-x1` 的测试文件直接加载）；簇5 复现：`probe_aclose_sequence.py`；is_closed 链：`probe_root.py` / `probe_sdk_shared.py`。
- 语义对照：`semantic_compare.py <tree> <out.json> <tmp_dir>`；六份读数 `sem-tree-{old,x1,old2,x1-2,old3,x1-3}.json` 在 `mig-20261011/`；对照矩阵用 §3 同款 diff 脚本；`PYTHONHASHSEED=0` 口径=命令加该前缀。

## 补记（2026-10-11，闭环完成后）

- **R5 追补**：复跑 19F→3F 后，残余 3 条（`test_factory_preserves…`、`test_per_chunk_parser…` 两参）归因为 **callbacks 事件 `serialized=None`（1.x）而 `name` 两栈保真**（探针 `probe_cb_event.py` 双栈实证）——两处断言改钉 `item[2]["name"]`（等价接口、不弱化）。此为 §4 清单外**同类第 5 处**；改前/改后：`assert all(item[0]["id"][-1] == "StrOutputParser" …)` → `assert all(item[2].get("name") == "StrOutputParser" …)`（test_stream_cancellation.py 两处，含注释）。
- **闭环终态**：冒烟 10 只 **258 passed / 3 skipped（0 failed）**，与旧树对照逐数相同（`evidence/d3-smoke-pytest-x1-rerun2.log`）。
- **R3 就地修正**：§4 表原列的 `test_llm_lifecycle.py:326` 系误列（该行 `assert not …` 在 1.x 亦真），实际只改 295-297 三行。
- 全量双跑、审计三口径、负向自证、逐 query 语义对照与总报告：见 `reports/d3-langchain-migration.md`。
