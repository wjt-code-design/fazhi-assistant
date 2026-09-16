# 独立验收交接包 —— 法智 T8 改动集（2026-09-10）

> **给复核者**：你的任务是从**原始证据**独立复算下表中的声明，并与"声明值"对照。
> 你**不需要**任何对话上下文——本文件是唯一入口，所有命令可逐字粘贴执行。
> **你不应该信任**：本文作者（实现者）的任何结论性文字。所有"声明值"都应被你的复算推翻或证实。
>
> **判定规则**：复算结果与"预期"一致 ⇒ 该声明成立；不一致 ⇒ **该声明失败**，请在回执中写明
> 命令、实际输出与预期差异。**不要**因为"数字接近"而放行。

---

## §0 复核者须知（先读，避免白跑）

1. **本仓库的事实工作方式是"脏工作树"**：HEAD 长期停在 `ebe82e2`，所有改动**不提交**，
   以「工作树 + 哈希锚定 manifest」为候选。⇒ **禁止** `git add / commit / checkout / stash / reset`。
2. **所有 Python 一律用 `backend/venv/Scripts/python.exe`**（绝对路径），不要用系统 Python。
3. **pytest 的退出码不可信**（本机 safe-delete 钩子会污染它）⇒ 一律读 `--junitxml` 的
   tests/failures/errors/skipped 属性，或用点阵交叉印证。
4. **`pytest --cov` 默认跑不起来**（safe-delete 拦截 coverage 擦除 `.coverage`）⇒ 需加
   `CODEBUDDY_SAFE_DELETE_ENABLED=0` 环境变量（见 §3.4）。
5. 所有声明都**只对其标注的条件成立**；§5 的"已知限制"是声明的一部分，不是脚注。

---

## §1 环境前置（一次性）

```bash
cd /c/Users/33393/Desktop/ai-legal-helper
git rev-parse HEAD          # 预期: ebe82e2bda26185236d50afd780cfb48c7c5e946
git status --short | head   # 预期（2026-09-10 21 时点）: 132 个 tracked 修改（M 开头）+ 大量未跟踪目录
```

> ⚠️ **复核回执勘误（2026-09-10）**：本包初版把此处的 tracked 修改数写成 **16** —— 那是
> 19:40 批量改动**之前**的旧值。19:40 的批量改动（见 §8）使 tracked 修改达 **132**。
> 该计数随工作推进变化，**不是稳定常量**；复核时以"与 manifest 逐哈希一致"（§3.1）为准，
> 不以此计数为准。

Python 解释器统一写法：`./backend/venv/Scripts/python.exe`（下文简称 `$PY`）。

```bash
PY=./backend/venv/Scripts/python.exe
```

---

## §2 待复核声明总表

| # | 声明 | 复算方式 | 预期 | 章节 |
|---|---|---|---|---|
| A1 | 候选锚定与工作树一致（**漂移 0**） | 脚本（§3.1） | drift = 0 | §3.1 |
| A2 | 冻结物**一字未改** | 与 T7 基线逐文件哈希比对（§3.1） | drift = 0 | §3.1 |
| A3 | 全量测试 **924 / 0 failed / 0 errors / 0 skipped** | `pytest tests/ --junitxml` + 解析（§3.2） | 924/0/0/0 | §3.2 |
| A4 | `ruff check .` **通过** | 实跑（§3.3） | "All checks passed!" | §3.3 |
| A5 | `ruff format --check .` **通过**（不得出现 would be reformatted） | 实跑（§3.3） | 无 reformatted 行 | §3.3 |
| A6 | `mypy .` **通过**（修前：配置错误直接中止） | 实跑（§3.3） | "Success: no issues found in 63 source files" | §3.3 |
| A7 | `pytest --cov`：**907 passed / 17 deselected，cov 78.12% ≥ 70**（复核回执勘误：初版误写 901/78.13%，系测试数增加前的旧值；907+17=924 与 A3 自洽） | 实跑 + safe-delete 绕行（§3.4） | 见 §3.4 | §3.4 |
| B1 | **争点总数**：qwen38(T7候选)=18 / qwen36(T7候选)=24 / run-14=32 / run-15=**37** | 直接查 DB（§3.5，含独立 SQL） | 见 §3.5 | §3.5 |
| B2 | **修复环在真实链路被触发并生效** | 服务日志 `issue_decomposition_repair`（§3.6） | detected→repaired 各 ≥1 | §3.6 |
| B3 | **本轮无 `ISSUE_DECOMPOSITION_INVALID`** | run-15 sessions 的错误码分布（§3.5） | 0 次 | §3.5 |

---

## §3 逐项复算步骤

### 3.1 A1 + A2：锚定一致性与冻结物完整性（**只读，零成本**）

```bash
# A1：候选锚定 vs 工作树（脚本会列出"变化/新增/腐化"）
$PY dispatch-output/t2-persistence-20260910/reanchor_t8_manifest.py
# 预期（关键字段，2026-09-10 21 时点）：
#   候选文件 139 个；变化 15 个
#   冻结文件漂移：0  ✅
#   新增候选文件：122  （相对 T7：119 个 tracked + 3 个未跟踪源码）
#   清单腐化（锚定集内但不脏）：0  （无）
#
# ⚠️ **复核回执勘误（§B.1）**：本包初版把"新增候选文件"写成 **0** —— 凭记忆填的错值。
#    算术自证：T7 candidate 键数 = 17，T8 = 139，且 T7 ⊆ T8 ⇒ added = 122 ≠ 0，"新增 0"在数学上不可能。
#    122 的来源 = 2026-09-10 19:40 批量改动（ruff format 重排 133 文件 + 新增 3 个测试/助手文件，见 §8.2）。
#    **A1 的实质声明是"漂移 0 / 变化 15 / 腐化 0"**；"新增 122"是事实描述，不构成失败项。

# A2：冻结物与 T7 基线逐文件比对（不依赖本仓库脚本）
$PY -c "
import json,hashlib,pathlib
t7=json.load(open('dispatch-output/t2-persistence-20260910/candidate-manifest-20260910.json',encoding='utf-8'))
drift=[r for r,e in t7['frozen_files_sha256'].items()
       if hashlib.sha256(pathlib.Path(r).read_bytes()).hexdigest()!=e]
print('冻结漂移 =',len(drift), drift)
"
# 预期: 冻结漂移 = 0 []
```

> ⚠️ **口径陷阱（复核者必读）**：`reanchor_t8_manifest.py` 的输出里
> "变化 15 个" 只列**相对 T7 有变化的候选文件**；"新增候选文件" 列**相对 T7 新出现的文件**。
> 两者都以**更早、独立采集的 T7 manifest** 为基线，不是同义反复。

### 3.2 A3：全量测试（约 3 分钟）

```bash
cd backend
$PY -m pytest tests/ -q --junitxml=../dispatch-output/t2-persistence-20260910/review-junit.xml
$PY -c "
import xml.etree.ElementTree as ET
r=ET.parse('../dispatch-output/t2-persistence-20260910/review-junit.xml').getroot()
s=r if r.tag=='testsuite' else r.find('testsuite')
print('tests=%s failures=%s errors=%s skipped=%s'%(s.get('tests'),s.get('failures'),s.get('errors'),s.get('skipped')))
"
```
**预期**：`tests=924 failures=0 errors=0 skipped=0`。
> ⚠️ **不要用退出码判定**——本机 safe-delete 钩子会把退出码污染成非 0（点阵全过也报 1）。
> ⚠️ 若你的复算数字 ≠ 924：先确认你**没有**新增/删除测试文件；数量本身随代码演进变化，
> **"0 failed" 才是声明**。

### 3.3 A4 + A5 + A6：三道门禁（约 1 分钟）

```bash
cd backend
$PY -m ruff check .            # 预期: All checks passed!
$PY -m ruff format --check .   # 预期: 206 files already formatted（**不得**出现 would be reformatted）
$PY -m mypy .                  # 预期: Success: no issues found in 63 source files
```

> ⚠️ A6 的前提是 `backend/pyproject.toml` 的 mypy 配置包含
> `mypy_path="."` + `explicit_package_bases=true` + `exclude` 含 `venv/` 与 `tests/`。
> 若你看到 "Source file found twice"，说明配置被回退——**报告它**。
>
> **已知限制（A6）**：`backend/pyproject.toml` 对冻结文件 `agent/verifier.py` 用了
> **最窄的** `disable_error_code = ["var-annotated"]` override —— 这是"改冻结物 vs 容忍一条注解缺失"
> 的**显式取舍**（unfreeze 时必须删除该 override 并补注解）。复核者应确认该 override **只**涉及这一条。

### 3.4 A7：coverage 门禁（约 3.5 分钟，需绕行 safe-delete）

```bash
cd backend
CODEBUDDY_SAFE_DELETE_ENABLED=0 PYTEST_ADDOPTS="-m 'not slow'" \
  $PY -m pytest --cov=. --cov-fail-under=70 -q
# 预期尾部:
#   Required test coverage of 70% reached. Total coverage: 78.12%
#   907 passed, 17 deselected, 50 warnings in ~3.5min
```
> ⚠️ **必须带 `CODEBUDDY_SAFE_DELETE_ENABLED=0`**，否则 coverage 在启动时擦除 `.coverage`
> 会被 safe-delete 拦截（`SHFileOperationW 失败: 0x2`）⇒ **跑不起来**。
> **已知限制**：78.12% 是"not slow"子集的覆盖率；`@pytest.mark.slow` 的测试不计入。
> **数值随测试数变化**：passed 数（907）+ deselected（17）= 全量总数（924，见 A3）；若你复算时
> 测试数又变，以 `passed + deselected` 与 A3 自洽为准，**覆盖率 ≥70% 这条门槛才是声明**。

### 3.5 B1 + B3：争点数与错误码（**直接查 DB，不经任何脚本**——这是独立性的关键）

**口径（三条都已在 §6 锁死成测试）**：
- 题号映射 = 会话首条用户消息 ⨯ 冻结题 `initial_question`（**空白归一后全等**）；
- 每臂窗口 = `[该轮 claim 起点, 全部已知轮次中紧邻的下一轮起点)`；
- **不得**用 `agent_runs.id` 排序（UUID 字典序）、**不得**用纯数字上界（DATETIME 亲和性）、
  **不得**按位置切分（预运行失败不落库会错位）。

```bash
cd backend
$PY -c "
import sqlite3, json, re, pathlib
EV=pathlib.Path('../release-evidence/legal-agent-v1-complex-v1-20260907')
def cs(a):
    r=json.loads((EV/f'gate2-run-{a}.claim.json').read_text(encoding='utf-8'))['started_at']
    return r.replace('T',' ').replace('+00:00','').split('.')[0]
raw=json.loads((EV/'frozen-cases-v1.json').read_text(encoding='utf-8'))
cases=raw if isinstance(raw,list) else raw.get('cases',raw)
items=cases.items() if isinstance(cases,dict) else [(c['id'],c) for c in cases]
qmap={re.sub(r'\s+','',c['initial_question']):str(cid) for cid,c in items}
con=sqlite3.connect('app.db'); con.row_factory=sqlite3.Row
for label,arm in (('qwen38(T7候选)','gate5-dev-run-13-qwen38'),
                  ('qwen36(T7候选)','gate5-dev-modelarm-qwen36'),
                  ('run-14(T8)','gate5-dev-run-14-qwen38-t8'),
                  ('run-15(T8收尾)','gate5-dev-run-15-qwen38-t8b')):
    lo=cs(arm)
    hi=[cs(a) for a in ('gate5-dev-run-13-qwen38','gate5-dev-modelarm-qwen36',
                        'gate5-dev-run-14-qwen38-t8','gate5-dev-run-15-qwen38-t8b')
        if cs(a)>lo]
    hi=min(hi) if hi else '2099-12-31 23:59:59'
    tot=0; per={}
    for row in con.execute('SELECT id,conversation_id,state_json FROM agent_runs '
                           'WHERE created_at>=? AND created_at<? ORDER BY rowid',(lo,hi)):
        f=con.execute('SELECT content FROM messages WHERE conversation_id=? AND role=\"user\" '
                      'ORDER BY id LIMIT 1',(row['conversation_id'],)).fetchone()
        cid=qmap.get(re.sub(r'\s+','',f['content'])) if f else None
        if not cid or cid in per: continue
        n=len(json.loads(row['state_json']).get('issues') or [])
        per[cid]=n; tot+=n
    order=[per.get('C%02d'%i) for i in range(1,11)]
    print('%-22s 总数=%2d  逐题=%s'%(label,tot,order))
"
```
**预期**：
```
qwen38(T7候选)         总数=18  逐题=[1, 4, 3, 1, 1, 3, 1, 1, 2, 1]
qwen36(T7候选)         总数=24  逐题=[3, 4, 4, 2, 2, 3, None, 2, 2, 2]
run-14(T8)             总数=32  逐题=[4, 3, 4, 4, 4, None, 1, 5, 3, 4]
run-15(T8收尾)         总数=37  逐题=[5, 5, 2, 2, 4, 5, 2, 4, 4, 4]
```
> ⚠️ `None` = 该题在该轮**预运行失败**（无 agent_run 记录）——这是**事实**，不是缺数据。
> **已知限制**：qwen36 臂的 C06 无记录 ⇒ 该臂分母实际是 9 题（**不得换分母**）。

**B3（错误码分布）**：读 `release-evidence/legal-agent-v1-complex-v1-20260907/gate2-run-<run>-sessions.json` 的
`results.<case>.error_codes`，预期：
- run-14：无码7 / `EVIDENCE_COVERAGE_DEFICIENT`×2 / `ISSUE_DECOMPOSITION_INVALID`×1
- run-15：无码6 / `CROSS_ISSUE_EVIDENCE`×2 / `NON_CANONICAL_CITATION`×1 / `UNSUPPORTED_NUMERIC_TOKEN`×1

### 3.6 B2：修复环在真实链路的证据

**这一条是本包里唯一需要"重跑"才能亲验的**（日志是进程 stdout，不落盘）：

```bash
cd backend
NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost AGENT_ENABLED=true \
  ./venv/Scripts/python.exe -u -m uvicorn main:app --host 127.0.0.1 --port 8001 &
sleep 30 && curl -s --noproxy '*' http://127.0.0.1:8001/healthz   # 预期 db/vector/llm_host 全 true
# 前置哨兵（不花钱）：伪造 resume → 404 = AGENT_ENABLED 生效
# 然后跑一轮（付费）：
NO_PROXY=127.0.0.1,localhost ./venv/Scripts/python.exe -u scripts/gate2_runner.py \
  --run review-repair-verify --case C08 --base-url http://127.0.0.1:8001
# 验收点（服务 stdout / uvicorn 日志）：
#   出现 msg="issue_decomposition_repair" 且 agent_repair_stage ∈ {detected, repaired}
```
> **替代（不重跑）**：上一轮 run-15 的运行日志**未落盘**，但其对照组（run-13-qwen38，同模型同题集）
> 在 18:42:53/18:43:01 产生的两条 `issue_decomposition_repair`（detected→repaired，issues=1→2、缺口 2→0）
> 已由实现者观察到并记录在 handoff §12.13。**复核者可要求实现者重跑一轮取证，或自行为之。**

---

## §4 复核者最容易踩的 5 个坑（都真实坑过实现者本人）

| # | 坑 | 正确做法 |
|---|---|---|
| 1 | `agent_runs.id` 是 **UUID 字符串** ⇒ `ORDER BY id` 是字典序、与插入顺序无关 | 用 `rowid` 或 `created_at` 排序 |
| 2 | `created_at` 声明 **DATETIME**（NUMERIC 亲和性）⇒ 纯数字上界 `'9999'` 恒 0 行 | 上界用格式一致的时间字符串 |
| 3 | **预运行失败不产生 agent_run 记录** ⇒ 位置切分错位 | 题号按「会话首条用户消息 ⨯ 题目文本」匹配 |
| 4 | pytest **退出码被污染**（safe-delete 钩子） | 只信 `--junitxml` 的机器可读计数 |
| 5 | `pytest --cov` 默认**跑不起来**（safe-delete） | `CODEBUDDY_SAFE_DELETE_ENABLED=0` |

> 这五条已固化成可执行的测试：`backend/tests/test_run_evidence.py`（7 项）。
> 复核者可直接跑它验证本表：`$PY -m pytest tests/test_run_evidence.py -v`。

---

## §5 已知限制与"不得声称"

1. **`full_closure` = 0/10**（run-14 与 run-15 均如此）——这是**实测**，不是缺陷修复失败：
   它被"终稿缺要件法条"钉死，属 **writer 引用轴**（执行书 F5/T8），**不在本轮改动射程**。
2. **本轮（T8）只证明了"分解覆盖改善 + 无回归"**，**未证明** `full_closure` 或任何端到端指标改善
   （run-14: completed 7/10 → run-15: 6/10，单轮 n=10 无法判定方向）。
3. **"5 争点需 19 步"是实测**（**run-14 C08**；run-15 的 C01/C02 亦为 5 争点/19 步/completed。
   复核回执 §E.6 勘误：初版误标为 run-15 C08——run-15 的 C08 实为 4 争点/16 步/failed），
   但"8 争点约需 26 步"是**线性外推**，未实测。
4. **非逐字引用修复路径未被真实链路触发**（本轮 `non_verbatim` 计数全程 0）——只有离线证据。
5. **独立验收缺位**（执行书 T7 硬前置）仍未补——本包就是为此准备的，但**验收行为本身**须由复核者完成。
6. `run-14` 的 C06 与 `modelarm-qwen36` 的 C07 均**预运行失败**，其分母为 9 题——**不得换分母**。

---

## §6 若复算与声明不一致

1. **逐条记录**：命令、预期、实际输出（全文）。
2. **判定该声明失败**——不要试图"解释掉"差异。
3. 回传差异清单；实现者有义务给出**根因**（并为此负责），而不是给"可能是波动"这类无证据解释。
4. 若差异源于**本包的口径错误**（例如上界写法、窗口界定），请同样记录——本包的口径也曾出错并被修正
   （见 §4），口径错误与实现错误同等重要。

---

## §7 附：本包未覆盖 / 需要额外授权的事项

- **LongCat 域**：Owner 已暂停使用；`modelarm-longcat` 臂仅 4/10（PARTIAL）。
- **付费轮的重复**：任何重跑都会产生新的付费调用（LongCat 单请求最慢 ~960s）。
- **§5.5 的"真第三方"验收**：本包的复核者若为另一会话，仍属"替代性独立"（同一工具链、同一仓库），
  应在该轮记录里如实标注。

---

## §8 复核回执处置记录（2026-09-10 21 时，回执 = `独立验收复核回执-20260910.md`）

> 复核回执判定：**10 项声明中 6 项成立、2 项成立但有数值偏差、1 项失败（局部）、1 项悬置**，
> 并另报 1 项超范围风险（§D.1）。以下逐条处置，**每条都注明"接受/部分接受/已核实更正"**。

### 8.1 回执判定的接受情况

| 回执发现 | 处置 | 状态 |
|---|---|---|
| **§B.1 A1"新增 0"失败（实测 122）** | **完全接受**。算术自证（17+122=139）无可辩驳；"新增 0"是本包**凭记忆填写的错值**，不是复算值。§3.1 预期已改为 122，并注明来源（19:40 批量改动）。**实质声明"漂移 0/变化 15/腐化 0"经复核者确认成立** | 已修正 |
| **§B.2 A7 数值不符（901→907 / 78.13→78.12）** | **完全接受**。901 采集于测试数增加**之前**（901+17=918=当时的全量数）；回执指出"901+17≠924"的内部矛盾正确。§2/§3.4 已改为 907/78.12% | 已修正 |
| **§B.3 A5 文件数偏差（204→206）** | **接受**。同源（19:40 后新增 2 个未跟踪测试文件）。§3.3 已改为 206 | 已修正 |
| **§C.1 B2 悬置** | **接受**。复核者正确指出：本包 §3.6 的"替代方案"（引用实现者自己观察到的 run-13 日志）**不满足独立性**。B2 在授权付费重跑取证前**保持悬置**，不得声称"真实链路已验证" | 已标注 |
| **§C.2 full_closure 无法复算** | **完全接受，已修复**。根因：judge 输出只进了实现者的终端，**从未落盘**。已补落盘 4 轮 judge 产物（见 8.3） | 已闭合 |
| **§E.6 §5.3 轮次标注错误** | **完全接受**。"5 争点/19 步/completed"属 **run-14 C08**（run-15 的 C08 = 4 争点/16 步/failed）。§5.3 已更正 | 已修正 |

### 8.2 §D.1 裁决（Python 版本）—— 回执最重要的一条

**回执正确**：19:40 批量改动中的 ruff `UP017` 自动修复**产生了语义改动**（`auth.py`：
`UTC = timezone.utc` → `from datetime import UTC`），**不是纯格式化**；且 `auth.py` 的旧注释
自称"服务器为 3.10"，与代码（`datetime.UTC` 需 3.11+）自相矛盾 ⇒ 若部署真是 3.10 会在导入期崩。

**实现者核查（引用部署证据，非口头）**：
- `backend/Dockerfile`：`FROM python:3.11-slim`（HEAD 即如此，非本轮改动）
- `DEPLOYMENT.md` §2.1：「后端（Python 3.11）」
- 本机 venv：Python 3.11.0

**裁决**：部署为 3.11 ⇒ `datetime.UTC` **可用，不会生产崩溃**；**过期的是注释**
（且该注释在 HEAD 就已过期——Dockerfile 早已是 3.11）。处置：`auth.py` 注释据实更正、
删除 no-op 别名 `UTC = UTC`；`gate2_runner.py` 仅 import、无矛盾注释，不动。

**教训（比修复本身更重要）**：① 本包把 19:40 批量改动称作"纯格式化"是**错的**——其中含语义修复
（UP017 ×2），`git diff -w` 后仍有 130 文件/4464 行实质改动；② **自动修复批次必须人工过语义 diff**，
尤其当 `target-version` 与**实际部署版本**可能不一致时；③ `auth.py` 的陈旧注释在自动修复前就存在，
却直到被独立复核才暴露——**过期注释是潜伏的错误诱饵**。

### 8.3 补落盘的 judge 产物（闭合 §C.2）

```
release-evidence/legal-agent-v1-complex-v1-20260907/gate2-run-gate5-dev-run-13-qwen38-judge.txt
release-evidence/legal-agent-v1-complex-v1-20260907/gate2-run-gate5-dev-modelarm-qwen36-judge.txt
release-evidence/legal-agent-v1-complex-v1-20260907/gate2-run-gate5-dev-run-14-qwen38-t8-judge.txt
release-evidence/legal-agent-v1-complex-v1-20260907/gate2-run-gate5-dev-run-15-qwen38-t8b-judge.txt
```
复核命令（零成本，确定性脚本）：`$PY scripts/gate5_judge.py <sessions.json路径>`
**结果与声明一致**：mechanical 7 / 4 / 7 / 6；**full_closure 四轮全部 0/10**。
§5.1 的"0/10"自此**可独立复算**。

### 8.4 复核回执给实现者的正向确认（留档）

- A2/A3/A4/A6/B1/B3 六项经**不同实现路径**复算成立（B1 用了单条 SQL CTE + `ROW_NUMBER()`，
  与验收包的 Python 循环完全不同路径，四个总数/逐题数组/None 位置/分母**全部精确一致**）。
- 复核者自建 11 个只读脚本、全程未跑会覆盖被复核证据的脚本、未触发付费调用、未做 git 写操作。
- 复核者对 §5.2 的"不得声称方向"提供了**增量证据**：30 条记录中 steps↔issues 严格线性（1→9…5→19），
  印证"8 争点逼近 29 步上限"的边界提醒。

### 8.5 仍开放的事项

- **B2**：需授权付费重跑一轮（建议用 C08：预登记 `issue_decomposition_repair` 的
  detected→repaired 出现即为成立）。
- **§5.5 真第三方验收**：本回执自评属"替代性独立"（同一工具链/仓库/另一会话）——如实标注，
  不冒充完整独立。
- **writer 引用轴**（`full_closure` 唯一的墙）：仍待立项分析。
