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

> 🔧 **同日更晚的接手会话已追加 §7 补记**（执行 `docs/superpowers/plans/2026-09-29-local-candidate-decision-and-release-prep.md`）。
> 它把上面这段的三处状态改了：**签字页又改了四处**（`trust_remote_code` 那条不只是限缩，是加了版本证据后**削弱**了它作为缓解证明的力度）、
> **D6 判结**、**D2 的射程被证实比原先写的窄**（多了"开发工具"与"未审计的 torch"两根轴没有结论）。
> 阶段判定仍是 **③ 候选受阻**，但受阻的理由比原先记的更具体。
> **转交时连 §7 一起转**；只读 §0 会把状态读旧。逐条现量在计划文件末尾 §5。
> ⚠️ **§7 之后同日还有两小轮，状态又要往前挪**（详见 §7 末「不花凭据的取证」两处）：
> **① torch 那轴的"未审计"已消**——`+cpu` 只是本地构建标签，摘掉后按实装上游版本 `torch==2.6.0` 单审得动，
> 出 **22 条唯一通报** ⇒ 措辞要从"未审计的 torch"改成**"审过了、但没清零"**（其中 `weights_only` 绕过那条压在签字页 ⑤ 上）。
> **② 两条待核证结**（1839 判不适用**带失效条件**；Chroma 两条**与猜测方向相反**：版本确实适用、靠部署形态不暴露、且无补丁可升）。
> **③ A-3（开发/构建工具那 5 条）也做完了**，但它**给 Owner 添了一件新的**：**O-6 = `pytest` 的在册上限 `<9` 正好挡住那条通报的修复版本**，
> 而 CI 是 `ubuntu-latest` 且真跑 pytest ⇒ 这条**不是**"构建期专用所以无风险"，要么放宽 pin、要么显式接受"CI 是一次性单租户 runner"这条限制。
> **阶段判定不变，仍是 ③**，但 ③ 的理由不再是"有待核"，而是"有 5 条只能靠限制条款接受 + 开发工具轴那 1 条要 Owner 选（O-6）+ torch 轴没清零 + 未签 + 未推 + 凭据未轮换"。
> **④ 同一晚 O-6 已按 Owner 授权执行**（`按你的建议执行即可，我授权`）：先在**隔离环境**跑全量（候选依赖、只把测试框架
> 8.4.2→9.1.1，`pip freeze` 前后只差一行；`1650/10/18`、cov **85.25%**、rc=0，**两场逐字相同**），
> 才把 pin 改成 **`pytest>=9.0.3,<10`**，再**钉住新范围重跑** `pip-audit --no-deps` ⇒ 旧范围 **rc=1**、新范围 **rc=0**。
> ⚠️ **这不叫解除**：Linux 那条腿本机没跑过（全在 Windows），决定性证据在 CI ⇒ 归 O-5；且这笔**动了 `backend/` 一个文件**
> （`requirements-dev.txt`），"本会话 backend 零改动"那句从这一刻起**不再成立**（生产码 `backend/*.py` 仍一个没动）。

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
7. **提交（别把两条线混了）**：本会话在 **`master`** 上一笔笔落地，内容只含文档、证据与分析脚本
   （复现：`git log --oneline 5be6e05..HEAD`；⚠️ **笔数不写死**——写死一次就被自己的下一笔追过，
   本段初稿里的"4 笔"正是被"把这份汇报提进去"那一笔当场作废的，见下面那条自招）。
   每条范围判据：`git diff --name-only 5be6e05..HEAD | grep -cE '^backend/'` → **0**（一行业务代码/测试都没碰）。
   另有一笔只动本份汇报：`git show --stat --oneline` 看最新那笔的文件清单即可。
   ⚠️ **候选代码分支 `codex/local-candidate-closeout`（tip `fbc29e8`）没有合进 master，也没有一笔推上远端**——
   D3 的"等 D2 有结论再合"仍生效。⇒ "我没合 master"这句只对**候选代码**成立，别读成"本轮没提交任何东西"。
   只 `git add -u` / 按名 `git add <文件>`，未跟踪件一律没扫进提交
   （现量：`git status --porcelain --untracked-files=all | grep -c '^??'`）。
   ⚠️ **自招一条**：本节原先写"本份汇报自己目前还是未跟踪件"，随后我把它提交了 ⇒ 那句话立刻过期。
   留在这儿是因为它就是"抄了就过期"的活样本，也正是我给复算器加"段落里不许手抄条数"那条绊线的理由。

## 2. 现量（每条给命令，别信我抄的数）

```bash
cd C:/Users/33393/Desktop/ai-legal-helper/dispatch-output/local-candidate-closeout-20260928
python b_probe_claim_check.py        # rc=0；合计行 = 主张通过数/条数
python b_probe_claim_mutants.py      # rc=0；末行"合计 k/n" = 变异被杀数（复算器侧 + 文档侧）
python b_probe_matrix.py             # 重写 b-probe-verdict-matrix.md（生成物，别手改）；末尾闭合检查：有桩 + 答不上 == 登记表去重数
python verify-protected.py protected-review-rerun.log   # rc=0；entries / unchanged / changed
cd C:/Users/33393/Desktop/ai-legal-helper
python -m ruff check --config backend/pyproject.toml dispatch-output/local-candidate-closeout-20260928/b_probe_claim_check.py dispatch-output/local-candidate-closeout-20260928/b_probe_claim_mutants.py
git log --oneline 5be6e05..HEAD ; git rev-list --count 5be6e05..HEAD   # 本会话落地的全部笔数（会随提交增加，别写死）
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
5. **补记：提交这一段里我自己撞的两条**（都是"抄了就过期"，与评审无关，但按同一规矩必须留痕）
   - 把这份汇报提交进去那一笔，**当场作废了它正文里"本会话落了 4 笔"** ⇒ §1.7/§2 改成只给命令
     （`git log --oneline 5be6e05..HEAD`），并把这份汇报本身加进复算器的扫描面 `DOCS`
     （它抄了最多别的文档里的数，正是最该被机器盯住的那份）。这是同一毛病的第三次撞上。
   - 提交前对暂存 diff 跑扫密，第一次读数看着"六类全 0"像是干净，但我写的**控制串本身是坏的**：
     `AKIA` 后面只接了 14 字符、那条 base64 没到 40 位 ⇒ 这两条规则那一跑**根本没被测过**，"0"不可信。
     把控制串按各自阈值写满后复跑，才得到"六类控制全命中 + 真实 diff 六类全 0"。
     ⇒ 教训：**负向自证的尺子要逐条证明能红**，一批正则里混进一条哑火，整批"干净"就一起作废。

## 4. 待办项（按"谁动"分，一行一词可答）

**A. Owner 动作（卡住后面的所有事）**

> 编号与计划 §5.6 的分档表对齐（`T#` 是本报告 09-29 早先的号，`O#` 是接手会话之后按同一批事重排的号；
> **两处若有出入，以计划 §5.6 为准**，那张表带"解除后我的一步动作"）。

| 编号 | 要你定的 | 卡住什么 | 现状（09-29 晚逐条核过） |
|---|---|---|---|
| T1 ＝ O-4 | **D2 落笔**：交接书 §6② 六栏 + 「二·补」⑥⑦⑧ 上"照签 / 改第＿条 / 不接受" | 候选合入 `master`（D3＝等 D2 有结论再合） | **未落笔**（Q4 已裁定：**CI 结果到手之后签**，见 §8）。同日多了两条**必须连失效条件一起签**的：`1839` 要求 torch 保持 ≥2.6；Chroma 两条要求"不起 Chroma HTTP/不服务化不多租户"——**删那条限制这两条立即适用且无补丁** |
| T2 ＝ O-1/O-3 | **凭据**：① 已暴露的那把 rerank key 撤销/轮换；② `ADMIN_PASSWORD` 轮换 | 真实 rerank 一次性验收；以及整条推送线 | **两件都未轮换**（Q2 已裁定：本窗口**暂时放一边**，见 §8）。⚠️ **复现点＝合并进 `master` 之前**；若最终不轮换，要转成在册的显式接受 + 失效条件。**真要轮换时新值别发到聊天里** |
| ~~T3~~ | `apply_case_domain_gate.py:104` 自称"值已轮换，旧值失效"与台账 D25 矛盾 | 别让人据注释认为旧口令无害 | ✅ **同日已改**：注释现在写"凭据是否已轮换由 Owner 掌握，本注释不作断言"，并把原句作为**被删记录**留在括号里（`git grep -c 值已轮换` = 1，命中的正是那句"原写…未经证实，2026-09-29 删"，不是断言） |
| ~~T4~~ ＝ 计划 A-1 邻近 | **D6**：`CVE-2024-7774` 公告↔包名映射疑点核对 | 该条能不能申报误报 | ✅ **同日判结**：上游 PyPA/OSV 映射缺陷（langchainjs 挂到 PyPI `langchain`）。⚠️ 但**不是"零风险"**：`mdelete` 同名存在 ⇒ 依据只能是"汇不存在 + 生态归属"，原始告警保留、未加 `--ignore-vuln` |
| T5 ＝ O-5 | **推送**是否要我准备 `--dry-run` / 开 PR 取 CI 证据 | 远端 CI 真实运行证据 | **已定（Q1＋Q3）**：转 private → 推一次性快照分支（**永不 force**，你按回车）→ 匿名 compare 判形 → PR 或 push 触发取 CI 绿。⚠️ 本轮实测三件事，都影响这条路：**仓库仍是 public**（⇒ 前置未满足，我没推）、远端只有 `master`=`985d53e4` 且**最近三场 CI 全 failure**、`ci.yml` **没有 `workflow_dispatch`** ⇒ 详见 §8 |
| T6 ＝ O-5 | **D5**：下一阶段回功能线还是先做发布准备 | 下一轮开什么票 | **未定**。我的立场不变：先发布准备（真正卡发布的是服务器选型与真实库写入策略） |
| **O-2** | 本机按**值**反查口令出现点（结果不落盘）——形状普查覆盖不到的那部分 | 推送前置 | ✅ **同日已做完**（09-30 第二轮）：**在我这边办不了**、得在 Owner 机器上跑的那条按值反查，**已经在 Owner 这台机器上跑完了**（值只进变量、全程未打印）。结果两条：当前 tracked 工作区命中 **0**；全历史命中只有 `ADMIN_PASSWORD`（2 笔＝`817e7d3` 引入、`7eda4bb` 删除）⇒ 细节与普查表见 §8.5／§8.6。形状普查（`secret_shape_scan.py`，结构上不输出值，`--selftest` 能红）仍在，但**它的 0 不能读成"没有明文"**——这条教训也写在 §8.5 |
| **O-6** | **新出现的一条（A-3 反查出来的）**：`requirements-dev.txt` 钉 `pytest>=7.4,<9`，而 `CVE-2025-71176` 的修复在 **9.0.3** ⇒ **在册上限正好挡住修复** | 开发工具轴那 5 条里的 1 条能否清零 | ✅ **同日已按你的授权执行**：先在"候选依赖 + 只换 pytest 9.1.1"的**隔离环境**上跑全量（1650 passed / 10 skipped / 18 deselected / 137 warnings / cov 85.25% / rc=0，两场逐字相同），再改 pin 为 `pytest>=9.0.3,<10`，并用 `pip-audit --no-deps` 钉住新范围复算 ⇒ 旧范围 **rc=1**、新范围 **rc=0**。⚠️ **Linux 那条腿没跑过**（本机 Windows），CI 才是决定性证据 ⇒ 见 O-5 |
| **T7** ＝ O-5 后半 | **真实语料写进真实库**要不要在本窗口做 | D2 所签的检索现量会不会当场过期 | **已定（Q5）：本窗口不动**，另开一票。三条理由：你要的 CI 证据链不依赖它（CI 跑 `pytest --cov` 与 `pip-audit -r requirements.txt`，都不连真实 Chroma）；它一动在册那批绿灯读数（`67/67`、`1650 passed/cov 85.25%`）就不是你签的了；默认 Chroma 落点被 `docker-compose.yml:47` bind-mount 进容器 ⇒ 验收前必须先建副本 |

**B. 助手侧：已做完的与还欠的（接手会话逐条核过，别再当"待办"引用）**

✅ **同日做完（都不花凭据、零远程调用）**
- **A-1**：登记表里两条"待核"证结——`1839` 判不适用（**带失效条件**）、Chroma `45830/45833` 判**版本适用而形态不暴露**。
- **A-2**：`torch 2.6.0+cpu` 的扫描盲区消除（摘掉本地标签按实装上游版本补审出 22 条），**但没有清零**。
- **A-3**：开发/构建工具那 5 条逐条给触发前提/平台条件/修复版本（见 `residual-risk-review-devtools-20260929.md`），
  反查出 **O-6** 这一件要 Owner 答的。
- 原 §4B"9 条需另行核实适用性"这条**已做完**，现量分布是 **2 判不适用 / 2 判版本适用但形态不暴露 / 5 只能靠限制条款接受**。
- 带凭据外发面的**形状**普查已做（`secret_shape_scan.py`，结构上不输出值，`--selftest` 能红）；
  它覆盖不到的**按值**反查是 **O-2**，只能在你机器上办。

⚠️ **仍然欠的（要授权或要凭据，我不擅自动）**
- 真实 rerank 一次性隔离验收（等 **O-1** 完成并告知后，按既有授权只跑一次，记模型名/降级/`(法名,条号)`；
  题集是 24 条断言但 3 模型轮换 ⇒ 一轮 ≤21 次调用；**验收前必须先建副本**，默认 Chroma 落点被 compose bind-mount 进容器）。
- 依赖升级选型（`pip-audit` 的红**不是探针能减的**，判据见计划 §5.1/§5.2；分案口径在
  `docs/assistant-briefs/t7-dependency-upgrade-options-20260927.md`，**尚未选型**——升级会牵动 BGE 向量空间，属 C 档另案）。
  ⚠️ 两个"接受"别混：**本轮这张登记表**（`residual-risk-review.md`）从头就是"未接受、未忽略、未解除"，
  复审最迟 **2026-10-05**（今天 09-29，还没到）；我此前说的"**已到期**"指的是**更早那份 09-07 的 Risk Accepted 记录**
  的有效期过了（出处：`t7-dependency-upgrade-options-20260927.md:40`，以及
  `docs/pending-owner-actions-20260926.md:29` 早就澄清过"到期的是旧那份记录的有效期，不是本轮重扫这份"）。
  ⇒ 别读成"本轮的接受到期了"，那是两回事；措辞已按此收窄。
- 带**真凭据**的外发面实跑普查（rerank / 云端嵌入 / LLM 调用本身 / MCP / `/api/chat/transcribe`）——本轮**一次都没进样本**，
  因为驱动把 `RERANK_ENABLED` 关了；这条要么等凭据轮换后实跑，要么另开一票用假端点桩住。

**C. 本轮明确没做（一条不省）**

未把**候选代码分支**合入 `master`（注意区分：本会话的文档/证据提交本身是直接落在 master 上的，
笔数与清单看现量 `git log --oneline 14a04ca..HEAD` 与逐笔 `git show --stat --name-only <sha> -- backend/`，
**不在这里抄数**（抄了下一笔就过期）。⚠️ 但也**别说成"backend 恒为 0"**：早期几笔只动 `docs/` 与 `dispatch-output/`，
而 O-6 那笔按 Owner 授权改了 `backend/requirements-dev.txt` 一行——生产码 `backend/*.py` 仍一个没动）。
未 push、未建远端分支/PR、未部署、未启动生产容器、**未写真实库**（应用路径场用空副本集合）、
**未调用生成模型与真实 rerank**、**未代 Owner 接受任何风险**、未动凭据与服务器侧 `.env`、未改共享 `backend/venv`、
⚠️ 但**为隔离变量临时动过 `%TEMP%` 那个副本树 scratch venv**（只把 pytest 8.4.2 换成 9.1.1，`pip freeze` 前后只差一行；
跑完已还原，还原后的 freeze 与改动前逐字节相同），也**没**跑通 Linux 那条腿——见 devtools 件「三之补」⑥，
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

## 7. 补记：接手会话（同日更晚，执行 `2026-09-29-local-candidate-decision-and-release-prep.md`）

> 本节只列**改动与新增事实**；逐条现量、命令与限制在计划文件末尾的 **§5「发布准备结果」**（那里是本会话唯一的结果落点，别在两处抄数）。
> 上面 §1–§6 讲的是本会话**之前**的探针轮与签字页轮，那两轮的历史记录不重写。

**阶段判定：③ 候选受阻、发布准备已备妥。** 主线 `master`、候选 `codex/local-candidate-closeout` 两个 SHA 以
`git -C $Repo rev-parse HEAD` / `git rev-parse --verify refs/heads/codex/local-candidate-closeout` 现量为准；**未合入、未推送**。

**签字页被改实的四处（Owner 引用时按新措辞，别再从旧正文转抄）**

1. **`trust_remote_code=False` 那条不只是"限缩到 G3a/G3b"** —— 接手会话补了一条会实质改变签字含义的版本证据：
   候选**实装** transformers 落在那条模型 config RCE 通报的受影响区间内，而公告原文写明该缺陷**绕过 `trust_remote_code` 机制**。
   ⇒ 所以签字页第三栏"不放开 `trust_remote_code`"是**使用限制**，**不是**该通报的缓解证明；页内已明写。
   另外旧措辞"`G3d/G3e` 读数为 `[]`"不准确（它们传了别的实参，不是实参为空），已按读数改正。
2. **`[6R]/[7R]/[8R]` 这个假出处在 4 份文档里，不是计划说的 2 份**；四份都改了，单一真源落在交接书新增的 **§4.1**。
   同处另更正一条计划漏掉的错：**第 9 步那次 rc=1 是扫描器 `pypi.org` ReadTimeout，正文却把它写成"漏洞非零的红"** ——
   纪律 README 有写、正文自己混了。原文日志一字未改。
3. **`:104` 那句"值已轮换，旧值失效"已删**，改成"轮换状态由 Owner 掌握，本注释不作断言"。
   归属先核过：该文件**早已入库**（`7eda4bb`）、两棵树同一 blob、改前工作树干净 ⇒ 不是别人未提交的活
   （我记忆里"只能 patch 不能 apply"那句已过期）。
4. **D6（`CVE-2024-7774`）判结**：上游 PyPA/OSV 把 **langchainjs（npm）** 的缺陷挂到了 PyPI `langchain` 名下 ⇒
   **对本项目 Python 依赖不适用**。⚠️ 边界写进了页内：公告点名的汇 `getFullPath` 在实装包 1326 个 `.py` 里 0 命中，
   但 **`mdelete` 同名存在**，所以依据是"汇不存在＋生态归属 JS"而不是"点名符号全无"；**原始告警保留、未加 `--ignore-vuln`**。

**新增的两条在册范围事实（这是本轮对 D2 最实际的改变）**

- **分母不是 26**：应用运行时 26 条之外，实装环境另有开发/构建工具（`pytest`/`setuptools`）那一轴 **5 条**，
  `requirements.txt` 里根本没有这两个包 ⇒ **D2 那笔"应用运行时不升级不改码"的签字射程不含它**，签字页新开「二·补」，第六条加 6a/6b 两条"签了也不解除"。
- **`torch 2.6.0+cpu` 是盲区不是零风险**：扫描读数给它的是 `skip_reason`（PyPI 无该分发）⇒ **一条漏洞读数都没产生**；
  而解析集里那个 torch 是**另一个版本**，不能替实装版本说话。对官方通报的逐条核查**未完成**，记"未核实"。
- 复扫本身：解析集/实装集相对 09-28 **零新增、零消失、零版本漂移**（比的是 (包, ID∪别名) 集合对称差，不是比条数）。
  一次误跑在主工作区的读数**留盘不删**，它正好证 **`master` 今天仍是升级前的红**，成了"合入候选才降得下来"的依据。

**一条新立的技术判断（会影响将来任何"靠版本判不适用"的结论）**
`pip-audit` **只比本包版本，不评估公告里的跨包前提** ⇒ 登记表原先那句"候选 torch 不满足公告中 `torch<2.6`，所以 `CVE-2026-1839` 不适用"
当时**一手没证到**，已把那行降回**待核**；同形另一条是 `CVE-2026-45833` 对嵌入式 chromadb 0.4.24 的适用性。
> ↩ **这两条待核同日已证结（Owner 选的是"继续做不花凭据的取证"）**，且**这条"新立判断"本身有一半是我读错了字段**：
> 1. **`CVE-2026-1839` ⇒ 判对本环境不适用**。跨包前提**就在同一份扫描 JSON 的 `description` 里**（我当时只查了 `fix_versions`），
>    公告原文要求"配合 PyTorch **2.6 以下**使用"，实装 `2.6.0+cpu` 不满足；应用侧 `Trainer` **0 引用**；
>    另实测本机 `torch.load` 默认**已是** `weights_only=True`（一枚 `__reduce__→os.system` 的 pickle 被 `UnpicklingError` 拦住）。
>    ⚠️ **带失效条件**：这条成立**依赖 torch 保持 ≥2.6**，将来为别的事降 torch 就重新适用——签字时要连失效条件一起签。
> 2. **`CVE-2026-45830` / `45833` ⇒ 核实结果与原先猜测方向相反**：公告写 "0.4.17 or later"，实装 0.4.24 **按版本确实适用**；
>    不暴露**全靠**"不起 Chroma HTTP 服务 / 不服务化 / 不多租户"那条限制撑着（compose 只有 backend/frontend/caddy，
>    `rag_chain.py:123` 走 `persist_directory` 嵌入式，应用侧 `HttpClient`/`start_api` 引用 **0**），
>    且两条 `fix_versions` 并集为空 ⇒ **没有升级即消的路**。**所以不能读成"查过了、不适用"**；删那条限制 = 这两条立刻适用且无补丁。
> 3. 9 条无桩通报的现量分布随之变成 **2 判不适用 / 2 判版本适用但形态不暴露 / 5 只能靠限制条款接受，待核 0 条**。
> 4. **又立了一条判据，因为我在这上面连错两次**：同一通报在 JSON 里可能有**多条来源行**，
>    **单行 `fix_versions` 为空不等于"无补丁"**。登记表那句"为空的 N 条"原写 **3** 却列了 4 个编号（数错），
>    我改成 **5（加 `CVE-2026-5241`）**又是一错——`5241` 另一行给了 `5.5.0`；**正确判据是按共享 ID 聚类后跨来源取并集**，答案是 **4**。
>    复算件 `b_no_fix_union.py`（两轴共用；`--selftest` 用"单行判空会多出 `5241`/`2953`"证明尺子能红），
>    它顺带从原始读数现算出 **唯一通报 26 == 唯一 CVE 26**，与登记表分母**各自独立**对上，不是抄的。

**真实 rerank：仍未执行，且预检查出了执行前必须知道的数**
题集是 **24 条断言**（7 意图 + 7 召回 + 3 引用校验 + 4 复杂度 + 3 自检），脚本内**无重试/预热循环**，
但 rerank 按 **3 个模型轮换** ⇒ **"跑一轮"最坏约 21 次远程调用**，不是 7 次。
最容易出事故的一条：`rag_chain.py` 的默认 Chroma 落点被 `compose:47` **bind-mount 进容器**（主树那份是真实库、候选树是空桩会让召回全不命中）
⇒ 验收**必须**先把 `CHROMA_DIR` 指到真实库副本，副本**本轮尚未建**。
⚠️ **本会话刻意没有读 `backend/.env`**：当前这个阻塞点的成因就是上一轮"检查本地配置"把凭据打印进了工具输出，
所以涉及 `.env` 取值的两项只能写成"由 Owner 执行前确认"，不给"我替你看过、没问题"的假安心。

**远端与 CI（两处与既有记载不同）**
- 本机 `git ls-remote` **rc=124 办不动**（https、未配 `credential.helper`）⇒ 实时远端改走匿名 API 读到：远端**只有 `master` 一条**，
  本地那个跟踪引用停在 08-25，**别当现状**。
- `pull_request:` **没有分支过滤** ⇒ 开 PR 也会真跑 CI（不必推 master）；而 `pip-audit` 那步**没有** `continue-on-error`/`if:`，**红是硬红**。
  三条可运行路径写在计划 §5.5，默认建议"推快照分支 + 开 PR 取其余步骤证据并如实标注 audit 预期红"，**推不推由 Owner 对确切对象决定**。

**接手时复量的仪表状态（都是本会话实跑，不是继承的结论）**
`b_probe_claim_check.py` 每次改完复跑 **全绿 rc=0**（未重跑 `b_probe_claim_mutants.py`——它原地覆盖交接书，计划明令本轮不跑）；
新增 `b_scope_recount.py`（三轴对账 + 闭合检查）与 `secret_shape_scan.py`（形状普查，结构上不输出值），
**两件都先做过负向自证**：塞一条不存在的 CVE ⇒ 前者 rc=1；造一枚假 key ⇒ 后者能红。
保护对象复验落**新日志名** `protected-takeover-20260929.log` ⇒ 全部未变，未覆盖任何旧证据。

**不花凭据的取证（Owner 选的一条：不轮换、继续做不花凭据的取证）**
本节「一条新立的技术判断（会影响将来任何"靠版本判不适用"的结论）」里那**两条待核**，用的全是**已有的一手读数 + 只读代码勘察**，
**没发一次远程调用、没读 `backend/.env`、没碰那把 key**：
- 公告正文就在我们自己的那份 JSON 的 `description` 里 ⇒ 不必外求；这是我上一段说"一手没核到"的真实反证——**我查错了字段**。
- 部署形态用只读命令核：`docker-compose.yml` 的服务/端口清单、`rag_chain.py:123` 的 `persist_directory`、
  `HttpClient`/`chromadb.app`/`start_api` 的应用侧引用数 **0**。
- 判据落盘成 `b_no_fix_union.py`（**分析脚本随票入库，否则数字不可核**），两轴共用。

**我自己的事故（照实记，别只记别人的）——第一到第七次；第八次记在下面"O-6 执行轮"里**
用 Edit 改登记表时，`old_string` 含 `## 可执行分案` 标题而 `new_string` 忘了带回 ⇒ **同一节标题被静默删过两次**，
第二次才想起本仓踩过这坑，两次都由 `grep -n '^## '` 抓回补上。
⇒ 结论：**改 md 后数标题是收尾动作，不是可选检查**。
**第三次是 `git diff --check` 自己红了一次**：我往计划文件尾部多写了一个空行，`rc=2`（`new blank line at EOF`），裁掉才转 0。
前两次的教训我在文档里写过"提交前要跑这条检查"，这一轮仍是在跑之前先说了"做完了" ⇒ **收尾顺序不是知识问题，是习惯问题**。
**第四次是同一个数连错两遍**：登记表"候选需求集扫描里 `fix_versions` 为空的通报数"原写 **3**（却列了 4 个编号），我发现不一致后"改正"成 **5**，
而**5 也是错的**——因为我是**按单行**数空，`CVE-2026-5241` 有一条来源行给空、另一行给了 `5.5.0`。
⇒ 教训：**发现文档里"数"与"清单"不一致时，先跑复算再动笔，别用另一种同样没核过的算法去覆盖它**。
最终 **4** 由 `b_no_fix_union.py` 定，且它自带能红的对照（单行判空会多出 `5241`；torch 轴会多出 `2953`）。
**第五次是把两条轴混了**：我在计划末尾写"候选与主线无共同祖先"——**rc=1 那条是 `master` 与 `origin/master` 之间的**，
候选与 `master` 实测 `git merge-base` **rc=0、共同祖先 `aec8d5c`**。⇒ 同一个"rc=1"结论换对象就完全反了，落笔前把命令连对象一起重打一遍。

**第六次是提交信息复用错了**：`21eeda5` 我直接沿用了上一条 A-3 提交的标题，而那笔内容其实是汇报 §4 台账重排 ⇒
两笔同号不同事。发现后 `git commit --amend` 改正（未推送、只含我自己的一个文件），现 SHA 以 `git log --oneline` 现量为准。
**第七次是又一次把退出码走了管道**：验"新 pin 能不能清零"时我写 `pip_audit ... | tail -3; echo $?`，
得到"旧范围也 rc=0"的**假读数**——那是 `tail` 的码。不落管道重跑才是 **旧 rc=1 / 新 rc=0**。
⇒ 这条教训我已经在文档里写过第三遍，仍在犯 ⇒ **管道后的 `$?` 一律不算退出码**，取码必须 `> file 2>&1` 之后单读。

**O-6 执行轮（Owner 授权"按你的建议执行即可"，同日更晚）**
按我自己写的顺序办：**先跑全量，绿了才动 pin**。
- **第一次跑其实变量没隔开**：直接拿 `backend/venv`（pytest 9.1.1）跑 ⇒ 它也绿，但 warnings 从 137 涨到 240，
  而那套的应用依赖本来就旧（fastapi 0.110.3 / starlette 0.36.3 / httpx 0.27.2 vs 候选的 0.141.1 / 1.7.0 / 0.28.1）。
  ⚠️ **所以我没有拿那场当结论**——它证明不了"是 pytest 9 造成的"。
- **隔离腿**：在副本树 venv 上 `pip install --no-deps pytest==9.1.1`（依赖本已够：pluggy 1.6.0 / packaging 23.2 / iniconfig 2.3.0），
  `pip freeze` 前后**只差一行** ⇒ 真单变量。结果 `1650 passed / 10 skipped / 18 deselected / **137 warnings**`（与 8.4.2 基线相同），
  覆盖率腿同环境 `cov 85.25%`、rc=0，**复跑两场逐字相同**。**240 那批警告属旧依赖集，不属 pytest 9。**
- **唯一差值已归因**：探针 `compile_event_total` 9826 → **9830（+4）**；8.4.2 两场都 9826、9.1.1 两场都 9830 ⇒ 稳定非抖动；
  而 `net_event_total/kinds`（348/206）、`collected`、`pytest_exitstatus`、`imports_watched` 全同，
  逐条 `net_events` **归一化端口后**只剩两条差（是我自己的 `subprocess.Popen` 参数里的树目录名）⇒ 判为框架自身编译面，
  **机制未追到具体模块**，按"已归因、未定死"记。
- **改 pin 与复算**：`pytest>=7.4,<9` → **`pytest>=9.0.3,<10`**（下限=修复版本，附两行注释说明为什么是这个数），
  钉住新旧范围各跑一次 `pip_audit --no-deps` ⇒ **旧 rc=1 / 新 rc=0**。
- **还原**：临时动过的那个 `%TEMP%` 副本树 scratch venv 已装回 8.4.2，`pip freeze` 与改动前**逐字节相同**（`diff` 空）。
  ⚠️ 这带来一个**必须一起读的后果**：在册 B 轮"实装集"读数（pytest 8.4.2）仍可复现，但它**比新 pin 旧**；
  日后若有人据此说"这条还在"，那是环境陈旧而非 pin 失效——全新安装才是新状态。
- **没验证到的**：Linux 那条腿（通报前提正是 UNIX `/tmp/pytest-of-{user}`）；CI 真实运行；dev 轴在 CI 里本来也不被审计
  （`ci.yml:46` 只 `pip-audit -r requirements.txt`）。⇒ 判定仍是 **③**。
- **仪器为此改了两处，其中我自己又错一遍（第八次）**：给读数加 `pytest_version` 字段之后，
  我把复算件里"compile 恒等 9826"和"两腿零差异"改成按版本分组，**第一版给缺字段的旧读数写了个"就当 8.4.2"的默认值**
  ⇒ 结果今天那三场 9.1.1 的腿（产自字段引入前，不带字段）被并进 8.4.2 组，"双跑差分"比的其实是两场不同环境，
  复算件报"两腿 compile 不一致"——**它是对的，错的是我的分组**。改成**"不声明就排除"**并补跑一场 8.4.2 配对，
  现参与比对的是 `-204600` 与 `-205049`（都声明 8.4.2、compile 都 9826）⇒ **`67/67 rc=0`**。
  ⚠️ 顺带一条反证：那套旧依赖环境的读数连 `net_event_total` 都不同（**346 vs 348**）⇒ "换 venv 比较"根本不能归因给单个包。

**现在能推动的（详见计划 §5.6 的分档表）**：Owner 侧 O-1（轮换那把已暴露的 rerank key）→ 才有一轮真实 rerank 现量；
O-4（D2 逐项落笔，含新出现的两轴 + 两条**失效条件**）→ 才谈合并窗口；O-2/O-3/O-5 各自独立。
助手侧三条取证活**同日全部做完**（都不花凭据）：A-1（两条待核证结）、A-2（摘掉 `+cpu` 标签补审 torch 那 22 条，见「二·补」⑦ 与 torch 单轴件）、
A-3（开发/构建工具那 5 条逐条给触发前提/平台条件/修复版本，落在 `residual-risk-review-devtools-20260929.md`）。
⇒ **A-3 反过来给 Owner 添了一件新的、只有一词要答的**（计划 §5.6 记为 **O-6**）：`pytest>=7.4,<9` 的**上限正好挡住那条通报的修复版本**，
而 CI 是 `ubuntu-latest` 且真跑 pytest ⇒ 平台与调用面两个前提**都成立**，这条**不能记成"构建期专用 ⇒ 无风险"**。
当时给的是二选一（放宽上限 / 维持并显式接受限制）；**同日更晚按 Owner 授权选了"放宽"并按上面 O-6 执行轮办完**，
所以这里留下的待办不再是"选哪条"，而是 **O-5：让 CI 真跑一遍，把"Windows 上兼容"升级成"CI 上已证"**。

## 8. 补记：grilling 对齐结果（第一轮 Q1–Q5，第二轮 Q6–Q14）与远端现量

**逐题裁定（Owner 一题一题答的，不是我推的就生效；第二轮的头一题答完即 09-30）**

| 题 | 裁定 | 自然复现点（若不处理会变成什么） |
|---|---|---|
| Q1 要不要远端 CI 证据 | **要** | 已排进下面的顺序 |
| Q2 那把已暴露的 rerank key | **暂时放一边**（本窗口不轮换） | **合入 `master` 之前必须回到你手上**；若最终不轮换 ⇒ 转成在册的显式接受 + 失效条件，不能只留"放一边"。**（此行的"合并前"由 Q7＋§8.5 更正：真正要防的是本地历史里的明文，属 Q14 那张票）** |
| Q3 推送前置 | **先把仓库转 private**，再推**一次性快照分支**（永不 force，**推这一下由你按回车**），再取 CI 证据 | 形状普查已做完且干净（193 个提交的树 0 命中 / 193 条提交信息 0 命中，栽桩对照 `PLANTED_RC=1`）⇒ 它不再是拦路的那件。**⚠️ 这半句 §8.5 已撤回**：形状普查量不到"没有形状的任意口令"，而那个明文在 `master` 与候选的**共同祖先**里 |
| Q4 D2 什么时候落笔 | **CI 结果到手之后签**（只签一次，签的就是准确文本） | 见 §4A T1 |
| Q5 真实库入库 | **本窗口不动** | 另开一票；**先建副本再验收**（默认 Chroma 落点被 `docker-compose.yml:47` bind-mount 进容器） |
| Q6 窗口终点画在哪 | **一路做到合 `master`**，部署选型与真实入库留票 | 现量：`master` 领先合并基线 24 笔、候选 4 笔 ⇒ 漂移已在发生（dev-pin 只活在 `master`） |
| Q7 已暴露的 rerank key 怎么落笔 | **不轮换，但落成在册接受 + 失效条件**（真实外联验收或上线部署前必须先轮换） | ⚠️ 我上一轮说它的复现点是"合并前"——**那句被 §8.5 更正**：合并不会放大它，形状普查与按值普查都证明它不在 tracked 对象里 |
| Q8 O-2 按值反查排在哪儿 | **签字前**（比合并再早一格） | 已由助手在 Owner 机器上代跑完（值未打印），见 §8.5 与 §8.6 那张表 |
| Q9 怎么合 | **`git merge --no-ff`** 一笔 merge commit | rebase／squash 会重写候选 SHA ⇒ 交接书那 **19 处** `fbc29e8` 引用当场变死号；回退＝`git revert -m 1`；候选分支合并后**不删** |
| Q10 新增项进签字格还是附注 | **折进已有的两栏**（「限制清单与自动失效条件」＋「签了也不解除」四→**五**条）；④⑤⑥写成"接受范围"的括注 | 栏数＝Owner 逐栏落笔的次数；把读数说明做成签字格会稀释真要人负责的限制 |
| Q11 `.env.bak` 只被 per-clone exclude 兜住 | **补 `.gitignore` 一行**（已执行，见 `318c588`） | 边界：只挡以后误提交，不消除磁盘明文（属 O-3）；`.git/info/exclude:9` **没删**，删了反而立刻扩大本机面 |
| Q12 部署那批现量怎么处置 | **只登记**，本窗口一处文档不改 | 已落 §8.7 |
| Q13 那段含明文的历史推不推 | **A：推无父孤儿快照** | §8.6；连带后果：**PR 路按构造关闭**，push 触发是唯一路，"触发配置略异"这条限制**必然**进 D2 |
| Q14 合并之后第一票开什么 | **凭据与外发面**（O-1＋O-3＋历史明文处置） | 部署票第二；⚠️ 若将来要把仓库转 public，唯一能消除历史明文的是重写历史 ⇒ 会作废 19 处 `fbc29e8`，是本轮**唯一会推翻已裁事项**的情形 |
| Q15 「为什么要转 private」（Owner 回头审我给的前提） | **不转，仓库保持 public** | 我那条前置的立足点（只靠形状普查）已被按值普查取代；且 private 吃 Actions 分钟配额而我读不到余额 ⇒ 反向代价实测存在。详见 §8.8① |
| Q16 外发的内容轴怎么处理 | **剔掉 `diag/frozen-index-004` 与 `-005` 两个目录（74 文件/296.7MB）再推** | 依据：两树 `--collect-only` 差分 `1678==1678`、错误行 `0==0`；`frozen-index` 在 backend 代码里 0 引用。⚠️ 连带后果两条：① 这次 CI **不会整体绿**（`pip-audit` 那步没有 `continue-on-error`，见 §8.8⑤）；② 在册文档里 6 处"13 位/字母数字"式旁路描述会首次进公开仓（见 §8.8⑥） |

另外两条一并定了：**O-2 按值反查**第一轮说"排在合并前"，第二轮（Q8）收窄为**签字前**，并且**已由助手在 Owner 机器上代跑完**（§8.5/§8.6，值全程未打印）；`2026-10-05` 复审日期**不延长**。

**远端现量（每条给命令；本轮全部匿名只读，未发任何写请求）**

- `curl -sS -o /tmp/ghrepo.json -w "%{http_code}" https://api.github.com/repos/wjt-code-design/fazhi-assistant`
  ⇒ HTTP **200**，`private=false`、`visibility=public`、`default_branch=master`、`pushed_at=2026-09-17T15:15:31Z`。
  ⇒ **Q3 的前置还没满足**（仓库仍是 public），所以这一步我停在这里，没有推。
- `GIT_TERMINAL_PROMPT=0 git ls-remote --heads origin` ⇒ rc=**0**，远端**只有一条分支** `master` = `985d53e4ee81efc066cc6915abcba98954e7d408`（提交时间 2026-09-17T15:15:22Z）。
- `curl … /repos/…/actions/runs?per_page=3` ⇒ `total_count=18`，最近三场全是 `event=push`、`head_branch=master`、`conclusion=failure`
  ⇒ **远端 `master` 自己是红的**，且这 18 场里**没有一场是 PR 事件**（PR 这条路在本仓从未真跑过）。
- `sed -n '1,10p' .github/workflows/ci.yml` ⇒ 触发只有 `push: branches:[main, master]` 与**无分支过滤**的 `pull_request`，**没有 `workflow_dispatch`**
  ⇒ 想让 CI 跑我们的内容，只有 PR 或"改那行分支名单"两条路。
- 本地 `git status --porcelain` ⇒ tracked 修改 **0** 条，未跟踪 528 个（别 sessions 的产物，不入库）；HEAD = `0eb2b08`，候选 `fbc29e8` 仍未推未合。

**我在这轮又错一遍（第九次，记账）**：先前"本地与远端**无共同祖先**"那次 `merge-base` 是拿**本仓陈旧的 `refs/remotes/origin/master`** 量的，
不是远端真实头（本轮 API 读到远端头是 `985d53e4`，比在册 ref 新）。方向不变——远端 09-17 之后没被推过、我们的提交从未上远端——
但**精确证据要等推完分支用匿名 compare 读 `merge_base` 与 `status`**，别拿我那句旧结论当已证。

**还差一岔（唯一要你答的，一词即可）：CI 怎么被触发。**
无共同祖先时 GitHub 建 PR 的 merge ref 可能失败 ⇒ checks 不跑或状态不可用。我的推荐：
推分支后先跑 `curl … /repos/…/compare/985d53e4…<快照分支>` 读 `merge_base`/`status`——
**能比就开 PR**（零管线改动）；**GitHub 判"无共同祖先"就退回**在**那条一次性分支自带的** `ci.yml` 里把分支名加进 `on: push.branches`
（push 事件用的就是被推分支自己的 workflow 定义，不动 `master` 的管线，且那条分支永不合并）。
代价要摊开：这样取到的 CI 证据来自**触发配置略有差异的分支**（步骤相同），这条限制得写进 D2 的依据里。

**执行顺序（已对齐，等你那一步）**：你把仓库转 **private** → 我推一次性快照分支（你按回车）→ 匿名 compare 判形 → PR 或 push 触发取 CI 绿 → 我起草 D2 文本给你签。
**本轮明确没做**：未推送、未建远端分支/PR、未改远端可见性（也没这个权限）、未改 `ci.yml`、未写真实库、未轮换凭据。

### 8.1 补记 2：为这条路做的可跑性核验（同日最晚，全部只读／无副作用）

- **"候选能不能干净合进当前 `master`"已证**：
  `git merge-tree --write-tree --name-only master codex/local-candidate-closeout` ⇒ rc=**0**，结果树 `7e2a758`，**冲突文件 0 个**。
  该树里 `backend/requirements-dev.txt:4` 是 `pytest>=9.0.3,<10` ⇒ **CI 会装 9.x**，那条没跑过的 Linux 腿拿到的才是有效证据；
  该树 vs `master` 差 **7** 个文件（＝候选带进来的那批）、vs 候选差 **83** 个。
  ⚠️ 这只证"能干净合并"，**不证"已合并"**——`master` 一个字没动（D2 未签，D3 在等它）。
- **HTTPS 传输现在不可用**（这条影响"什么时候能推"）：`curl https://github.com/` 三次全 `HTTP=000`（连不上 `github.com:443`），
  同一时刻 `api.github.com` ⇒ 200；`git push --dry-run` ⇒ rc=**128** "Failed to connect to github.com:443"；
  `git ls-remote`（HTTPS）本轮先 rc=0、后 rc=128 ⇒ **时好时坏，不能当成已具备的能力**。
- **可用的那条传输是 SSH over 443**：`ssh -o BatchMode=yes -p 443 -T git@ssh.github.com` ⇒ `Hi wjt-code-design!`（rc=1 是 GitHub 不给 shell，正常）；
  `git ls-remote --heads ssh://git@ssh.github.com:443/wjt-code-design/fazhi-assistant.git` ⇒ rc=**0** 并读到远端 `master=985d53e4`。
  ⇒ 真要推时**用命令行里内联的 ssh URL**，不动 `git config`（在册的 `credential.helper=manager` 是否可用**仍未证**——dry-run 从没跑到过鉴权那步）。
- **一件只能在 GitHub 页面上确认的**：仓库转 private 之后，Actions 消耗的是套餐分钟数（Free 档每月 2000），而这条 job 要装 torch CPU 再跑 1650 条测试。
  分钟数若已用尽，private 里的 CI 只会排队不出结果。匿名 API 读不到（`/repos/…/actions/permissions` ⇒ **401 Requires authentication**），所以我只能说"未见异常"，不能说"够用"。

### 8.2 补记 3：CI 触发路已定，并据此省掉一次本地全量预跑

- **触发路（Owner 已裁）**：推完快照分支后先跑匿名 compare 读 `merge_base`/`status` ⇒ **能比就开 PR**（零管线改动）；
  `merge_base` 为 null（无共同祖先）就**不开 PR**，改在**那条一次性分支自带的** `ci.yml` 里把分支名加进 `on: push.branches` 再推一次。
  `workflow_dispatch` 排除：GitHub 只列默认分支上存在的 workflow，而我们改 `ci.yml` 要先让它进默认分支就得先合 `master` ⇒ 循环依赖（D2 未签）。
- **我先前那句"合并树 vs `master` 差 7 个文件"已经过期**（记账，第十次）：`7e2a758` 是在我那两笔文档提交**之前**算的；
  文档落进 `master` 后同一比较变成 8 个文件。派生的树号必须重算，别拿旧号继续推。重算：
  `git merge-tree --write-tree --name-only master codex/local-candidate-closeout` ⇒ rc=**0**，新树 **`cdcf579`**（无冲突）。
- **省掉预跑的依据是逐字节比对，不是"改动笔数为 0"的推断**：候选带进来的 7 个文件在合并树里的 blob 与候选侧**全部相同**
  （`git rev-parse <候选>:<file>` 与 `git rev-parse cdcf579:<file>` 逐一相等：`knowledge_service.py`、`main.py`、`requirements.txt`、
  `tests/test_pdf_upload.py`、`tests/test_request_bootstrap.py`、`tests/test_upload_rate_limit.py`、`t7-dependency-upgrade-options-20260927.md`）。
  ⇒ **候选那份六步全绿读数可迁移到合并树**，不必在 Windows 上再跑一遍全量（那还得临时再动 scratch venv）。
- ⚠️ 但迁移有一条边界要说清：`backend/requirements-dev.txt` **不在差集里**，合并树取的是 `master` 那份 blob `a71ea7c`
  （候选那份是 `339f391`），内容就是 `pytest>=9.0.3,<10` ⇒ **CI 装的是 9.x**，而那 1650 条本地腿是在 8.4.2 与 9.1.1 两套 venv 上分别跑的。
  ⇒ 结论：CI 这次要买到的新信息只有两件——**Linux 这条腿**、以及**全新安装依赖集**下的结果；本地已有读数不覆盖它们。

### 8.3 补记 4：一条会把"形状普查干净"读成"口令安全"的坑（Owner 授权后已修）

同一轮派出去的部署勘察回来说有一条比前五题都硬的现量，我自己复现了：

- `backend/.env.bak-20260910-pre-qwen38:11` 的 `ADMIN_PASSWORD=` 是**非空、13 位、字母数字混合**的字面值（值未打印、未入库、未发到聊天）。
- `git check-ignore -v` 该文件 ⇒ 命中的是 **`.git/info/exclude:9`（`.env.bak*`）**，**不是** `.gitignore`。
  ⚠️ 这就是要害：`.git/info/exclude` 是**每个克隆各自**的文件，不随仓库走 ⇒ 别人 clone、换机器、重装环境时那行值**没有任何规则挡**，一次 `git add -A` 就把管理口令提交进主线。
- 我此前那句"推送对象集合不带凭据形状"的普查**覆盖不到它**，两个原因叠在一起：① 它只扫 tracked 对象（未跟踪文件结构上不在面内）；② **任意口令没有形状**（`sk-`／`AKIA` 那类前缀对口令不适用）⇒ 形状尺子量不到，只有**按值**反查能量到（＝O-2）。
- 同轮量到的两个数（这才是"不会带出口令"该有的说法）：**未跟踪且未被忽略 528** 个文件，其中写着非空 `ADMIN_PASSWORD` 的 **0** 个。
  命令：`git status --porcelain -unormal` 数集合，再对每个文件正则 `^ADMIN_PASSWORD=.+$`（只打印命中数，不打印值）。
- ⚠️ 文档口径不一致（登记不裁决）：`docs/progress-handoff-report-20260925.md:442-443` 说口令字面值"逐字等于 3 份 `.env`"，
  而勘察实测**含字面值的文件是 8 个**（3 份 `.env` ＋ 5 个 `dispatch-output/**.bak`）。那 5 个 `.bak` 落在 `.gitignore:88 dispatch-output/config-backups-*/` 与 `:89 *.bak` 里 ⇒ 未被跟踪，但**文档那句"3 份"是窄的**。

**已修的这一条**：`.gitignore` 环境变量段补一行 `.env.bak*`（在 `.env`／`.env.local` 之后），把兜底从"本机私有"变成"随仓库走"。五条验证：

1. 规则本身有效（临时仓、无 `info/exclude` 干扰）：`git check-ignore -v backend/.env.bak-20260910-pre-qwen38` ⇒ `.gitignore:31:.env.bak*`。
2. **不误伤已跟踪文件**：`git ls-files | git check-ignore --no-index --stdin -v | grep -c '\.env\.bak'` ⇒ **0**。
3. 负对照（必须不命中）：`.env.example`、`backend/.env.example`、`dispatch-output/*/.env.example` ⇒ 三条 `check-ignore` 全 rc=**1**。
4. `未跟踪且未忽略` 计数仍是 **528** ⇒ 这次改动没有悄悄缩小或放大那个集合。
5. ⚠️ 顺带量到一条**既有**卫生问题，不在本票范围、只登记不处置：`git ls-files | git check-ignore --no-index --stdin` 有 **72** 个"已被跟踪却又被忽略规则命中"的文件，
   归类是 `.gitignore:72`（69 个 `docs/benchmark_results/*2026*.json`）、`:48 *.log`（2 个）、`:80 dispatch-output/task1/`（1 个）。

**这条修的边界（别读成"泄露面消除了"）**：它只挡"以后不误提交"。那个 `.bak` 里的明文还在磁盘上，真消除属 **O-3 口令轮换**那一格；
`.git/info/exclude:9` 我**没删**（删了会让这台机器上的历史快照立刻变成"未跟踪且未忽略"，反而扩大面）。

### 8.5 补记 5：⚠️ 撤回一条我给错的推送前置——管理口令的明文**在本地历史里**，而形状普查量不到它

> 编号说明：**§8.4 是空的**。那节原计划写"部署现量"，写之前先量出了 §8.5 那桩更硬的事，于是部署输入顺延到 §8.7。
> 没把 8.5/8.6/8.7 往前挪号，是因为正文与台账里已有十余处按号引用它们，重编号的风险大于留一个洞。

按值反查（O-2 那条命令）我在 Owner 机器上跑了，**只打印长度和计数、没打印值**：

```
PW=$(grep -m1 '^ADMIN_PASSWORD=' backend/.env | cut -d= -f2-); 长度=${#PW}=13
git grep -l -F "$PW" -- .            → 0 个（当前工作区的 tracked 文件干净）
git log --all -S"$PW" --oneline      → 2 笔
负对照（不存在的串）                  → 0 / 0（尺子两端都能指对）
```

那两笔是同一个值的**加**与**删**：

- **引入**：`817e7d3`（2026-09-22），载体 `dispatch-output/t12-frontend-sweep-20260920/apply_case_domain_gate.py`——
  就是那句被打码规则"顺手"写成明文 pattern 的 `:104`。
- **删除**：`7eda4bb`（2026-09-26），提交主题本身就写着"把 `:104` 的明文口令改成形状规则"。
- 现量：**`817e7d3` 同时是 `master` 和候选的祖先**（`git merge-base --is-ancestor … ` 两个 rc 都 **0**）
  ⇒ **按普通分支推上去，GitHub 就会收到那个含明文口令的 blob**，即使分支顶端已经删掉了它。
  四棵顶端树（`master`／候选／`HEAD`／`7eda4bb`）命中都是 **0** ⇒ 只有**历史**带它。

**所以我要撤回一句自己说过的话**：Q3 那句"推送前置＝证明外发对象集合不带凭据形状，普查已做完且干净（193 树 0 命中）"——
**对这把凭据不成立**。原因两条叠着：① 那次普查扫的是**形状**（`sk-`／`AKIA` 那类前缀），而任意管理口令**没有形状**；
② 它扫的是**提交树顶端集合**，没有对历史做按值 pickaxe。09-26 那条"先轮换口令→再推"的原案本来就是为这件事立的，是我把它从关键路径上摘下来的。

**同时要说清没发生的事**：远端 `master` 仍是 09-17 那份、**我们一段历史都没推上去过** ⇒ 泄露面**没有扩大**，
现在改路线的成本是零。

### 8.6 补记 6：路线 A 已构造完并**按值**验过（尚未推送）

Owner 裁 A（推无父孤儿快照）。我把"要推的东西"做成了一个**可核的对象集合**：

- **合并树重算**：现号 **`50f519e`**（我上一条自己立的规矩第二次生效——`cdcf579` 已过期）。
- **孤儿提交**：分支 `snapshot/ci-fbc29e8-20260930`，`git rev-list <该提交>` ⇒ **1 笔**（`%P` 为空，**无父**）；
  `git rev-list --objects` ⇒ **2545** 个对象，对照 `master` 的 **4078** ⇒ 结构上不可能带上 09-22 那个明文 blob（它不在这棵树里，也没有父链可达它）。
- **相对合并树只偏离一行**：`ci.yml` 的 `branches: [main, master, "snapshot/ci-fbc29e8-20260930"]`。
  用 venv 解析过快照里那份（不是工作区那份）：`jobs=[backend, frontend]`、backend `steps=10`、`pull_request` 触发仍在。
  ⚠️ 走 A 之后 **PR 那条路按构造关闭**（无父 ⇒ 无共同祖先），push 触发是唯一路，所以 §8.2 那句"触发配置略异"的限制**必然**要进 D2 依据。
- **按值普查**（值只进变量，全程未打印；命令形态同 §8.5）：

  | 键（8 个密钥类） | 快照树命中 | 全历史命中 | 备注 |
  |---|---|---|---|
  | `ADMIN_PASSWORD` | 0 | **2** | 正对照用它：`git grep -l -F "$PW" 817e7d3` ⇒ **1** ⇒ 尺子能红 |
  | `LLM_API_KEY`/`JWT_SECRET`/`EMBEDDING_API_KEY`/`RERANK_API_KEY`/`ZHIPUAI_API_KEY`/`DASHSCOPE_API_KEY`/`SILICONFLOW_API_KEY` | 0 | 0 | 全部无命中 |
  | 负对照（不存在的串） | 0 | 0 | — |

  另有 5 个键在快照里命中非零，**都是模型名字符串**（`LLM_MODEL`、`RERANK_MODEL`、`RERANK_MODELS`、`EMBEDDING_MODEL`、`LLM_MODELS_JSON`），属可公开内容，不是凭据。
- ⚠️ 一条诚实限制：这轮普查里**只有 `ADMIN_PASSWORD` 有"活体正对照"**（它确实曾在历史里）。其余 7 个是"查不到命中"，
  不是"证明过能命中"；要给它们加置信，靠的是此前那次栽桩（`PLANTED_RC=1`）与两个 0 的对照，读的时候别把两者混成一件事。
- **待你按回车的那条命令**（走 SSH over 443，内联 URL，不动 `git config`；永不 force）：
  `git push ssh://git@ssh.github.com:443/wjt-code-design/fazhi-assistant.git snapshot/ci-fbc29e8-20260930:refs/heads/snapshot/ci-fbc29e8-20260930`
  回退（删掉远端那条分支）：同 URL、源写空：`git push ssh://… :refs/heads/snapshot/ci-fbc29e8-20260930`
- **仍未推**：仓库仍是 `private=false`。本地多了一个分支引用 `snapshot/ci-fbc29e8-20260930`，不进 `master`、不参与合并。

### 8.8 补记 8：Owner 一句"为什么要转 private"掀掉我给的前置， consequently 外发集合被重做

**① 那条前置的立足点没了，而且有反向代价。** 我当初建议转 private，是因为那时"对象集合干净"只靠**形状**普查；
现在按值普查已经背书（见下），保险的技术理由空了。反向代价是实测的：public 仓库 Actions 分钟不限量，
private 吃套餐配额，而我**读不到余额**（`/actions/permissions` ⇒ 401）⇒ 为了拿 CI 证据，转 private 可能反把 CI 卡住。
Owner 裁定：**不转 private，仓库保持 public。**

**② 真问题在内容轴，不在凭据轴。** 现量（`git ls-tree -r -l`）：未剔的快照 **350.0 MB / 2640 文件**，其中
`diag/frozen-index-004|005` = **74 文件 / 296.7 MB** 的向量索引二进制（⚠️ 更正：`894 文件 / 306.6 MB` 是**整个 `diag/`** 的数，我先前混了一档）；
另有 **42 份 `gate2-run-*-sessions.json`（0.7 MB）**——对它跑了形状普查（邮箱／IPv4／手机号／`sk-`／身份证）：**全 0**。
`frozen-index` 在 `backend/tests` 与 `backend/scripts` 里 **0 引用**；`diag/` 的引用只在注释/文档字符串
（`gen_phase1_audit.py:18` 与 `gen_route_mask_grayscale.py:15` 读的是**其它** diag 子目录）。
CI 那个 guard 步骤只跑 `dispatch-output/agent-quality-20260911` ⇒ 剔这两个目录不碰 CI 的任何一步。

**③ 剔完的外发集合（当前推送对象＝读现量 `git rev-parse --short=8 snapshot/ci-fbc29e8-20260930`）**：
无父、**1 笔提交**、**2566 文件 / 53.3 MB**、`git rev-list --objects` = **2507**。两处刻意偏离在册树：`ci.yml` 多本分支名、删那两个目录。
验证三件：
- **差分**（`b_snapshot_trim_diff.py`，读数 `b-snapdiff-20260930-024044.json`）：未剔树与剔过的树同一解释器同一命令各跑一次
  `pytest --collect-only -q` ⇒ `collected` **1678 == 1678**、错误行 **0 == 0**、体积差 **296.6 MB**。
  ⚠️ 这个 1678 还与在册全量读数自洽（`1650 passed + 10 skipped + 18 deselected == 1678`）。
  顺带修了仪器一处：副本树那套 venv 是 **3.11.0**，没有 `extractall(filter=)`，我第一版直接 TypeError ⇒ 改成在册建树器那套"手工校验成员再解压"。
- **按值普查带活体正对照**（每条都打印被测命令的 rc）：`ADMIN_PASSWORD` 快照 **rc=1（无）**、同一值打在 `817e7d3` **rc=0（有）**；
  `JWT_SECRET`／`RERANK_API_KEY` 两处都 rc=1 ⇒ 诚实措辞是"查不到命中"，不是"曾能命中"；负对照 rc=1。
- **树号随 `master` 一动就重算**：`.gitignore` 那笔位移之后重建了一次，差分对象只剩 `.gitignore` 与本报告两个文件。

**④ 我自己的两次记账。** 第十二次：`.gitignore` 规则**插在中段**把后面所有行号顶移 +3，而本仓多处按号引用它
（`backend/tests/conftest.py:133` 引 `:31`＝`backend/chroma_db/`、`test_harness_fact_reveal.py` 与 `hidden_runner.py` 引 `:77`＝`dispatch-output/task1/`）
⇒ 已把规则挪到文件**末尾**（`8d4bda7`），逐号复验 `26=.env 31=backend/chroma_db/ 45=*.log 54=backups/ 77=dispatch-output/task1/ 85=.workbuddy/` 全部复原。
第十三次更要紧：我**手抄了一个不存在的 SHA**（`53b259e`）去跑 `git grep`，git 报 `fatal: unknown revision`，
而我用 `grep -c .` 数命中 ⇒ 把"命令失败"读成了"三个键全部 0 命中"。**假阴性就是这么产生的**：普查的计数必须同时打印被测命令的 rc。

**⑤ 推之前必须先说清的一条：这次 CI 不会"整体绿"。** `ci.yml:45-46` 的 `pip-audit -r requirements.txt`
**没有 `continue-on-error`、也没有 `--ignore-vuln`** ⇒ 在册那 26 条运行轴通报会把它打成 **rc=1**，整个 backend job 判红；
这既不是新问题、也不是我们靠 CI 要否证的东西（远端 `master` 那三场 failure 至少有一部分同源）。
所以 Q4 那句"CI 之后签"里的"CI 绿"要按此收窄成：**ruff／format／mypy／pytest／guard 逐步绿 ＋ pip-audit 红＝已知在册风险的表现**，
读的时候逐步读、不看整体徽章。⚠️ 我**不会**为了绿去加 `continue-on-error` 或 `--ignore-vuln`（计划 §授权边界明令禁止用放宽 CI 代替处置）。

**⑥ 还有一条内容轴要 Owner 知情**：即将公开的文档里带着对那把**仍有效**口令的旁路描述（"13 位、字母数字混合、在哪些文件的哪一行"）。
现量：这类描述**不是我这次写的**——`docs/pending-owner-actions-20260926.md:80`、`docs/progress-handoff-report-20260925.md:443/707`、
`dispatch-output/a-docs-t7-report-20260927.md:58` 等在册文档里已有 **6 处**；值本身不在快照（③ 已按值证）。
⇒ 推快照＝这些描述**首次**进公开仓。归 Q14 那张凭据票处置；D2 的限制栏要落一条。我不建议为推送去改窄文档（那等于做假账）。

**⑦ 后来把整件事脚本化了**（`b_build_snapshot.py`，随票入库），因为这一轮我被同一根绊线咬了三次——派生树号随 `master` 一动静默过期。
脚本每次从现量重算合并树、构造两处偏离、并自验；关键是它把"普查"变成带闸门的形式：

- **第十四次记账（也是这条最险）**：脚本第一版的按值普查没带 `-C <仓根>`，而 `git grep` 在**子目录**里跑会**隐式收窄到该子目录**——
  同一棵树、同一个值，仓根命中 **1**、脚本所在子目录命中 **0**。于是那次输出的"4 个键全 0 命中"是**查错了地方**产生的假阴性，
  而暴露它的正是活体正对照自己变成 0。修法：所有普查带 `-C REPO`，并加一条**硬闸**——
  `ADMIN_PASSWORD` 打在 `817e7d3` 上若命不中，直接 `return 9` 拒绝产出可推快照。
- **闸门能红已用变异证明**（不是声称）：把 `POSITIVE_REF` 从 `817e7d3` 改成 `master`（那里本就没有那个值）⇒
  脚本走到 `FATAL: 正对照打不红…不许推`，rc=**9**。变异副本跑完即删。
- 每次构造都打印被测命令自己的 rc；`rc=1` 才是"没有"，命令失败绝不读成"0 命中"。
- **第十五次记账（对照被自己污染）**：那次真实构造打出一行 `负对照 rc=0`——不是快照里有东西，而是
  **我的负对照字面量写死在脚本源码里，而我刚把该脚本提交进了 `master`** ⇒ 对照串出现在被验树里，对照当场失效。
  修法：对照串改为**运行时生成**（`zz-absent-` + 16 位随机 hex），并规定 `rc != 1` 直接 `return 10` 拒绝产出。
  这条比前几条更难看，因为它说明：**只要对照是写死的，它就会随时间被自己的产物污染**。
- 所以**推送对象号不写死在这里**：推之前重跑 `b_build_snapshot.py`，现量取 `git rev-parse --short=8 snapshot/ci-fbc29e8-20260930`。
  本轮最后一次自验读数：无父、提交数 1、剔除 74 个文件、快照约 **2568 文件 / 53.4 MB / 2509 对象**，
  四个键快照命中全 0（rc=1）且 `ADMIN_PASSWORD` 正对照命中 1（rc=0）。

**待你按回车的那条命令**（SSH over 443、内联 URL、不动 `git config`、永不 force）：
```
git push ssh://git@ssh.github.com:443/wjt-code-design/fazhi-assistant.git \
  snapshot/ci-fbc29e8-20260930:refs/heads/snapshot/ci-fbc29e8-20260930
```
回退（删远端那条分支）：同 URL、源为空 `git push ssh://… :refs/heads/snapshot/ci-fbc29e8-20260930`。

### 8.7 补记 7：部署票的现量输入（Q6 裁定＝只登记，本窗口一处文档都没改）

编号靠后是因为中间插进了 §8.5/§8.6 那两桩更硬的事。全部给出处，**未处置**：

- **目标环境本身未定**：`DEPLOYMENT.md:3-4` 声称"本地开发启动 → 阿里云 ECS 部署""面向 2~3 人小规模使用，单机部署"；
  而 `docs/runbooks/deployment-v1.md:108` 写"**无生产服务器访问凭据**：M/N 的实际部署动作需数据所有者提供目标环境后执行"。
- **HTTPS 在仓库形态下没生效**：`Caddyfile:4` 是固定 `:80 {`；`docker-compose.yml:80` 是 `DOMAIN: ${DOMAIN:-}`（默认空）；
  `:79` 自己注明"空＝HTTP 监听 :80（Cloudflare Tunnel 穿透场景）；设域名才自动 HTTPS"。⇒ 在册无任何"证书已签发"的读数。
- **端口口径自相矛盾**：`docker-compose.yml:12-13` 自陈"backend/frontend 不再对宿主机暴露，公网只暴露 80/443（Caddy）"，
  而全文件**唯一一处 `ports:`** 是 `:77` 的 `"8088:80"`；`README.md:46` 还写着"前端 `localhost:3000` 后端 `localhost:8000/healthz`"。
- **镜像大小三处 vs 两处**：`DEPLOYMENT.md:82`、`README.md:49`、`backend/docs/OPS.md:82` 都写"约 1.5GB"；
  `docker-compose.yml:9`、`backend/Dockerfile:2` 写"约 3.92GB（2026-09-04 实测；早期 1.5GB 已过时）"。
- **真实库就在部署路径上**：`backend/rag_chain.py:119-123` 默认 `persist_directory=chroma_db`，`docker-compose.yml:47` 把 `./backend/chroma_db` bind-mount 进容器；
  实测该目录 **349MB**（另有异常同名目录 `backend/chroma_db;C` 为 0）。⇒ Q5"本窗口不动真实库"这条是靠得住的。
- **口令放置方式**：`DEPLOYMENT.md:28/78`、`README.md:44`、`OPS.md:78` 都指示 `cp .env.example .env` 后填 `ADMIN_PASSWORD`；
  `DEPLOYMENT.md:142` 只教"绝不能提交进 git"，**没教轮换与旧值失效验证**（轮换那句只在 `deployment-v1.md:82`）。
- **compose 的注入形状**（部署票要照着改的地方）：`docker-compose.yml:30` 用 `ADMIN_PASSWORD=${ADMIN_PASSWORD:?请在根 .env 设置 ADMIN_PASSWORD}`
  走 environment 白名单、**没有 `env_file`**；`:43` `DATABASE_URL=sqlite:////data/app.db`；`:51` `restart: unless-stopped`；`:53-58` healthcheck 打 `/healthz`。
- ⚠️ **我自己的一次普查范围搞错（第十一次，记账）**：第一次数"含口令明文的文件"我用 `fn.startswith('.env')` 过滤，
  于是**结构上漏掉了 `env.before-*.bak` 这一族**（它们不以 `.env` 开头），得到 2 份；改用"名字含 `env`"重新数才是 **8 份**。
  同轮另一次我用 `git ls-files --others --exclude-standard` 枚举，那**按定义看不见被忽略的文件**，
  而危险的恰好全是被忽略的——**枚举集合的构造方式本身就是结论的一部分**，别拿"0 命中"当"没有"。
