# D 单验收结论（主会话，2026-10-10 深夜）

被验对象：`reports/browser-acceptance.md`（31,725 B / 218 行 / mtime 21:36:40）+ `evidence/browser/**`。
尺子：`tickets/acceptance-ruler-D-20261010.md`（**在它交付之前写好**，含"不用它用的那把尺子复算"与六种直接驳回形状）。

## §0 结论

**采纳**。7 条判据里 6 绿 1 红（J3），红的那条我用**两种独立方法各自复现**；另附 **1 条要求补齐**、**3 条我未复算**、**3 处措辞/读数偏差**（都不改判定）。

它不是"自证式交付"：核心数字我逐个换方法重算过，且我自己那条最怀疑的"会不会是假绿"没有成立。

## §1 我用什么方法（与它的做法正交在哪）

| 它的方法 | 我的方法 |
|---|---|
| `srv/check-css-purge.py` 数选择器 | 直接 `cat .next/static/css/*.css \| grep -o -F`，并**自带阳性对照**（`.badge{`） |
| `srv/host-histogram.py` 出 host 直方图 | 我自己的 Python：逐行 `json.loads` → 正则抽 `host:port` → 分类 `http` vs `data/blob/about` |
| 它自己的对比度尺子 | 我按 WCAG 2.2 公式**重算**它 JSON 里记录的 fg/bg |
| 它读的 `file:line` | 我按**内容重定位**（不按号跳） |
| 它的收尾三条打印 | 我**原样重跑**三条并逐字比对 |

## §2 逐条复算结果

| 条目 | 它报 | 我的独立读数 | 判定 |
|---|---|---|---|
| J1 非回环=0 | 2 个 jsonl 共 117 行、http 108、非回环 0 | 我自己的脚本：**files=2 http=108 non_http=9**、hosts 只有 `127.0.0.1:3101`、NON_LOOPBACK=**[]** | **采纳**（连 9 = 8 data + 1 blob 的拆分都对上） |
| J2 真实数据零触达 | `backend/data` 1 命中且先于其会话（mtime 15:09:03） | 我重跑 `find`：**同样 1 命中**、`stat` = **15:09:03**；以 19:00 为界 = **0**；候选三目录 mtime 与它逐字相同（chroma 03:11:23 / data 02:16:58 / media 03:08:14） | **采纳**，且它"不替别人认领也不替别人开脱"的标注方式正确 |
| **J3 purge（红）** | 5 个类名在产物里 0、`.badge{`=1；六状态计算样式全同 | 我用 `grep -o -F` 独立复现：**badge-success/-error/-neutral/-accent/btn-ghost-dark 全 0，`.badge{`=1**；`ui.tsx:39` 确为 `` className={`badge badge-${kind}`} ``；**且这两个类定义在 HEAD 版 globals.css 里也存在** ⇒ **缺陷不是 §14 引入的，是既有生产形状缺陷** | **采纳**（这条是本次验收最有价值的产出） |
| J4 键盘 | Enter/Space 各 1 次、两把尺子对账 | 读 `chooser-count.json` 原始值：`base{0,0,0} → afterEnter{1,1,1} → afterSpace{2,2,2}`，`scrollY` 全 0，另含 `trusted` 字段 | **采纳** |
| J5 三档响应式 | 1440 档 h4 w=519 | 读 `responsive-chat.json`：`h4.cls=answer-h4`、`fontSize=15.2`、`rect.w=519` | **采纳**（390 档 41 个越界元素我**未逐条复算**，只抽了一档） |
| J6 四腿矩阵 | false 腿零提交 | `caps-false.json`：三路 `sendEnabled=False`、`dialogsAll` 2 条 alert、`routes.select.skipped="no image button in DOM"`；`caps-missing.json` 有 `submit{upstreamVisionDelta:1}` | **采纳**（见 §3 措辞偏差） |
| J7 取消/切换 | 三不变量成立；切换"设计内不可达"；55 passed | `pytest-cancel.log` = `55 passed in 18.27s`；守卫经我**按内容重定位**确认真实存在（`:41`/`:57`）；占位文案 `服务暂时无响应` 确在 `main.py:1037/1090` | **采纳**（行号偏差见 §3） |
| §8 幻符号 | 零命中、按幻觉处置 | 我复跑 `git grep -n "_sse_transport\|requeued"` = **0 命中** | **采纳** |
| §11 收尾自证 | porcelain 5 行 / 端口空 / find 1 命中 | 我原样重跑：**5 / 0（rc=1）/ 同样 1 命中**；8088 两 PID 仍在听 | **采纳** |

## §3 三处偏差（都不改判定，但按纪律点名）

1. **守卫行号错 2 行、且少报一条**：它写 `useConversations.ts:43/59`，真身是 **`:41`（`newChat`）/ `:57`（`selectConv`）**，另有 **`:88`（`deleteConv`）** 第三条同款守卫它没提。内容断言正确（流式中切会话在设计内不可达），只是号与条数不准。
   ⚠️ **归因修正（2026-10-11，改我自己上一版的说法）**：我原先把这写成"在册那条 `file:line` 是会过期的读数"——**该归因不成立**。现量：主仓与候选树 `HEAD:frontend/lib/hooks/useConversations.ts` 的 blob **同为 `1124fc6a7294221f721df8e1008b42b44fc6005b`**，且该文件**不在** §14 那 5 只脏文件里、`9e3cfc5` 也没碰它 ⇒ 两棵树、盘上与历史三方字节一致，**没有可漂动的轴**。所以这是**它当初读错**（或数错），不是时间造成的漂移。判定仍不受影响（守卫确实存在），但这条偏差的性质要按"读数错"登记，别拿"行号会过期"替它开脱。
2. **对比度小数位未对齐**：按其 JSON 记录的 `fg=[35,49,79] bg=[241,249,255]`，我独立算出 **12.15**，它报 **12.12**（差 0.25%）。两者都远超 4.5:1，**不影响任何判定**；但两把尺子的小数位口径没对齐这件事该记一笔（它另有 `ratioBestCase=12.65`，说明它自己也在处理"合成底不唯一"）。
3. **`submit: null` 是叙述简写**：`caps-false.json` 里**没有 `submit` 这个键**（false 腿没有可提交对象）；真正的证据是三条路由的 `sendEnabled=False` + 2 条 alert。"零外发"由上游计数为 0 支撑，成立；但"`submit: null`"这个写法会被读成"有该字段且为 null"。

## §4 要求补齐（唯一一条，属"可补则补"）

**6 只 JSON 仍带着旧计数器的错读数、且文件内无任何标记**：`cancel-scenarios.json`/`caps-failure.json`/`caps-false.json`/`caps-missing.json`/`caps-true.json`/`responsive-chat.json` 里的 `"nonLoopback": 2~3`，offender 是 `:80 data:image/svg+xml;utf8,…`（就是它 §10 第 9 条说的 `new URL()` 误判）。
报告已在 §1/§10 披露，但**读者按报告指路去开这些 JSON 时，看到的是错值**。⇒ 建议（不阻塞采纳）：在这 6 只文件里加 `"isolationStale": true` 或加一份 `json/README.md` 注明"以 §1 的修正计数器为准"。

## §5 我未复算的三条（如实列出，别读成已验）

1. 390 档 **41 个越界元素全表**（只抽样了这一档的条数与几何分布方向）。
2. 四腿矩阵里的**上游计数逐腿核对**（只核了 `caps-missing` 的 `submit.upstreamVisionDelta=1` 与 `caps-false` 的零提交形状）。
3. §10 **九条仪器自曝**我一条都没有独立复现（它们都是"尺子坏"的自述，方向上是降低结论强度、不是抬升，故不阻塞；且其中第 1 条它主动**撤回**了"应用卡死"的结论，这个动作值得肯定）。

## §6 J3 的后续判据（给修复票的最小变异）

它的**事实层**我复现了（类名不在产物 + 计算样式六者全同），但"**根因是 Tailwind purge 扫不到动态类名**"这句它自己标为**推断**，我同意现状是推断。要把机理证死，最小变异是：
把 `components/ui.tsx:39` 的模板串**临时**改成静态字面量（例如 `kind === "success" ? "badge badge-success" : …`），重建 `frontend/.next`，再对同一只 CSS 跑同一个计数——若 5 个类名出现，机理即证；若仍不出现，则根因另有其人。**这是一次 build 级变异，须排在 H 的构建腿里做**，不在本验收范围。

## §7 交付映射（这条连着 D-21）

D 验的是**盘上未提交字节**（那 5 只 `frontend/` 修改）。我在交付前已证明：**纯净 HEAD + `evidence/frontend-dirty-20261010.patch` 重放 ⇒ 5/5 与盘上 blob 逐字节一致**。
⇒ 因此本次验收**可以迁移到即将提交的那一笔**（D-21）：只要提交的字节与盘上同源，D 的读数对这些字节有效。反之，若有人改了盘上那 5 只再提交，本次验收作废。

## §8 复算（整块可重跑）

```bash
C=/c/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010
R=/c/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2
for p in badge-success badge-error badge-neutral badge-accent btn-ghost-dark ".badge{"; do \
  printf "%-16s %s\n" "$p" "$(cat "$C"/frontend/.next/static/css/*.css | grep -o -F "$p" | wc -l)"; done
grep -n "streaming" "$C/frontend/lib/hooks/useConversations.ts" | head -3
"$R/candidate-envB/Scripts/python.exe" -c "
def lin(c):
 c=c/255.0; return c/12.92 if c<=0.03928 else ((c+0.055)/1.055)**2.4
def L(t): return 0.2126*lin(t[0])+0.7152*lin(t[1])+0.0722*lin(t[2])
a,b=L((35,49,79)),L((241,249,255)); print('ratio=%.2f'%((max(a,b)+0.05)/(min(a,b)+0.05)))"
find /c/Users/33393/Desktop/ai-legal-helper/backend/chroma_db /c/Users/33393/Desktop/ai-legal-helper/backend/data -newermt "2026-10-10 19:00" | wc -l
git -C "$C" status --porcelain | wc -l
netstat -ano | grep LISTENING | grep -cE ':8111|:3101|:8399|:9222'
tail -2 "$R/evidence/browser/logs/pytest-cancel.log"
```
