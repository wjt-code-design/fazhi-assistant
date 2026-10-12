# 待你裁台账（2026-10-10 非部署收尾轮）—— 每条一词可答

> **2026-10-11 Owner 会话复核：本轮工程成果可继续接收，非部署阶段仍 BLOCKED，不是“只差推送”。** 当前权威补充为同目录 `owner-review-and-next-actions-20261011.md`（含修正后的前置、边界与证据归属）。旧推送卡暂停直接执行；未修改产品或任何 Git/真实数据/凭据状态。报告交付、派单完成不等于验收通过；旧裁定沿用记录不构成本次新授权。
>
> 核验要点：1933/86.38 对应 `final-gates2-*` 而非本文旧引用的 `final-gates-*`；第二轮静态日志格式 rc=1 是历史事实，当前候选另行完整 Ruff lint/format 均 rc=0。D-33 仅在合规状态免计步；超过上限仍有拒绝分支，不能按死代码删除。D-34 建议独立修复票，不并入 D-14。管理员改环境变量不会更新既有账号密码，密码改变也不自动撤销 JWT。历史整合、当前 PR CI、安全修复和 F/G 等未满足门禁仍保留，不得因轮换后推分支而变绿。

口径：只列**现在真的还没定**的。已裁过并执行完的放在最后一节，不再问你。
每条都给了现量证据的位置，你要查就按那条命令查，不必信我的转述。

## 给 Owner 的几句话（先看这段，再看表）

- **10-12 接手轮做了什么（一句话）**：把两笔「已交付但停在未提交」的成果做成可交付——先证明盘上字节＝被审过的字节（8/8 sha256 命中交付锚定），再补上两份交付报告都欠的那趟**全量门**：第一趟红 2 只（红的正是 D-34 改接口后的旧测试接线，与 D-3 复核件预告的读数逐字相同），落接线修后第二趟 **2016 passed / 0 failed / cov 86.55%**；随后分三笔提交（`c15b775`、`87f58c0`、`a9ef432`），提交后逐只把库里 blob 与盘上字节比对全等。顺带关掉 H 那条 `backend/.dockerignore` 会把真库烘进镜像层的缺口（合成上下文 10 格对照全中，本轮没有再读真实库字节）。
- **我要更正 D-5 那句话一次**：你签的「先轮换 `ADMIN_PASSWORD`」如果只改环境变量，**库里的管理员口令不会失效**——`seed_admin.py` 见账号已存在就直接返回，登录校验读的是库里的 `password_hash`，而 JWT 由 `JWT_SECRET` 签名、认证不检查密码版本，所以已签发的会话也不会因此作废。我不把「轮换」当成已完成，另立 D-35 问你失效动作的真实入口。 **10-12 第二遍再更正我自己**：那句「全仓没有改口令入口」是**假阴性**——我只 grep 了 `main.py` 与 `backend/` 根目录，漏了 `backend/scripts/`。入口自 `5e51384`（2026-09-17）就在了，只是零测试、零文档指针、口令走 argv、还会回落到 `.env` 里正在退役的旧值。所以你签的 (a) 里「新写一个脚本」这半句作废，我实际做的是把它修成可用（§C D-40），你要的属性一条没少；仍要你动的是服务器上那两步（§A D-35）。
- **10-12 第二遍做了什么（一句话）**：按你「按推荐」的整包，落 D-35(a) 候选侧（重置入口改造 + 10 条判据 + 变异仪 9/9 杀）与 D-33 三条负例（负控 VERDICT=NEGATIVE_CONTROL_HOLDS，产品文件前后 sha 相同），静态门三腿 rc=0，并把推送卡的 A1 那句错话就地更正成 A1 跑脚本 + A1b 换 `JWT_SECRET`。


- 这一轮真正值钱的不是那几处代码，是两条纪律落了地：**验收对象必须等于交付对象**（盘上那批前端修复从来没进过任何提交，这件事到这轮才算清），以及**数只以同行命令为准**——上传对象数我在同一个指标上连错三版，第三版还是「纠正上一版」的姿态，最后是被一个只会读 `ls-tree` 的脚本钉住的。
- 凭据处置是公开推送前置，但不是唯一质量/交付门：依赖迁移、Agent 失败闭环、历史整合及当前 CI 等仍未完成。轮换完旧值仍可能留在历史中，失效证明与同意公开旧历史必须分别核实。
- 我实现里最贵的一处错留在正文里（取消占位用「有没有走到结尾」反推语义，被独立复核的对抗腿当场打中）——现在由一条结构不变量测试钉着。**下一轮请继续派对抗腿，别只派复现腿**：复现腿这次给我的结论是「你算的数没错」，而错的是前提。
- 待答项不等于全部待办。D-5 阻塞公开；D-34 的持久化一致性问题需要独立复现和修复裁定，不应先宣称“不阻塞质量”。D-33 推荐保留越界防御、不改变澄清上限语义。
- 转发时先读同目录 `owner-review-and-next-actions-20261011.md`，再按本文件追溯历史。旧 `tickets/runbook-I-push-pr-merge.md` 已标注暂停直接执行，不能当作逐行操作卡。
## A. 已裁，但只剩你手上的动作（我不代做，也不代签）

| 编号 | 已裁成的形状 | 为什么我不能推进它 | 你可以答 |
|---|---|---|---|
| **D-5 凭据与推送** | 按推荐＝先轮换 `ADMIN_PASSWORD`，再普通 `git push` + 开 PR | 轮换只能你动（我不读 `.env`、不碰凭据）；推送与开 PR 是共享状态动作，没有你那一键我不做。连带两条已在册：① 推 `codex/*` 本身不产生 CI 读数（`on.push.branches` 只列 main 与 master，10-11 重核过），要第三方验证就得连开 PR 一起做；② 远端主线历史 push 全红，别把 CI 红当成这笔候选的判决。逐条前置与命令在 `tickets/runbook-I-push-pr-merge.md`（已刷到 10-11 现量） | 「已轮换，推+开 PR」/「走无父快照备选」/「先不推」**（10-12 接手补一句：这句里『先轮换』的真实入口要重问，见 §B D-35；你已裁的方向我没有改）** **10-12 Owner 现答：「等我改完密码再推」**⇒ 本轮不推、不开 PR、不走快照；推的钥匙排在 D-35 两步之后（当天到 GitHub 的三条探测全 rc=35，那是当天的轴，不是理由）。 |
| **D-19 文档 ref 一起推** | 按推荐＝一起推 `codex/local-candidate-closeout`（现读（写行时 10-12：**109 次 / 13 个文件**；这两个数随头动，推前必重跑）：`git -C 候选 grep -o fbc29e8 -- '*.md' \| wc -l` 与 `git -C 候选 grep -l fbc29e8 -- '*.md' \| wc -l`，而该尖端 `fbc29e8` 不是 master 的祖先（`merge-base --is-ancestor` rc=1）、这支从未推送 ⇒ 不推就是那些引用在远端解析不出来（条数用同行上面那两条现读）） | 同一个动作、同一把钥匙：它也是一条 push，排在 D-5 之后。两条已核的连带事实：只多 4 笔独联提交（`rev-list --count 候选..closeout` = 4），且**不新增凭据外泄**（按值反查 closeout 对象集 value_hits=1，候选里也已是 1） | 「随 D-5 一起推」/「只推代码支」 **10-12 现答**：随 D-5 一起等——同一把钥匙，Owner 启动前不动。 |
| **D-35 口令与会话的真实失效动作** | 10-12 按推荐裁 (a)＋同换 `JWT_SECRET`。候选侧那一半我已做完（见 §C D-40），剩下两步只能你在服务器上动：① 跑 `python scripts/reset_admin_password.py --username admin`（先预览再加 `--write`）把库里那个 `password_hash` 换掉；② 换 `JWT_SECRET` 并重启后端，代价是**所有用户重新登录** | 口令值不经我手、不进 argv、不进日志；我不读 `.env`、不连真实库。两步的形状与判据在 `tickets/runbook-I-push-pr-merge.md` 的 A1/A1b（原 A1「供应商控制台」那句已就地更正） | 「两步已做完，推+开 PR」/「只做①，先不换 `JWT_SECRET`（接受最长 7 天旧 token 仍有效）」/「先不动」 |

## B. 新发现与范围待裁（是否阻塞须按影响判断）

| 编号 | 一句话 | 现量证据 | 我的推荐 | 你可以答 |
|---|---|---|---|---|
| **D-39 按用户作废会话的能力** | **非破坏性**的按用户作废入口没有：全局换 `JWT_SECRET`（所有人一起掉线）或 `is_active=False`（把管理员自己也挡在 `require_admin` 外）。库里无 token 版本、无会话登记表。**10-12 复核 B4 就地更正**：还有第三条**破坏性**形状——`main.py:2870` 的 `DELETE /api/admin/users/{id}` 是硬删（`:2883 db.delete(user)`，级联会话/消息、不可逆），它能断该用户的已签发 token，但那不是「踢会话」的正确工具 | 本轮只读复核 `backend/auth.py:45-68`（payload 只有 sub/username/role/exp，7 天有效）；`tests/test_reset_admin_password.py::test_reset_does_not_revoke_already_issued_token` 把这条限制走现役 `get_current_user` 钉住了 | 推荐**本轮不做**：先按 D-35 两步收口，真需要「精准踢人」时再立一张票（要动认证面 + 一次 schema 迁移，不该塞进收口轮） | 「本轮不做，登记」（推荐）/「开票做」 **10-12**：Owner 本轮没答这一格（他先定了「等改完密码再推」）⇒ 按推荐默认**不动**，要用时再问一次。 |

> 这两条是复核 A/B（10-11 06:5x）之后新问出来的，发现时间在上一次整包授权**之后**，所以不并入已裁。
| **D-42 口令只从终端进——这条性质没人保证** | 脚本里没有 `isatty` 前置（`grep -c isatty` 现量 0），`getpass` 在拿不到终端时**退回读 stdin 并警告「可能被回显」**。Windows 上这条测不出来（`msvcrt` 不吃重定向），但**生产是 Linux 容器**，`docker exec` 不带 `-t` 就是这个形状 | 复核第三轮钉子 8 自拟反证：非终端 stdin + `--write` 在私有临时库上真把口令写进去了（rc=0，库哈希变化）；我这轮只复量了「`isatty` 0 次 / `os.getenv("ADMIN_PASSWORD")` 0 次」 | **推荐先零代码改法**：把 runbook A1 的 `docker exec -it` 从注释升格成硬前置（已随本轮改）；下一轮再补一行 `isatty` 前置 + 一条能红的用例 | 「按推荐（先改 runbook）」/「现在就加 isatty 前置」/「仅登记」 |
| **D-43 重置脚本「写哪个库」没有显式目标** | 目标完全由现役 `.env` 的 `DATABASE_URL` 决定（`load_dotenv()` + `database.py` 的 `DB_URL`），没有 `--database-url` 之类的显式开关 ⇒ 与 D-14 刚立的「写入要显式目标」是同一形状的第二遍 | `backend/database.py:9-13` + 脚本 import 序；复核 B 路②同判 | **推荐本轮不动**（Owner 已在跑的那台机器上，加开关等于再改一次入口行为）；下一轮连 D-14 的口径一起收 | 「本轮不做，登记」/「开票加开关」 |
| **D-45 迁移测试用了新 SDK 的私有模块，窗口比已测组合宽** | `test_llm_lifecycle.py` 无条件 `from langchain_openai.chat_models._client_utils import …`（私有路径），而声明窗口是 `langchain-openai>=1.1.14,<2` ⇒ 窗口内任意版本都算合规，但**只有实测的 1.7.0 被证明过**。我在旧栈上拿这只迁移后的测试单独跑，当场 `ModuleNotFoundError: langchain_openai.chat_models._client_utils`（收集期就红） ⇒ 这类跳窗不会静默降级，会硬炸 | 本轮实测：`pytest tests/test_llm_lifecycle.py`（envB/旧栈）= 1 error in 1.95s，`--tb=line` 点名 `ModuleNotFoundError`；envD/新栈同一只文件 0 error | 推荐**不吞 ImportError、不加 skip 凑绿**：保持窗口不变，在 `requirements.txt` 注释里写明「已测组合 = langchain-core 1.6.9 / langchain-openai 1.7.0 / langsmith 0.14.7；跳到别的 1.x 若炸在收集期，视为支持边界外，另开票」（我本轮已把这句写进落地的 requirements 注释） | 「按推荐（写明边界，不吞异常）」/「把窗口收到 ==1.7.0」/「让测试兼容两栈」 |
| **D-46 推上去 CI 仍会红，成因只剩 chromadb 2 条** | `ci.yml` 有两步审计且**都不许失败**：`:55 pip-audit -r requirements.txt`、`:64 pip-audit -r requirements-dev.txt`；全文件里 `continue-on-error` 只出现在注释文字（「不用 continue-on-error 凑绿——红就让它红」）。P1 落地把通报从 **15 条降到 2 条**，但那 2 条（`PYSEC-2026-3813/3814`，`fix_versions` 为空、升 1.5.0 反而扩适用面）仍会让这两步 rc=1 ⇒ **「推了就等于有第三方验证」这句要加一条限定** | `ci.yml:54-64` ＋ 我这轮实跑 `pip-audit -r requirements-migrated.txt` 现量残余 = chromadb 2 条（`p1-migration-20261012/audit-resolved.json`）；旧栈对照 15 个主 ID 见 §E | 推荐**保持红**并在 runbook/台账写清成因（这是 D-2 在册接受的直接后果，不该用忽略规则把它藏起来）；若你要「推了就有一场绿」，只能选：给这两步加 `--ignore-vuln`（＝降低门禁严格度，需你明确裁并写失效条件），或把这两步改非阻塞 | 「保持红，写清成因」（推荐）/「加 --ignore-vuln 两条并登记失效条件」/「改非阻塞」 |
> 10-12 接手轮第二遍：上一批 §B 的 D-33、D-34 已裁并执行提交；本节原来的 D-35 搬到 §A（候选侧已完成，只剩你服务器两步），D-36、D-37 搬进 §C（已裁已执行，零残留）。⇒ 等你动的现在是 §A 三条（D-5、D-19、D-35）+ 本节若干（现读用下面那条命令）。**档位计数不要引用本句，用下面那条命令现读。**
> 各档现数不要引用本节措辞，用脚本现读：`evidence/ledger_row_audit.py`（按 §A/§B/§C 切段，抽编号，报重复与缺号）。
## C. 已裁过、已执行完（不再问你，只作对账）

| 编号 | 内容 | 落地位置 |
|---|---|---|
| D-1 | `agent/state_machine.py` 解冻并保留 DB-15 改动 | `backend/pyproject.toml` ruff exclude 3→2 + 解冻记录；格式化前后 **AST 等价**已证（`evidence/state_machine-format-ast.json`）；提交 `5ca3315` |
| D-2 | chromadb 两条残余风险「在册接受 + 失效条件」 | 复用 10-03 那份风险册（不新建第二份）；候选复扫：0.4.24 两条 `fix_versions` 空、1.5.0 反成 5 条 |
| D-3 | langchain 族 13 个 ID：BLOCKED，另开跨大版本迁移票 | `reports/gates.md` C 行；未动任何调用面 |**10-12 第三遍补记：迁移已落地**（Owner 下 P1 开工令；干净安装 envD + 纯发布物树新栈门 2030 passed/cov 86.57%，两轴审计把 langchain 族 13 个主 ID 归零），提交 `0ce047d`＝requirements + 三只迁移测试同一笔 ⇒ 本行「未动任何调用面」只描述 10-10 那一轮。
| D-4 | DB-19 回落**收窄** | `backend/retrieval.py` + `observability.py` + 新测试 9 条；变异仪 M1/M2 双向红（`evidence/category-mutants.log`） |
| — | B-45 `import_laws` CLI 守卫 | `backend/scripts/import_laws.py` + 新测试 4 条（子进程真跑 CLI）；变异 M1 删守卫 ⇒ 恰好红在分歧腿 |
| — | E.2 加载信任门 / E.3 合成备份恢复演练 | `reports/trust-and-data-drill.md`；行为级五臂 `GATE_HOLDS` + 入库 4/7 条 + 两台变异仪 |
| D-26 | D-3 跨大版本迁移票派给谁 ⇒ Owner 答「新会话」（10-11 01:5x） | 票 `tickets/dispatch-D3-langchain-migration-20261011.md`（8 节，含并发纪律）；分母与符号面两根轴都随票落盘（`evidence/audit_axes.js`、`evidence/d3_symbol_surface.py`） |
| D-27 | 独立复核腿怎么办 ⇒ Owner 答「新会话」（同上） | 票 `tickets/dispatch-independent-review-20261011.md`（5 节 / 7 颗钉子 / 只读约束）；本会话已停派 agent，结果将并进 `closeout-final-J-draft.md` §5 |
| D-13 | 并行会话那 5 只 `frontend/` 改动的处置 ⇒ Owner 先答「等 D」，D 交回后按 hunk 整合 | **已执行**：D 验收「6 绿 1 红」后落第五笔 `9e3cfc5`（5 文件 `+69/−7`）；提交前用 `git apply -R --check` 与「纯净 HEAD 重放 ⇒ 5/5 blob 相等」自证；现量候选树 `porcelain=0` ⇒ 盘上那份不再处于「只活在磁盘」状态 |
| D-21 | 「§14 那份从没进过任何提交」的整合动作 | **已执行**（同上，第五笔 `9e3cfc5`）；证据 `evidence/frontend-dirty-20261010.patch` 与 `.manifest`。**注意 J3（生产构建 purge 徽章类名）没有随这笔修掉**，那是 D-22，另开票 |
| D-22 | J3：生产构建把四个 `badge-*` 类名 purge 掉 | **已执行并闭合**（Owner 裁「按推荐」→ 本会话自验）：`ui.tsx` 改静态映射 + 新增 `npm run build:check`（带 INERT 判据）+ CI 既有 Build 步并入；提交 `842ef0b`、`0d3d662`。产物层 0/0/0/0 → 1/1/1/1；变异臂只让被改那一类变 0 |
| D-28 | D-22 暴露的徽章配色 AA（前景压自己浅底只有 1.42–4.01）怎么裁 | **已裁 (b) 并已执行**：前景统一 `--ink`，差异交给底色 + inset 环（不用 `border-left`：胶囊会弯成碎片且撑高 2px）。复量 **11.15 / 11.22 / 10.30 / 5.70，全部 ≥4.5**；按「底色+环」两维 6 对里相同 0 对；提交 `033cd3d`。同一把尺子本轮出现三态（全同→红 / AA 不达→红 / 现在→绿）⇒ 它不是恒绿的 |
| D-12 | 本轮交付物要不要入库 | **已执行**：`docs/closeout-20261010/` 现量 **32 只 `.md` 全部 tracked**（10-11 06:5x；这数随每轮交付增，读法 `ls docs/closeout-20261010/*.md \| wc -l` 配 `git ls-files -- docs/closeout-20261010 \| wc -l`，两数相等才算入库）（随 4 笔 docs 提交入册；未含 `evidence/`、`candidate-env*`、`synthetic/`）。入库前三检留痕：逐只 CR=0；凭据形状复扫 `sk-`/AKIA/JWT/PEM/URL-in-creds 命中 0，13 位形状 45 处全是普通标识符、与参照值相同 0 处；`git diff --cached --name-only` 自证未夹带 |
| D-6 | 开发环境对齐怎么办 ⇒ 已开票，本轮不动宿主机 venv | 票 tickets/dispatch-D6-dev-env-alignment-20261011.md（7 节）。10-11 现量：对【候选】requirements.txt 偏离 6 只（fastapi 0.110.3 / uvicorn 0.52.1 高于上限 / sentence-transformers 2.7.0 / sqlalchemy 2.0.51 / pypdf 6.14.2 / torch 2.6.0+cpu），pip check 既有 2 条红；⚠️ 同一条命令读【主仓旧那份】只得 4 条偏离（那份没有 torch 行、sqlalchemy 下限还是 >=2.0）⇒ 报数必须点名读哪一份。尺子 evidence/venv_vs_requirements_axis.py，读数 evidence/d6-venv-axis-20261011.txt | **10-12 第四遍：已推到「可替换但未替换」**——宿主 venv 对**落地后**的新清单偏离由 6 条变 **12 条**（目标变了），另建 `backend/venv-new` 并四道验证全绿（`pip check` 零红、对账尺 24/24、核心导入、纯树全量门 2030/cov 86.57%）；按执行书 §G「主工作区未整合则 G 暂停」与 Owner 裁 **①**，**停在切换前**，换名留到 I 之后。细读 `reports/d6-venv-alignment-20261012.md`。
| D-8 | DB-19 的 category 字段摘不摘 ⇒ 已裁：不摘 | Owner 10-11「都交由你的推荐执行」＝采纳维持现状；schema 与回落形状未动，category_filter_* 三字段读数继续存在。零代码改动 |
| D-9 | DB-22 拒答冷却分档 ⇒ 已执行并测到 | backend/llm_registry.py：REJECT_COOLDOWN_BY_STATUS（401/403/404 = 3600s）+ reject_cooldown_s() + reject_kind() + ModelEntry.rejected_kind；status() 每行带 rejected_kind（config 与 shape 分得开）；两字段登记进 observability._ACCOUNT_FIELDS。新增 3 条用例（tests/test_llm_reject_channel.py）。负向自证：M1 把长档塌回 300 ⇒ 杀 2 条；M2 取消登记 ⇒ 杀 2 条（含 AST 哨兵那条）⇒ evidence/batchA-mutation-20261011.log |
| D-10 | DB-23 的 409 文案 ⇒ 已执行，且实拆成 4 档（台账原写三条） | backend/agent/controller.py：RESUME_CONFLICT_DETAILS 成因码表 + resume_conflict_detail()（未登记码回落旧句 ⇒ 409 不会变 500），ResumeRunConflict.detail 承载；main.py 用 _resume_exc.detail，不再拼第二份。分档轴是【用户下一步动作】（已处理过 / 再答一次 / 预算用完 / 接不上），所以 answer_invalid 单列一档 ⇒ 共 4 条文案。新腿：AST 现读成因码全覆盖（新增抛点自动进门）+ 回落腿 + 四档互不相同且不泄漏内部标识；变异 M5（全塌成旧句）杀 5 条、M6（两档共用一句）杀 1 条 ⇒ evidence/batchB-mutation-20261011.log。文案由我起草并经整包授权落地，Owner 未逐字过稿（D-31）：改词只动常量，逐字用例会变红（那是预期信号） |
| D-11 | 在册风险册入库 ⇒ 已执行 | 主仓那份 docs/chroma-risk-triage-20261003.md（3,252 B / 23 行 / sha256 前缀 0847ba2d）10-11 现量仍是未跟踪且未被忽略（两棵树 ls-files 都 0、check-ignore 无命中），候选树里根本没有 ⇒ 已 cp -a 进候选 docs/（mtime 与 sha 逐字相同），随本轮文档提交。⚠️ 同族未跟踪文档主仓现量 34 只 ⇒ 见新行 D-30 |
| D-14 | 索引 CLI 安全改造 ⇒ **已执行并已提交**（10-12 接手复验） | 提交 `87f58c0`：`backend/scripts/`（`import_docs`、`backfill_time_meta`、`chroma_dir_guard`、`eval_chunking`、`verify_new_law`）+ 新 `backend/tests/test_index_cli_safety.py` 40 项。接收时先验字节：8 只未提交文件 sha256 与交付报告锚定值 8/8 命中。本轮把它放进**全量**里复跑：2016 passed / 0 failed。原判据仍红的那条（`verify_new_law` 测量退出码 1）没有被改成绿 ⇒ 见 §B D-36。报告 `reports/d14-index-guards-20261011.md` |
| D-33 | 恢复预算越界防御 ⇒ 已裁：保留（Owner 10-12「按你的推荐执行」） | 本轮**零代码改动**：免计步与 `_limit` 的现状与文案维持。推荐里那条「恢复 API 的旧状态与预算下降负例」本轮未实现 ⇒ 转票 `tickets/dispatch-D33-resume-budget-negative-20261012.md`（下一轮首票之一） |
| D-34 | Agent 轮次响应接管前中断的补偿与归属收敛 ⇒ 已裁 A 并**已提交** | 提交 `c15b775`：`backend/main.py` + 新 `backend/tests/test_agent_turn_compensation.py` + 两条旧测试接线改桩（`test_agent_resume.py`、`test_chat_turn_persistence.py`）。接线修与接口变更同笔，是为不留自身带红的中间提交；补丁出自 D-3 复核会话，本轮只做接收复验。报告 `reports/d34-response-owner-closeout-20261011.md` |
| D-38 | `backend/.dockerignore` 盖不住 `data/` 下两个真库（上一轮实装面已证） ⇒ 本轮按整包授权直接修掉并复量 | 提交 `a9ef432`：`*.db` 改 `**/*.db`、`*.sqlite*` 改 `**/*.sqlite*`、加 `.ptmp*`。没有整目录排除 `data/`（`git ls-files backend/data` 现量 2 只运行时评测件会被静默少掉）。复量 `dockerignore-probe-20261012/`：合成上下文 10 格预登记期望全中、VERDICT=FIX_VERIFIED，本轮不重复读真实库字节 |
| D-44 | 候选工作树被整片重写 ⇒ Owner 裁「由我从 HEAD 重刷后再落」⇒ **已执行**：重刷前把 31 只内容差异文件整份备份（689,835 B）到运行根 `incident-20261012-worktree-overwrite/pre-restore-backup/`，再 `git checkout -- .` 从 HEAD 重刷；重刷后现量 `porcelain=0`、untracked=0，三只代表标记回到修好的状态（`backend/.dockerignore` 的 `**/*.db`+`.ptmp*`、脚本的 `import getpass`）。 | 取证与备份在 `incident-20261012-worktree-overwrite/`；第三轮复核 §1 独立得出同一结论（两条不相交的路径）。**仍未查明是谁做的**——我只恢复了树，没有替任何会话认领。 |
| D-41 | 真实模型验收轮的资源边界 ⇒ 已裁：用**现役账号**、**上限 100 元**、双阈值（金额 + 次数）、只在副本树 + 私有临时库/索引/配额库上跑、六根出网轴只放开模型那一根 | 本节 §H 第 31 条（原只有编号散文、没有档位行，复核 B6 抓出后本轮补格）；执行归 F 轮，**审签交独立复核 ⇒ 结论上限是「机器复核分」，不得报「法律专业审签通过」** |
| D-36 | `verify_new_law.py` 测量退出码 1（检索质量原判据仍红）⇒ 已裁「并入 F 轮」，本轮不改判据、不动法律规则，也不为变绿扩范围 | 零代码改动。读数原样保留在 `reports/d14-index-guards-20261011.md` 的重要限制节；下一轮与真实模型/真实语料一起查（F 的三根阻塞仍在 F 票里） |
| D-37 | 前端格式门（`npm run format:check` rc=1、3 只文件）⇒ 已裁「接受现状、明确不加门」 | 那 3 只文件（Stats、Upload、Users Section）**一字未动**，`ci.yml` 前端作业也没加格式腿（一塞就红，且它们不是本轮改的）。读数在 `evidence/static-and-frontend-20261012.log` 第 [10] 段 |
| D-40 | D-35 的**候选侧那一半**：把已有但没人知道的重置入口改成可用 | 入口 `backend/scripts/reset_admin_password.py` 自 `5e51384`（2026-09-17）就在库里，零测试、零文档指针，且 `--password` 走 argv、回落 `.env` 的旧值、改密不落审计（在册 B-44）。本轮：去掉 argv/`.env` 两条口令来源、默认预览 + 显式 `--write`、拒绝空口令与公知默认口令、未知用户不创建、改密落 `log_audit(admin.password_reset)`、docstring 写清「改口令不作废已签发 JWT」。新增 `backend/tests/test_reset_admin_password.py` 10 条，变异仪 9/9 杀（`evidence/d35-mutation-20261012.log`，VERDICT=ALL_EXPECTED_ARMS_DIE，只在副本树动、还原逐字节相同）。**你服务器上的那两步没做，所以 D-35 不算关闭** ⇒ 见 §A |
| D-15 | DB-7 技术降级白名单 ⇒ 已执行并测到 | backend/routing_metrics.py：TOOL_BUSY 进 TECHNICAL_FALLBACK_REASON_CODES（集合 5→6）；record_agent_route 的 raise 两侧都有用例钉住；管理台快照 fallback_reason_code_counts 里 TOOL_BUSY 与 TOOL_UNAVAILABLE 分列（逐键断言）。变异 M3 摘掉 TOOL_BUSY ⇒ 杀 2 条（精确集合 + 分列） |
| D-16 | DB-10 事件响应文档 ⇒ 已执行，并更正我台账的读数面 | DEPLOYMENT.md 新增 §7（三行表：信号 / 看哪个计数器 / 读到之后做什么），只写计数器不写法律口径。⚠️ 我原句写错：读数面不是 /metrics（全仓没有这个路由），真身 = GET /api/admin/llm-status（backend/main.py:3082，require_admin），返回 models / utility_quota / metrics |
| D-17 | F 的可播种语料 ⇒ 已裁：用冻结题集，本轮不播种 | Owner 10-11「按你的推荐」＝可播种条文仅 11 对，不足以撑 F2 的 12 题；F 腿仍由 §A 的 D-7 卡着，零代码改动 |
| D-18 | DB-24 注释与真值不符 ⇒ 已执行，且发现比台账宽 | 两处「8」改成「条数以 DEFAULT_ROLES 为准，注释里不抄数」。新发现：同一只 docstring 举的 7 个模型名里 6 个不在表里（deepseek-r1-distill-qwen-7b / qwen2.5-omni-7b / qwen3.5-omni-flash / qwen3-vl-235b / qwen3-vl-32b / qwen-plus 现量命中 0，只有 qwen3.7-plus 与 qwen3.5-omni-plus-2026-03-15 在）；「现有 6 个辅助调用点」这条现量是 registry.get() 15 处 ⇒ 假例子已删，条数与调用点数都改成指向真源。get() 返回 omni-plus 那句核为真（DEFAULT_KEY=vision_flag ⇒ qwen3.5-omni-plus-2026-03-15），未动 |
| D-20 | 合 master ⇒ 已开票，且数会随头动 | 票 tickets/dispatch-D20-merge-into-master-20261011.md（7 节）+ 尺子 evidence/merge_trial_blobs.py、evidence/merge_trial_reconcile.py + 清单 evidence/d20-diff-list.txt。10-11 04:0x 在头 5e9bba8 × refs/closing/remote-master（985d53e，与当日 ls-remote 一致）重跑：候选 2706 / 远端 2136 / 交集 2136 / 远端独有 0 / 同 blob 2040 / 异 blob 96 = CONFLICT 96（全 add/add）⇒ 两把尺子吻合。台账旧写 94 是 9e3cfc5 轴、更早 115 是本地陈旧 ref 轴，均已就地作废。分组（176899f 上的 99 只）：backend 74、frontend 15、docs 5、`DEPLOYMENT.md`/`CONTRIBUTING.md`/`.gitignore`/`.github`/`dispatch-output` 各 1；**头一动分組就重算**，别引用本句做排工。⚠️ **同一把尺子在 10-11 05:5x 的本轮三笔提交后再跑 = 异 blob 99 = CONFLICT 99（头 bffbe1c，A 路径 2707、B 独有 0）** ⇒ 96 只在 5e9bba8 上成立；这条不是笔误，是"数随头动"的现行演示，也正是票里写死"开工时与最终头上都要重跑"的原因 |
| D-23 | 取消占位文案 ⇒ 已执行并测到 | backend/main.py：_PLACEHOLDER_NO_RESPONSE（复用 _ERROR_NO_RESPONSE，两处只差句号，不抄第二份）与 _PLACEHOLDER_STOPPED 两档；_post_placeholder(pre, reason)。两条路分别钉住：正文生成器 finally 只在【抓到 GeneratorExit / CancelledError】时记 stopped。〔10-11 复核 B 打中我第一版：那时用「有没有走到 try 结尾」反推取消，而 try 体里有 5 处主动 return （轻量分支空答走 :2415），会把「服务端没给出内容」错写成「用户已停止」，同样的空答在旗舰分支却写「不响应」——同一症状两句话。已改为断开信号置档，并补一条 AST 结构不变量测试（只有 except 能置 _client_gone）。变异读数：旧版 M4 杀 4 条；改写后 M8 抽掉该信号杀 3 条（含这条新测试），日志 evidence/batchC-mutation-M8-20261011.log〕；compensate_unstarted（响应已关而正文从未进入）记 stopped（M7 ⇒ 杀 2 条）。服务侧真故障（空答 / 异常 / bootstrap 抛错 main.py:738）仍走 no_response。前端当场文案未动 ⇒ 见新行 D-32 |
| D-24 | 探针失败往宽还是往窄 ⇒ 已裁：保持宽 | Owner 10-11「按你的推荐」＝保持 _corpus_advertises_category 探测失败 return False ⇒ 无过滤回落；代价由 category_filter_* 三条日志字段承担（可见而不静默）。零代码改动 |
| D-25 | 出厂 Dockerfile 源侧缺陷 ⇒ 已执行（回落 + 可观测两条腿） | backend/Dockerfile：torch 步与 requirements 步各加 `\|\|` 失败回落（官方 CPU find-links / -i pypi.org），选 `\|\|` 而非 --extra-index-url 的理由写在文件里（不合并两源候选，避免版本选择权外移）。.github/workflows/ci.yml 新增 source-probe 作业（PyPI 逐包 pip download --no-deps --no-cache-dir + torch CPU 目录双源核对；主源红 = 降级 warning，两源同红 = 真红），只挂 schedule + dispatch，不占每次 PR。⚠️ 10-11 本机复量：缺陷已自愈（阿里云 pydantic-2.14.0 可取 487 kB rc=0；官方页 torch-2.13.0%2Bcpu-cp311 在列）⇒ 落的是【这一类】故障的兜底，不是复现中的补丁。自检：evidence/d25-probe-selfcheck-20261011.log、evidence/d25-pipleg-selfcheck-20261011.log（假版本必两源皆红、rc=1） |
| D-29 | D-3 的两份 diff 要不要现在落 ⇒ 已裁：本轮不落 | Owner 10-11「按你的推荐」＝不落地。迁移证据已交付且我独立复算过族 ID 13→0，但落它＝换整栈依赖，与本轮【验收对象 = 交付对象】的收口顺序冲突；登记为下一轮首票（连同 D-3 报告 §6 的两条观察项） |**10-12 第三遍：这两份 diff 已落地**（requirements 迁移版 + `migration-tests-reviewed.patch`，提交 `0ce047d`）；「本轮不落」是 10-11 那一轮的裁定，未回改。
| **D-7 | F 五类真实模型验收这轮开不开 ⇒ 已裁：不开 | 按推荐执行＝本轮零模型调用（在册预算 81/162 未动用）；冻结稿在 `docs/closeout-20261010/gold-freeze-draft.md`，F 的三根阻塞（含可播种语料仅 11 对）逐条仍在报告里挂着，**没有**被本轮顺手做掉 |
| **D-30 | 主仓其余未跟踪文档 ⇒ 已裁：本轮不收 | 现量：主仓 `docs/` 未跟踪 34 只，本轮只按 D-11 收了点名的 `chroma-risk-triage-20261003.md`。不收的理由是公开仓一推就永久可见；要收时一次性裁「收哪几类、放哪个目录」 |
| **D-31 | 我代起草的用户可见文案 ⇒ 整包授权下按草案落地（**未逐字过稿**；要改词只动常量，判据不动） | 409 四档在 `backend/agent/controller.py` 的 `RESUME_DETAIL_*`；取消与故障两档在 `backend/main.py` 的 `_PLACEHOLDER_STOPPED` / `_PLACEHOLDER_NO_RESPONSE`。每条都有用例逐字钉住 ⇒ 将来改词只动常量，分档与判据不动（改词会让那几条逐字断言红，那是预期信号，不是回归） |
| **D-32 | 取消的历史文案与前端当场文案 ⇒ 已裁：保持两套 | `frontend/lib/hooks/useChatStream.ts:65-66`（当场，可能有半截答案）与 `backend/main.py` 的历史占位（一定没有答案）语义不同，不合并；本轮前端零改动 |

## D. 一句话门禁现状（截至本文件写出时）

候选 `codex/nondeploy-closeout-20261010`；笔数与头**都不钉数**：本行每入册一笔就 +1，钉它必然自我过期。现读 `git log --oneline 0b54396..HEAD | wc -l` 与 `git rev-parse HEAD`；本文件只钉三笔**代码交付**的号（`c15b775`、`87f58c0`、`a9ef432`），它们是固定对象不是当前位置。`porcelain` 现量 0 行。
**未 push、未开 PR、未合并、未轮换任何凭据、未读真实库内容、未动 3021 与 8088 现役栈。**

**10-12 接手轮现量（当场跑，不是引用历史日志）**：全量非 slow **2016 passed / 0 failed / 10 skipped / 18 deselected**，cov **86.55%**，rc=0；
分母闭合：collected **2026/2044**，junit `tests=2026 skipped=10 failures=0 errors=0`。
静态与前端 11 条腿 **10 条 rc=0**：`pip check`、ruff check、ruff format --check、mypy 整仓、mypy 点名 D-14 五脚本、`git diff --check`、`npm run lint`、tsc、vitest **9 files / 83 tests**、`npm run build:check` 产物断言 **VERDICT=OK**（四个 `.badge-*` 各出现 1 次，控件 `.badge{`=1、`.upload-zone`=3）。
唯一 rc=1 的一条是 `npm run format:check`（**3 只**文件），⇒ §B D-37。
证据：`evidence/integration-gates-backend-pass2-20261012.log` 与同名 junit XML、`evidence/integration-gates-backend-20261012.log`（第一趟红的那次）、`evidence/wiring-fix-targeted-20261012.log`、`evidence/static-and-frontend-20261012.log`、`evidence/dockerignore-probe-20261012.log`。

**三组旧数各属于哪棵树（别混用）**：1933 passed / 86.38% / collected 1943 与 1961 是**候选提交树**（不含 D-34、D-14 那 11 只文件）的读数，出处 `evidence/final-gates2-*`；
本轮 2016 = 1933 + D-14 的 40 + D-34 的 43，是同一棵树**加上这两笔交付**的分母；更早的 1925 / 86.35% 是第五笔 `9e3cfc5` 之前的树。
三组各自成立，引用时必须点名读的是哪一棵。`socket` 守卫与在线 `pip audit` 两轴本轮未重跑（未动依赖面）。

## E. C 单元（依赖风险）的收口建议：15 条其实只剩**两条处置要你点头**

现量（`evidence/audit-cand-{runtime,dev}.json` 两轴同集）：**15 个主 ID，分布 5 只包**。不是 15 个独立决定——按「修法是否存在」分两堆：

| 堆 | 条数 | 包 | 修法 | 现处置 | 建议 |
|---|---|---|---|---|---|
| A | **13** | `langchain-core` / `langchain-openai` / `langchain-text-splitters` / `langsmith`。**两根轴都要点名**：每包**条目**（含重复）= `core 11 / langsmith 5 / splitters 4 / openai 2`；每包 **distinct 主 ID** = `core 6 / langsmith 4 / splitters 2 / openai 1`，且**跨包无重叠**（和 = 并集 = 13） | 修复线全在 **0.3.x / 1.x**（如 `langchain-core 1.2.22`、`langsmith 0.8.18`）⇒ 必须跨大版本 | **D-3 已 BLOCK 成独立迁移票**（本轮不动调用面） | **维持 D-3**；本条只是把分母说清：它背 13/15 |
| B | **2** | `chromadb` `PYSEC-2026-3813/3814` | **两条 `fix_versions` 均为空**（无修复版；且升到 1.5.0 反把适用面从 2 条扩到 5 条） | **D-2 已在册接受**（复用 10-03 风险册，不新建） | **维持 D-2** |

⇒ **已裁（2026-10-11，Owner「按你的推荐」）：按这两条处置收口** —— **A 堆 13 条**走 D-3 的独立迁移票（本轮不动调用面）；**B 堆 2 条 chromadb** 沿用 D-2 的在册接受（不新建第二份风险册）。本条自此为**已执行状态**，不再是待决项。

**就地更正（2026-10-11 01:3x，两处，都是我自己的错）**
1. 上一句原写「本轮不动调用面，**票面已存在**」——**该断言当时为假**：`tickets/` 当时只有 3 只文件（D 单票、D 验收尺、I 执行卡），没有任何迁移票；"票面要点"只以散文形式存在于 `reports/owner-decisions-20261010.md:39`（写着"供你派单"）。
   现已按 D-3 把票**真正写出**：`tickets/dispatch-D3-langchain-migration-20261011.md`（7 节，含现量分母、符号面 16 项、副本树双跑配方、能红的验收尺子、停止条件）。这条"已裁"自此才有归宿。
2. 上面 A 行原写每包 `core(7)/openai(1)/splitters(2)/langsmith(3)` ⇒ **这一处是错的**（7 与 3 两个数在任何轴上都数不出来）。
   但我要**同时撤回自己 01:2x 那次"更正"**：我当时写"两处手抄拆法（含 `owner-decisions-20261010.md:35` 的 core 6 / langsmith 4 / splitters 2 / openai 1）都不可复现"——**这句为假，是我错怪了那只文件**。
   现量（复算器 `evidence/audit_axes.js`，读 `evidence/audit-cand-runtime.json` 与 `-dev.json`，两份同集）：
   - 每包**条目**（同一 ID 在同包可出现两次）= `core 11 / langsmith 5 / splitters 4 / openai 2`（+`chromadb 2` = 全 24 条目）；
   - 每包 **distinct 主 ID** = `core 6 / langsmith 4 / splitters 2 / openai 1`，**跨包无重叠**（和 = 并集 = **13**，与"A 堆 13 条"吻合）；
   - `distinct ID with fix_versions` 与上面同值（⇒ "有修复线/无修复线"不是差异来源），CVE 前缀只有 `langsmith 1`，族主 ID + aliases = **38**。
   ⇒ **`owner-decisions:35` 那句在 distinct 轴上完全正确，保持原样不改动它**；要改的只有本文件那行的 7/3。
   **根因登记**：我第一次只算了"条目"和"族并集"两根轴，就宣布别人的拆法不可复现——**报"不可复现"之前要先把对方可能用的那根轴跑一遍**（这台机器我已经在别的节里批评过一次）。

```bash
# 两根轴一次印全（2026-10-11 独立复核 C §3.3 之后，脚本已补上 per-package distinct 轴）
R=C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2
node "$R/evidence/audit_axes.js" "$R/evidence/audit-cand-runtime.json" "$R/evidence/audit-cand-dev.json"
# 注意：原先这块写的是 python -c 里 glob('<msys 路径>').replace('','/')，两处坏：
#   ① '' 是未闭合字符串 ⇒ SyntaxError；② 即使修好，Windows 解释器打不开 /c/... 形式 ⇒ 会静默打印 0（假干净）。
```

## F. 本轮总账（这一节的存在理由：让本文件可以单独转发）

**状态**：候选分支本地笔数与头只给命令（`git log --oneline 0b54396..HEAD | wc -l`、`git rev-parse HEAD`——写这行时钉过一次 33，入册这笔之后当场过期，所以改成规则句）、`git status --porcelain` 现量 0 行；**未 push、未开 PR、未合并、未轮换任何凭据、未动真实库/向量库/容器/端口 3021 与 8088**。最后一笔代码交付是 `a9ef432`，其后都是文档入册。
**门禁现量（10-12 00:5x 当场跑，不是推的）**：全量非 slow 2016 passed / 0 failed / 10 skipped / 18 deselected、cov 86.55%、rc=0；collected 2026/2044、junit tests=2026；ruff check、ruff format（285 files）、mypy（整仓与 D-14 五脚本各一次）均 rc=0；前端 lint、tsc、vitest 9 files / 83 tests、`build:check` VERDICT=OK；`format:check` rc=1（3 只，在册两把口径）。复算命令与逐腿 rc 在 `reports/gates.md` §48 与本文 §D。

**等你答的 / 你已答的（10-12 现量）**：D-5 与 D-19 已答「**等我把密码改完再推**」⇒ 本轮起我不再准备推送动作，只等你先做 D-35 两步（服务器上跑重置脚本 + 换 `JWT_SECRET`）。还开着的一格是 D-39（推荐不动，你没答就默认不动）。另有两件事在你手上但不必现在答：第三轮复核票要不要派（票已刷到新头、九颗钉子），以及要不要我把 D-35 两步写成一张能照抄的纸条。

**独立复核二轮（两路子代理，正交）**
- A 复现腿 `reviews/20261011-round2/independent-review-A-replication-20261011.md`：采纳 8 / 驳回 1 / 核不了 0。它自己在 `git archive` 副本树上复刻了变异、重跑了全量门禁与对象轴，没引用我的转述。
- B 对抗腿 `reviews/20261011-round2/independent-review-B-challenge-20261011.md`：新发现 12 条，其中四处我当场验实后**本轮已修**——① 取消档原先用"有没有走到 try 结尾"反推 ⇒ 只认真实断开信号（并补结构不变量测试）；② `source-probe` 缺**作业级** `if:` ⇒ 补上（我三处"不占每次 PR"是假话）；③ torch 回落只换 find-links 不换 index ⇒ 已同时换官方源；④ D-14 票的机制前提不成立（那四只脚本跟随 `CHROMA_DIR`，`assert_matches` 对它们是**恒等式**、永不咬红）⇒ 票已重写。
- 另两条只登记不实现：就是 §B 的 D-33、D-34。

**推送量的一条自我更正（影响你怎么读 D-5）**：我上一轮写"上传集会因对象身份被折小"**是错的**，这次复量到 `rev-list --objects remote-master..HEAD` == `rev-list --objects HEAD` == **4464**，且两侧同 blob 的 2037 只**全部**仍在上传集里 ⇒ 无关历史时剪的是 commit 链不是对象身份。方向不变的结论只有一条：那只 13 位裸值的 blob 在上传集里、不在远端可达集里 ⇒ **先轮换再推**。

**我本轮的自曝错（原先只在对话里说过，现按规矩落进正文；细节在 `reports/gates.md` §42、§45、§47 与 J §10.2）**
1. 给新测试编了不存在的符号（`registry.snapshot()` 真名 `status()`；白名单真名 `_ACCOUNT_FIELDS`）。
2. 写过一条**恒真**三元断言（期望值由被测值现算，永不红）。
3. D-6 对账第一次**读错轴**：拿主仓旧那份 requirements 比 venv，得 4 条偏离；换成候选那份才是 6 条。
4. D-20 的两把尺子各带一处仪器错（`rev-parse` 取不到返回空被算成差异；`partition` 把行尾留在 key 里）。
5. 计数词口算：写过"18 条全部处置完"，真值是 §A/§B 由 18 降到 2 ⇒ 现在**计数词又是口算的**这条被脚本兜着（差集实测）。
6. 中文串里嵌 ASCII 双引号 ⇒ `SyntaxError`，**同一个坑我又踩第三次**；之后脚本里的中文散文不带 ASCII 双引号，竖线用 `chr(124)`、反斜杠用 `chr(92)`。
7. 表格单元里写 shell 的竖线导致**劈列**（4 列变 7 列），被 `evidence/md_table_columns.py`（自带 `--selftest`）抓到。
8. 用 `bytes(10)` 当换行去数节数 ⇒ 恒返 0（那是 10 个 NUL）；改按 `chr(10)` 切行后现量 47 节。
9. 在册报告 `gates.md` 里有一个**真 NUL 字节**（`grep` 把整份台账当二进制），已修并复量 NUL=0。
10. heredoc 会把双反斜杠折成单个 ⇒ 第一次修 NUL 时被自己的长度断言拦下；写法改成 `chr(92)` 构造。
11. `grep -q` 在 `set -o pipefail` 下让上游 `sed` 收 **SIGPIPE** ⇒ 正对照假阴性（探针差点被我误判为"两页都缺件"）。
12. `pip download` 不加 `--no-cache-dir` 时用 "Using cached" 冒充"官方源真取到"（第一次的假绿）。
13. 两条**新待裁项错放进 §C**（已裁档）且列数写成四列 ⇒ 被列数检查器与重号脚本同时抓到，已挪回 §B。
14. 汇报自查：本轮"都写进决策文件了吗"由 `evidence/work_log_key_audit.py` 出数——29 个 key 只对这一只文件跑，最初缺 14 个（就是本节存在的原因）。
15. 10-12 接手轮：我第一条 pytest 命令给出「`PYTEST_RC=0`、耗时 1 秒、正文一个字没有」的假绿。根因是 PATH 上 `~/.local/bin/env`（绝对写法 `C:/Users/33393/.local/bin/env`） 那个只设 PATH 的 shell 脚本把 `env VAR=x cmd` 整条吞掉并返回 0 ⇒ 这台机器上任何用裸 `env` 起的命令都要先证明它真的跑了。改用 `export` 起才有 17%/35%/53% 的真实进度。
16. 10-12：我第一版 `.dockerignore` 探针的期望表把 `(old,new)` 元组当成值用 ⇒ 10 格里 9 格被误标 BLOCKED；是打印出来的「ALLOWED=1」这个荒谬数暴露的。自造复算器的手写期望表自己也要跑一遍对照。
17. 10-12：我把那条 Windows 路径写进正文时漏了盘符后的冒号，而我当时的断言只查「反斜杠加 Users 在不在」、没查真实形状 ⇒ 它没被自己拦住，是事后 grep 才看见的。断言必须断在内容上，否则它只是我意图的回声。

**交付物路径**（运行根 `C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2`）
- 汇报：`reports/closeout-final-J-draft.md`（§0 状态、§3 待裁四条、§10.2 我的错、§11 复核二轮）
- 状态与读数：`reports/gates.md`（§38–§47）
- 本文件：`reports/decisions-needed-20261010.md`（§A/§B 待裁、§C 已裁 30 条逐条落地位置、§D 门禁、§F 总账）
- 下一轮三张票：`tickets/dispatch-D14-index-write-guards-20261011.md`、`tickets/dispatch-D6-dev-env-alignment-20261011.md`、`tickets/dispatch-D20-merge-into-master-20261011.md`
- 你要动手时用：`tickets/runbook-I-push-pr-merge.md`（推送前置与命令；已按 §44 更正刷新）
- 两份复核报告：上面"复核二轮"里那两个路径；均已同步进仓内 `docs/closeout-20261010/`（写这行时 34 只，10-12 接手轮已到 42 只，逐只 sha 与运行根相同）

**本轮未做（不是"已做"）**：F 五类真实模型腿未跑（Owner 裁本轮不开，冻结稿在册）；`socket` 守卫与 `pip check` 两轴未重跑（未动依赖与网络面）；D-18 的旧断言我只清了代码注释与文档引用面；D-33/D-34 只登记未实现；D-3 的两份 diff 按 D-29 本轮不落。

## G. 本轮做了什么（穷尽清单；细读数在 `reports/gates.md` §38–§47，叙述在 J）

**单元层（A–J 按执行书的单元记账）**
- A 接手保护与登记：闭合（基线 `reports/baseline.md`，候选分支 `codex/nondeploy-closeout-20261010`）。
- B 后端四票 + B-45 守卫 + D-3 迁移证据：闭合（D-3 由我独立复算验收，落地转 D-29）。
- C 依赖风险：处置方案已登记，风险门未通过。13 项迁移未落地；2 项受限接受按报告追溯，不能自动令现有 pip-audit 门变绿。
- D 前端五项残差 + 取消流程真实浏览器验收：已验收；其 J3 红（生产构建 purge 掉 `badge-*`）由我自验并修（D-22），连带暴露的配色 AA 按 D-28(b) 修（D-22/D-28 均闭合）。
- E 模型来源、加载信任门、合成数据演练：闭合（行为级五臂 + 恢复演练）。
- F 五类真实模型验收：**本轮不跑**（Owner 裁；冻结稿在册，可播种语料仅 11 对是三条阻塞之一）。
- G 现役环境升级：判为不动（现役是 Docker 容器；宿主 venv 的对齐转 D-6 票）。
- H 包装、凭据/历史、远端 CI：各子项分别记账；候选包装、凭据失效与公开范围、当前对象 CI 不能相互替代。现阶段不能称 H 全通过。
- I 独立审查、本地提交、PR、合并：本地成果在册；历史整合、当前整合对象独立审查、凭据/公开前置、PR 检查与正常合并仍待执行，不是仅一次推送。提交笔数按固定对象现读。
- J 收尾：正式稿（本文件 §F/§G/§H + `closeout-final-J-draft.md`）。

**改动面（代码，按文件）**：`backend/llm_registry.py`（拒答冷却两档 + `rejected_kind` 进 `status()` + DB-24 注释更正）、`backend/observability.py`（两个日志字段登记进 `_ACCOUNT_FIELDS`）、`backend/routing_metrics.py`（`TOOL_BUSY` 进白名单、与 `TOOL_UNAVAILABLE` 分列）、`backend/main.py`（409 用异常携带的分档文案；占位两档；只认 `GeneratorExit`/`CancelledError` 为断开）、`backend/agent/controller.py`（`RESUME_CONFLICT_DETAILS` 成因码表 + 回落 + 不可达性标注）、`backend/settings.py`（注释去抄数）、`backend/tests/`（`test_llm_reject_channel.py`、`test_agent_rollout.py`、`test_agent_resume.py`、`test_cancel_boundaries.py`（含新结构不变量测试）、`test_chat_turn_persistence.py`、`test_stream_cancellation.py` 签名对齐）。
**改动面（文档与部署）**：`DEPLOYMENT.md` §7 事件响应三行；`backend/Dockerfile` 两步各加失败回落（torch 那发同时换 index）；`.github/workflows/ci.yml` 新增 `source-probe` 作业（含作业级门与逐包正对照）+ 触发段加 schedule/dispatch；`docs/chroma-risk-triage-20261003.md` 入库（D-11）；`docs/closeout-20261010/` 交付镜像现读 `ls docs/closeout-20261010/*.md | wc -l`（写本行时=34，且与 `git ls-files` 同数）。
**判据与仪器（本轮新增）**：变异 9 枪（M1–M3 批 A、M4–M7 批 B、M8 复核后；每枪只动一个 site、finally 还原、逐文件 sha 位级相同）；`evidence/venv_vs_requirements_axis.py`、`merge_trial_blobs.py` + `merge_trial_reconcile.py`、`md_table_columns.py`（自带 `--selftest`）、`ci_yaml_check.py`、`d25-*-selfcheck`、`work_log_key_audit.py`（key×文件对账）、`push-upload-axis-recheck-20261011.md`。
**票与复核**：新写三张票（D-14 / D-6 / D-20），刷新 runbook；两路独立子代理复核（A 复现、B 对抗）报告入库，其判决与我的响应在 §F 与 gates §46。

**10-12 接手轮追加（本会话做的事，全部现量，不引用上一轮转述）**
- **接收复验停在未提交态的两笔交付**：先验字节（8 只文件 sha256 与交付报告锚定值 8/8 命中），再跑「第一趟全量红 2 只 → 定向接线修 2 passed → 第二趟全量 2016 passed / 0 failed / cov 86.55%」。
- **三笔提交**：`c15b775`(D-34 加两条旧测试接线) → `87f58c0`(D-14) → `a9ef432`(`backend/.dockerignore`)；每笔提交前 `git diff --cached --name-only` 只列点名路径；提交后逐只把 `git ls-tree -r HEAD` 的 blob 与 `git hash-object --no-filters` 的盘上值比对，11 只全等、CR 全 0 ⇒ **交付字节＝验收字节**。
- **H 的 `.dockerignore` 缺口关闭**：改成 `**/*.db`、`**/*.sqlite*`、加 `.ptmp*`，并用合成上下文跑 10 格预登记对照（同一目标只差规则一个变量；评测件两套规则都放行；runner 在缺基底镜像或正对照不合格时自身 REFUSE，而不是报修好）。
- **静态与前端 11 条腿复量**：10 条 rc=0；`format:check` 的 3 只文件按现状登记成 D-37，不顺手改、也不静默把门塞进 CI。
- **Owner 会话复核件 R1–R8 折进台账**：R3 落成新的 D-35；R4 的一半在本轮复量中已过期（候选 `ci.yml` 第 86-97 行现量确实跑 lint、tsc、`npm run test`、build、`build:check`）；R7 关于「1933 对应哪组日志」写进 §D 的三组数轴说明；R8 的「最终门禁同数不是机械要求」正是本轮分母从 1933 变 2016 的解释口径。
- **交付镜像补齐**：`docs/closeout-20261010/` 从 34 只增到 **42 只**（D-34 四份、D-14 一份、Owner 会话复核一份、D-3 当前候选复核一份，加本轮新写的 D-33 负例票一份），并把改过的 `gates.md` 与本文一起重镜像；逐只 sha 与运行根相同（本轮实测 checked=10 differing=0）。只数现读 `ls docs/closeout-20261010/*.md | wc -l` 配 `git ls-files -- docs/closeout-20261010 | wc -l`，两数相等才算入库。

- **D-35(a) 候选侧做完**：把「已有但没人知道」的重置入口改成可用（去 argv、去 `.env` 回落、默认预览 + `--write`、拒绝空/公知默认口令、未知用户不创建、改密落审计、docstring 写明 JWT 限制），新增 10 条判据 + 变异仪 9/9 杀（`evidence/d35-mutation-20261012.log`，VERDICT=ALL_EXPECTED_ARMS_DIE，只在 `d35-mut-tree/` 副本树上动，每条臂还原后逐字节相同，控制腿绿）。
- **我自己那条错前提已更正**：上一版我写「全仓没有改口令入口」——假。我只 grep 了 `main.py` 和 `backend/` 根目录，漏了 `backend/scripts/`；入口自 `5e51384`（2026-09-17）就在库里，零测试、零文档指针。你签的 (a) 里「我新写一个脚本」这半句作废，实际做的是**改造既有入口**，你要的那组属性一条没少。
- **D-33 负例已自己执行**（票上四条里缺的三条：越界拒绝的状态机腿 + 恢复层腿、预算下降腿、澄清轴反向护栏；用例 1「steps 恰满 cap 可恢复」`test_agent_resume.py:690` 早在册且断言够硬，不重复造）。负控走**内存源码变异**（磁盘产品一字未改，前后 sha 相同）：`evidence/d33-mutation-20261012.log` VERDICT=NEGATIVE_CONTROL_HOLDS，点名杀的正是那三条，反向护栏腿按预期存活。
- **推送卡已修**：`tickets/runbook-I-push-pr-merge.md` 的 A1「你在供应商控制台轮换 `ADMIN_PASSWORD`」是错的（这是应用自己库里的账号，且改环境变量碰不到 `password_hash`），已就地更正为 A1 跑脚本 + 新增 A1b 换 `JWT_SECRET`。
- **台账档位重排**：D-35 从 §B 搬到 §A（只剩你服务器两步），D-36、D-37 进 §C（已裁已执行），新登记 D-39（按用户作废会话的能力，推荐本轮不做），D-40 记我这边那一半。复算见 `evidence/ledger_row_audit.py`。
- **第三轮复核票随本轮刷头扩到九颗钉子**（新增：复跑 D-35 判据并要求自拟反证、专挑我那条「反向护栏存活是预期」的说法）；派发权在你，我没有派。票 `docs/closeout-20261010/dispatch-independent-review-20261012-round3.md`。

## H. 还差什么没做（分类穷尽；每条指名归属与出处）

**只能你动、我没动（也不该动）**
1. 凭据轮换（`ADMIN_PASSWORD` 等）——D-5 的前置；我不读 `.env`、不代做。
2. 普通 push + 开 PR + 合并 master——共享状态动作；命令与三条"推送前现跑"的前置在 `tickets/runbook-I-push-pr-merge.md`。
3. 推 `codex/local-candidate-closeout` 那支文档 ref——D-19，同一把钥匙。
4. 用户可见文案的**过字**（409 四档 + 取消两档由我起草、按整包授权已落地，但你未逐字过稿）——D-31；改词只动常量。

**已裁成票、留给下一轮执行（本轮有意不做）**
5. D-14 四只无守卫 CLI ⇒ **本轮已关闭**：交付会话按 A 做完，10-12 由我接收复验并提交 `87f58c0`。编号保留不重排，免得按号引用的地方漂移（下同）。
6. D-6 开发环境 `backend/venv` 对齐（现量 6 条偏离 + `pip check` 2 条既有红）。
7. D-20 合 master：现量 **99 次**内容裁决（会随头动，开工前重跑）。
8. D-29 落 D-3 的两份 langchain diff（本轮不落；下一轮首票）。
9. D-33、D-34 ⇒ **D-34 已关闭**（Owner 裁 A，本轮复验后提交 `c15b775`）；**D-33 已裁保留**，但推荐里那条「恢复 API 的旧状态与预算下降负例」本轮未实现 ⇒ 转票 `tickets/dispatch-D33-resume-budget-negative-20261012.md`。 ⇒ **10-12 第二轮：这条负例已由我执行并提交，本条关闭。**
10. D-30 主仓其余 33 只未跟踪文档：本轮不收，要收时一次性裁范围。

**未跑的读数/轴（我明确没做，不是做了没写）**
11. F 单元全部：五类真实模型验收、真实路由、独立 gold（零模型调用，预算未动用）。
12. `socket` 守卫非回环读数 与 `pip check`（本轮未动依赖与网络面）⇒ 仍是上一轮在册值。
13. 远端 CI 读数：合并前拿不到（`on.push.branches` 只列 main/master，推 `codex/*` 不产生 run；新加的 `source-probe` 又只在默认分支才响应 schedule）。
14. `docker build` 全量冒烟：探针只覆盖源侧"文件取不取得到"，模型烘焙那层没跑；且 10-10 那次源侧故障今天复量已自愈 ⇒ 没有正在复现的缺陷可证。
15. 真实知识库语义面：两棵树 `backend/chroma_db` 都是空壳 ⇒ `real_kb` 走 skip，10 条 skip 的**构成**未逐条列（在册纪律要求报"几条走 skip"，这条只做到"未逐条列"）。
16. 浏览器计算样式那一腿（J3 的六状态视觉等价）由 D 会话与我的 CSS 产物断言承载，我**没有**独立复跑浏览器腿；复核 C 也把这条列为未复算项。
17. `evidence/` 整目录不入库（交付镜像只含 reports 与 tickets）⇒ 数字可复算的前提是这台机器上的运行根还在。

**已知限制（不影响"做没做"，影响怎么读结论）**
18. `closeout-final-J-draft.md` §7 那张自我更正表写的是"八条"，那是**写表时**的条数；第二批的错在 §10.2、复核后的错在 §F 第 1–14 条。编号不重排，避免十余处按号引用漂移。
19. 凭据轴的结论是"轮换前不能推"，**即使推了并轮换，历史里那只 13 位裸值仍在**（只是不再现役）——签了也不解除。
20. D-25 的 CI 探针**不等于**出厂构建可用；`--no-deps` 逐包解析与整表联合求解可能选到不同版本（该偏差写在作业注释里）。
21. 台账里所有"几笔提交/几份文件/几次裁决/几个对象"都是**写行时的现量**，一律以同行给的命令为准；本行写这些数字时头是 `50b39ec`。

**10-12 接手轮追加（还差的，仍按上面四类分档，编号接着往下）**
22. 只能你动：D-35 的凭据失效入口。在我这边无论怎么做都只是改环境变量——库里那个账号的 `password_hash` 不变，`seed_admin.py` 见管理员已存在就返回，认证也不检查密码版本，所以已签发的 JWT 更不会因此作废。 **此句 10-12 第二轮就地更正**：「无论怎么做都只是改环境变量」为假——入口本来就在 `backend/scripts/reset_admin_password.py`，本轮把它修成可用，你现在只剩「跑脚本 + 换 `JWT_SECRET`」两步（见 §A D-35）。
23. 已转票留下一轮：D-33 的恢复负例；D-6 宿主 venv 对齐；D-20 合 master（冲突数随头动，开工与终头各重跑一次）；D-29 落 D-3 的两份 diff；D-36 若你选「单独开票现在查」。
24. 本轮明确未跑的读数：在线 `pip-audit` 两轴（D-3 未落地，重跑只会复述旧读数）；`slow` 与 `real_kb` 腿；浏览器计算样式的独立腿；远端 CI 当前对象读数（未推送，且推 `codex/*` 本身不产生 run）；`socket` 非回环守卫本轮未重跑。
25. 已知限制（影响怎么读那个 2016 全绿）：它是在合成嵌入、测试自建数据库、六个上游 URL 全指死回环的形状上取得的，证明接口、控制流、存储、取消与隔离，**不证明**真实语义检索质量与真实模型表现；`format:check` 那条 rc=1 原样保留，没有从分母里摘掉。
26. 已知限制：本轮所有后端读数只在运行根 `candidate-envB`（Python 3.11.0）上成立，不外推到宿主 `backend/venv`、Docker 镜像或 CI——那三套依赖集合不同源（在册事实）。

**10-12 接手轮第二遍追加（仍按四类，编号接着往下）**
27. 只能你动：D-35 的服务器两步——① `python scripts/reset_admin_password.py --username admin`（先预览再 `--write`），② 换 `JWT_SECRET` 并按现役形态重启。口令值全程不经我手；我不读 `.env`、不连真实库、不登你账户。
28. 本轮明确未跑的腿：`--write` 从未对**真实库**执行过（判据只在 conftest 的进程私有临时 SQLite 上跑）；重置后「旧口令登录失败/新口令成功」这条只能由你在页面上给出现场读数。
29. 已知限制：改动作废会话的能力仍然没有（新登记 D-39）。在换 `JWT_SECRET` 之前，已签发的 token 最长 7 天内照旧有效——这条限制本轮由 `test_reset_does_not_revoke_already_issued_token` 走现役 `get_current_user` 钉成了判据，不是口头承诺。
30. 已知限制（接口变更）：`--password` 参数被删除 ⇒ 任何照旧命令粘贴的调用会 argparse 直接报错（rc=2），这是有意的。仓库内除 `dispatch-output/*-source-sha.json` 的哈希清单外没有调用者，复算：`git grep -n reset_admin_password -- ':!dispatch-output'`。
31. **已裁待执行（新登记 D-41，真实模型验收那轮的资源边界）**：Owner 10-12 裁「**用现役那套账号**（不另开测试号），**上限 100 元**」⇒ 执行侧按双阈值设闸（金额 100 元 + 调用次数上限由执行会话按题量折算并报 Owner 确认），到数即停；只在副本树 + 私有临时库/临时索引/私有配额库上跑，六根出网轴里**只放开模型那一根**，其余指死回环；跑完拿平台控制台真实读数校准一次（本地 token 估算不可信是在册纪律）。**审签已答（10-12 第二遍）**：Owner 裁「回答合不合法交给独立复核（AI 助手）判」⇒ 那轮结论的**上限是「机器复核分」**，**不得报成「法律专业审签通过」**（生成≠验证是在册纪律，同一个模型群既生成又自证尤其弱）；要对外说专业认可，得另排人力。另：Owner 已下「P1 开工」令。
32. **第三轮独立复核到位并全部采纳（10-12）**：`reports/independent-review-20261012-round3.md`。B 路 7 条 + 钉子 8/9 的三处新洞我都自己重跑过一遍才落笔，逐条处置见 `reports/gates.md` §50；因它而新登记的档位是 **D-42（终端前置/`-it` 硬前置）**与 **D-43（显式 DB 目标）**，就地更正的旧句四处：`gates.md` 的「零文档指针」「命中 1」「BRE 尺子零命中」「chroma_db 按构造不存在」，以及 D-39 那句「只有」。
33. **我自己违反过的一条纪律（不算别人抓的才算）**：§48/§49 三趟全量都是在候选工作树里直跑的，而复核票要求纯发布物树。复核在它自己的 archive 树上是**同值**复现的，所以读数不作废；但从下一轮起门禁前置改为「`git archive HEAD` 出树 + 前后各一次 `find -type f | wc -l`」——它这轮还发现跑完的树会多出 `backend/chroma_db/chroma.sqlite3`，即 **`porcelain=0` 单独不构成「树未变」的证据**（我此前正是只报 porcelain）。
34. **P1（D-3 迁移）状态＝新栈已验绿、尚未落地**：envD 干净安装 + `git archive HEAD` 纯树上 **2030 passed / cov 86.57%，两轴审计把 langchain 族 13 个主 ID 归零（残余只有 chromadb 2 条，D-2 在册接受），构建工具升级已实测（`pip 22.3→26.2.1`、`pip check` 仍零红）。**阻塞点是 D-44**（工作树被整片重写），不是我还没测。细读 `reports/p1-d3-migration-20261012.md`（镜像同名，入册后镜像 45 只）。
35. **P1 已落地（10-12 第三遍，Owner「按推荐」）**：`requirements.txt` + 三只迁移测试同一笔提交 `0ce047d`；落地前静态腿 ruff/format/mypy 全 rc=0，落地门在副本树与提交后纯发布物树上各跑一次全量非 slow （读数与复算命令见 `reports/gates.md` §52）。**新基线自此是 envD/新栈**；envB 降级为旧栈历史基线，回退方式是 revert 那一笔。仍欠的独立腿：`docker build`（生产 Linux `+cpu` 轮与本机 win_amd64 `+cpu` 不是同一对象）、前端腿未重跑、`slow`/`real_kb`、真实模型（P3）。
