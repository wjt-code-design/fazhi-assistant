# F 前置现量（未发起任何模型调用 · 零花费 · 2026-10-10）

状态：**F 仍 BLOCKED**。这份文件只交付三件事：① 本机配置可得性（按变量名，不取值）；
② 若强行开跑会踩到哪条禁令；③ 两处活的文档/代码漂移。所有指针给成命令。

候选：`C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010`，`HEAD=3f605de`。

## 1. F1 第 1 条的可得性读数（只报键名存在性）

判据：**执行助手能否从"已配置的进程环境变量"拿到所需配置**。跑的是
`os.environ` 的键名存在性检查（脚本形态见 §4），**没有打开 `.env`、没有读任何值、没有打印任何值**。

| 变量名 | 本机进程环境 | 备注 |
|---|---|---|
| `DASHSCOPE_API_KEY` | **PRESENT** | 只报存在性；是否有效未验（验它=就地认证，属 F 开跑时的事） |
| `RERANK_API_KEY` | **PRESENT** | 同上 |
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` / `LLM_MODELS_JSON` | absent | 主回答路由与多模型覆盖全靠这几根 |
| `ZHIPU_API_KEY` / `ZHIPU_BASE_URL` | absent | 注意 `settings.py:43` 的 `zhipu_base_url` **自带官方默认值** |
| `DASHSCOPE_BASE_URL` | absent | `settings.py:48` 自带官方默认值 |
| `RERANK_BASE_URL` / `RERANK_MODEL` | absent | `settings.py:205` 自带官方默认值；**`rerank_native_url`（`:209`）是第六条出网轴，最容易被漏** |
| `EMBEDDING_API_KEY` / `EMBEDDING_BASE_URL` / `EMBEDDING_MODEL` / `EMBEDDING_PROVIDER` | absent | `embedding_base_url:194` 与 `embedding_model:195` 自带阿里云默认值；provider 默认 `local`（离线，免费） |
| `JWT_SECRET` / `ADMIN_PASSWORD` / `DATABASE_URL` / `CHROMA_DIR` / `QUOTA_DB` / `HF_HUB_OFFLINE` / `RERANK_ENABLED` | absent | 这几根是**隔离出口**，F 开跑时由我自己设假值，不需要 Owner 配 |

⇒ **需要 Owner 在本机补的只有上面 absent 的模型侧变量**；隔离侧我自己解决。

## 2. 为什么"现在就开跑"会直接违反执行书 §F1

`llm_models_json` 为空 ⇒ 回落 `llm_registry.DEFAULT_ROLES` 内置表（`settings.py:188` 的注释明写这个回落）。
执行书 §F1 原文禁令：**"不能把 registry 默认第一项、默认 rerank URL 或旧 10-02 路由当本轮实配"**。
所以现在开跑 = 用一张**没人确认过的默认表**当"本轮实配"，正撞那条禁令。
`RERANK_BASE_URL` 缺会同撞"默认 rerank URL"那半句。

**图片/语音这两类不是"无路由"**（我中途一次读数把 `DEFAULT_ROLES` 按 `NR 42..210` 的窗口采样数成"18 条全 text"，**错了**；
全表 `NR 44..298` 现量：**27 条 = 19 text / 3 vision / 5 voice**，能力含 `["text","vision"]`、`["speech","asr"]`、`["speech","tts"]`）。
正确的说法是：**路由存在，但只存在于默认表里** ⇒ 仍属未实配，且 `pick(modality, tier)` 之外还要确认 `tier` 语义（现量 27 条**全部 `tier="flag"`**）。

## 3. 两处活的文档/代码漂移（建议登记成新 B 项，本会话未改码）

| 处 | 声称 | 现量 |
|---|---|---|
| `backend/llm_registry.py:3` docstring | "代表模型 **8 个**（按 modality × tier 分层）" | `DEFAULT_ROLES`（`:44..298`）= **27 条** |
| `backend/settings.py:188` 注释 | "留空则用 llm_registry 内置的 **8** 代表模型默认表" | 同上，27 条 |

这条不是口味：F1 要求"每类从当前有效配置选一个代表模型并**冻结** provider/model/endpoint/版本"，
而文档给的分母（8）与真值（27）不符 ⇒ 照着文档做冻结会漏掉 vision/voice 那 8 条里的候选。

## 4. 复算（零出网、零花费、只读）

```bash
R=/c/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2
C=/c/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010
# 键名存在性（不打印值）——把你要验的名字加进这个列表
"$R/candidate-envB/Scripts/python.exe" -c "import os;print({n:(n in os.environ) for n in ['DASHSCOPE_API_KEY','RERANK_API_KEY','LLM_API_KEY','LLM_MODELS_JSON','RERANK_BASE_URL','EMBEDDING_PROVIDER']})"
# 默认表条数与模态（**区间要钉全**：先定位边界再取边界内）
grep -n "^DEFAULT_ROLES" "$C/backend/llm_registry.py"      # 现量 :44
awk '/^DEFAULT_ROLES: /,/^]/' "$C/backend/llm_registry.py" | grep -c '"model":'      # 期望 27
awk '/^DEFAULT_ROLES: /,/^]/' "$C/backend/llm_registry.py" | grep '"modality"' | sort | uniq -c   # 19/3/5
grep -n "8 个\|8 代表模型" "$C/backend/llm_registry.py" "$C/backend/settings.py"      # 两处漂移
grep -n "rerank_native_url" "$C/backend/settings.py"       # 第六条出网轴 :209
```

## 5. 我给 Owner 的一句话决定

**F 本轮不开跑**（默认表未确认 ⇒ 一开就跑进禁令），改做两件零花费的事：
① 我把 F2 那张表的病例与 gold 写成**冻结稿**（不发起任何调用），等你裁"允许从 `DEFAULT_ROLES` 里点名 5 只代表模型"或"本机补 `LLM_MODELS_JSON`"；
② §3 两处漂移登记成新 B 项，随下一轮同族票一起修（本会话不动码）。
你若说"就按默认表点名冻结"，我就把 27 条里的候选按 modality 摊给你选，仍然零调用。
