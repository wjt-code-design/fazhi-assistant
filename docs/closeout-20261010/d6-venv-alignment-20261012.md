# D-6 / P2：宿主 venv 对齐（2026-10-12）

**一句话结论**：候选环境 `backend/venv-new` 已建好并**四道验证全绿**（能过产品门），但按执行书 §G 的原文与 Owner 裁定 **①「等主仓整合后再换」**，本轮**停在切换前**——`backend/venv` 一字未动，换名留到 I 完成之后。

## 0. 三行汇总

1. **现量**：宿主 `backend/venv`（7 月建的）对**落地后的新清单**偏离 **12 条**（低于下限 11 + 高于上限 1），`pip check` 另有 **2 条既有红**（starlette）。票面原写的"6 条"是按**迁移前**那份清单数的——目标变了，不是数错。
2. **建了什么**：`backend/venv-new`（基座＝系统 Python 3.11.0，与旧环境同基座）。建造用仓库 `Dockerfile:58` 的两发形状装 CPU torch（阿里云 find-links → 官方 find-links 回落），再装候选 `requirements.txt` 与 `requirements-dev.txt`+pre-commit。
3. **怎么停的**：执行书 §G 原文——「若依赖兼容修复只在候选、**主工作区尚无安全整合条件，则先完成 I 的工程交付，G 暂停**」。现在正是这个形状（新栈只在候选分支，主仓 `requirements.txt` 仍是旧清单），故不换名、不移动、不删旧目录。

## 1. 现量读数（开工时）

| 检查 | 读数 | 证据 |
|---|---|---|
| 旧环境 freeze | 181 行 | `p2-d6-20261012/d6-venv-freeze-before.txt` |
| `pip check` | 2 条红：`fastapi 0.110.3` 要 `starlette>=0.37.2,<0.38`；`sse-starlette 3.4.8` 要 `>=0.49.1`；现装 `0.36.3` | 同上命令输出 |
| 对账尺（vs 新清单） | 声明 24 条，符合 12、**偏离 12**：`fastapi 0.110.3`↓、`uvicorn 0.52.1`↑、`langchain-{core,openai,chroma,huggingface,text-splitters}` 五只↓、`sentence-transformers 2.7.0`↓、`sqlalchemy 2.0.51`↓、`pypdf 6.14.2`↓、`torch 2.6.0+cpu`↓、`openai 1.109.1`↓ | `evidence/venv_vs_requirements_axis.py` |

## 2. `venv-new` 的建造与四道验证

| 腿 | 读数 | 证据 |
|---|---|---|
| 建造 | `TORCH_LEG1_RC=0`（阿里云一发成功）、`REQ_RC=0`、`DEV_RC=0`、`INVALID_WHEEL_COUNT=0`、freeze **171 行** | `p2-d6-20261012/venv-new-build2.log`、`venv-new-freeze.txt` |
| ① `pip check` | **No broken requirements found**（rc=0） | 同上 |
| ② 对账尺 | 声明 24 条**全符合、偏离 0** | `venv_vs_requirements_axis.py` |
| ③ 核心导入冒烟 | OK：`torch 2.13.0+cpu`（`cuda=None`）、ST 6.1.0、fastapi 0.141.1、uvicorn **0.27.1**（从越上限的 0.52.1 降回）、sqlalchemy 2.1.4 | 本轮命令输出 |
| ④ 产品门（纯发布物树，解释器＝venv-new） | **2030 passed / 0 failed / 10 skipped / 18 deselected，cov 86.57%，rc=0**；junit `tests=2040 failures=0 errors=0 skipped=10`；树前后 2726→2727（+1＝测试自建的 `chroma.sqlite3`） | `p2-d6-20261012/p2-venv-new-gate.log` / `.xml` |

| ⑤ torch wheel 与官方 sha256 | **MATCH**（细节见 §4 第 1 条） | `p2-venv-new-gate.log` |
关键版本与 envD（P1 的干净安装）**逐版相同**：core 1.6.9 / lc-openai 1.7.0 / lc-chroma 0.2.3 / openai SDK 2.54.0 / chromadb 0.4.24 / numpy 1.26.4 / fastapi 0.141.1 / sqlalchemy 2.1.4 / pypdf 6.19.0 / ST 6.1.0 / transformers 5.19.0。

## 3. 为什么不换名（§G 原文 + Owner ①）

- §G 原文：「确认待恢复服务实际使用的**源码版本**与新依赖兼容。若依赖兼容修复只在候选、主工作区尚无安全整合条件，则先完成 I 的工程交付，G 暂停；主工作区有他人差异时不自动 pull/reset 或整树覆盖。」
- 现况：主工作区（主仓）`requirements.txt` 仍是**旧清单**、21 只 tracked 脏；新栈的所有权在候选分支。若此时把 `backend/venv` 换名，主仓那份声明与实际装的东西将对不上，且**"现用解释器归属"未能唯一证实**（§G 另一条要求）。
- Owner 2026-10-12 裁定 **①**「等主仓整合后再换」⇒ 本轮不换名、不动旧目录。

## 4. 已知限制（不写成通过）

1. **torch wheel 的镜像哈希比对 —— 已闭合**：任务书 §C 要求「官方源或**可对官方 SHA256 的镜像**」。阿里云 `mirrors.aliyun.com/pytorch-wheels/cpu/` 页面本身**不提供哈希**，故改为拿**实际下载的那枚 wheel** 算 sha256 与官方索引值逐字比对：`torch-2.13.0+cpu-cp311-cp311-win_amd64.whl`（121,892,056 B）的 sha256 ＝ `10717d8b3b67c45a4788bf7ffc0bab1ea1e5ebbedd24466be6100102d141fac1` ＝ 官方索引值 ⇒ **VERDICT=MATCH**（证据 `p2-d6-20261012/p2-venv-new-gate.log` 尾部；wheel 留存 `D:/fazhi-big/torch-wheel/`，部署离线安装可复用）。**镜像源作废条件未触发**。
2. 建造第一版出现过 **两个来源同报 "wheel is invalid"**（torch 与 fastapi）——单包探针证明下载路径本身正常 ⇒ 判为**下载被截断**；第二版 `INVALID_WHEEL_COUNT=0` 佐证。此现象会偶发，重跑即可。
3. 环境只在本机（Windows/win_amd64）成立；生产是 Linux 镜像（`+cpu` 为 manylinux 轮），**两边不是同一个二进制对象**，不能互相当证据。
4. 本轮**没有**跑 `slow`/`real_kb`、没有碰真实库、没有动容器与 compose 栈。
5. C 盘余量在建造期间从 18G 降到 15G（venv-new 约 3G + 下载解包）；后续大件已改走 `D:/fazhi-big/`（Owner 指示）。

## 5. 将来换名与回退（本轮未执行，供 I 完成后照抄）

```bash
M=C:/Users/33393/Desktop/ai-legal-helper
# 换名前：记录两边的 freeze 与 python 版本作归属证据
"$M/backend/venv/Scripts/python.exe" -V; "$M/backend/venv-new/Scripts/python.exe" -V
# 换名（同一盘内，秒级，可逆）
mv "$M/backend/venv" "$M/backend/venv-old-20261012"
mv "$M/backend/venv-new" "$M/backend/venv"
# 回退（把名字换回来即可，两个目录都还在）
mv "$M/backend/venv" "$M/backend/venv-new"
mv "$M/backend/venv-old-20261012" "$M/backend/venv"
```

回退**实测条件**：换名后至少跑一次 `pip check` + 核心导入 + 一条全量门；任一条红即按上面第二段换回。旧目录在确认新环境稳定前**不删**。

## 6. 待裁台账（每条一词可答 + 推荐）

| 编号 | 一句话 | 推荐 | 你可以答 |
|---|---|---|---|
| P2-收尾 | 换名时机 | **等 I（主仓整合）完成后换**（已裁 ①），换时按 §5 三段命令，旧目录保留到新环境稳定 | 「到时换」/「现在改主意了要换」 |
| P2-清理 | 旧的 `venv-old-*` 何时删 | 新环境稳定跑过两轮门之后再删（删前记 freeze） | 「稳定后删」/「一直留着」 |

## 7. 证据指针（均在运行根 `p2-d6-20261012/`，除非另行注明）

- `d6-venv-freeze-before.txt`（旧环境 181 行 freeze）
- `venv-new-build2.log`（建造日志：两发 torch、`INVALID_WHEEL_COUNT`、freeze 171）
- `venv-new-freeze.txt`
- `p2-venv-new-gate.log` / `p2-venv-new-gate.xml`（产品门 2030/86.57%、junit 2040、torch 哈希比对）
- 对账尺：`evidence/venv_vs_requirements_axis.py`（运行根 `evidence/`）
