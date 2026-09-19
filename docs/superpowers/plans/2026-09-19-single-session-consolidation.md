# 单会话合并执行计划（两份交接 + 本会话残余）2026-09-19

> **For agentic workers:** 逐 task 执行，每步 checkbox 打勾；每个 Task 收口跑一次 show-your-work 五问。
> 本会话现为**唯一执行者**（Owner 02:4x 决定）⇒ 原先"因并行而不能动"的约束按新前提重估。

**Goal:** 把 R15/git 修复票（T1/T2/T3/T4）与本会话遗留（G3-a、文档订正、现场收口）按风险从低到高做完。

**Architecture:** 先做**安全与现场**（密钥扫描 → .gitignore 堵漏 → 历史洞非破坏式排查），
再做**代码**（备份面补全 → 快车道版本判定），最后做**备份刷新与文档订正**（必须压在所有提交之后）。

**Tech Stack:** Python 3 / FastAPI / pytest / chromadb 0.4.24 / git plumbing / Git Bash。

## Global Constraints（逐条来自实测，不是偏好）

1. 解释器只用 `backend/venv/Scripts/python.exe`；pytest 的 `--basetemp` 必须在 `backend/` **外**。
2. `.git/hooks/pre-commit` **不存在** ⇒ 每次提交前手跑
   `backend/venv/Scripts/pre-commit.exe run --files <显式路径>` 并回报 rc；提交后 `git show --stat HEAD` 复核。
3. 提交只 `git add` **显式路径**；禁 `git add -A` / `.` / `git stash` / `reset --hard` / `git clean` / `git gc`。
4. **不推远端、不部署**（origin 当前公开可读）；**不重写 master**。
5. 禁碰冻结资产与冻结判据：`state_machine.py` / `prompts.py` / `gate5_judge.py`、
   `evals/frozen-cases-v2.json`、`evals/probe-results.json`、`*-sessions.json`、
   `gate2_runner.py`（其 sha256 已钉为 `ae2e412059ed68ac1514c62727cee61c50b8a2d6fe7e38a77c7e05631847e295`）；
   不改任何既有 feature flag 的默认值。
6. 付费真实模型调用**不在本计划内**（Task T2 只做代码 + 离线测试；三臂需 Owner 另给额度）。
7. 进度只往两处写：`docs/execution-plan-entity-precision-20260917.md`（就地追加）+
   `.workbuddy/memory/2026-09-19.md`（`cat >>` 追加）。
8. 引用一律**按符号名锚定**，行号只当快照；文档里的绝对数字（28 笔 / 97 个 / 44MB）动手前重测。

---

## Task S1: 递归密钥扫描（R1 票 T1-c，安全最高优先）

**Files:** 只读全仓；输出脚本 `dispatch-output/secrets-hygiene-20260919/scan_trace_shape.py`（新建）
**Interfaces:** Consumes 无；Produces `scan-result.json`（**只含形状字段**：文件、命中数、长度、字符集、是否含数字）

- [ ] **Step 1** 写扫描器：`os.walk` 递归（含目录内部，纠正原扫描未加 `-r` 的下界），
  对未跟踪 + 已跟踪留痕文件跑三条正则（`sk-[A-Za-z0-9]{20,}`、`AKIA[0-9A-Z]{16}`、`eyJ[A-Za-z0-9_-]{20,}\.`），
  **命中只记录形状，绝不 print 值本身**（防值进终端记录/日志）。

```python
PATTERNS = {
    "openai_style_sk": re.compile(rb"sk-[A-Za-z0-9]{20,}"),
    "aws_akid": re.compile(rb"AKIA[0-9A-Z]{16}"),
    "jwt_like": re.compile(rb"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{5,}"),
}
def shape(m: bytes) -> dict:  # 只出形状，永不出值
    return {"len": len(m), "has_digit": any(c in b"0123456789" for c in m),
            "charset": "".join(sorted({chr(c) for c in m if chr(c).isalpha()}))[:8],
            "sha256_12": hashlib.sha256(m).hexdigest()[:12]}
```

- [ ] **Step 2** 跳过 `backend/venv/`、`.git/`、`chroma_db/`、`node_modules/`、`.next/`（依赖树与二进制，不是留痕）。
- [ ] **Step 3** 跑，回报：命中文件数、每个文件的命中数与形状、与"1 个命中（下界）"这一旧结论的差异。
**DoD:** 一条命令 + rc + 命中清单（形状级）；若发现真形态密钥在**受跟踪**文件里 ⇒ **立即停手上报**，不自行删改。

## Task S2: `.gitignore` 加根目录留痕规则 `/_*`（R1 票 T3）

**Files:** Modify `.gitignore`（末尾追加一节，不动 `*.log` / `*.bak` / `*.env` 三条防泄密规则）
**Interfaces:** Produces 判据两条（见 Step 2），供任何后续会话复验。

- [ ] **Step 1 先照现状**（改动前后各一次，用来点名"哪些条目会从 status 消失"）：

```bash
git status --porcelain --untracked-files=all | grep '^??' | wc -l   # 记为 N_before
git ls-files "_*" | wc -l                                           # 期望 0：根目录无已跟踪 _* 文件
```

- [ ] **Step 2** 追加规则 `/_*`（**必须带前导斜杠**：`_*` 无前导斜杠会匹配任意层级，
  实测会命中 9 个已跟踪的 `__init__.py` / `_r15_tripwire_probe.py` 一类探针）。两条判据都要过：

```bash
git check-ignore -q _probe.txt                                && echo RC0=0   # 期望 rc=0（被忽略）
git check-ignore -q backend/tests/_r15_tripwire_probe.py; echo RC1=$?         # 期望 rc=1（不被忽略）
```

- [ ] **Step 3** 复测 `N_after`，把"从视野消失的根目录留痕条目数"写进报告（该规则的本意就是让它们不被 add）。
**DoD:** 两条 check-ignore 判据 + 已跟踪文件零影响的实测（`git ls-files "_*"` = 0）+ 一次 `git status` 差异说明。
**风险标注:** 这条规则让别人的未跟踪留痕**不再出现在 `git status`** ⇒ 报告里点名条目数，别静默。

## Task S3: 历史洞的非破坏式排查（R1 票 T1-b 的**改道**）

**为什么改道**：票面让我"删掉 `tmp_pack_lu4Uc1`"。但 `0263bd5`（缺失的父提交）至今没有任何替代获取路径，
而**中断的 fetch 残留正是唯一可能装着它的容器**；删掉 = 不可逆地放弃最后的线索。
⇒ 本票只做**只读探测**，不做删除；探测结论交回 Owner 决定去留（红线 R3 也说别清 garbage，两者一致）。

- [ ] **Step 1** 复制两份 tmp pack 到盘外工作区（**不动原件**）：
  `cp .git/objects/pack/tmp_pack_* /c/Users/33393/Desktop/fazhi-tmppack-probe-20260919/`
- [ ] **Step 2** 在副本上 `git index-pack`，再用 `git verify-pack -v <idx> | grep -E "^0263bd5|^<40位>"` 查目标对象；
  同时 `git cat-file -t 0263bd5…`（在临时环境）确认能否解析。
- [ ] **Step 3** 分支：
  - **命中** ⇒ 写清"该 pack 可 `git index-pack` 后放入 live 使 `0263bd5` 可读、洞可补"，**停手报 Owner**
    （把它放进 `.git/objects/pack` 属仓库级不可逆动作，且会改变 `fsck`/`bundle` 行为，需 Owner 点头）；
  - **未命中** ⇒ 记录"两个 tmp pack 均不含缺失对象"，则 T1-b 的删除前提（确认无价值）才成立，
    仍由 Owner 决定删不删。
**DoD:** 每个 tmp pack 的对象清单摘要（能否解析、含不含 `0263bd5`/`04463121`）+ 原件 mtime 前后不变。

## Task S4: 备份面补全（本会话 G3-a，TDD）

**Files:** Modify `backend/scripts/backup_data.py`；Test `backend/tests/test_backup_data.py`
**Interfaces:** Consumes `backup_data.main(argv)` 既有 CLI；Produces 备份包内新增
`quota_used.sqlite`、`data_app.db`、`media/`（目录名固定，供 `restore_drill.py` 后续消费）

- [ ] **Step 1 先红**：在 `test_backup_data.py` 追加一条断言"备份包内应含 `quota_used.sqlite`"，
  跑 `pytest tests/test_backup_data.py -q` ⇒ 期望 **FAIL**（当前实现不备 quota）。红因写进留痕。
- [ ] **Step 2 实现**：新增 `backup_extra(out)` —— 用 `sqlite3` backup API 备 `data/quota_used.sqlite`
  与 `data/app.db`（存在才备，缺则打印 `[Extra] 跳过`），`media/` 用 `copytree`；**不新增 flag、不改默认值**。
- [ ] **Step 3 转绿** + **mutation 两道**：(a) 摘掉 quota 备份 ⇒ 新测试必须红；(b) 把 `data/app.db` 路径写错成
  `app.db` ⇒ 必须红（证明它锚的是**具体文件**而不是"多一个文件"）。
- [ ] **Step 4** `--basetemp` 在系统 temp 跑定向 + `run_gate_full.py <标签>` 全量；pre-commit 手跑。
**DoD:** 红→绿留痕 + 两道 mutation 目录 + 一次真备份跑通（产物清单含三件新增）。

## Task S5: 快车道版本判定最小可用（R1 票 T2，只做代码 + 离线测试）

**Files:** Modify `backend/main.py`（快车道出口）、`backend/settings.py`（新增 `fast_path_law_version_check: bool = False`）
**Test:** 新建 `backend/tests/test_r15_fastpath_tripwire.py`
**Interfaces:** Consumes `limitation_calc.law_version_crosses_watershed(claim_text, fact_texts, law_as_of)`（已存在，纯函数）
与 `request_bootstrap.RequestBootstrap.law_as_of`；Produces 快车道在 `clean_answer` 之后、落库之前的判定门。

- [ ] **Step 1** 复量入口符号是否还在：`grep -n "def fallback_to_fast_path\|agent_enabled" backend/main.py`、
  `grep -n "law_version_crosses_watershed" backend/agent/limitation_calc.py`、
  `grep -n "law_as_of" backend/request_bootstrap.py`。**任一不符 ⇒ 停手**（票面行号是快照）。
- [ ] **Step 2 先红**：写测试断言"开关开 + 答案文本引用了跨分水岭的期间法 ⇒ 返回降级口径"，
  默认开关关 ⇒ 现有行为逐字不变（这条也要有测试：`=False` 时输出与门不存在时**完全相同**）。
- [ ] **Step 3 实现最小门**（方案 Q，票面建议）：只在 `AGENT_ENABLED=False` 分支生效，命中落日志时
  **必须带被判定原文**（沿用 `5afc8d0` 的可归因教训）。
- [ ] **Step 4 mutation ≥2** + 两态（`AGENT_ENABLED` True/False）都跑；对照样本用
  `evals/watershed-cases-r15.json`（**不进冻结集**）做**离线**断言（不调模型）。
- [ ] **Step 5** 全量门禁 + pre-commit + 提交。
**DoD:** 红→绿 + mutation 记录 + "默认关 ⇒ 行为零变化"的实证（同输入前后输出逐字比对）。
**明确不做：** 付费三臂、把开关设默认开、动 agent 路径任何行为。

## Task S6: 现场收口（必须最后做）

- [ ] **S6-a** 刷新救援仓到**当时** tip（R1 票 T1-a）：`git fast-export master | git fast-import`
  到新目录 → `bundle create` → `bundle verify` → 从 bundle `clone` → 克隆内 `git fsck` 零输出 →
  tree 哈希逐一对应全等。**回报每一项 rc。**
- [ ] **S6-b** 订正本会话文档里已被外部事实推翻的引用：
  ① `Desktop/fazhi-rescue-20260919`（23 提交版）**已被 R15 会话删除**，现为 `fazhi-rescue-4465080-20260919`（28 提交，
  已验证 bundle/clone/fsck）；② "打开即回写 `length.bin`"已订正为"加载 HNSW 索引才回写"；
  ③ `rev-list --count HEAD` 从 26 → 28；④ 缺失 blob `04463121` **已被 blobless clone 逐字节复原**（28/28 可读），
  只剩 `0263bd5` 一个洞。
- [ ] **S6-c** 项目记忆同步（`project-precommit-and-concurrent-sessions.md` 条目 k/o、`te-chroma-isolation-state.md`）。
- [ ] **S6-d** 交回 Owner 的清单：付费三臂额度、`tmp_pack` 去留、A2 推送（需先确认目标仓 private）、
  B1–B5 五个裁决项、A4 红测证据是否销毁。

---

## 自审（writing-plans 三项）

**覆盖率**：R1 票 T1-a→S6-a、T1-b→S3（改道并说明）、T1-c→S1、T2→S5、T3→S2、T4→S6-b；
本会话残余 G3-a→S4、文档订正→S6-b/c；P2-2 票 A1→**已于 02:06 满足**（`phase2-g2` RUN_VALID 1272/0 @ `4465080`），
其 §4"不许动"清单与本文 Global Constraints 第 5 条一致。
**占位符**：无 TBD；S5 的实现体在 Step 1 复量通过后按当时代码写（此处不给伪代码，避免照抄过期形状）。
**类型一致性**：新开关命名沿用 `*_check: bool = False` 既有法；纯函数名以
`limitation_calc.law_version_crosses_watershed` 为准，引用前先 `grep -n` 实证（票面已提醒拼写/签名都会漂）。

---

## 执行记录（追加式）

### S1 + S2 完成（03:4x，提交 `3c51879`）

**S1 递归密钥扫描**：`scan_trace_shape.py` rc=0，**71,159 个文件 / 29 个文件命中 / 共 71 次命中**。
（S7 订正 2026-09-19：原句"29 个命中"把两件事混成一件 —— `files_with_hits=29` 是**文件数**，
`by_pattern.n` 合计 **71** 才是命中次数（openai 17 / generic 46 / aws 4 / jwt 4）。
且 S7-a 改口径后 `files_scanned` **只数"打开并读到结尾"**，0 字节与超限文件另计 `skipped` ⇒
新旧 `files_scanned` 不可直接比。S7-a 收口时在同一棵树上重跑（`--out` 指到 temp，不覆盖本目录
`scan-result.json`）实测：**69,939 scanned + skipped{zero_byte 1324, too_big 5, oserror 0}
= 71,268 个文件、30 个文件命中 / 共 72 次命中**。多的那 1 个文件、那 1 次命中是
`docs/code-review-report-02e3851-20260918.md` 里一条 27 字节 generic 形状（未跟踪、不属停手指征；
按 S7 票 §11 未读该报告内容。归因：它 mtime = **2026-09-19 15:02:36**、`git ls-files` 里 0 条 ⇒
是并行会话在 S1 扫描之后落盘的文件）⇒ 差异来自本仓自 04:2x 起被并行会话改动，不是仪器判据变化。）
先做已知答案标定（合成文件三种形状全部命中）才敢用它的读数。
命中分族（**只报形状**）：
- 真形态密钥族 = `sk-` 前缀 **51 字节、0 位数字、sha 前 12 位 `1ed4b9c74505`**，出现在
  `.env`(1) / `backend/.env`(2) / `.workbuddy/evidence/r15-tripwire-t2-red.txt`(多) /
  `dispatch-output/config-backups-20260915/env.before-*.bak`(各 2) ⇒ **四类全部已被 ignore 规则挡住**（逐条 `check-ignore -v` 实测）。
- 受跟踪的 2 个 verify 脚本命中的是 **27 字节、0 数字、三家共用同一值** 的合成占位 ⇒
  独立复核后**认同** R15 会话"非真密钥"的判断（不是我信它，是形状对得上：与真族不同长度不同哈希）。
- `dispatch-output/token.json`（120B JWT）已被 :76 显式规则挡住；**姊妹文件
  `t2-evidence-replay-20260916/p2-auth-state.json` 漏了** ⇒ 见 S2 补规则。
- 22 个命中来自 `.worktrees/legal-agent-v1/backend/.venv311/**`（第三方库自带的示例 key），
  被 `.gitignore:17 .worktrees/` 挡住 ⇒ 噪声，不是本仓风险。
**S1 自我纠正两次**（都记下来，因为我差点把错结论写进报告）：
① `git check-ignore -v -q` 这个组合对**已知被忽略**的 `backend/app.db` 也返回 1 ⇒ 我第一轮据此
   得出"6 个文件全裸奔"，**假**；去掉 `-q` 后全部 IGNORED。
② 把文件清单经 `$(python -c ...)` 送进 `for` 循环时，Windows 的 `\r\n` 让每个路径多带一个 `\r`
   ⇒ `.env`/`backend/.env` 又被误报 NOT-IGNORED。用**字面量**重测才定案。
   ⇒ 通用规矩：**批量判定前，先拿一个"已知答案"的样本走同一条管道。**

**S2 判据（四条全实测）**：`_probe.txt` rc=0；`backend/tests/_r15_tripwire_probe.py` rc=1；
`git ls-files -i -c --exclude-standard` **72 → 72**（零已跟踪文件被卷入）；
根 `_*` 未跟踪条目 **97 → 0**、全仓未跟踪条目 **261 → 164**（差值正好 97）。
`p2-auth-state.json` 现由新规则 :112 挡住。
**风险点名**：这条规则让 97 个根目录留痕条目**从 `git status` 视野消失**（本意的反面），
需要人看见它们时用 `git status --ignored` 或临时 `!/_xxx` 例外行。
门禁：pre-commit 首跑 rc=1（end-of-file-fixer 补 `.gitignore` 换行、ruff format 重排扫描器，
都是钩子正常修复），复跑 rc=0 全 Passed；提交 `3c51879` 仅含我的 2 个文件。

**副作用与处置**：跑 P4 的 `over2_replay.py --verify` 会**就地重钉**该票自己的
`over2-replay-report.md` / `replay-results.json` 里的 provenance（`61fbd11` → `4465080`）。
除 provenance 外两文件**逐字节不变** ⇒ 这同时是"重放幂等"的最强证明。
我已把两文件恢复到 HEAD（恢复前将 diff 存
`dispatch-output/secrets-hygiene-20260919/p4-verify-sideeffect-over2-provenance.diff`），现在
`git status --porcelain -uno` **0 行**。

### S3 结果：**未完成**，且据此**否决 R15 票 T1-b 的删除动作**（04:0x）

- 只读探测（原件一个字节没动，实测 `ls -l .git/objects/pack/tmp_pack_*` 前后都是 2 个文件、
  尺寸 44,269,567 / 19,316,735、mtime 01:31 / 00:26 不变）。副本放在 `Desktop/fazhi-tmppack-probe-20260919/`。
- **两条 pack 的头 12 字节完全相同**（`PACK` v2、声明 **1943** 个对象）⇒ 是同一次 fetch 的两个时刻的残留，
  不是两次独立事件。
- `git index-pack` 对**两个副本都**报 `fatal: early EOF` ⇒ 尾部的对象名表根本没写出来。
  ⇒ git 自带工具一个对象都列不出来（这也是 `--keep` 失败的原因）。
- 于是自造了一个"绕过名表、顺序 inflate 逐个对象算 SHA-1"的解析器
  （`dispatch-output/secrets-hygiene-20260919/parse_partial_pack.py`）。
  **它经过已知答案标定**：对完整 pack `pack-6892e414…` 走出的 10 个对象 OID 与
  `git show-index` 的权威 OID **逐个吻合（10 匹配 / 0 失配）**，并且能命中我故意指定的已知 OID。
  标定过程还纠正了我对 pack 格式的既有假设：本机 pack 实测是
  `[不压缩的对象头 varint][该对象自己的 zlib 流]` 交替，不是"整包一条流"。
- **但它只能覆盖 10 / 1943 个对象**：第 11 个对象处 `incorrect header check` ⇒
  我的边界推进逻辑在跨对象上断开（未修，见下面"限制"）。
- **因此结论是"无法判定"**：既不能证明 `0263bd5` 在里面，**也不能证明它不在**。
  而 T1-b 要"先确认无价值再删"——**该前提没有被满足** ⇒ 本票**不删**任何 tmp pack，
  把两份副本与解析器留在盘外，交回 Owner 决定。
- 限制（诚实标注）：① 未修的断开点很可能是 ofs-delta/ref-delta 的额外字段推进或某类对象后的
  `unused_data` 长度算错；② 我的第一版实现里那段"指针推进"写得含混，已整段重写为
  "每对象独立 decompressobj + 用 `unused_data` 定界"，但只验证到第 10 个对象。

### S4 完成（04:1x，提交 `88bd167`，2 文件 +151/−2）

红→绿→变异全跑完，且**中途抓到一条自己的假绿**：
- 红①：1 failed / 9 passed（红因正确：quota 账本没进备份包）。
  **同轮第二条测试却直接绿了**——它只断言输出含"跳过"，而旧代码 `--skip-chroma 跳过` 里就有这两个字；
  把断言改成"必须点名 `quota_used.sqlite` 与 `media`"后，红②：2 failed / 8 passed。
- 绿：11 passed。
- 定向变异 4 道**全部拦住**，失败数分别 3/2/1/1（对应各被摘掉的行为），
  每道跑完按字节还原，最终 `sha256 == 基线 abd99ecfd890…`。
- 真跑一次备份 rc=0：包内新增 `quota_used.sqlite`(12,288B) / `data_app.db` / `media/`。
  差点被自己的显示骗过：`ls -l | cut -c30-` 把尺寸列切掉，`19,939,328` 只剩 `39328`，
  看起来像"19.9MB 备成 39KB"。实测源与备份 **page_count 4868 相同、
  conversations 2234 / agent_runs 291 / messages 4326 逐表相同** ⇒ 备份是忠实的。
  （⇒ 以后 `ls` 不要 cut 列。）
- 三门禁：`ruff check .` rc=0、`ruff format --check .` rc=0（235 文件）、
  `mypy .` = Success / no issues in 71 files；
  `run_gate_full.py s4-green` = **RUN_VALID / 1275 passed（= 基线 1272 + 3）/ 18 deselected / 0 failed**，
  同轮真实 chroma 整目录指纹、`app.db cc 10784`、`quota cc 2` 全部前后不变。

### S5 **本会话不做完**：已把 seam 量清，改成交接得动的票（04:2x 决定）

票面三个符号全部复量存在（不是照抄）：
- `agent/limitation_calc.py:208 law_version_crosses_watershed(claim_text, fact_texts, law_as_of) -> bool`，
  docstring 自带四条"任一不满足 ⇒ False（不拦）"的保守规则；
- `settings.py` 的开关惯例实测为 `*_check: bool = False`（`entity_precision_check:69`、
  `phantom_tool_check:80`、`law_version_tripwire_check:88`、`agent_proc_misroute_check:94`）；
- `request_bootstrap.py:49 RequestBootstrap.law_as_of: date | None = None`，并在 `:396` 被填。

**但快车道的出口不是一个，是三个**（这是票面没写的）：
| 出口 | 位置 | 现状 |
|---|---|---|
| 流式主链路 | `main.py:1729` `async for piece in stream_with_retry(...)` | 答案**分片流出**，要判必须先在流尾收口 |
| 第二个流式分支 | `main.py:1870` 同一形状 | 同上，且与 :1729 的降级口径不完全一致 |
| 缓冲轻量路径 | `main.py:1799` → `_light_buffered` → `_light_buffered_locked:1164` | 已有 `quality.self_check` + `NOTE_QUOTA/NOTE_COMPLEX` 的**降级惯用法**可复用 |
另：`main.py:703 _pre()` 在 `main.py` 内**查不到调用点**（只有 `_prepare_fast_path_only` 的 :713 自引用），
可能是测试专用或已废弃 —— **未证实前不要顺手删**，但它是"哪条路真的在线上跑"的关键问题。

**为什么不当场接**：① 三处出口的收口点不同，最小改动也会碰生产主链路两处以上；
② 票面 DoD 要求 `AGENT_ENABLED` 两态 + 真实模型对照臂，**额度不在本会话授权内**；
③ 本仓对"文档说接好了但判分端不认"有专门教训（[PL#14] 假接线），
   没有对照臂读数就说"快车道缺口已闭合"正是那个形状。
**下一位执行者的第一步**：先确认线上到底走哪条出口（`grep -n "agent_enabled" main.py` 的两处分支 + 三个出口），
再把判定挂在 `_light_buffered_locked` 的 `v.ok` 之后复用 NOTE 惯用法（那是唯一"答案已成文且未流出"的点），
流式两处需要单独设计（流尾收口），并各自带一条"开关关 ⇒ 行为逐字不变"的测试。

### S6-a 完成（04:1x–04:2x）：救援仓刷新到 `88bd167`，五项判据全过

新目录 `C:/Users/33393/Desktop/fazhi-rescue-88bd167-20260919/`（`repo.git` + `cloned` +
`fazhi-master-88bd167.bundle` 135,496,420B + 四个日志/对照文件）。实测：
`fast-export` rc=0（流 184,554,784B，用完即删）→ `fast-import` rc=0 →
`bundle create` rc=0 → `bundle verify` rc=0 且报 "records a complete history" →
`clone <bundle>` rc=0 → **克隆内 `git fsck` rc=0 且输出 0 行** →
`git log --pretty='%T|%an|%ae|%ad|%s'` 两侧 **30 行 diff 为空**、tree 列逐位 **ok=30 bad=0**、
tip tree `c4949feded41…` 与 live 相同、`ls-files` **2154 = 2154**。
顺带自己复量了两件**与交接文档不同**的事实（见执行书 D1 的订正）：
`04463121` 确已复原（`cat-file -t` = blob）、最旧三提交 `git archive` 全 rc=0；
`git fsck` 的 broken link 是 **10 条而不是 2 条**，其中只有 1 条是 master 的真洞，
其余 9 条挂在 filter-repo 的 4 条 replace 残骸上、不影响遍历。

### 本计划收口状态

| 票 | 结论 |
|---|---|
| S1 密钥递归扫描 | ✅ 完成（含两次仪器自我纠正） |
| S2 `/_*` + auth-state | ✅ 完成，提交 `3c51879` |
| S3 tmp_pack | ✅ 以"无法判定 ⇒ 不删"收口（判据前提未满足） |
| S4 备份面补全 | ⚠️→✅ **两轴评审判定"票面 DoD 未达成"，S7-b 已补齐**：`88bd167` 那 4 道变异里没有一道钉得住 "源↔目标映射"（Step 3(b) 要求"源路径写错 ⇒ 必须红"，M2 做的是丢掉目标名；而两份源库同播 `'x'` + 测试整份替换 `EXTRA_SQLITE` ⇒ 映射原理上不可能变红）。S7-b 依据 **M5/M6** 补齐（提交 `7f5429b`；M6 红因 `assert 'main' == 'dataapp'`，见"S7 整改轮"） |
| S5 快车道版本判定 | ⛔ **本会话不做完**：三出口已测绘，未接线（理由见上，避免 [PL#14] 假接线） |
| S6-a 救援仓刷新 | ✅ 完成（五项判据；⚠️ tip 哈希不是 `88bd167`，见"审计 A-6"） |
| S6-b/c 文档与记忆订正 | ✅ 完成（本文件 + 执行书 D1 + 当日日志 + 项目记忆） |
| S6-d 回 Owner | ⏳ 见对话末尾清单 |

---

## 审计轮（12:20–12:30）：对上面每一句完成声明重测

规则：**上次运行 ≠ 本次证据**。能重测的一律重测；重测不出来的就改口。结果：**7 条成立、2 条我说过头、
1 条仪器失效导致读数作废**。

### A-1 全量门禁：本次重新跑，绿 ✅

`./venv/Scripts/python.exe ../dispatch-output/te-chroma-isolation-20260918/run_gate_full.py audit-20260919`
（HEAD `88bd167`，三件产物在 `dispatch-output/te-chroma-isolation-20260918/gate-audit-20260919.*`）：

```
结论: RUN_VALID   pytest 退出码 0   耗时 2.9 分   basetemp: fazhi_gate_audit-20260919
末行: 1275 passed, 18 deselected, 52 warnings in 164.57s (0:02:44)
源码变动文件 (0): []
chroma fingerprint 前==后 = 71e7a7a47b47…-n38-s362449354；collection legal_provisions_cos 10266
app.db cc 10784 → 10784 不变 ✅      quota cc 2 → 2 不变 ✅
```

⇒ 上一轮报的 `1275 passed / 0 failed` 不是引用旧输出，本次同一棵树重跑得同一个数。

### A-2 四道变异：失败用例名逐条对上 ✅（此前只报了"全变红"）

| 变异 | 期望被击中 | 实测 FAILED | 计数 |
|---|---|---|---|
| M1 附属 SQLite 循环摘空 | 3 条新测试全部 | 3 条全部 | 3 failed, 8 passed |
| M2 备份目标名丢掉 | 覆盖 + 失败关闭 | 这 2 条 | 2 failed, 9 passed |
| M3 media 复制整块短路 | 仅覆盖测试 | 仅它 | 1 failed, 10 passed |
| M4 失败关闭分支摘掉 | 仅 fail-closed 测试 | 仅它 | 1 failed, 10 passed |

四道留下**四种不同的失败签名** ⇒ 三条新测试不是"同一件事测三遍"，各自锚住一块行为。日志：
`dispatch-output/s4-backup-coverage-20260919/mut-M*.log`（`ls` 实测目录内 4 log + 4 pt-* + 跑者）。

### A-3 S2 那四个数：三个复现，第 4 个口径没锁死 ⚠️

本次实测：`_probe.txt` rc=0 ✅；`backend/tests/_r15_tripwire_probe.py` rc=1 ✅；
`git ls-files -i -c --exclude-standard` = 72 ✅；根 `_*` 未跟踪条目 = **0** ✅。

但"**全仓未跟踪 261 → 164**"这句**没写用哪个 `-u` 口径**，而三种口径差一个数量级：

| 命令 | 值 |
|---|---|
| `git status --porcelain`（默认 `-u`，未跟踪目录折叠成 1 条） | **168** |
| `git status --porcelain -uall`（逐文件展开） | **6415** |
| 脏的已跟踪文件 | 0 |

168 的归因（按 mtime 筛出 03:45:09 之后新建的未跟踪条目）：**164 + 3 + 1 = 168** ——
S2 之后我自己又产出 `dispatch-output/s4-backup-coverage-20260919/`、
`secrets-hygiene-20260919/parse_partial_pack.py`、`secrets-hygiene-20260919/p4-verify-sideeffect-over2-provenance.diff`
三条（+3），加本轮我写的 `dispatch-output/audit-20260919-gate-wrapper.txt`（+1）。
唯一残余不确定：`p4-verify…diff` 的 mtime 是 03:45:47，只比 S2 提交晚 38 秒，
**我无法证明"164"是在它之前测的**（只能说它晚于记录它的那次提交）。
⇒ 订正：凡引用"未跟踪条目数"必须同时写命令与 `-u` 口径，否则不同人量出 168/6415 都算"对"。

顺带否掉一条我自己的怀疑：看到 `backend/.ptmp-s4-run2/` 时我以为自己违反了"basetemp 不许落在 `backend/` 内"，
`stat` 实测其 mtime = **2026-09-17 16:46** ⇒ 早于本会话两天，是别人的 pytest 残留，名字里的 "s4" 与我的 S4 无关。

### A-4 S1 扫描：数字复现，但有两处欠交代 ⚠️

从 `scan-result.json` 原文重算（不引用我自己的摘要）：`files_scanned` = **71159** ✅。

- 真实键家族 = 形状 `len 51 / has_digit=False / head8=bcdefhij / sha12=1ed4b9c74505`，
  命中 **21 次**（`openai_style_sk` 15 + `generic_assign_secret` 6）落在**恰好 6 个文件**：
  `.env`(1)、`backend/.env`(2)、`.workbuddy/evidence/r15-tripwire-t2-red.txt`(12)、
  `dispatch-output/config-backups-20260915/env.before-{b-desensitize,partial-delivery,q38f-removal}.bak`(各 2)。
  六条**全部 `tracked=False`**，且逐条 `git check-ignore -v` 命中规则
  （`:26 .env`、`:85 .workbuddy/`、`:88 dispatch-output/config-backups-*/`）。
- **此前没交代的短形状命中**（len 20–31）：绝大部分在 `.worktrees/legal-agent-v1/backend/.venv311/**`
  里（PIL/grpc/torch RECORD/langchain RECORD/posthog、transformers 测试），`.gitignore:17 .worktrees/` 已挡住 ⇒ 第三方库噪声。
- **两条命中已跟踪文件**：`dispatch-output/agent-mainline-fix-20260911/verify.ps1`、
  `dispatch-output/agent-timeout-h1-20260912/verify-h1.sh`（各 2 个 27 位形状，另有同名 2 个未跟踪 verify）。
  脱敏后看形状：len 27、**0 位数字、全小写、distinct 13–14、前缀 `test…`** ⇒ 是假环境变量的占位值，不是云凭据。
- **独立佐证**（另一台仪器、非同源）：A-1 那次 pytest 日志里出现
  `InsecureKeyLengthWarning: The HMAC key is 27 bytes long`（`venv/Lib/site-packages/jwt/api_jwt.py:147,368`）
  ⇒ 那 27 位就是本仓自带的**弱 JWT 开发密钥**。
  这一条从"扫描器噪声"升级为"确实存在一个 27 字节 HMAC 密钥被测试使用"，属**已知弱点、非泄漏**。

⇒ S1 结论订正为：**真键只在盘上、未进索引、被忽略规则覆盖；已跟踪文件里的命中均为占位值 + 一个 27 字节弱 JWT 开发密钥**。

### A-5 "这把键只存在于这一块盘"：这条一度是**假绿**，换仪器后才成立

在活仓跑 `git log --all -- <path>` 时输出夹了一条
`fatal: unable to read tree (02b3c7d2…)`，而 `backend/.env` 的 `history-commits=0` 正是**紧跟在这条 fatal 之后**读到的
⇒ 按本仓纪律（仪器一失效，该次调用所有读数全废），这个 0 **作废**。
改到"完整图"的救援仓 `fazhi-rescue-88bd167-20260919/repo.git` 上重问同一句：六个路径全部 **0 条提交、且无 fatal** ✅。
（`--all` 覆盖救援仓内 30 提交 = 活仓 master 全部 30 提交。）

### A-6 救援包：内容可复现，但"刷新到 `88bd167`"这句是**哈希层面的错话**

| 量 | 活仓 `88bd167` | 救援仓 tip |
|---|---|---|
| tree | `c4949feded4185ba33ad57aadfb822d65934f5d2` | **同一个** `c4949fe…` ✅ |
| master 提交数 | 30 | 30 ✅ |
| 提交哈希 | `88bd167` | **`2fdba83`**（父链第一跳 `99d7d34a` ≠ `3c51879`） |

哈希不同的原因就是我做过 graft：**自 `0263bd56` 起重写祖先，其上每一笔都换哈希**。S6-a 当时比对用的是
`%T|%an|%ae|%ad|%s`（**故意不含 `%H`**），所以那五项判据没写错；错的是我口头/标题那句"刷新到 `88bd167`"。
**给下一位的提醒**：从包恢复后 `git rev-parse master` 会得 `2fdba83`，这不是坏了，是重写链的必然结果。

新测两件（12:26）：
- 从救援仓 `bundle create` **耗时 691 ms**，产物 **135,496,420 B 与 04:21 那份逐字节相同**
  （sha256 两侧均 `8b59d2e5cbad…ddf42702`）⇒ 救援包**可复现**；`bundle verify` 112 ms rc=0，
  verify 明确报内含 `2fdba83f2950… refs/heads/master`。探针包已删除（我自己的临时产物）。
- ⇒ 我那句"整个刷新约 1 分钟"**收回**：单步实测 0.7 秒，全程只能由目录 mtime 给到"04:20 起、04:22 前 ⇒ ≤2 分钟"
  的**分钟级**上界，不到秒。**"约 1 分钟"当时是没测就说的。**
- 反向复证（本轮意外白捡）：在**活仓**跑 `bundle create` 直接 rc=1，
  `error: Could not read 0263bd56fcfc…` / `fatal: Failed to traverse parents of commit 76c1eea694f4…`
  ⇒ "graft 只修读侧、`pack-objects` 不认 replace ref ⇒ bundle/push 仍 fatal"这条不再是转述，本次亲眼复现。

### A-7 **本会话造成的数据破坏与恢复**（写在这里是因为它是我这轮最贵的一次错）

给 `.workbuddy/memory/2026-09-19.md` 追加审计小结时把 `>>` 打成 `>` ⇒ **整文件覆盖**，
232 行 / 21,691 B 全没，其中**含另一会话（`9985e4cb`）写的 4 个块**（git 历史修复诊断、fetch 结论订正、
blob 回填收口、"推救援仓库有什么风险"）。本仓纪律（记忆条目 i）明令并发追加只能走 append 原语，
而我 12:29 还 `tail` 过一次这个文件、知道它有别人的尾巴 ⇒ 这不是不知道，是**手比脑快**。

恢复做法（已跑通，可复制）：

1. 两个会话的 Bash 调用原文都在项目转录 `~/.qoder-cn/projects/<proj>/*.jsonl` 里；
   用 `>>?<path> <<'EOF' … EOF` 的**绑定式**正则（重定向目标 ↔ 它自己的 heredoc）逐块取出，
   按 `timestamp` 排序拼接。⚠️ 上一版正则没绑定目标，把同一条命令里写给**执行计划**的 heredoc 也吞了
   ⇒ 多算 2 块、1,775 字符，靠"重建比原件还大"这个反常才发现。
2. 转录里还留着**当天唯一一次 Edit**（1 行 → 3 行）的 old/new，回放它。
3. 三条**独立**锚点判定成功，而不是"看起来差不多"：行数 **232 = 232**、字节 **21,691 = 21,691**、
   我 12:29 `tail` 到的**末 6 行逐字相同**；再加 `CR 计数 = 0`——Windows 上 `write_text()` 会把 `\n`
   悄悄换成 `\r\n`（我第一次落盘就多了 231 B），必须按字节写。
4. 写回后实测 251 行 / 23,950 B、八个块标题各命中 **1** 次、读回字节与候选完全相等。

**残余风险（不许省）**：若曾有第三个会话**不经 heredoc** 改过该日志，那段不在重建来源里；
目前的唯一硬证据只有"总字节与受损前实测相等"这一条，它要求对方"恰好贡献 0 字节"才能骗过去。
留痕脚本在 `Desktop/fazhi-tmppack-probe-20260919/`（`recover_daylog2.py`、`append_calibration.py`、
`rebuild_final.py`、`restore_daylog.py`）。

**硬规矩（写进记忆）**：向共享追加式文件写入，只允许 `open(path,'ab')` 或 `>>`；
`>` / `write_text` / 整段 Edit 一律禁止；动手前先 `wc -c` 记下期望值，写完立刻复测字节数与行数。

---

## S7 整改轮（16:0x–16:4x，交接票 `docs/handoff-s7-backup-and-scanner-hardening-20260919.md`）

起票时 HEAD = `88bd167`。**P1–P8 八条前置取证全部符合期望**（逐条读数见当日日志）；
§1.1 那条"并行会话在途"的前提本会话全程成立 —— 那 19 个在途文件一份没被我碰，
收口时工作树脏项 = 别人的 19 + `.gitignore`（见末段"未提交的那一件"）。
两笔提交：`79e2bd3`（S7-a）、`7f5429b`（S7-b）。没有第三笔。

### S7-a 扫描器加固（提交 `79e2bd3`，只含 `scan_trace_shape.py` 一个文件）

**退出码契约**：`0` 正常 / `3` 停手（真凭据形状命中**受跟踪**文件）/ `4` 仪器失效（`git ls-files` 非 0）；
两条件同时成立取 4（仪器失效优先，它让 3 的判定不可信）。三面判据用**种子仓**跑
（`--repo <temp>/seed`，伪造串只在系统 temp、用完 `rm -rf`；**没往真仓库写过任何伪造键**）：

| 面 | 构造 | 期望 | 实测 |
|---|---|---|---|
| A | `planted.txt` 已 `git add`（`sk-` + 48 个 `a` = **51 字节**，与真键家族同形状、故意全同） | rc=3 + `[STOP]` 点名 | **rc=3**，`[STOP] 真凭据形状命中受跟踪文件：planted.txt pattern=openai_style_sk` |
| B | 同一文件 `git rm --cached` | rc=0，且命中**从 tracked 挪到 untracked**（不是"没命中"） | **rc=0**；`files_with_hits` 仍 = 1，planted.txt 由 `tracked_with_hits` 出现在 `untracked_with_hits` |
| C | `--repo <temp>/notarepo` | rc=4 + `[INSTRUMENT]` | **rc=4**，`[INSTRUMENT] git ls-files 失败 rc=128 stderr=fatal: not a git repository…`，命中全部落进新增的 `unknown_with_hits` |

C 面顺带把 §3#7（`check=False` 把 git 失败洗成"全都没被跟踪"）测没了。

**口径拆分**（`… scan_trace_shape.py --out <temp>/full.json`，真仓库、`--repo` 用默认值）：
`files_scanned=69939`（只数"打开并读到结尾"）+ `skipped={zero_byte 1324, too_big 5, oserror 0}`
= **71,268 个文件**；`skipped_dirs` 合计剪枝 2802 次。⚠️ 这个 69,939 与 S1 记的 71,159 **不是同一个量**
（旧口径把 0 字节/超限算进去了），两个数都给了、各注口径。

**去重**（§5.5：键 = `pattern` + 绝对起始偏移 + token 字节长）—— 这里要写一条**票面预期被实测否掉**的：
真仓库上**去重前后都是 72**（`{openai 17, generic 47, aws 4, jwt 4}`），即这棵树上没有跨块双计，
"去重后 n 会变小"在本树不成立。所以另造一条专供红绿的分块边界样本：51 字节的串摆到**首块末尾那 64 字节
重叠窗口内**（文件 1,048,673 B > 1 MiB、token 绝对起始 1,048,521、结束 1,048,572）⇒
同一把尺子**旧版读 2 次、新版读 1 次**。这才是"去重生效"的证据；72→72 只说明"这棵树恰好没有那个形状"。
（顺带：S1 的 71 与本次 72 差的那 1 条 generic，归因见上面 S1 段的订正 —— 并行会话 15:02 落的文件。）

**证据基线没被覆盖**：开工前 `scan-result.json` sha256 = `a38881590cc0b1884d935eb4af22fc3c4a9002d721aa50b56a7571508cc4a27d`，
收口复测**同一串** ⇒ 所有标定一律 `--out <temp>`（§5.3 先加 `--out` 再跑任何东西，就是为这一步）。
**全仓重扫 rc=0**（无停手指征），`tracked_with_hits` 仍是票面点名的两条 verify 脚本。

### S7-b 备份面加固（提交 `7f5429b`，3 份文件 +293/−70）

- **§6.1** `EXTRA_SQLITE` 拆成 `DATA_DIR` + "包内名 → 源文件名"映射 ⇒ 测试只 patch `DATA_DIR`，
  **映射第一次进入被测面**；三份附属库改播**互不相同**的哨兵值 `main`/`quota`/`dataapp`。
- **§6.2** 守卫复用 `chroma_dir_guard.assert_matches(QUOTA_SOURCE, "backup_data", env_name="QUOTA_DB")`，
  **没写私有函数**（`test_chroma_dir_guard.py` 有源码级 `assert_matches(` 接线断言，另起名字会红得莫名其妙）。
  按 §6.2.3 **不**去直接调 `_check_env_contract()`（conftest 无条件设 `CHROMA_DIR` ⇒ 第一道守卫恒抛，
  两个方向都测不到 QUOTA_DB），改为 CLI 三面实测：
  分歧 ⇒ **rc=1 + "拒绝执行"、连备份目录都没创建**；同指一处 ⇒ rc=0；未设 ⇒ rc=0。
- **§6.3** `backup_manifest.json` 顶层 `{version:1, created_at, entries}`，entries 按 dest 排序、
  **只来自显式创建的目标名（不 walk 包目录）**。真跑一次备份 rc=0 ⇒ 包内 **6 条**：
  `app.db`(20,205,568B) / `data_app.db`(19,939,328B) / `quota_used.sqlite`(12,288B) 三条 sqlite 带 sha256+integrity_check、
  `chroma_index.json`(1,317,497B) file 带 sha256、`chroma_db` dir **只记 files=38 / bytes=362,449,354 不哈希**、
  `media` dir files=58（= 源文件数 58）且逐个 sha256。清单里 `.verify.tmp` 出现次数 = 0。
  两条失败路径各有断言"坏包不带清单"。
- **§6.4** 附属那侧 `verify_sqlite` 补 `try/except (OSError, sqlite3.Error)`（与主库对称），文案
  `[Extras] ERROR <name> 恢复验证执行失败：<exc>`；`raising=False` **6 处清零**
  （`grep -c raising=False tests/test_backup_data.py` = **0**）；缺件断言升级为"原因+名字同现"。
- **§6.5 七道变异全部拦住**（跑者 `dispatch-output/s7-backup-hardening-20260919/run_mutations.py`，
  日志 `mut-M*.log` 七份；S4 那份跑者与日志**一个字没改**）。各自 FAILED 用例名：

  | 道 | 摘掉什么 | 结果 |
  |---|---|---|
  | M1 | 附属循环摘空 | 4 failed：maps… / tolerates_absent / corrupt / verification_raises |
  | M2 | 备份目标名丢掉 | 3 failed：maps… / corrupt / verification_raises |
  | M3 | media 复制整块短路 | 2 failed：maps… + media_items_degrade（清单里那句"仅记计数"也不打了） |
  | M4 | 失败关闭分支摘掉 | 2 failed：corrupt / verification_raises |
  | **M5** | 两份附属源 value 互换 | 3 failed：maps…（**`assert 'dataapp' == 'quota'`** ⇒ 按内容红）/ verification_raises（换的是名字）/ quota_guard_target |
  | **M6** | 容器侧库指向主库（票面 Step 3(b)） | 3 failed：maps…（**`assert 'main' == 'dataapp'`** ⇒ 能打开、内容不对，正是"按内容判红"）/ tolerates_absent（清单多出一条 `data_app.db`）/ chroma_residue（同一原因，清单集合对不上） |
  | **M7** | 删掉 `env_name="QUOTA_DB"` | 1 failed：`test_backup_data_wires_the_guard_for_quota_db_too`（在**另一个**测试文件里 ⇒ 跑者的 pytest 目标必须两份都带，否则会假报"逃过"） |

  三份目标文件 sha256 跑前 = 跑后（跑者逐一校验）。M7 的锚点 `, env_name="QUOTA_DB")` 全文件唯一。
- **七道不计入 §6.5 那张表的定向验证**（`run_mut_extra.py`；§8"pytest 只报第一条失败断言 ⇒ 没单独红过就记未验证"）：
  EXTRA-A 摘掉附属那侧 try/except ⇒ rc=1（`sqlite3.DatabaseError: cannot open` 直接冲出 `main()`）；
  EXTRA-B 只把文案改一个字（`恢复验证执行失败` → `恢复验证失败`）⇒ 那句整串断言确实红；
  EXTRA-C 把"只来自显式目标名"换成 walk 包目录 ⇒ `app.db.verify.tmp` 被记进清单、当场红；
  EXTRA-D 给 dir 条目补一个 sha256 字段 ⇒ "chroma_db 不哈希"那条确实盯着字段；
  EXTRA-F 把 media 的上限判断改成恒假 ⇒ 红在 `assert "items" not in entry`；
  EXTRA-G 只改退化那行 print ⇒ 红在文案断言；
  EXTRA-E 只留 CHROMA_DIR 那一支、把 env_name 挂到它身上 ⇒ 收紧后的正则红，
  **而收紧前的弱正则在这一道下命中=True（绿）** ⇒ 弱正则原本是空枪，这条对照是跑者打出来的、不是我推的。
  七道各自只动一个形状，跑完按字节还原、三份文件 sha 跑前=跑后。
  过程中本机跑者的"命中次数≠1 就停手"守卫挡下一次错锚点：光"恢复验证执行失败："在文件里**命中 2 次**
  （主库那条 `[SQLite] ERROR 恢复验证执行失败：` 同文案）⇒ 半截变异没落盘，文件 sha 不变。
- **门禁**：定向 `pytest tests/test_backup_data.py tests/test_chroma_dir_guard.py` = **22 passed**
  （两笔时是 20 passed，自审整改笔 +2）；`ruff check .` rc=0；`ruff format --check` 我这三份 already formatted；
  `mypy .` Success / 72 files；
  `run_gate_full.py s7c-green` = **RUN_VALID / rc=0 / 1333 passed, 18 deselected / 源码变动 0**，
  隔离判据单列：真实 chroma 指纹前==后（`71e7a7a4…-n38-s362449354`）、`app.db cc 10784→10784`、`quota cc 2→2`。
  产物三件 `dispatch-output/te-chroma-isolation-20260918/gate-s7c-green.{log,-source-sha.json,-verdict.txt}`。
  （整改前另有一轮 `s7b-green` = RUN_VALID / 1331 passed，两份都在盘上。）
  ⚠️ **1333 不可与 S4 那轮的 1275 直接比**：我只 +4 条测试，多出来的主要来自并行会话在途的
  `tests/test_law_snapshot_review.py` / `tests/test_review_regressions.py` 等 —— 同一棵树上收进来的。
  本轮能声称的只有"0 failed"，不能声称"S4 基线仍然全绿"。
  ⚠️ 全仓 `ruff format --check .` 报 **9 份待格式化**，逐条比对全部属于并行会话在途文件
  （`agent/{limitation_calc,phantom_check,verifier,writer}.py`、`main.py`、`schemas.py`、
  `tests/test_entity_precision.py`、两份新测试）⇒ **未代改**。

### S7-c 自审整改笔（提交 `708559b`，两笔之外的一笔）

两笔交完后，让一个**只读**评审者拿票面 §5/§6/§13 逐条回查那两笔 diff（不改文件、不跑测试）。
抓到 4 条真缺陷，全部已修；另有 2 条**决定不改**的限制，写在下面而不是藏起来：

| # | 缺陷 | 处置 |
|---|---|---|
| 1 | 扫描器对每个命中文件**再 `stat()` 一次**取字节数 ⇒ 这是一棵别的会话正在写的树，两次 stat 之间文件可以消失，仪器会以 **rc=1 崩在 0/3/4 契约之外**（契约里根本没有 1） | 改为 `scan_file` 把字节数随读数一起交出，`per_file` 不再自己 stat：少一次 syscall，也少一条崩溃路径 |
| 2 | §6.2 那条接线断言的原文是 `assert_matches\([^()]*env_name="QUOTA_DB"[^()]*\)` —— 它只钉"**有没有**传 env_name"，**没钉被比的是谁** | 收紧为 `assert_matches\(QUOTA_SOURCE…`；并用 EXTRA-E 对照实证：把 env_name 只挂在 CHROMA_DIR 那一支、删掉 QUOTA_SOURCE 那一支，**弱正则命中=绿、收紧后=红** ⇒ 这不是审美调整，是那条洞真的在 |
| 3 | `test_quota_guard_target…` 的第二条断言 `basename(QUOTA_SOURCE) == EXTRA_SQLITE["quota_used.sqlite"]` **恒真**（两端同源，M5 也打不红它） | 删掉，只留那条独立写死的期望 |
| 4 | 清单的 chroma 面（`chroma_db` 不哈希、`.verify.tmp` 不进清单、media 超上限退化）此前**只有真跑那一次**证明过，单测全走 `--skip-chroma` ⇒ "删掉实现也仍 20 passed" | 补两条单测 + 三道定向验证（EXTRA-C/D 各打一红），§13 那两条从此有测试撑 |

**决定不改的两条限制**（要改就得动票面钉死的东西，或引入从未变红过的新分支）：
1. 去重键按 §5.5 是 `(pattern, 绝对起始偏移, token 字节长)` 三元组 ⇒ 只能并掉"**整段**落在 64 字节重叠窗内"的重复。
   若某条命中起点落在块尾、但**长度跨过块边界**，首块记的是截断形状（len/sha12 都是半截的）、次块记完整形状
   ⇒ 同一条凭据仍会产生 2 条读数、其中 1 条是伪形状。根治要把 `len` 从键里去掉（同起点只留最长那条），
   那与 §5.5 钉的三元组冲突 ⇒ **不改，交 Owner**。实测本树 `n` 去重前后都是 72，这条路径未被触发过。
2. `manifest_entries` / `dir_stats` / `file_sha256` 没有异常处理：清单构建中途抛错 ⇒ 以 traceback 收尾，
   运维既看不到"备份完成"也看不到"备份失败"。它是 fail-**loud**（不会给坏包发凭证，也不会有清单落盘），
   但确实不是"一条明确的失败结论"。补 try/except 会引入一条从未变红过的分支 ⇒ **不改，记为已知限制**。
3. **断言级的红绿覆盖，逐条说清哪句是"红过的"、哪句只是"跑过的"**（pytest 只报第一条失败断言）：
   media 退化那条测试里，`assert "items" not in entry` 由 EXTRA-F（把上限判断改成恒假）单独打红、
   退化文案由 EXTRA-G（只改那行 print）单独打红；M3 让这条测试死在更早的 `KeyError: 'media'`，
   所以**没有 F/G 的话这三句里只有第一条沾光**。chroma 那条测试同理：EXTRA-C 红在集合相等断言
   （消息里直接印出多出来的 `app.db.verify.tmp`），EXTRA-D 红在 `"sha256" not in chroma_db`；
   而 `files/bytes == (2, 1500)` 与末尾那条 `".verify.tmp" not in json.dumps(...)` **从未单独红过** ——
   前者由构造独立已知（2 个文件、1000+500 字节），后者与集合断言同义、被它先挡住。


**整改后重测**（不能拿整改前的读数交差）：**最终提交的那份构建**（`scan_trace_shape.py` 工作树
sha256 前缀 `3005dd85…`，且 `git hash-object` == `git rev-parse HEAD:…` ⇒ 测的就是入库的那份）重建种子仓后重跑四面 =
A `rc=3` + `[STOP]`×1（tracked 含 planted.txt）、B `rc=0`（同一文件取消跟踪后命中**挪进** untracked、
`n` 仍为 1 ⇒ 不是"没命中"）、C `rc=4` + `[INSTRUMENT]`×1 且命中落进 `unknown_with_hits`、
分块边界样本 `n`=1（同一把尺子的旧版在这条上是 2）；另加一次子树扫描 `--repo backend` = **rc=0**（518 个文件）。
用完 `rm -rf` 掉全部种子（里面有伪造串）。
7 道变异在最终测试集（22 条）上**重跑仍全部拦住**，M3 多红一条、M6 多红一条（见上表）；
定向 22 passed、`mypy .` Success、`ruff` 两项 rc=0、pre-commit 首跑 rc=0 且没顺手改别人的文件。
另一条把"测的=交的"钉死的读数：`git show HEAD:backend/scripts/backup_data.py | sha256sum` =
`a63599901091fe41…` = 变异跑者那份**基线 sha** ⇒ 7+5 道变异证明的就是入库的那份字节。
全仓重扫（`files_scanned=70213` 那次 = 票面要的基线门）跑在**最后一条纯类型注解改动之前**
（该行有 `from __future__ import annotations`、无运行时效果，但**我没有为它重跑 12 分钟的全仓扫**；
入库构建上另跑了一次 `--repo backend` 子树扫 = rc=0，见上一段）：
`files_scanned=70213` + `skipped={zero_byte 1365, too_big 5, oserror 0}`
= 71,583 个文件、`files_with_hits=30`、`by_pattern.n` 合计 **72**（`{openai 17, generic 47, aws 4, jwt 4}`），
`tracked_with_hits` 仍是那两条 verify 脚本、`unknown_with_hits=[]`；`scan-result.json` 的 sha256 复测
**仍等于开工前那串**。⇒ 一票里新增的全部产物（`dispatch-output/s7-backup-hardening-20260919/` 的两份跑者 +
15 份日志（7 道 M + 7 道 EXTRA + 一次真跑备份）+ 13 个 `pt-*` basetemp、`backend/backups/20260919_163503/`
那个 `du -sk` = 397,996 KiB（≈408 MB）的真包）**没有带进任何新命中** —— 这顺带排掉了那条已知风险：
`monkeypatch.setattr` 打不到属性时会把整个 `Settings`（含真 key）dump 进测试日志，日志落在 `dispatch-output/`
下就是一次 `git add -A` 事故。temp 里那些带伪造串的标定种子已 `rm -rf`，没往真仓库写过任何伪造键。
（补一条**在最终态上重量**的：`--repo dispatch-output/s7-backup-hardening-20260919` 单独扫一次 =
278 个文件、`files_with_hits=0`、`tracked`/`unknown` 均空 ⇒ 两份跑者 + 15 份日志 + 13 个 `pt-*` 里
一条凭据形状都没有。）

**真跑那个包是不是忠实的**（清单只哈希包内文件，回答的是"包里有什么"，不回答"和源一不一致" ⇒ 另量一次）：
`app.db` 源/包 `page_count` 4933/4933、`data_app.db` 4868/4868、`quota_used.sqlite` 3/3，
三份的表数各 11/11/1 相同、**逐表行数差异集合为空** ⇒ 副本忠实。
⚠️ 成立条件要写清：**备份时没停后端**（票面也没要求停），比的是"包 vs 当下源"，不是"包 vs 备份那一瞬间的源"；
`PRAGMA integrity_check` 三库全 ok ⇒ 包自洽，跨时刻一致性**未证**。

### `.gitignore` 注释订正：已按裁决 Q2 入库

改动内容 = 把"实测根目录有 97 个这样的条目"换成**复测命令**
（`git status --porcelain --ignored | grep -c '^!! _'`，本会话实测 **108**）并写清"97 与 108 不是同一个量、
原命令现在返回 **0**"，外加 auth-state 那条注明"执行者自加 → Owner 已于 2026-09-19 追认（Q6）"。
自证只动了注释：`git diff -U0 .gitignore` 里非 `#` 开头的增删行数 = **0**；
`git ls-files -i -c --exclude-standard | wc -l` 仍 = **72**（未放宽任何规则）。
入库 = **`c036cb6`**（`chore(留痕/S7)`，1 file changed, +11/-3，pre-commit rc=0，提交前 index 里只有这一个文件）。

### S7-d：Owner 五项裁决之后补的两笔（Q3 / Q4）

**入库的六笔**：`79e2bd3`（S7-a）→ `7f5429b`（S7-b）→ `708559b`（自审）→ `c036cb6`（留痕）
→ `891de5f`（**Q3** 去重键去掉 `len`）→ `c362c91`（**Q4** 清单面 fail-closed）。

Q3 实测（种子只在 temp、用完删；扫描器以子进程跑入库字节）：

| 样本 | 改前 | 改后 |
|---|---|---|
| `crossing.bin`（起点 `CHUNK-30`、长 51，**跨块**） | `n=2` = `len=30/sha12=2f89390e1943` + `len=51/e1aa1d5b99d6` | `n=1` = `len=51/e1aa1d5b99d6`（留的是完整形状） |
| `inside.bin`（起点 `CHUNK-51`，整段在重叠窗内） | `n=1` | `n=1` ⇒ 无回归 |
| `multi.txt`（两条不同起点的独立命中） | `n=2` | `n=2` ⇒ 去掉 `len` 不误并 |
| 三面契约 A/B/C | rc=3 / 0 / 4，各 `n=1` | 同左 |

入库字节自证：`git show HEAD:…scan_trace_shape.py | sha256sum` = 工作树 = `78927bd39fca…`；
`ruff format --check` + `ruff check` 均 rc=0；pre-commit 首跑 rc=0；改后另跑一次 `--repo backend` 子树扫 =
**rc=0**（518 files、`.env` 未跟踪 2 条 openai 形状）。

**Q4 入库 = `c362c91`**（两个文件：生产 1 + 测试 1；本轮 `test_chroma_dir_guard.py` 未改所以不在里面）：
`main()` 里清单那两处裸 I/O 包了 `except OSError` → `[Manifest] ERROR 清单构建失败：<exc>` → `return 1`
（**只兜 `OSError`**：清单面没有任何 sqlite 调用，跟抄 `(OSError, sqlite3.Error)` 会多一条永远走不到的分支）；
新测试 `test_backup_fails_closed_when_manifest_construction_raises` —— 先在生产码未改时**亲眼看它红**
（`OSError: disk gone` 冲出 `main()`，captured stdout 停在 `[Extras] quota_used.sqlite 备份=PASS`，
既无"备份完成"也无"备份失败"= 就是这个缺陷本身），改完定向 **23 passed**；
`ruff`/`mypy`/pre-commit 全 rc=0 且 pre-commit 没改动任何字节（跑前跑后 sha 相同）。
替身 **EXTRA-H/I/J** 三道各自把新分支改坏（摘整个 try / `return 1`→`return 0` / 文案改一字），
三道都红在新测试对应的那一句上，跑者退出码 0 ⇒ **十道替身**全部有效且三份文件字节还原一致。
补跑的两张回归网：**§6.5 那 7 道变异（M1–M7）在 23 条测试上重跑全部拦住**（rc 均 1、还原 sha 一致=True、
跑者 rc=0），**全量门禁 `gate-s7d-green` = RUN_VALID**、`1334 passed, 18 deselected`
（比 `s7c-green` 的 1333 多且仅多这一条新测试）、源码变动 0、真实 chroma 零写入、`app.db` cc 10784→10784、
`quota` cc 2→2。

**"测的 = 交的"这条这次要分开说**：生产文件 `98a63dd5…` 工作树 == 入库 blob（字节级同一份，7+10 道
变异与门禁证明的就是入库那份）；测试文件工作树是 **CRLF**（404 处）⇒ 入库 blob 是它的 LF 归一形态
（`721f3820…` vs `a76da6b5…`），我另跑了一次逐字节比对确认两者**只差换行**（`w.replace(CRLF,LF) == blob` True）。
以前我只写"sha 相同"没区分换行口径，那对 LF 的工作树成立、对 CRLF 的测试文件不成立。

**§6.4 那条 grep 判据的口径**：票面钉的是 `grep -c raising=False tests/test_backup_data.py` = **0**（现 0 ✅）。
`test_chroma_dir_guard.py:25` 有一处 `monkeypatch.delenv("CHROMA_DIR", raising=False)` —— 那是**另一个 API**、
删环境变量时本就需要它，且不在这条判据的文件范围内；不要把它报成违规，也不要顺手改它。

**取证教训一条（本机复现了记忆里那个坑）**：暂停前我在变异窗口内取 `sha256sum` 读到 `7950be3e…`，
跑完是 `98a63dd5…` ⇒ **窗口内的哈希读数无意义**；判"还原干净"只能信跑者自己那一次
`shas() == base`（它是在**写回之后**、且用同一份基线比的）。`pgrep -f run_mut_extra` 在 Git Bash 下**假阴性**
（进程明明在跑却返回空），第一次"已退出（第 1 次探测）"就是它差点让我在中途收尾 ——
以后等长跑者用"输出文件非空"这种**副作用探针**，别信 pgrep。

### S7-d 收口补充（救援仓刷新 + 最终构建上重跑的两件真跑）

**全仓重扫补跑了**（此前那条 `files_scanned=70213` 的读数不属于最终入库构建，是个已知空洞，现在补上）：
在 `891de5f` + `c362c91` 都入库之后，用入库那份扫描器（sha `78927bd3…`）对整棵树重扫一次，
`--out` 指 temp —— **rc=0**、耗时 11 分（19:23:16 → 19:34:14）、
`files_scanned=70283` + `skipped={zero_byte 1365, too_big 5, oserror 0}`（= 走到 71,653 个文件）、
`skipped_dirs` 里 `__pycache__` 2640、`chroma_db` 178、`backups` 1（ ⇒ 备份包不进扫）；
`files_with_hits=30`、`by_pattern.n` 合计 **72**（`{openai 17, generic 47, aws 4, jwt 4}`）
⇒ **二元键与三元键在本树上读数相同**，Q3 那次改动没有动真实命中数（它的效果只在合成样本上可见，
这正是当初票面 §5.5 "去重后会变小"在本树不成立的那个结论的复测）。
`tracked_with_hits` 有 2 个文件却 **rc=0**：两条都只命中 `generic_assign_secret`（它按 S1 判据**不算**停手形状），
逐条复算"受跟踪 ∩ 真形态"= **0**，与退出码自洽。
⚠️ 好性质一条：这两条正是 `dispatch-output/agent-mainline-fix-20260911/verify.ps1:5` 与
`agent-timeout-h1-20260912/verify-h1.sh:6` —— **同一把尺子的两条独立仪器看到了同一个对象**
（扫描器的 generic 命中 vs 只读调查员逐文件找 JWT_SECRET，两条路径各说各话却指到同两行），
比任何单点读数都可信。证据安全：`scan-result.json` 跑后仍 `a3888159…`、mtime 仍 03:33:45（我每次标定都带 `--out <temp>`）。

**救援仓已刷新**（票面 §10"携带路径"那条，Owner 已授权）：新建 `Desktop/fazhi-rescue-c362c91-20260919/`，
配方与 04:21 那次同（live 只读 `fast-export master` → 工作树外 bare 仓 `fast-import` → `bundle create --all`），
脚本 `refresh.sh` 原样留在包内可重跑。**五条判据实测**：`bundle verify` rc=0 且报
"The bundle records a complete history"、从 bundle 克隆 rc=0、克隆内全量 `git fsck` **零输出**（0 字节）、
`git log --pretty='%T|%an|%ae|%ad|%s'` 两侧逐行 diff = **0 字节**（36 行 = 36 行）、
`ls-tree -r` 两侧都 **2154**；另 `git archive HEAD` rc=0、克隆内 `git log -- <path>` 可用。
tip tree 两侧同为 `ed1d96d1…`，而 **tip SHA live `c362c91` ≠ 包内 `7ed416e`**（graft 重写父链，
只能按内容引用不能按哈希引用）。bundle 135,550,233 B。
旧的两份**没删**（去留归 Owner），且"真子集"这句是量出来的不是推的：28 提交版 28 个 tree、
30 提交版 30 个 tree，**全部**出现在新包 36 个 tree 里。⚠️ 那份目录名叫 `fazhi-rescue-88bd167-…` 的包
内部 tip 其实是 `2fdba83`，票面 §10 抄的也是这个坑（它写的"刷新到 88bd167"同样只能指内容）。

**§6.5 DoD 里"真跑一次备份"在 Q4 之后重跑过**（因为 Q4 改的正是清单那条路径，旧读数属于改前的构建）：
`backend/backups/20260919_192441/`，rc=0、26 秒，`[Manifest] … entries=6`
= `app.db:sqlite chroma_db:dir chroma_index.json:file data_app.db:sqlite media:dir quota_used.sqlite:sqlite`。
逐条读清单（不只是看条目数）：4 条 sqlite/file 带 `sha256`，**`chroma_db` 无 `sha256` 字段**、
记 `files=38 bytes=362449354`（"chroma 只记计数"= 是 ✅），`media` 记 `files=58 bytes=3359117` 且
`items` 有 58 条逐项哈希（未触上限退化分支）。

### §11 摸底（只读派发的 T-1）：那条"27 字节弱 JWT"的前提是**我写错的**

Owner 授权派发后，我给一个只读调查员写的 brief 说"一个 27 字节、以 `eyJ` 开头的 JWT 形状开发密钥"。
它跑完**纠正了这个前提**，我随后逐条复跑它的读数核实（4 项全对）：
- 全仓 `len=27` 且 `eyJ` 开头的串只有 1 处，在 **第三方 venv** 的 `posthog/test/test_code_variables.py:945`
  （公开文档示例，无人 import；`pyproject.toml:93 testpaths=["tests"]` ⇒ venv 根本不进收集）。
- 真正的 27 字节那个是 **HMAC 签名 key、不是 JWT 形状**：`backend/tests/conftest.py:9`
  `os.environ.setdefault("JWT_SECRET", "test-jwt-secret-for-ci-only")` —— 明文测试默认值，len 实测 **27**、
  `startswith("eyJ")` = **False**（我自己量的）。运行时可达链：`auth.py:24 getenv("JWT_SECRET")` →
  `auth.py:52 jwt.encode` / `:62 jwt.decode` → `main.py:366/:392`；另有 `main.py:153` + `settings.py:32` 的
  存在性校验。**没有任何测试断言它的值/长度/存在性**（`grep -rn JWT_SECRET backend/tests` = 2 命中，
  都在 conftest 自己那两行）。
- 若哪天要换：最小改动集是 `conftest.py:9` + 两个**已跟踪**的离线 verify 脚本
  （`dispatch-output/agent-mainline-fix-20260911/verify.ps1:5`、`agent-timeout-h1-20260912/verify-h1.sh:6`，
  `setdefault` 语义下 shell 值优先 ⇒ 漏改会静默用旧 key 签 token）。
- 顺带一条日志内嵌项（**已核实不构成泄漏路径**）：`.workbuddy/evidence/r15-tripwire-t2-red.txt` 有 6 处
  Settings repr 内嵌该 key，形状正是记忆里 `(m)` 那条"monkeypatch 失败把 Settings dump 进日志"。
  但 `git check-ignore -v` 实测该文件被 **`.gitignore:85` 的 `.workbuddy/`** 整条覆盖 ⇒ 只有 `git add -f`
  才可能进仓，**本票不需要为它加规则**。（我先前写"现有规则没覆盖 `.workbuddy/evidence/`"是错的，已订正。）
- venv 那处也复量过：`posthog/test/test_code_variables.py:945` 确有一条 `len=27 sha12=2f9f7bd22960` 的
  `eyJ` 串，与它报的一致。
- 纪律教训：brief 里凡是"我记得的形状/长度/前缀"必须标成待核实，别写成事实（已进用户记忆）；
  以及**子 agent 报的"泄漏面"我也要用 `check-ignore` 自己量一遍**，否则它的乐观/悲观会原样传给你。

### S5 已起票（本会话不执行，票面 `docs/handoff-s5-fastpath-version-gate-20260919.md`）

上一代留下的 S5 测绘（`:249-268`）我在新构建上重量了一遍，并把它落成一张可交接的票。三条与旧记录不同的新事实：
1. **坐标又漂了 +32**：两个流式出口从 `1729/1870` 变成 **`1761/1902`**（就是别人那 34 行未提交改动推的）；
   `_light_buffered` 的调用点从 `:1799` 变成 **`:1831`**，而被调两处 `:1155/:1164` 未动（hunk 在它们之后）。
2. **"最小可用"其实不最小**：三条出口里只有缓冲轻量能便宜接门（文本已在手、有 `NOTE_QUOTA/NOTE_COMPLEX`
   降级惯用法可复用），两条流式出口要判就得在流尾收口 = 改用户可见行为 ⇒ **票拆成 S5-a（只做轻量）+ 流式收口另开**。
3. **`law_as_of` 在 `:1831` 作用域里本来就够得着**（端点 `:1486-1494` 已把 `body.law_as_of` 传进 bootstrap），
   所以不必经 `pre` 字典中转 —— 而走 `pre` 会撞上 `test_request_bootstrap.py:601` 钉死的
   `set(result) == LEGACY_KEYS`。这条决定了票面 §4-Q2 的推荐路线。
   顺带把旧记录里"` _pre()` 未证实可能废弃"结掉了：`main.py` 内 **0 调用点**，只有
   `tests/test_pre_rewrite_order.py:93/:149` 调它，它 `:713` 转发到 `_prepare_fast_path_only`
   ⇒ 不是死码、但也不是挂门的地方，票面明写"不要碰它"。
- **排队条件写在票最前面**：`main.py` 有他人未提交的 +34/−1 时不许领票（领了第一个提交就是夹带他人工作），
  且领票后第一件事是重测行号。
- 派发成本入账：为 S5 派的那次只读调查 **27 分钟 / 46 次工具调用 / 失败无交付**，票面里的读数全是我自己量的。

### 接手指引（S7 会话收口 → 下一代必读，按顺序四件）

本会话**没有**另建一份 `handoff-s7-*.md`：一是仓库纪律禁止新建互相覆盖的交接/进度文件，
二是 S5 那张票本身就是交接文档。但要读的顺序是这四件，缺一条就会重复我已经付过的成本：

| 顺序 | 读什么 | 只在这里能拿到的东西 |
|---|---|---|
| ① | `docs/handoff-s5-fastpath-version-gate-20260919.md` | 下一张要干的活。§1 八条前置取证、§2 实测坐标（21:22 重测，车道已被 `8734a8f` 清空）、§4 Q1/Q2/Q3 已定稿、§11 不许动的 |
| ② | 本文件 `### S7-d` / `### S7-d 收口补充` / `### S5 已起票`（`:605`起） | S7 三笔改动**为什么**长成现在这样：Q3 去 `len` 的判据、Q4 清单 fail-closed 的兜底范围（只兜 `OSError`，不抄 sqlite）、10 探针变异、真跑备份 |
| ③ | `.workbuddy/memory/2026-09-19.md` 第 5、6 块 | 时间线级留痕。**注意：`.workbuddy/` 被 `.gitignore:85` 屏蔽**，全新克隆看不到 ⇒ 下面两条问题已就地抄录进本文件 |
| ④ | `C:/Users/33393/Desktop/fazhi-rescue-INDEX.txt` | 可携带历史在哪、哪份最新（现量：`fazhi-rescue-d6077d0-20260919`，40 提交）、"腾空间只删 `cloned/`，绝不删 bundle / repo.git" |

**留给审查会话（不是本会话能答的）两个问题**，此处登记是为了不被 `.gitignore` 吞掉：
1. 谁在往 `.git/objects/15/` 反复写 20–58MB 的 `tmp_obj_*`？21:5x 实测 **15 个文件 / 633MB**，最新一个距测量时刻
   207 秒仍在生成，工作树里的克隆已排除。**别拿它当"gc 该跑了"** —— 本仓库 `.git` 有洞（缺父提交 `0263bd5`），
   任何"历史里没有 X"的负证明都不能在 live 上做。
2. `backend/app.db` 最后一次被写是 **09-19 00:28**，是谁写的？实测 file-change-counter `cc 10784`、无 wal/shm、
   18126 端口无监听、21 小时零写入。旁边 00:26 有个 `tmp_pack_lu4Uc1` —— **时间巧合，未证实因果**，别顺着写成结论。

**本会话收口时点**：`HEAD = d6077d0`，40 提交，跟踪面零脏，未推送（不推送是 Owner 的边界，不是待办）。
