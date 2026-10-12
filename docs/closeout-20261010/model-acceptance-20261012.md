# F 腿（五类真实模型验收）开工记录：仪具已就位，四条路里三条是死的（2026-10-12）

本轮范围＝Owner 10-12 裁定②「必须开真实模型，测试真实回答质量」＋「a，上限 100 元」＋「授权读 `.env`」。
**这份文件的上限＝机器复核分**：审签交 AI（D-41），所以这里没有任何一句是「法律质量通过」。

## 0. 先看这段

1. **仪具已经全部就位并自证能红**：私有播种 16 只（10 真＋6 合成）走产品自己的索引入口 `knowledge_base.build()`，零出网实测；G-a 内容锚点、G-c 自查询 16/16、G-b 开/关两趟都跑了；transport guard 现在 10 条控制全 PASS，含新加的「接到产品自建 client」那三条。
2. **但现役凭据撑不起真实验收**：四条路里三条是死的——DashScope **403 AllocationQuota.FreeTierOnly**（账号只有免费额度，需你在控制台开通付费）、SiliconFlow rerank **401**（在册 key 不被接受）、在册冻结的默认 LLM `qwen3.5-omni-plus-2026-03-15` **该账号根本没有**（`GET /models` 现量只有 `LongCat-2.0`、`LongCat-2.5-Preview` 两只，请求它返回 400 invalid_parameter）。唯一能答的长路是 `LongCat-2.5-Preview`。
3. **现在只需你一句话**：F 的代表模型用哪一个。我的推荐＝**先在控制台开通 DashScope 付费额度**（那是 在册 registry 的 6 只模型的实际供应商，开通后本轮冻结值不用改，五类里至少文本/Agent 两类能真跑）；如果你不动控制台，那我按 `LongCat-2.5-Preview` 重冻一版只跑文本 RAG，rerank 与 Agent 两类仍按 BLOCKED 记。**我不擅自换代表模型**——执行书 §F2 原文写了「换代表模型先重新对齐」。
4. 花费摊开：本轮实际发出 **10 次 HTTP**，其中 3 次成功生成，合计 **2319 tokens（prompt+completion，全部 LongCat）**。**折成多少元我说不出来**——F1 要求先查供应商官方价格再花，这一条我没做（见 §5 未做清单），所以「上限 100 元」目前只有用量读数、没有金额读数，账单也未核。

## 1. 私有隔离（F1 第二 bullet 的现量）

| 出口 | 绑定值 | 说明 |
|---|---|---|
| `DATABASE_URL` | `.../model-validation/p3-20261012/data/app.db` | 本轮私有，真实 `backend/data/app.db` 未触达 |
| `QUOTA_DB` | `.../p3-20261012/data/quota.sqlite` | 同上 |
| `CHROMA_DIR` | `.../p3-20261012/chroma-public` | 播种 16 只，真实 `backend/chroma_db` 未触达 |
| `HF_HOME`/`HF_HUB_CACHE` | `D:/fazhi-big/p3-20261012/model-cache[/hub]` | 781 MB，C 盘现量 97% 满，大件按你的话落 D 盘 |
| `HF_HUB_OFFLINE` | `1`（且 `TRANSFORMERS_OFFLINE=1`） | 嵌入素材零出网，见 §2 |
| `ANONYMIZED_TELEMETRY` | `False` | chromadb 埋点在 `rag_chain` import 期就发生，早于 socket 守卫 ⇒ 把它做成构造性质而不是靠测那段窗口 |

读键名不读值：`p3_env.read_env()` 只取 `WANTED` 那 16 个键，打印键名与长度；`.env` 的读取是你 10-12 授权的例外，这条例外本身记在这里。

## 2. 播种与三道门（全部零付费）

- 素材：`seed-corpus-frozen.json`，sha256 前缀 `06d233548d601198`，来自候选 `43e5037` 的 `data/laws.json` + `data/laws_extra.candidate-20260925.json`；三只源文件的 **HEAD blob == 盘上 git-blob** 逐只核过（`seed-manifest.json`）。
- **分母更正（在册冻结稿 §0 的那句要改字）**：可播种对数是 **10 不是 11**——`data/laws_extra.json` 的「劳动法·第三条」正文是占位符 `【请粘贴…】`，导入器自己就拒绝它，所以它不是「可播种原文」。这条是脚本算的，不是我看出来的（`p3_freeze_seed.py` 打印 `dropped`）。
- 合成件 6 只：两只双日期（澄清题）、一只带注入串、两只互相冲突（3 日 vs 5 日）、一只同名误导干扰项。**都挂在《合成X法》这种不存在的法名下**，不借用真实法名——这是对冻结稿 §2 第 11 题的一处改动：原稿要在真实条文正文尾部追加注入串，那会把一只官方原文的 gold 弄脏（§F3「原文零改写」），所以我把注入载体单独成条。
- G-a：`count=16`、真实 `(法名×条号)` 集合与清单**逐字相等**、合成标题集合相等——不是尺寸闸。
- G-c 自查询：16 只各自用自己正文去检索，**16/16 召回自己**。
- G-b：`RERANK_ENABLED=false` 与 `true` 两个独立进程跑同三个探针，`guard_calls` 从 0 变成 >0 ⇒ 开关确实改了路径；但**三只探针的排序一字未变**，原因是 rerank 401（见 §3），不是因为排序本来就这样。

复算：
```
R=/c/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2
C=/c/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010
"$R/candidate-envD/Scripts/python.exe" "$R/model-validation/p3-20261012/p3_transport_guard.py"
"$R/candidate-envD/Scripts/python.exe" "$R/model-validation/p3-20261012/p3_freeze_seed.py" "$C"
"$R/candidate-envD/Scripts/python.exe" "$R/model-validation/p3-20261012/p3_seed.py" "$C"
"$R/candidate-envD/Scripts/python.exe" "$R/model-validation/p3-20261012/p3_gate_gabc.py" "$C" off
"$R/candidate-envD/Scripts/python.exe" "$R/model-validation/p3-20261012/p3_gate_gabc.py" "$C" on
"$R/candidate-envD/Scripts/python.exe" "$R/model-validation/p3-20261012/p3_probe_rerank.py" "$C"   # 会再发一次真实 401，计入 F2 的 rerank 额度
for f in probe-llm probe-llm2 probe-llm3 probe-llm4; do echo "== $f"; cat "$R/model-validation/p3-20261012/logs/$f.json"; done
```

## 3. 四条模型路的读数（只打状态码与 token 数，不打值、不打正文）

| 路 | 冻结值 | 现量 | 定性 |
|---|---|---|---|
| 「默认 LLM」 | `qwen3.5-omni-plus-2026-03-15` @ `api.longcat.chat/openai` | **400 invalid_parameter**（4 次都是这个码）；`GET /models` 200 ⇒ 认证通，该账号只有 2 只模型，此名不在其中。**⚠️ 这一行的框架已在 §7 撤回**：`LLM_MODEL` 是死配置（`settings.py:40` 明文「无任何代码读取」），这个名字其实是 `DEFAULT_ROLES` 的 `vision_flag`；产品真正的文本兜底是 registry 的 `qwen3.7-max-2026-06-08` @ DashScope ⇒ 403 | ~~在册默认模型对本账号不可达~~ ⇒ 死配置键对本账号不可达（不影响 chat 路由） |
| registry（6 只） | `qwen3.7-max-2026-06-08` @ `dashscope.aliyuncs.com/compatible-mode/v1` | **403 `AllocationQuota.FreeTierOnly`** | 账号只有免费额度 ⇒ **只能你动** |
| rerank | `BAAI/bge-reranker-v2-m3` @ `api.siliconflow.cn/v1/rerank` | **401**（两次，产品路径与自己直连各一次） | key 不被接受 ⇒ **只能你动** |
| 可用替代 | `LongCat-2.0` / `LongCat-2.5-Preview` | 200。`2.0` 在 1024 输出预算内 **content 恒空**（`finish_reason=length`，2037 字全花在 `reasoning_content`）；`2.5-Preview` 同预算给出 **403 字正文＋1561 字推理**，但同样 `finish_reason=length` ⇒ 正文可能被截 | 只有 `2.5-Preview` 能答，且受推理预算支配 |

Embedding：`provider=local` ⇒ 走本地 BGE（`rag_chain._build_embeddings()` 在非 aliyun 分支忽略 `EMBEDDING_MODEL`，所以 `.env` 里那个 `qwen3.7-text-embedding` 在现役配置下**不生效**，这是一条容易读错的事实）。BGE 用的是本机已有缓存，副本 sha256 与原缓存逐只相同：`model.safetensors=eccb1d94…`、`config.json=6675c035…`、许可 **mit**。

## 4. 我这轮自己造出来又改掉的两台仪器

1. **guard 计数失真**：`TransportGuard.post()` 里 append 一次，`install()` 之后 httpx 传输层又 append 一次 ⇒ 一次真实发送被记成两次（第一次 rerank 诊断报的 `guard_calls=3` 其实是 2 次发送）。改法：真实腿一律走 `install()`＋裸 `httpx`，让「一次发送＝一次计数」；控制项 `installed_client_passes / installed_unknown_host_refused / installed_budget_refused / uninstall_restores` 已进自检并全 PASS。
2. **零出网不能只靠 socket 守卫**：chromadb 的埋点在 `rag_chain` import 期就发，早于我装守卫的窗口 ⇒ 改成 `ANONYMIZED_TELEMETRY=False`（构造性质），同时保留 `attempts=0` 的实测读数（播种腿实测 0 次）。

## 5. 明确没做、也没声称做了的

- **官方价格轴未查**（F1 第四条）⇒ 没有「元」的读数，只有 tokens；也没有账单校准。开跑真验收前应先补这一条。
- 12 题 gold 未冻结成 `cases-frozen.json`、runner 未写：因为它们的第一行配置就是「代表模型」，你这一句没答之前写死等于我替你裁。
- 图片/语音两类未起步：`LLM_MODELS_JSON` 6 只 registry 全 `caps=["text"]` ⇒ **registry 里没有声明多模态的模型**；冻结的 omni 默认值又是死的。两类都得等你 §0-3 那句（或另指一个供应商账号）。
- Agent 3 run、rerank 3 组、真实 `--write`、现役栈：一律未跑。
- 本轮**没有**碰真实库/向量库/配额库/媒体/备份，没有提交、没有推送。

## 6. 待你回答的那一格（写成可改字的句子）

> D-47：F 的代表模型——(A) 你去控制台开通 DashScope 付费额度，本轮按 在册冻结值 `qwen3.7-max*` 跑文本＋Agent；(B) 不动控制台，我把代表模型重冻为 `LongCat-2.5-Preview`，只跑文本 RAG 12 题，输出预算取满 2048，rerank/图片/语音/Agent 记 BLOCKED；(C) F 本轮再停一次，零花费收口。
> 我的推荐＝**A**；退而求其次选 **B**（B 的代价：读数只代表 LongCat 这一只模型，且推理吃掉近半输出预算，法律结论的「正文完整性」这一维会被预算支配，报告里必须这样写）。

## 7. 就地更正（同一轮第二遍，Owner 裁「同意用长猫跑文本」之后现量）

**撤回我在 §0-2 与 §3 第一行里的框架**。我原先写「在册默认 LLM `qwen3.5-omni-plus-2026-03-15` 对本账号不可达 ⇒ 产品默认路由是死的」。这句错在两点，都由 `p3_freeze_routes.py`（读本机 registry 与 settings，不发包）现量推翻：

| 我错在哪 | 现量 |
|---|---|
| `LLM_MODEL` 根本不是路由来源 | `settings.py:40` 明文：对抗审计 v2 #12 已删该死配置，「无任何代码读取，真正入口是 llm_registry」。那个模型名其实是 `llm_registry.DEFAULT_ROLES` 里 **`vision_flag`** 的模型 |
| 产品文本兜底我读错了端点 | `roles_source=LLM_MODELS_JSON`（6 只，provider 全 `dashscope`）⇒ `registry.get()` = **`qwen3.7-max-2026-06-08` @ `dashscope.aliyuncs.com`**，403 FreeTierOnly。⇒「现役文本路是死的」这句**结论不变、成因换了**：死因是阿里云额度，不是长猫模型名 |

顺带三条新事实（同一台机器现量，写在 `p3_routes_frozen.json`）：

1. `has_modality(vision)=false`、`has_modality(voice)=false` ⇒ 现役 JSON 把 `DEFAULT_ROLES` 的 `vision_flag`/`voice_lt` 挤掉了，产品对带图请求是**显式 501**（能力门正常，不是"能用"）。
2. `DEFAULT_ROLES` 里 `provider:"aliyun"` 的角色实际端点 = `settings.llm_base_url` = **长猫**（`llm_registry.py:452-454` 的 else 分支）⇒ 要"用阿里云多模态"必须写 `provider:"dashscope"` 或显式 `base_url`，否则模型名是阿里云的、请求打到长猫。
3. `_build()` 只在模型名以 `qwen` 开头时发 `thinking:disabled`（`llm_registry.py:386`）⇒ 长猫这类模型拿不到关思考的开关，而本轮预算把输出封顶 2048，正文可被推理挤空（`LongCat-2.0` 实测 content 恒空）。
4. 另：`read_env()` 我原先手写逐行解析 ⇒ 已改成产品同款 `dotenv_values(encoding="utf-8")`；并用真实结构做过对照：同一份 `.env` 存成 GBK 时 dotenv 直接 `UnicodeDecodeError`（⇒ 换 key 时编辑器必须 UTF-8 保存）。

**Owner 10-12 已裁**：文本用长猫（三条前提见正文）；语音/图片继续走阿里云 ⇒ 待他给 `.env` 的两只多模态 entry 与额度。
