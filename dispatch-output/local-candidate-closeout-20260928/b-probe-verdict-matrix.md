## B 档运行时判定（由读数现生，勿手抄）

### 测试场

- 读数文件：`b-probe-readings-pytest-20260929-103511.json`（mode=`pytest-suite`），装桩时刻 2026-09-29T10:35:44，装桩前已加载：无
- 监视模块在场 29 个；外联事件 206 类 / 348 次（另有 compile 9826 次不计入外联）
- 别名补钉：{'G1a': ['langchain_core.load.load.load', 'langchain_core.tracers.log_stream.load'], 'G1b': ['langchain_core.load.load.loads'], 'G1c': ['langchain_core.prompts.loading.load_prompt'], 'G1g': ['langchain_core.language_models.chat_models.dumps', 'langchain_core.load.dump.dumps', 'langchain_core.tracers.log_stream.dumps']}；打桩异常：无

| 组 | 目标 | 公告 | 判定 | 依据 |
| --- | --- | --- | --- | --- |
| G1 | `G1a` load | CVE-2025-68664 / CVE-2026-44843 | ZERO-CALL | 在场但 0 次调用 |
| G1 | `G1b` loads | CVE-2025-68664 / CVE-2026-44843 | ZERO-CALL | 在场但 0 次调用 |
| G1 | `G1c` load_prompt | CVE-2025-65106 / CVE-2026-40087 | ZERO-CALL | 在场但 0 次调用 |
| G1 | `G1d` load_prompt_from_config | CVE-2026-34070 | ZERO-CALL | 在场但 0 次调用 |
| G1 | `G1e` from_template | CVE-2025-65106（模板暴露面，非漏洞本身） | ZERO-CALL | 在场但 0 次调用 |
| G1 | `G1f` from_messages | CVE-2025-65106（模板暴露面，非漏洞本身） | ZERO-CALL | 在场但 0 次调用 |
| G1 | `G1g` dumps | CVE-2026-44843（序列化写出面） | ZERO-CALL | 在场但 0 次调用 |
| G2 | `G2a` get_num_tokens_from_messages | CVE-2026-26013 / CVE-2026-41488 | ZERO-CALL | 在场但 0 次调用 |
| G2 | `G2b` get_num_tokens_from_messages | CVE-2026-26013 / CVE-2026-41488（基类） | ZERO-CALL | 在场但 0 次调用 |
| G2 | `G2c` get_num_tokens | CVE-2026-26013（相邻纯文本计数面） | ZERO-CALL | 在场但 0 次调用 |
| G3 | `G3a` from_pretrained | CVE-2026-4372 / CVE-2026-5241 | 1-CALLS | 调用方 backend/rag_chain.py:39×1；实参首项 BAAI/bge-base-zh-v1.5 kw=_from_auto,adapter_kwargs,cache_dir,config,revision,trust_remote_code；trust_remote_code=False |
| G3 | `G3b` from_pretrained | CVE-2026-4372 | 1-CALLS | 调用方 backend/rag_chain.py:39×1；实参首项 BAAI/bge-base-zh-v1.5 kw=cache_dir,revision,token,trust_remote_code；trust_remote_code=False |
| G3 | `G3c` from_pretrained | CVE-2026-4372（config 基类实现） | ZERO-CALL | 在场但 0 次调用 |
| G3 | `G3d` from_pretrained | CVE-2025-14929（相邻 tokenizer 面） | 1-CALLS | 调用方 backend/rag_chain.py:39×1；实参首项 BAAI/bge-base-zh-v1.5 kw=_commit_hash,_from_auto,cache_dir,revision,token |
| G3 | `G3e` SentenceTransformer | CVE-2026-4372（本项目实际调用者） | 1-CALLS | 调用方 backend/rag_chain.py:39×1；实参首项 BAAI/bge-base-zh-v1.5 kw=cache_folder,device |
| G4 | `G4a` TracingMiddleware | CVE-2026-59152 | NEVER-IMPORTED | 运行期从未被导入 |
| G4 | `G4b` Client | CVE-2026-41182 / CVE-2026-45134 | ZERO-CALL | 在场但 0 次调用 |
| G4 | `G4c` pull_prompt | CVE-2026-45134 | ZERO-CALL | 在场但 0 次调用 |
| G4 | `G4d` SitemapLoader | CVE-2024-2965 | NEVER-IMPORTED | 运行期从未被导入 |
| G4 | `G4e` EverNoteLoader | CVE-2025-6984 | NEVER-IMPORTED | 运行期从未被导入 |
| G4 | `G4f` FAISS | CVE-2024-5998 | NEVER-IMPORTED | 运行期从未被导入 |
| G4 | `G4g` GraphCypherQAChain | CVE-2024-8309 | NEVER-IMPORTED | 运行期从未被导入 |

### 应用路径

- 读数文件：`b-probe-readings-app-20260929-103841.json`（mode=`app-paths`），装桩时刻 2026-09-29T10:38:41，装桩前已加载：无
- 监视模块在场 25 个；外联事件 11 类 / 15 次（另有 compile 7860 次不计入外联）
- 别名补钉：{'G1a': ['langchain_core.load.load.load', 'langchain_core.tracers.log_stream.load'], 'G1b': ['langchain_core.load.load.loads'], 'G1c': ['langchain_core.prompts.loading.load_prompt'], 'G1g': ['langchain_core.language_models.chat_models.dumps', 'langchain_core.load.dump.dumps', 'langchain_core.tracers.log_stream.dumps']}；打桩异常：无

| 组 | 目标 | 公告 | 判定 | 依据 |
| --- | --- | --- | --- | --- |
| G1 | `G1a` load | CVE-2025-68664 / CVE-2026-44843 | ZERO-CALL | 在场但 0 次调用 |
| G1 | `G1b` loads | CVE-2025-68664 / CVE-2026-44843 | ZERO-CALL | 在场但 0 次调用 |
| G1 | `G1c` load_prompt | CVE-2025-65106 / CVE-2026-40087 | ZERO-CALL | 在场但 0 次调用 |
| G1 | `G1d` load_prompt_from_config | CVE-2026-34070 | ZERO-CALL | 在场但 0 次调用 |
| G1 | `G1e` from_template | CVE-2025-65106（模板暴露面，非漏洞本身） | ZERO-CALL | 在场但 0 次调用 |
| G1 | `G1f` from_messages | CVE-2025-65106（模板暴露面，非漏洞本身） | ZERO-CALL | 在场但 0 次调用 |
| G1 | `G1g` dumps | CVE-2026-44843（序列化写出面） | ZERO-CALL | 在场但 0 次调用 |
| G2 | `G2a` get_num_tokens_from_messages | CVE-2026-26013 / CVE-2026-41488 | NEVER-IMPORTED | 运行期从未被导入 |
| G2 | `G2b` get_num_tokens_from_messages | CVE-2026-26013 / CVE-2026-41488（基类） | ZERO-CALL | 在场但 0 次调用 |
| G2 | `G2c` get_num_tokens | CVE-2026-26013（相邻纯文本计数面） | ZERO-CALL | 在场但 0 次调用 |
| G3 | `G3a` from_pretrained | CVE-2026-4372 / CVE-2026-5241 | 1-CALLS | 调用方 backend/rag_chain.py:39×1；实参首项 BAAI/bge-base-zh-v1.5 kw=_from_auto,adapter_kwargs,cache_dir,config,revision,trust_remote_code；trust_remote_code=False |
| G3 | `G3b` from_pretrained | CVE-2026-4372 | 1-CALLS | 调用方 backend/rag_chain.py:39×1；实参首项 BAAI/bge-base-zh-v1.5 kw=cache_dir,revision,token,trust_remote_code；trust_remote_code=False |
| G3 | `G3c` from_pretrained | CVE-2026-4372（config 基类实现） | ZERO-CALL | 在场但 0 次调用 |
| G3 | `G3d` from_pretrained | CVE-2025-14929（相邻 tokenizer 面） | 1-CALLS | 调用方 backend/rag_chain.py:39×1；实参首项 BAAI/bge-base-zh-v1.5 kw=_commit_hash,_from_auto,cache_dir,revision,token |
| G3 | `G3e` SentenceTransformer | CVE-2026-4372（本项目实际调用者） | 1-CALLS | 调用方 backend/rag_chain.py:39×1；实参首项 BAAI/bge-base-zh-v1.5 kw=cache_folder,device |
| G4 | `G4a` TracingMiddleware | CVE-2026-59152 | NEVER-IMPORTED | 运行期从未被导入 |
| G4 | `G4b` Client | CVE-2026-41182 / CVE-2026-45134 | ZERO-CALL | 在场但 0 次调用 |
| G4 | `G4c` pull_prompt | CVE-2026-45134 | ZERO-CALL | 在场但 0 次调用 |
| G4 | `G4d` SitemapLoader | CVE-2024-2965 | NEVER-IMPORTED | 运行期从未被导入 |
| G4 | `G4e` EverNoteLoader | CVE-2025-6984 | NEVER-IMPORTED | 运行期从未被导入 |
| G4 | `G4f` FAISS | CVE-2024-5998 | NEVER-IMPORTED | 运行期从未被导入 |
| G4 | `G4g` GraphCypherQAChain | CVE-2024-8309 | NEVER-IMPORTED | 运行期从未被导入 |

### 每组问题与答（「测到 0 次」与「没测到」分栏，绝不合并）

  前一版这里把两样东西混在一个判定集合里打出来（`['NEVER-IMPORTED', 'ZERO-CALL']`），读起来像「这组都答了、都是 0」。`NEVER-IMPORTED` 的含义是**这场压根没走到那个模块**，它是「未测」，不是「测到 0 次」的阴性证据。

- **G1** 问：应用是否在运行期把外部内容当作序列化对象或模板配置来重建
    测到 0 次：G1a, G1b, G1c, G1d, G1e, G1f, G1g
    （同一只桩在两档里同时出现 = 两场结论不同，例如测试场测到 0 次而应用场从未导入，那是「分场」不是矛盾）
- **G2** 问：token 计数路径是否会在运行期去抓图片 URL（SSRF/重绑定）
    测到 0 次：G2a, G2b, G2c
    未测（模块从未导入）：G2a
    （同一只桩在两档里同时出现 = 两场结论不同，例如测试场测到 0 次而应用场从未导入，那是「分场」不是矛盾）
- **G3** 问：模型与 config 加载发生在哪、用的是不是钉死的模型名、trust_remote_code 是否放行
    测到有调用：G3a×1, G3b×1, G3d×1, G3e×1
    测到 0 次：G3c
    （同一只桩在两档里同时出现 = 两场结论不同，例如测试场测到 0 次而应用场从未导入，那是「分场」不是矛盾）
- **G4** 问：未被应用引用的 loader / 追踪中间件 / Hub 拉取是否在场或被实例化
    测到 0 次：G4b, G4c
    未测（模块从未导入）：G4a, G4d, G4e, G4f, G4g
    （同一只桩在两档里同时出现 = 两场结论不同，例如测试场测到 0 次而应用场从未导入，那是「分场」不是矛盾）
### 公告视角（覆盖到 / 没覆盖到，两张清单都要看）

登记表 `residual-risk-review.md` 里的公告去重 26 条；本探针有桩可答的 17 条，**探针答不上的 9 条**。

| 公告 | 覆盖它的桩 | 各场判定 |
| --- | --- | --- |
| CVE-2024-2965 | G4d | 测试场: NEVER-IMPORTED; 应用路径: NEVER-IMPORTED |
| CVE-2024-5998 | G4f | 测试场: NEVER-IMPORTED; 应用路径: NEVER-IMPORTED |
| CVE-2024-8309 | G4g | 测试场: NEVER-IMPORTED; 应用路径: NEVER-IMPORTED |
| CVE-2025-14929 | G3d | 测试场: 1-CALLS; 应用路径: 1-CALLS |
| CVE-2025-65106 | G1c, G1e, G1f | 测试场: ZERO-CALL; 应用路径: ZERO-CALL |
| CVE-2025-68664 | G1a, G1b | 测试场: ZERO-CALL; 应用路径: ZERO-CALL |
| CVE-2025-6984 | G4e | 测试场: NEVER-IMPORTED; 应用路径: NEVER-IMPORTED |
| CVE-2026-26013 | G2a, G2b, G2c | 测试场: ZERO-CALL; 应用路径: NEVER-IMPORTED, ZERO-CALL |
| CVE-2026-34070 | G1d | 测试场: ZERO-CALL; 应用路径: ZERO-CALL |
| CVE-2026-40087 | G1c | 测试场: ZERO-CALL; 应用路径: ZERO-CALL |
| CVE-2026-41182 | G4b | 测试场: ZERO-CALL; 应用路径: ZERO-CALL |
| CVE-2026-41488 | G2a, G2b | 测试场: ZERO-CALL; 应用路径: NEVER-IMPORTED, ZERO-CALL |
| CVE-2026-4372 | G3a, G3b, G3c, G3e | 测试场: 1-CALLS, ZERO-CALL; 应用路径: 1-CALLS, ZERO-CALL |
| CVE-2026-44843 | G1a, G1b, G1g | 测试场: ZERO-CALL; 应用路径: ZERO-CALL |
| CVE-2026-45134 | G4b, G4c | 测试场: ZERO-CALL; 应用路径: ZERO-CALL |
| CVE-2026-5241 | G3a | 测试场: 1-CALLS; 应用路径: 1-CALLS |
| CVE-2026-59152 | G4a | 测试场: NEVER-IMPORTED; 应用路径: NEVER-IMPORTED |

**探针答不上的公告（不许把这栏读成「已排除」）**：CVE-2024-3095, CVE-2024-7774, CVE-2025-6985, CVE-2026-1839, CVE-2026-41481, CVE-2026-45830, CVE-2026-45833, CVE-2026-55443, CVE-2026-9856

闭合检查：17 + 9 == 26 -> PASS
