# 票 D-22：修「生产构建把六种徽章类名 purge 掉」＋补上 dev/build 差异的回归腿

> 派单对象：新会话（前端票）。触发：Owner 2026-10-11 答「按推荐」。
> 这是**已证缺陷**，不是猜想：证据与复算器都在下面，先自己复跑一遍再动手。
> 并发：**此刻另有两个会话在跑**（复核票 `dispatch-independent-review-20261011.md`、迁移票 `dispatch-D3-langchain-migration-20261011.md`）。
> 你**不许**在候选树或主仓里跑 `next build`（复核会话可能正在用 `frontend/.next`）——**只在副本树构建**，见 §4。

## 0 缺陷（现量，两把独立尺子）

- **类名怎么来的**：`frontend/components/ui.tsx:39` 用模板串拼类名（`badge badge-` 加变量 `kind`）⇒ 类名**运行时才成形**。
- **构建产物里量到什么**：`python evidence/check_badge_purge.py <frontend 目录>` ⇒ `.badge-success`/`.badge-error`/`.badge-neutral`/`.badge-accent` 四个选择器在 `.next/static/css/*.css` 里 **grep 计数全 0**（阳性对照：`.badge{` = 1、`.upload-zone` = 3；`.btn-ghost-dark` 也是 0 但**零使用**，不在缺陷面）。
- **浏览器里量到什么**：六种知识状态徽章的计算样式**逐列相同**（前景 `rgb(35,49,79)`、背景 `rgb(241,249,255)`、对比 12.12:1）⇒ 部署形状里**只有文字不同**，H2 想要的「未验证别再显示成现行」等于没生效。
- **机理已被变异实验证实**（不是推的）：把那只拼接换成含静态字面量的等价写法并重建 ⇒ 四个类名各出现 **1 次**；还原后再建 ⇒ 回到 **0**。日志 `evidence/h-next-build.log`、`evidence/h-next-build-mutant.log`、`evidence/h-next-build-restored.log`，脚本 `evidence/mutate_ui.py`（三次构建 rc 均 0）。
- **为什么一直没被发现**：`frontend/package.json` 的门禁只有 lint + tsc + vitest，**没有任何一条跑 `next build` 并对产物断言** ⇒ dev 与 build 的差异是盲区。

## 1 两种修法（你选，但要把代价写清）

| 方案 | 做法 | 代价 | 推荐 |
|---|---|---|---|
| A | 把 `StatusBadge` 的 kind 到类名改成**显式静态映射**（每个分支写完整字面量，如 `badge badge-success`），让 Tailwind 的 content 扫得到 | 只改一只组件；产物体积不变；语义零改动 | 推荐 A |
| B | 给 `tailwind.config.ts` 加 `safelist`（四个 `badge-*`） | 全局豁免，将来同类问题继续被掩盖；且 `@layer components` 的自定义类是否吃 safelist 需先证 | 次选，仅当 A 在同树构建后仍为 0 才用 |

⚠️ 不要改颜色/色相语义（G11 未裁）、不要改六种状态到四类的映射（那是已入库的 H2 改动）、不要动对比度（现 12.12:1，远高于 AA 的 4.5）。**本票只解决「类名到不了产物」这一件事。**

## 2 验收尺子（四条都齐才算完，缺一不可）

1. **产物断言**（修复前红、修复后绿）：`python evidence/check_badge_purge.py <副本树>/frontend` ⇒ 四个 `badge-*` 计数**各 ≥1**。
2. **浏览器成对断言**（不能只断言「不同」）：在副本树起 standalone 前端，实测 `badge-success` 与 `badge-error` 的 `color` 与 `background-color` **两两不等**，其余成对也各给读数；同时对比度仍 ≥4.5（WCAG 2.2 AA）。⚠️ 注入 token 属绕守卫，必须写进「已知限制」。
3. **回归腿入库**（本票真正持久的价值）：新增一条**跑 `next build` 并对产物断言**的脚本 + npm script（例：`build:check`），并写明它在 CI 里应挂哪个作业。只修一次样式而不堵盲区，下一个动态类名还会这样消失。
4. **负向自证**：把修复回退一处（例如只留一个分支仍是拼接写法），确认尺子 1 **变红**；报告里点名红的是哪条断言，不接受「红了」三个字。

## 3 停止条件（出现就停下回报，别自行推进）

- 方案 A 下尺子 1 仍为 0 ⇒ 停，回报（说明 purge 还有第二根因，别硬凑 safelist 盖过去）。
- 需要改设计 token、引入新色相，或改六状态的映射 ⇒ 停，那是 G11/H2 的口径，不在本票射程。
- Windows 上 `next build` 无报错无进度卡死 ⇒ 先查有没有活进程持有 `.next`（在册事实），换目录/换端口重来，**不要杀别人的进程**。

## 4 硬边界

只在运行根下**你自己命名的副本树**里构建与起服务（建议 `C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2/badge-20261011/`）；**不碰候选树与主仓的 `frontend/.next`**。
不改 Python、不改后端契约；不开/不哈希 `backend/.env*`，不读写真实 `app.db`/`data/`/`chroma_db/`/`media/`/`backups/` ——**注意两棵树都有这些**（候选树里 `.env` 是 0 字节、`chroma_db/chroma.sqlite3` 147,456 B），别按「候选树里没有」推理。
若环境里出现任何 `*_BASE_URL`（含 `RERANK_NATIVE_URL`）必须指 `127.0.0.1`；不 `git push`、不改历史、不动任何 ref、不部署、不碰端口 3021/8088；不打印凭据值。
**默认不 commit**；要入库先报 Owner（并行会话的 tracked 改动不得夹带）。

## 5 交付

`C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2/reports/d22-badge-purge-fix.md`
结构：§0 三行汇总（改了哪几只文件、尺子 1/2/4 的**修复前后读数**、回归腿挂在哪个命令）→ §1 修法与取舍 → §2 四条读数各自怎么复算 → §3 我自己犯的错 → §4 已知限制（含「这是副本树读数，不是 CI 读数」）。
指针一律绝对路径 + 可跑命令；产物（构建日志、断言 JSON）落 `evidence/` 并在报告里点名。
