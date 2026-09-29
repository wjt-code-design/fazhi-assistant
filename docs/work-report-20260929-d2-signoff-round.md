# 工作汇报 · 本地候选收口：B 档探针 → D2 签字页 → 独立评审轮（2026-09-29）

> 单一可转发文件。**§0 是给第三方看的一段话**，细节逐条带指针与可复跑命令。
> 数字口径：凡"条数/只数/笔数"都给命令，不给手抄值（本轮正是这条规矩救了我一次，见 §1 第 4 条与 §3 第 3 条）。

## 0. 一段话汇报（可直接转交）

接手上一轮中断的"本地候选收口 A–F"后，本会话做了三件事：**① 交付 B 档运行时探针**（把 26 条依赖通报中
**有桩可答的 17 条**的可达性证据，从"静态 grep 0 命中"升级到"两个执行窗口内运行时读数"；
另有 **9 条探针答不上**，不是"已排除"，见 §4B；仪器自带脱敏、归类、复算与反例）；
**② 按 Owner「你来执行」起草 D2 的可签文本**（六栏 + 签字位，压在既有交接书里，没另起文件；**草案不是签字**）；
**③ 跑独立只读评审复核自己的汇报**，八条发现逐条本机复现：六条证实并已修（其中两条是"把没测的说成测了"），
两条证伪/部分证伪并留反证。
现在**代码与文档都在本地，一笔都没推**；能立刻推动这件事的是 §4A 里的 **T1 与 T2 两个前置动作**
（**在六栏上落笔**、**轮换那两把凭据**——其中一把是此前被意外打印过、按"已暴露"处理的 rerank key，
它同时挡着真实 rerank 验收）。⚠️ **T3–T6 不是可省的**：它们不挡签字，但挡推送与下一轮立项。

## 1. 我做了什么（按顺序，每条给落点）

1. **接续收口并复跑门禁**：按 `docs/superpowers/plans/2026-09-28-local-candidate-closeout-plan.md` 继续。
   ⚠️ 诚实标注：**纯发布物树那六步门禁本轮没有复跑**——本报告这两笔提交（`ddafea7..HEAD`）改到的文件全部落在 `docs/` 与
   `dispatch-output/local-candidate-closeout-20260928/`，一条 `backend/` 下的代码或测试都没碰
   （复现：`git diff --name-only ddafea7..HEAD | grep -cE '^backend/'` → **0**；
   ⚠️ 别写 `^(backend|tests)/`——本仓**没有顶层 `tests/`**，测试真路径是 `backend/tests/`，那样写有一支恒空）。
   所以"09-28 跑到全 rc=0"那条既有结论**未被本轮改动影响**，但**要声称"现在仍全绿"必须复跑一遍**，我不替它背书。
2. **B 档运行时探针**（证据目录 `dispatch-output/local-candidate-closeout-20260928/`）：
   - 仪器 `b_runtime_probe.py`（`sys.addaudithook` + `sys.meta_path` 后置补钉，登记 22 只桩；
     自检场实装 **19/22**，差的那 3 只是 `PENDING-UNRESOLVED`——自检进程里那三个模块本就未导入、桩无处可贴，
     不是漏报；在两腿实测场它们被记成 `NEVER-IMPORTED`，见 `b-probe-selfcheck.json` 的 `install` 字段），
     两腿读数复现一致（`b_probe_pair_check.py` 五轴零差异 + junit 从各场 `junit.xml` 现算）。
   - 外联**逐键机器归类**（`b_probe_net_audit.py`，non-loopback 优先 + `ipaddress`），
     唯一那次非环回已归因到用例（`b_probe_dns_trace.py` → `tests/test_phase3.py::test_healthz_components` →
     `backend/main.py:340`；⚠️ **行号绑树**：那是探针跑的**候选树**（副本树自 `codex/local-candidate-closeout`），
     master 工作树同一行是 `:339` ⇒ 复现前先确认你在哪棵树上）。
   - 读数脱敏：`urllib.Request` 只记 URL/方法/**头键名**，请求体一律不碰；哨兵对照 `b_probe_net_sanity.py` 双向证明
     "既记下了该记的、又没把口令记进来"。
   - 判定表由读数现生：`python b_probe_matrix.py` → `b-probe-verdict-matrix.md`（末尾「公告视角」带闭合检查）。
3. **D2 可签文本**（Owner「你来执行」之后）：`docs/handoff-local-candidate-closeout-20260929.md` §6② 末尾，
   六栏 + 签字位：一 接受范围（分档绑各自证据等级）｜二 **不写进"已接受"**的 5 件｜三 限制清单与自动失效条件｜
   四 两条须算进暴露面的应用事实｜五 复审日期｜六 签了也不解除的在册阻塞。
4. **给签字页加同源核对**：`b_probe_claim_check.py` 新增主张——六栏齐备带签字位、① 栏"无桩可答"清单
   ==（登记表公告去重集 − 读数里真有桩的集合）且连页面自写条数一起比、复审日期与登记表**全部出现处**一致、
   页内每条公告号必须在登记表内、第六条要同时含两条凭据主题且不许把已完成的 Q5 当待走、
   以及"指向本复算器的段落不得手抄条数"。
5. **新增第三类反例**：`b_probe_claim_mutants.py` 的 `DOC_MUTANTS`（**文档侧**）——真把签字页日期/清单/登记表第二处日期改错，
   要求复算器必须红，并在 `finally` 按**原字节**还原 + 复比 sha256；另加"窗口内被别人改过就判本只无效"的并发守卫。
   三侧分工：复算器侧证"不恒真"、数据侧证"谓词判得对"、**文档侧证"手抄会被抓"**。
6. **独立评审轮 + 修复**：判决全文在交接书 §12.2、证据 README G.7 补、主报告 (11)。要点见下面 §3。
7. **提交（别把两条线混了）**：本会话在 **`master`** 上落了 **4 笔**，内容只含文档、证据与分析脚本
   （复现：`git rev-list --count 5be6e05..HEAD` → 4；
   `git diff --name-only 5be6e05..HEAD | grep -cE '^backend/'` → **0**）。
   本报告讲的是后两笔（签字页轮 + 评审轮）：`git log --oneline -2`。
   ⚠️ **候选代码分支 `codex/local-candidate-closeout`（tip `fbc29e8`）没有合进 master，也没有一笔推上远端**——
   D3 的"等 D2 有结论再合"仍生效。⇒ "我没合 master"这句只对**候选代码**成立，别读成"本轮没提交任何东西"。
   只 `git add -u`（tracked），未跟踪件一律没扫进提交（现量：`git status --porcelain --untracked-files=all | grep -c '^??'`）。
   ⚠️ **本份汇报自己目前还是未跟踪件**（`?? docs/work-report-20260929-d2-signoff-round.md`）——"代码与文档都在本地"
   这句包含"有一部分还没入库"，别读成全都在 git 里；要它进历史得再说一声，我不擅自提。

## 2. 现量（每条给命令，别信我抄的数）

```bash
cd C:/Users/33393/Desktop/ai-legal-helper/dispatch-output/local-candidate-closeout-20260928
python b_probe_claim_check.py        # rc=0；合计行 = 主张通过数/条数
python b_probe_claim_mutants.py      # rc=0；末行"合计 k/n" = 变异被杀数（复算器侧 + 文档侧）
python b_probe_matrix.py             # 重写 b-probe-verdict-matrix.md（生成物，别手改）；末尾闭合检查：有桩 + 答不上 == 登记表去重数
python verify-protected.py protected-review-rerun.log   # rc=0；entries / unchanged / changed
cd C:/Users/33393/Desktop/ai-legal-helper
python -m ruff check --config backend/pyproject.toml dispatch-output/local-candidate-closeout-20260928/b_probe_claim_check.py dispatch-output/local-candidate-closeout-20260928/b_probe_claim_mutants.py
git log --oneline -4 ; git rev-list --count 5be6e05..HEAD   # 本会话落地的笔数（=4）
git rev-list --count origin/master..HEAD                     # ⚠️ 这是"本地不可达自 origin/master 的提交数"，
                                                             # **不是**"未推送工作量"：两线**无共同祖先**
                                                             # （`git merge-base HEAD origin/master` 为空），
                                                             # 推上去是在远端并出第二条线，不是补落后的洞
git status --porcelain -uno | wc -l                          # tracked 脏数
```
本会话最后一次跑到（作用域写清，别当全仓绿灯）：`b_probe_claim_check.py` 与 `b_probe_claim_mutants.py` 均 rc=0；
`verify-protected.py` 打印 `changed: 0`；tracked 工作树干净；
**ruff 只对"本轮我改的两个脚本"是绿的**（`python -m ruff check --config backend/pyproject.toml <那两个文件>`，rc=0）。
⚠️ 整目录扫 `dispatch-output/local-candidate-closeout-20260928/` 仍会有 1 条红（`watch-ref-write.py` 的 `UP009`），
那是 09-28 就登记、本轮**故意不混改**的旧脚本（理由在证据 README G.6），不是新缺陷，也不是"全仓 lint 绿"。
**具体条数/只数以你复跑为准**——本轮正是因为把这些数抄进文档，加一条主张就集体过期一次。

## 3. 独立评审抓出、我复现后确认的两条重的（这是本轮最值钱的部分）

1. 🚨 **签字页第六条漏了唯一一把"已暴露"的凭据**。我只列了 `ADMIN_PASSWORD`，漏掉 §6① 那把
   **被意外打印过、按已暴露处理、同时挡着真实 rerank 验收**的 SiliconFlow rerank key。
   后果不是文档不完整，而是**Owner 把一次签字读成整批放行**。⇒ 两条凭据分开编号各写状态，并加主张钉这栏。
2. 🚨 **B 档被我统一写成"两场内运行时 0 调用"，与自家读数冲突**：现量 `G3a/G3b/G3d/G3e` 两场均 **1-CALLS**
   （模型/config/tokenizer 各加载 1 次），`G2a` 在应用路径场是 **NEVER-IMPORTED**（该场从不构造聊天客户端＝未测）。
   ⇒ 一栏改成三种读数形态分列，并明写"**签的是读数说的那件事，不是档位标签**"。
3. 另四处已修：同源核对覆盖选反（恰好没钉出错的第六条）、"第五条那四条在册阻塞"指错栏、
   复审日期只比登记表**第一个**出现处（⇒ 改 `findall` 要求全部出现处一致，并加一只真改第二处的文档侧变异）、
   绊线"按空行分段"会把**缩进续行**排除在作用域外（⇒ 折回上一段，标题段提到本件时纳入下一段）。
   ⚠️ 记一下**绊线真抓到的实物**，别让它听起来像抽象防范：证据 README 里那段"本目录文件数"快照
   （"总 120 只 / `.log` 60 只 / 可提交 58 只"）**两轮前就已经是过期数**，是复核把它指出来、现改成只给
   `git ls-files` 两条命令。⇒ 判决全文与它落在哪一条，见交接书 §12.2 第 6 条。
4. **两条经我复现后改判**（不照抄评审）：
   - 评审说 `post-commit`/`post-checkout` 钩子"在跑"，会把我改脏的签字页提交走 ⇒ **一半证伪、一半采纳**：
     两个文件确实存在，但各 **10 字节、内容只有 `#!/bin/sh`**，是**空壳**（`core.hooksPath` 未配置），不会做任何事；
     但它提醒的"窗口内别人提交会带走脏文档"**成立且我无法阻止** ⇒ 采纳了并发守卫（还原前比字节，不一致就判本只无效）。
     顺带修正交接书 §9.1：嵌套 ref 被外部进程删掉**不是这两个钩子**干的，真凶仍未定。
   - 评审说绊线该覆盖 `1660 / 206 类 / 348 次` ⇒ **不采纳**：那是运行读数，不是"本件条数"，不在该绊线射程内。

## 4. 待办项（按"谁动"分，一行一词可答）

**A. Owner 动作（卡住后面的所有事）**

| 编号 | 要你定的 | 卡住什么 | 备注 |
|---|---|---|---|
| T1 | **D2 落笔**：交接书 §6② 六栏上"照签 / 改第＿条 / 不接受" | 候选合入 `master`（D3＝等 D2 有结论再合） | 草案≠签字；第六栏已把"签了也不解除"逐条列出 |
| T2 | **D4 凭据**：① 已暴露的那把 rerank key 撤销/轮换；② `ADMIN_PASSWORD` 轮换 | 真实 rerank 一次性验收；以及整条推送线 | 顺序仍是 轮换 → 复扫 → 推；**新值别发到聊天里** |
| T3 | **注释措辞**：`dispatch-output/t12-frontend-sweep-20260920/apply_case_domain_gate.py:104` 自称"值已轮换，旧值失效"，与台账 D25 / 你 09-29 的"还没轮换"矛盾 | 别让人据注释认为旧口令无害 | 我不改别人的凭据结论；已登记进签字页第六条第 5 项 |
| T4 | **D6**：`CVE-2024-7774` 公告↔包名映射疑点核对 | 该条能不能申报误报 | 探针管不到（映射问题不是调用点问题） |
| T5 | **推送**是否要我准备 `--dry-run` | 远端 CI 真实运行证据 | 一次性快照分支、**永不 force**；真推由你按回车 |
| T6 | **D5**：下一阶段回功能线还是先做发布准备 | 下一轮开什么票 | 我的立场：先发布准备（真正卡发布的是服务器选型与真实库写入策略） |

**B. 助手可做（等授权，不擅自动）**

- 真实 rerank 一次性隔离验收（T2 完成并告知后，按既有授权只跑一次，记模型名/降级/`(法名,条号)`）。
- 依赖升级选型（`pip-audit` 47 条/8 包、57 条/10 包的红**不是本探针能减的**；分案口径在
  `docs/assistant-briefs/t7-dependency-upgrade-options-20260927.md`，尚未选型）。
  ⚠️ 两个"接受"别混：**本轮这张登记表**（`residual-risk-review.md`）从头就是"未接受、未忽略、未解除"，
  复审最迟 **2026-10-05**（今天 09-29，还没到）；我此前说的"**已到期**"指的是**更早那份 09-07 的 Risk Accepted 记录**
  的有效期过了（出处：`t7-dependency-upgrade-options-20260927.md:40`，以及
  `docs/pending-owner-actions-20260926.md:29` 早就澄清过"到期的是旧那份记录的有效期，不是本轮重扫这份"）。
  ⇒ 别读成"本轮的接受到期了"，那是两回事；措辞已按此收窄。
- 9 条"探针答不上"的公告：其中 Chroma HTTP 面 / text-splitters XSLT-URL splitter / Trainer / LightGlue / X-CLIP /
  `save_pretrained` 需另行核实公告对嵌入式版本的**适用性**，不是运行期探针能答的。
- 带凭据的外发面普查（rerank / 云端嵌入 / LLM 调用本身 / MCP / `/api/chat/transcribe`）——本轮**一次都没进样本**，
  因为驱动把 `RERANK_ENABLED` 关了；这条要么等凭据轮换后实跑，要么另开一票用假端点桩住。

**C. 本轮明确没做（一条不省）**

未把**候选代码分支**合入 `master`（注意区分：本报告这四笔文档/证据提交本身是直接落在 master 上的，见 §1 第 7 条）、
未 push、未建远端分支/PR、未部署、未启动生产容器、**未写真实库**（应用路径场用空副本集合）、
**未调用生成模型与真实 rerank**、**未代 Owner 接受任何风险**、未动凭据与服务器侧 `.env`、未改共享 `backend/venv`、
未动其余 worktree、未 `git add -A`（未跟踪项只列不入）、未加 `--ignore-vuln`、未跳测试、未放宽 CI、
未动那两个 `*.INVALID`（闸门判废的读数，留盘作缺陷证据、不入库）。

## 5. 边界：这批东西**不**证明什么

- 运行时读数只覆盖**两个执行窗口**（非 slow 测试场 + 两条直调路径），不是"不可达证明"；将来新增入口即失效。
- 测试场里生成链是**替身**：`backend/tests/_sse_harness.py:207` 用
  `monkeypatch.setattr(main, "make_chain", lambda llm: _FakeChain(...))` 把链工厂整个换掉
  （该文件在 master 与候选两棵树里是同一个 blob，`git rev-parse HEAD:backend/tests/_sse_harness.py` 与
  候选 ref 同一路径同哈希 ⇒ 与树无关，别绕树找）。⇒ 部分"0 调用"是**替身没去调真链**，不是真链被证明不调。
- "运行期 0 调用"**撑不起**"这个应用不会 outbound"：`/healthz` 就是按 `LLM_BASE_URL` 主机主动 TCP 探测的设计内外联点；
  且本轮普查是在外发面被开关关掉的前提下跑的（本机 `backend/.env` 里 rerank 是开着的）。
- "离线"是**读数结果不是环境保证**：`knowledge_base.py:5` 无条件把 `HF_HUB_OFFLINE` 改回 `0`，
  将来任何进程 import 它，前提就地失效。
- 子进程 / 第二解释器 / `backend/scripts/*` 在仪器之外；模型**文件**完整性未验（探针只证"没放行远程代码"）。
- 手抄条数那条绊线的词表**不完备**（夹 `**`、跨行的写法抓不到）⇒ 它只拦"再往回抄"，不证明"已无手抄"。

## 6. 指针（绝对路径）

- 交接书（可单独转交，含签字页与台账）：`C:\Users\33393\Desktop\ai-legal-helper\docs\handoff-local-candidate-closeout-20260929.md`
- 主汇报（阶段记录，最新看 §9.12.17 的 (10)(11)）：`...\docs\progress-handoff-report-20260925.md`
- 证据与仪器目录：`...\dispatch-output\local-candidate-closeout-20260928\`（README §G 是本探针轮的总说明，G.7 是本轮）
- 依赖风险登记表（真源，26 条 + 复审日期 + 共同状态）：`...\dispatch-output\local-candidate-closeout-20260928\residual-risk-review.md`
- 规划书（权威）：`...\docs\superpowers\plans\2026-09-28-local-candidate-closeout-plan.md`
- 候选分支引用与恢复：`...\dispatch-output\local-candidate-closeout-20260928\restore-candidate-ref.sh`；
  仓库外增量 bundle：`C:\Users\33393\Desktop\ai-legal-helper-bundles\`（`git bundle verify` 核对）
