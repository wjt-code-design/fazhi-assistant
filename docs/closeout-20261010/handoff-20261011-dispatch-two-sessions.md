# 交接件：两张票各开一个新会话（2026-10-11 02:0x）

用途：你把下面两段**原样粘进各自的新会话**即可，票是自足的（指针全写成命令，不需要本会话的记忆）。
运行根（两个会话共用的证据目录，但**各自建子目录**）：`C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2/`
候选树（只读）：`C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010`，HEAD `9e3cfc5`，`porcelain=0`。

## 会话 1 · 证伪式独立复核（补本轮缺的那根非实现者腿）

```
读并执行这张票：C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2/tickets/dispatch-independent-review-20261011.md
你是独立复核者，不是来确认对方做对的：逐条试图推翻票里 7 颗钉子，每个判决必须带你自己跑的命令与它的原样输出，禁止转述对方的报告。
全程只读候选树与主仓；不 commit / 不 push / 不动 ref / 不部署 / 不重启 docker compose / 不开 backend/.env* / 不读写真实 app.db·data·chroma_db·media·backups；不打印凭据值。
硬约束（票末"并发纪律"）：candidate-envB 你只能只读，开跑前先做 pip freeze 的**行集合**指纹核对（不比 sha，顺序会变）；发现指纹变了就立刻停止复跑门禁并回报。
交付：reports/independent-review-C-20261011.md（§0 三行汇总 / §1 逐条判决 / §2 你发现而对方没登记的漏项 / §3 对方"更正"里又错的地方 / §4 已知限制）。
```

## 会话 2 · langchain 族跨大版本迁移（D-3）

```
读并执行这张票：C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2/tickets/dispatch-D3-langchain-migration-20261011.md
先跑票 §1 的三条现量，与票面不符就先回报差异，不要按票里的数字硬改。
顺序不许颠倒：先出 API 冻结表（16 个 module.symbol，含 callbacks 与 runnables），再装包；没这张表不许开始迁移。
硬约束（票末"并发纪律"）：**禁止**向 candidate-envB 或主仓 backend/venv 装包，自建 candidate-envC-1x；每次 pip install 前打印 sys.prefix 自证；不许碰前端构建（next build 只许会话 1 做，且要确认没有活进程持有 .next）。
停止条件照票 §5：基线对不上 / 召回或引用语义漂移 / 需要动第七个版本窗 / 装包触到 backend/venv ⇒ 停下回报，别自行推进。
默认不 commit。
```

## 两边共同的三条（我在票里都写了，这里再点一次给你做派单判断）

1. **它们会撞**：会话 2 天生要装 1.x、会话 1 要用 `candidate-envB` 复跑门禁基线（1925 passed）⇒ 规矩是"会话 2 禁入 envB、会话 1 只读 envB + 前后各做一次 freeze 行集合指纹"。
2. **`next build` 只许一方**（会话 1，为复量 J3）：Windows 上有活进程持有 `.next` 时它会**无报错无进度地卡死**。
3. **副本各建各的、不许互相读中间产物**：同法复现不等于独立印证。

## 它们回来之后我做什么（顺序）

1. 先核**会话 1（复核票）**：逐条出采纳/驳回/要求补测，并进 `closeout-final-J-draft.md` §5；只要它的判据没被推翻，J 才能去"草稿"标记。
2. 再核**会话 2（迁移票）**：它会产生真实调用面改动 ⇒ 我要看它的旧/新双树对照读数，不看它自述的 diff 大小。
3. 我这边仍未闭的只有：D-5（推送，网络今天已通、但**推分支不触发 CI**）、D-7（F 开不开）、D-6/D-8…D-25 等你答。
