# H 单：包装、凭据/历史安全与远端 CI（2026-10-10）

运行根：`C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2`
候选：`C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010`

状态：**H-CI PASS（含两条我自己造出来的红）/ H-凭据：**普通推会上传历史裸值——已证**（现役性未知，见 §2.1）/ H-包装部分完成，Docker 与 standalone 两条腿见 §4**

---

## 1. 远端 CI 的两处不足（已改，改的是"门根本不产出信号"那一类）

`​.github/workflows/ci.yml`（候选，本轮 +2 处）：

| 缺什么 | 为什么是缺陷而不是口味 | 本轮动作 |
|---|---|---|
| 作业装 `requirements-dev.txt`，却只 `pip-audit -r requirements.txt` | dev 解析集在 CI 读数里**从不出现**（在册已久）。⚠️ **本条我第一版理由写错了、同日勘误**：我原本写「本轮实测 dev 轴确有独立通报」，复算后**不成立** —— 两份 JSON 逐对比较是完全相同的 15 个 (包, ID)，dev-only 与 runtime-only 都是 0 | 新增 `pip-audit (dev axis)` 一步（理由改成「让 dev 解析集将来漂移时有读数」，步骤保留）；勘误落在提交 `a934fa7` |
| frontend 作业只有 `npm run build` | vitest 用例**从来不在** build 里；lint/类型只是"顺带"，且只在 `next.config.js` 没设 `eslint.ignoreDuringBuilds` / `typescript.ignoreBuildErrors` 时才发生 | 拆出 `npm run lint` / `npx tsc --noEmit` / `npm run test` 三条独立腿 |

上面那条"顺带"的前提我当场核了，不是想当然：
`frontend/next.config.js` 现量只有 `output: "standalone"`（:4）与一条 rewrite 注释，**两个 ignore 开关都不存在** ⇒
今天 build 确实带 lint+tsc。我在 CI 注释里写清了"下一轮若动 next.config.js，先确认这两个开关仍是关闭态"。

**没有做的事**（本书明令）：不降 `--cov-fail-under`、不删 audit 步、不扩大 ignore、不用 `continue-on-error` 凑绿。
新增的 dev 轴审计在现量上**会让 CI 该步红**（15 个 ID 里 13 个卡 `>=0.1,<0.2` 一族、2 个上游无修复，见
`reports/dependency-decision.md` §10）。红就是红：那是门在说话，不是门坏了。

触发形状（在册，未改）：`on: push: branches [main, master]` + `pull_request` ⇒ 推 `codex/*` 分支不出远端读数，
**要远端证据必须开 PR**。`on:` 里没有事件字段插值，故不存在"把 payload 拼进 shell"那一类注入面。

---

## 2. 凭据/历史：历史裸值已证，现役性未知——上一版把这两件事混写成了一句 BLOCKED

**要回答的问题**：把候选分支按普通 `git push` 推上去，会不会把现役凭据带出去？

### 2.1 结论（2026-10-10 晚间更正——我上一版这里写错了方向）

**会带上历史裸值：已证。** **该值现在是否仍有效：不能证**（要读 `.env`，本书禁区）。两件事分开，别混成一句"做不到"。

| 读数（只读，零值输出） | 命令形状 | 现量结果 |
|---|---|---|
| 候选分支起点与 master 同头 | `git rev-parse HEAD`（候选 worktree，起点笔） | `0b54396…`（= 主仓 master） |
| 09-22 那笔是候选历史的祖先 | `git merge-base --is-ancestor 817e7d3 HEAD` | rc=0 **是** |
| 本地 `origin/master` 与 HEAD 的关系 | `git merge-base HEAD origin/master` | **NONE —— 两 disjoint 历史**（远端那 192 笔不在我 238 笔里） |
| 普通推要上传的对象数 | `git rev-list --objects origin/master..HEAD \| wc -l` | **4301** |
| 裸值的直接读法（关键的一条） | 读 `git show 817e7d3:dispatch-output/t12-frontend-sweep-20260920/apply_case_domain_gate.py` 第 104 行 | 该行是 `(r"'<13 位纯字母数字>'", "'<masked>'")`：**一个 13 位字面量被当成正则 pattern 写进打码工具自己**（指纹 sha256 前 8 位 `e32743f3`，值不落纸面） |
| 按值反查全历史 | `evidence/value_reverse.py`（对 238 棵树逐棵 `git grep -F <值>`） | **hits=61 / files=1 / lines=104**；`HEAD` 与 `7eda4bb` 的 blob 均 False（已改成按形状匹配） |
| 该值是否仍现役 | 需以 `.env` 里的现役值做内存比对 | **未做**（书禁开 `.env`）⇒ 只能说"历史里有它"，不能说"它现在能不能登录" |

### 2.2 我上一版为什么读反了（这条要留在册，因为它是我的仪器缺陷而不是运气）

上一版这里有一行"**该 blob 里 `ADMIN_PASSWORD` 的出现……都是键名，不是明文值**"，据此把整节判成 BLOCKED/"没有证据说有，也没有证据说没有"。**那句是过度声明**：我量的是**键名**在不在场，却拿它当**值**不在场的证据。而那只裸值恰好**一个键名都不带**——它被塞进 `(r"'…'", "'<masked>'")` 的正则里，`grep ADMIN_PASSWORD` 结构性看不见。这正是在册教训"形状普查覆盖不到无形状的值 ⇒ 要按值反查"的现场复发，只不过这次值的来源不是 `.env` 而是 **git 对象自己**。

**授权边界要说准**：从 git blob 取该串做内存比对**不在禁区里**（禁区是开 `.env`/`app.db`/`chroma_db` 等现役数据，以及把值打印出来）。所以我**做得到**"证明历史里有裸值"，也**做得到"证明 HEAD 树已无"**（两条本轮都跑了）；**做不到**的只有"证明它是否仍等于现役口令"。上一版我把这三者压成一句"做不到按值验"，方向就错了。

### 2.3 在册另一头：轮换状态文件自己就否认过

同一只文件 `7eda4bb`(09-26) 的注释写"值已轮换，旧值失效"，而 **HEAD 的注释把这句删了**，改成"凭据是否已轮换由 Owner 掌握，本注释不作断言（此处原写'值已轮换，旧值失效'未经证实，2026-09-29 删）"。⇒ 我不能拿 09-26 那句当"旧值已失效"的证据；册子里那条撤回就是为本轮这种情况留的。

### 2.4 给 Owner 的那一词（不变，但理由换成了现量）

- **(a) 先轮换 `ADMIN_PASSWORD`**（并确认 `LLM_API_KEY` 那把在册"已暴露"的处置），然后普通推 `codex/` 分支 + 开 PR ⇒ 4301 个对象里那只旧 blob 变成"已失效历史值"；
- **(b) 沿用 09-30 的无父孤儿快照路线** ⇒ 对象集合按构造不含历史，代价：PR 的 base 无共同祖先、`ci.yml` 触发要按 compare 分流，且本轮我改的两步 CI **不会**出现在远端读数里。

我推荐 **(a)**，理由一句话：(b) 需要为 CI 触发行做偏离，D2 签的读数形状会因此要加注，而 (a) 只花一次轮换。
**我不替 Owner 选**：本书把"操作外部账户/撤销凭据"列在非授权动作里，"改写历史/force push"在红线里。

## 2b. 那条勘误是怎么自己查出来的（复算命令）

```bash
cd C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2
candidate-envB/Scripts/python.exe -c "import json; f=lambda p: sorted({(d['name'].lower(), v['id']) for d in json.load(open(p,encoding='utf-8')).get('dependencies',[]) for v in d.get('vulns',[])}); rt=f('evidence/audit-cand-runtime.json'); dv=f('evidence/audit-cand-dev.json'); print('dev-only:', sorted(set(dv)-set(rt)), ' runtime-only:', sorted(set(rt)-set(dv)))"
```

现量输出：`dev-only: []  runtime-only: []` ⇒ 两轴是同一批 15 个 ID（5 只包：chromadb / langchain-core /
langchain-openai / langchain-text-splitters / langsmith）。

**两件事分开记**：① 补这一步的**决定**没错（测量面确实缺失）；② 我给它的**理由**错了，已在提交 `a934fa7`
里改成分得清的那半句。这条错误值得留在册，因为它正是"先有结论再找证据"的形状——我写 CI 注释那天，
手上只有「§10 说两轴同为 24 记录/15 ID」这句，而它其实已经在否定我的理由。

## 3. 本轮我自己制造的一条红，与它暴露的仪器弱点

覆盖率趟（`--cov=. --cov-fail-under=70`）出现 `1 failed / 1924 passed`，而**同一套件的无 cov 趟是 1925/0**。
红的是 `tests/test_settings_repr_masking.py::test_repr_masks_every_secret_value`（"settings 的 repr 不得含敏感字段实际值"）。

单变量隔离（同一条用例、两次只差我传进去的假值形状）：

| 假值 | 读数 |
|---|---|
| 五个 key 各给不同多字符串（`alpha-not-a-real-key-111` …） | `3 passed` |
| 五个 key 全给单字符 `k` | `1 failed / 2 passed` |

⇒ 根因是**我的 harness 值形状**，不是打码实现：那条断言用 `str(value) in text` 判"泄漏"，
单字符值必然作为其它词的子串命中。两台仪器弱点登记（本轮不改，`817e7d3` 的打码面不在本书 B 单里）：
1. 该用例对**短值/空值**不具鉴别力，会假红；建议把比对改成"值的精确 token"或给 fixture 一个最小长度门槛。
2. 我这边：给被测面喂假凭据时，值形状本身是实验条件的一部分，要写进日志（本轮已写进本段）。

修正后的覆盖率趟读数见 `reports/gates.md` 补记六。

---

## 4. 包装腿：现量与差距

- Docker **可用**（`docker version --format '{{.Server.Version}}'` = 29.6.2）⇒ 本书"不可用即 BLOCKED"那条不成立，可以真做 Linux/镜像腿。
- 但 `docker build` 后端镜像要装整套运行时（含 CPU torch ~200 MB），且 `frontend/` 的 `next build` 与
  D 单的浏览器验收**共用同一棵 `frontend/` 树**——本仓在册教训：活进程持有 `.next` 时 `next build` 会
  无报错、无进度地卡死。⇒ 顺序上我把 **D 单跑完再做 build/镜像**，本轮此处为**未跑**，不是失败也不是通过。
- 镜像内容面（未构建，先记声明与实装的差）：`backend/Dockerfile` 里 torch 本轮已同钉 `2.13.0+cpu`；
  `.dockerignore` 覆盖 `.env`/数据目录的声明需要在真构建产物上复量（"镜像声明不等于内部实装"）。
- 未跑清单（诚实摊开）：`next build`（Windows 与 standalone `node server.js` 生产形状）、Linux 镜像构建、
  容器 smoke（`127.0.0.1` 独占端口 + 合成数据 + 无模型外发）、远端 CI（未推送 ⇒ 无远端证据）。

## 5. 复算

```bash
C=/c/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010
git -C "$C" --no-pager diff -- .github/workflows/ci.yml           # 两条 CI 补步
git merge-base --is-ancestor 817e7d3 master; echo "rc=$?"          # 候选起点确实含那笔历史
git --no-pager diff-tree --no-commit-id --name-only -r 817e7d3 | grep apply_case_domain_gate
git merge-base HEAD origin/master || echo "NONE (disjoint histories)"
git rev-list --objects origin/master..HEAD | wc -l   # 期望 4301（本轮现量）
python evidence/value_reverse.py <候选 worktree 路径>   # 期望 hits=61 files=1
grep -n "ignoreDuringBuilds\|ignoreBuildErrors" "$C/frontend/next.config.js"   # 期望：无命中
"$R/candidate-envB/Scripts/python.exe" "$R/evidence/value_reverse.py" "$C"        # 期望 hits=61 files=1 lines=104
"$R/candidate-envB/Scripts/python.exe" "$R/evidence/shape_scan_committed_set.py" "$C" "0b54396..HEAD"   # 期望 VERDICT=PASS_VALUE_LEG_PROVED_BITING
```

---

## 6. 晚间两条新读数：远端网络轴（改了 D-5 的价值）与镜像排除面的静态缺口

### 6.1 GitHub：推得动，但**我读不到远端状态**（单变量对照，零写入）

| 目标 | 结果 | 含义 |
|---|---|---|
| `ssh -p 443 git@ssh.github.com`（BatchMode） | **rc=0，`Hi wjt-code-design!`** | 推送路**今天可用**（在册配方成立） |
| `https://api.github.com/meta` | **rc=35（TLS 握手失败），http=000** | 匿名 API 读不到 |
| `https://github.com` | **rc=35，http=000** | 网页/HTTPS 克隆同样不通 |
| `ssh -T git@github.com`（22 端口） | **Connection refused** | 22 不通，只有 443 那条 |
| 对照：`https://mirrors.aliyun.com/pypi/simple/` → 200；`https://hf-mirror.com/api/whoami-v2` → 401 | 本机**有网** | 失败是 **GitHub 专属**，不是断网 |

⇒ **对 D-5 的连带影响（要摊在你签字前）**：选项 (a)"先轮换 + 普通推 + 开 PR"里，
**"推送"今天可做，"自动拿到远端 CI 读数"今天做不到**（API 与网页都不可达）。
所以 (a) 的"远端证据"那半只能靠你在浏览器里看，或交给一台网络条件正常的会话取。
在册旧说法"api.github.com 现在匿名 200 可读"**今天已被现场推翻**（我已去改那条参考记忆）。
另：这次身份握手会在你账号的访问日志里留一条记录（我按你批准的"GitHub 那条"执行，未做任何写操作）。

### 6.2 `backend/.dockerignore` 的排除面盖不住 `data/` 下的两个真库（静态可证，**未构建**）

先钉一件容易读错的事：compose 的 build 上下文是 **`build: ./backend`**（`docker-compose.yml:17`）与 `./frontend`（`:61`），
所以生效的是 **`backend/.dockerignore`（457 B）与 `frontend/.dockerignore`（599 B）**，
**仓库根那份 `.dockerignore`（494 B）对这两条构建根本不参与**——`backend/.dockerignore:2-3` 的注释自己也这么写。

现量（`backend/Dockerfile:64` 是 `COPY . .`）：

| 上下文内路径 | 现有规则是否挡住 | 依据 |
|---|---|---|
| `.env`、`.env.example`、`.env.bak-20260910-pre-qwen38` | **挡住** | `.env` / `.env.*` |
| `app.db`（顶层） | 挡住 | `*.db` |
| **`data/app.db`**（主仓现量存在） | **没挡住** | `*.db` 是顶层通配，Docker 的 `*` **不跨 `/`**；且文件里**没有任何 `data` 相关规则**（`grep -cE "^data/" backend/.dockerignore` = 0） |
| **`data/quota_used.sqlite`**（主仓现量存在） | **没挡住** | 同上，`*.sqlite*` 只在顶层生效 |
| **`.ptmp-s4-run1` / `.ptmp-s4-run2` / `.ptmp-syv-run1`**（主仓现量存在） | **没挡住** | 无 `.ptmp*` 规则 |
| `chroma_db/`、`media/`、`backups/` | **静态判不准** | 目录型规则的递归语义要看 moby 的 patternmatcher 实现，我不拿"应该能盖住"当已验 ⇒ 交给构建腿复量 |

⇒ **结论分两半**（别混）：**声明面已证缺口**（`data/app.db`、`data/quota_used.sqlite`、`.ptmp-*` 三类，靠的是"`*` 不跨 `/`"这条有文档语义，不需构建）；
**实装面未验**（必须真构建后 `docker run --rm <img> ls -la /app/data` 才算数）。
这条**不是本轮新造的担忧**——`backend/.dockerignore:1` 的注释写明它就是为了修"审计 v2 #3：`backend/.env` 曾被 `COPY . .` 烘焙进镜像层"，
而它这次修的是 `.env` 一族，**没把同一形状推广到 `data/`**。
候选 worktree 里 `backend/data/` 只有 2 只已跟踪评测文件（`app.db` 不在候选树，在**主仓**）⇒ 缺口在部署目录被构建时才会咬人。

### 6.3 复算

```bash
C=/c/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010
sed -n '15,20p;59,63p' "$C/docker-compose.yml"          # build 上下文 = ./backend 与 ./frontend
cat -n "$C/backend/.dockerignore"                        # 17 条规则里没有任何 data/ 前缀
grep -cE "^data/|^\.ptmp" "$C/backend/.dockerignore"    # 期望 0
ls -a /c/Users/33393/Desktop/ai-legal-helper/backend/data   # 主仓现量：app.db / quota_used.sqlite（只列名，不读内容）
curl -s -o /dev/null -w "%{http_code}
" --max-time 20 https://api.github.com/meta   # 今天 rc=35
timeout 45 ssh -o BatchMode=yes -p 443 -T git@ssh.github.com                          # 今天 rc=0
```

---

## 7. D-5 选项 (b) 的决策级读数：无父快照**已造出并按值验过**（不动 ref、不动工作树）

Owner 批准的第四条并行腿。脚本 `evidence/orphan_pin.py`（临时 `GIT_INDEX_FILE` + `read-tree HEAD` + `write-tree` + `commit-tree`，
**没有任何 ref 移动、没有 commit、没有 push**）。

| 读数 | 现量 | 怎么核 |
|---|---|---|
| 快照提交 / 树 | `5df5a1277f775fd226f930336fb6c839027fed4e` / `04dd97ad6acbfc0ef4fcd23a966abe58b6c88618` | `cat evidence/orphan-snapshot.sha` |
| 与 HEAD 的关系 | **树逐字等于** `git rev-parse HEAD^{tree}`（同一内容，零历史） | 冷恢复那次两条 print 同行比对 |
| 无父证据 | `git log -1 --format='%P'` 为**空**、`parent_lines=0` | 见下命令块 |
| 对象数 | 快照 **2581**（1 commit + 173 tree + 2407 blob） vs 普通推 **4301** ⇒ 少 **1720** | `git rev-list --objects` |
| **按值反查（关键）** | 那只 13 位历史裸值在快照对象集里 **0 命中**；同一把值在真实历史对象集里 **1 命中（正对照咬住）** | `evidence/orphan_pin.py` 的 value leg |
| 归宿 | pack `evidence/orphan-snapshot.pack` = **141,791,027 B**，`git index-pack` + `verify-pack … : ok`；**冷恢复已跑通**：把 pack+idx 放进一枚临时裸仓（只补一个 `HEAD` 文件），无 ref 指向它也能 `cat-file -t = commit`、`rev-parse <snap>^{tree}` 回到同一枚树 | 下命令块第 4–6 行 |

### 内容轴（别把 351 MB 当成要推的体量）

`git ls-tree -r --long HEAD` 按**路径**加总 = 368,248,372 B，但其中 `diag/frozen-index-004` 与 `-005`
各 155,515,338 B，而这两只目录**逐 blob 相同**（`diff` 空），且每目录 37 条路径只对应 **30 个唯一 blob**。
⇒ 去重后唯一 blob = **149,091,038 B（未压缩）/ 128,433,591 B（盘上）**；实际外发体量看 pack = **141,791,027 B**。
按路径加总会把体量**说大近 2.6 倍**（重复目录 + 目录内重复 blob + 未压缩三件事叠在一起）。

**这 311 MB（按路径）该不该从快照里剔掉，不在我能定的范围**：`frozen-index` 现量被 **8 个文件引用**
（`diag/PROGRESS-20260905.md`、`docs/law-source-inventory.md`、`docs/runbooks/law-updates-monthly.md`、
`docs/progress-handoff-report-20260925.md`、`docs/superpowers/plans/2026-09-25-…md`、`docs/work-report-20260929-d2-signoff-round.md`、
`dispatch-output/local-candidate-closeout-20260928/b_build_snapshot.py`、`b_snapshot_trim_diff.py`）
⇒ 与 09-30 那句"`frozen-index` 在 tests/scripts 0 引用"**不再一致**（那时只看 tests/scripts，这轮把 `docs/` 也纳入了面）。
剔它会同时改掉这 8 处引用 ⇒ 属 Owner 的内容轴裁决，不是我这轮的清洁工活。

### 复算

```bash
R=/c/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2
C=/c/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010
cat "$R/evidence/orphan-snapshot.sha"
git -C "$C" rev-parse 'HEAD^{tree}'                       # 期望 == sha 文件里的 tree
git -C "$C" log -1 --format='%P' 5df5a1277f775fd226f930336fb6c839027fed4e   # 期望空行（无父）
for t in commit tree blob; do printf "%s=%d
" "$t" "$(git -C "$C" verify-pack -v "$R/evidence/orphan-snapshot.idx" | awk -v T=$t '$2==T' | wc -l)"; done   # 现量 1/173/2407，合计 2581
git -C "$C" ls-tree -r --long HEAD | awk '{s+=$4} END{print s}'             # 368,248,372（按路径，会偏大）
git -C "$C" grep -l frozen-index -- . ':(exclude)diag/frozen-index-004' ':(exclude)diag/frozen-index-005' | wc -l   # 8
```

---

## 8. `.dockerignore` 缺口的**真构建**证据（2026-10-10 深夜，H 包装腿）

上一节（§6.2）我写的是"声明面已证、实装面待真构建复量"。现在**构建过了**，用一对能红/能绿的 COPY 实验（基底用本地已存在的 `ai-legal-helper-backend:latest`，不拉网；上下文 = 主仓 `backend/`，即 compose 的 `build: ./backend`）：

| 探针 | Dockerfile | 期望 | 现量 |
|---|---|---|---|
| **负对照** | `COPY .env /probe/dotenv` | 被 `.env` 排除 ⇒ 应失败 | **rc=1**，`failed to compute cache key … not found` ⇒ 排除机制在该上下文**确实生效**（尺子能红） |
| **实验组** | `COPY data/app.db /probe/appdb` | 我判它没被排除 ⇒ 应成功 | **rc=0**；`docker run … ls -la /probe` 显示 **`appdb` = 19,939,328 B**，`head -c 16 \| od -c` = **`S Q L i t e   f o r m a t   3 \0`** |

⇒ **结论从"声明面缺口（推断）"升级为"实装面缺口（已证）"**：从部署目录构建后端镜像时，真实 `backend/data/app.db`（19.9 MB SQLite）**会被烘进镜像层**；同理 `backend/data/quota_used.sqlite`（`*.sqlite*` 也只是顶层通配）与 `backend/.ptmp-*`。
根因：`backend/.dockerignore` 的 `*.db` / `*.sqlite*` 只匹配上下文**根**下的名字，而这两个库在 `data/` 子目录；文件里**没有任何 `data/` 规则**（`grep -cE "^data/" = 0`）。

**可选的修法**（我不动手，登记给票）：在 `backend/.dockerignore` 里把 `*.db`/`*.sqlite*` 改成 `**/*.db`/`**/*.sqlite*`，或直接加一行 `data/`；改完**必须重跑本节的探针**（负对照仍须失败、实验组须变失败）才算修好。

探针产物：`evidence/probe-df-env`、`probe-df-appdb`、`probe-env.err`、`probe-appdb.err`；探针镜像已 `docker rmi`（只删我建的 tag `fazhi-probe-*:tmp`）。

---

## 9. 镜像构建腿：**成**（2026-10-11 00:2x），含两处披露的偏离与两条源侧缺陷

**产出**：`fazhi-closeout-probe:20261010-final`，**3.89 GB**，`v3_build_rc=0`。日志 `evidence/h-backend-image-build-v3.log`。

### 9.1 九步耗时（现量）

| 步 | 内容 | 耗时 |
|---|---|---|
| [1/9]–[3/9] | FROM / WORKDIR / COPY requirements | ~1 s |
| [4/9] | `pip install torch==2.13.0+cpu`（**官方源**） | 392 s（在 v3 里走缓存） |
| **[5/9]** | `pip install -r requirements.txt` | **4319.7 s ≈ 72 分钟**（长杆） |
| [6/9] | 防呆断言（torch 必须 +cpu、无 nvidia-*） | 2.5 s ✅ 通过 |
| [7/9] | **模型烘焙** `SentenceTransformer('BAAI/bge-base-zh-v1.5')` | 823.3 s ≈ 13.7 分钟 |
| [8/9] | `COPY . .` | 0.2 s |
| [9/9] | **`.env` 防呆守卫**（`test ! -f /app/.env`） | 0.3 s ✅ 通过 |

⇒ 端到端 ≈ **1 小时 40 分**（本机、今天）。

### 9.2 镜像内容复量（`docker run --rm --entrypoint sh …`）

| 项 | 现量 | 判定 |
|---|---|---|
| `/app/.env` | **不存在** | ✅ 守卫与 `.dockerignore` 都生效 |
| `/app/data/` | 只有 2 只 in-tree 评测件（`eval_agent_complex.*`），**无 `app.db`、无 `quota_used.sqlite`** | ✅ 候选树形状（主仓那份缺口不适用于候选构建） |
| `chroma_db` / `media` / `backups` | **均不存在** | ✅ |
| torch | **`2.13.0+cpu`，`cuda=None`** | ✅ 与三轴钉版一致 |
| 模型烘焙 | `/root/.cache/huggingface/hub/models--BAAI--bge-base-zh-v1.5`，HF 缓存 **782 M** | ✅ 上线不必拉模型 |
| 关键依赖 | chromadb **0.4.24** / fastapi **0.141.1** / sentence-transformers **6.1.0** / SQLAlchemy **2.1.4** | ✅ 与声明一致 |
| 应用入口 | `/app/main.py`、`/app/agent/` 均在 | ✅ |

### 9.3 容器 smoke（回环、合成、用完即删）

回环端口 **127.0.0.1:8123**；落盘全指容器内 `/tmp`；**六个上游 URL 全指死回环 `127.0.0.1:9`**（构造上不出网）；`HF_HUB_OFFLINE=1`。

| 读数 | 值 |
|---|---|
| `/healthz` | **200，第 9 秒**，正文 `{"status":"ok","db":true,"vector":true,"llm_host":false}`（db/向量自建成功；`llm_host:false`＝死上游不可达，正合设计） |
| `/api/health`（前端消费的那条） | **200** |
| 宿主侧监听 | **只有 `127.0.0.1:8123`**，无 `0.0.0.0` |
| 收尾 | 容器已 `rm -f`，8123 残留监听 **0**；`fazhi-backend/caddy/frontend`（Up 9h）全程未碰 |

### 9.4 两处**披露的偏离**（出厂 Dockerfile 逐行比对：76 行差 2 行，`evidence/Dockerfile.official-v3`）

1. **torch 源 阿里云 → 官方源**（Owner 批准，"今晚要容器"）；
2. **[5/9] 步加 `--extra-index-url https://pypi.org/simple`** 作回落。

### 9.5 两条**源侧缺陷**（出厂路径今天会红，与代码无关）

- **阿里云 `pytorch-wheels` 卡死**：第一轮用出厂源构建时，日志停在下 `torch-2.13.0+cpu`（191.8 MB）那一行**三十多分钟无进展**（后经连接判据确认当时并无该下载的活连接）⇒ 该路径今天不可用。
- **阿里云 PyPI 缺文件**：`pydantic-2.14.0-py3-none-any.whl.metadata` **HTTP 404**（本机可复现：索引页 200、文件 404）⇒ **出厂 Dockerfile 的 [5/9] 今天必红**。修法建议（登记，不擅自改）：给该步加 pypi 回落，或换完整镜像（清华 tuna 已核有该版本）。

### 9.6 我自己的一次 fixture 错（非镜像缺陷）

首跑 smoke 用 `DATABASE_URL=sqlite:////tmp/smoke/app.db` ⇒ 容器内 **`/tmp/smoke/` 目录不存在** ⇒ `sqlite3.OperationalError: unable to open database file`。改成 `/tmp` 下不存在的**文件**路径后 9 秒就绪。**这是我的夹具错，不是镜像缺陷**，记在此以免被读成后者。

### 9.7 复算

```bash
docker images --format '{{.Repository}}:{{.Tag}} {{.Size}}' | grep fazhi-closeout-probe
grep -E "^#[0-9]+ \[[0-9]+/9\]|DONE" "$R/evidence/h-backend-image-build-v3.log" | tail -12
docker run --rm --entrypoint sh fazhi-closeout-probe:20261010-final -c 'ls -la /app/.env; ls /app/data; python -c "import torch;print(torch.__version__, torch.version.cuda)"'
```

---

## 补记（2026-10-11 01:5x）：本文件 §6 那张网络表**已被同日的复测推翻**

§6 里的 `api.github.com` 与 `github.com` 双双 **rc=35 / http=000**、以及文末复算块那句"今天 rc=35"，都是 **10-10 的读数，现在不成立**。10-11 01:5x 三条重探：`api.github.com` **200**、`github.com` **200**、`ssh -p 443` 认证通、`git ls-remote --heads origin` **rc=0**。
拿回来的读数与后果（**全文在 `reports/gates.md` §25 与 §25-a**，此处不重复抄）：
1. 仓库 **public** ⇒ 转 private 会开始吃套餐分钟而余额匿名读不到；若目的是"让 CI 真跑一次"，转 private 可能把目的本身卡死。
2. 远端**只有 `master` 一支** = `985d53e`（09-17 15:15）；本地 `origin/master`=`15562fc`（08-25）是**陈旧跟踪 ref**，与候选 `merge-base` 空（rc=1）。
3. CI `total_count=18`：**17 场 `push` 全 failure** + 1 场 `dispatch` success（#1，08-08）；**`pull_request` 0 场**。最新那场红在**唯一一步** Backend **step 7 `ruff format --check .`**（Frontend job 绿）。
4. ⇒ **推 `codex/*` 分支不触发 CI**（`ci.yml` push 白名单只有 `[main, master]`）——本文件早先"推上去就能拿远端读数"的那类说法要按这条改；要读数得**主动**开 PR 或 dispatch。
5. ⇒ 我在 §2/§7 写的"今天两边都拿不到 CI 证据"**原因换了**：不是网络，是触发语义不覆盖我这棵树。结论（"我只能主张本机绿"）**不变**。
