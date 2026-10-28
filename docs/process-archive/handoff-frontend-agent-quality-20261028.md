# 法智 · 交接书：前端镜像重建上线 + Agent 质量门禁（2026-10-28）

> **本文写给没有本会话记忆的助手。** 两项任务均已完成根因定位，只差"最后一段路"，
> 所有中间态与已验证事实都在下文，**照做即可，不必重新试错**。
>
> **前置必读**：`docs/process-archive/progress-handoff-report-20260925.md`（项目主线状态）、
> `.workbuddy/memory/2026-10-28.md`（当天全部实测记录，含云服务器部署全过程）。
>
> **代码基线**：本文写作时 HEAD = `40738a4`（前端 Agent 入口 + 发送键右对齐 + Dockerfile npm 源可配）。
> 接手前先 `git log -8 --oneline` 确认实际 HEAD —— **并行会话正频繁提交**。

---

## 0. 30 秒定位

- **仓库**：`C:\Users\33393\Desktop\ai-legal-helper`
- **线上服务**：`http://8.156.78.5:8080`（阿里云 ECS，Ubuntu 22.04.5，2核4G，40G 盘）
- **本机**：`http://127.0.0.1:8088`（Docker Desktop）
- **账号**：`admin` / 密码在根 `.env` 的 `ADMIN_PASSWORD`（2026-10-28 已换成 26 位强密码）
- **当前状态**：**线上完全可用**，2026-10-28 17:37 全链路验收 **24/24 通过**（见 §5 验收脚本）
- **本文的两项任务**：
  - **任务 A**：前端镜像重建 → 上线两个 UI 改进（发送键右对齐 + 「深入分析」按钮）
  - **任务 B**：Agent 质量门禁频繁拒绝，导致用户点了「深入分析」会看到报错

---

## 1. 任务 A：前端镜像重建与上线

### 1.1 要上线什么（代码已就绪，只差镜像）

提交 `40738a4` 含 5 个文件改动，**已通过 tsc / eslint / vitest（101 个测试全过）**：

| 文件 | 改动 |
|---|---|
| `frontend/lib/api.ts` | `ChatPayload.forceAgent`；`buildChatBody` 仅在 true 时写 `force_agent` |
| `frontend/lib/hooks/useChatStream.ts` | `doSend` 的 `sendOpts` 增 `forceAgent`；**resume 时不传** |
| `frontend/components/chat/InputBar.tsx` | 新增「深入分析」圆形切换按钮；发送按钮补 `ml-auto`（右对齐） |
| `frontend/app/chat/page.tsx` | `deepAnalysis` 状态，**发出的那一轮生效后自动复位** |
| `frontend/Dockerfile` | npm 源改为 `ARG NPM_REGISTRY`（默认 npmmirror）+ fetch 重试参数 |
| `frontend/Dockerfile.prebuilt` | 新增：跳过 npm ci/next build，只把已有 `.next` 产物打进镜像 |
| `frontend/tsconfig.json` | 补 `"baseUrl": "."`（配合 `paths` 别名） |

⚠️ **`Dockerfile.prebuilt` 是本次专门准备的备用路径**，专治"装依赖装不上"：
它以 `ai-legal-helper-frontend:latest` 为基础镜像，只 COPY 三样产物，**零联网、几秒完成**。
只要能拿到一份构建好的 `.next`，用它打包即可。

### 1.2 卡在哪（四道关卡，逐一实测）

| # | 路线 | 失败原因（实测） |
|---|---|---|
| 1 | 本机 `docker build` | `RUN npm ci` → **ECONNRESET**。容器内**不继承**宿主机代理（`http_proxy=127.0.0.1:59863` 在容器内不可达）；改用 npmmirror 后仍断 |
| 2 | 本机 `next build` | `EPERM: operation not permitted, open '.next/trace'`。**沙箱拦截独占打开**；已排除 `NODE_OPTIONS` shim（`env -u NODE_OPTIONS` 后依旧失败） |
| 3 | 服务器拉 `node:20-alpine` | Docker Hub **被墙**：`registry-1.docker.io` 连接超时（DNS 解析到污染 IP） |
| 4 | 复用服务器现有前端镜像构建 | 权限 → 已解（`--user root`）；缺 devDeps → 已解（见下）；**最后 `npm ci` 仍 ECONNRESET** |

### 1.3 关键根因（这条最值钱，别再踩）

**服务器上 `npm ci` 只装了 21 个包，devDependencies 全被跳过** ⇒ 缺 `typescript`
⇒ Next 解析 `tsconfig` 的 `@/*` 路径别名依赖 typescript 包 ⇒ 报
`Module not found: Can't resolve '@/components/ui'`。

两个叠加原因：
1. 前端镜像里有 `ENV NODE_ENV=production`
2. 该镜像的 npm 全局配置 **`omit=dev`**（`npm config get omit` → `dev`）

⇒ `npm ci --include=dev` **单独用无效**（被 omit 覆盖），必须同时清空：
```sh
export npm_config_omit=""            # 关键，--include=dev 不足以覆盖 omit=dev
export npm_config_registry="https://registry.npmmirror.com"
npm ci --include=dev --no-audit --no-fund
```

### 1.4 建议执行路径（按可行性排序）

**路径 ①（推荐）：传 node_modules 绕过网络**
本机 `frontend/node_modules` 是完整可用的（tsc / eslint / vitest 都跑通了）。
把整个 `node_modules` 打包传到服务器，直接 `next build`，全程零联网。

```bash
# 本机
tar czf /d/_fazhi-deploy/fe-nm.tar.gz -C frontend node_modules
# 传到服务器后
docker run --rm --user root -v /opt/fazhi/fe-build:/app -w /app \
  fazhi-frontend:latest sh -c 'npx --no-install next build'
```
⚠️ node_modules 约 300MB，按实测上行 0.8MB/s 需 **6-8 分钟**（家宽上行只有 6Mbps，别按 30M 估）。

**路径 ②：给容器配代理（未实测，值得一试）**
宿主机代理在 `127.0.0.1:59863`，容器内要用 `host.docker.internal` 才能访问到：
```bash
docker run --rm --network host \
  -e HTTP_PROXY=http://host.docker.internal:59863 \
  -e HTTPS_PROXY=http://host.docker.internal:59863 \
  ...
```
⚠️ 未实测。WorkBuddy 的代理端口可能随会话变，**先 `env | grep -i proxy` 确认当前值**。

**路径 ③：构建完成后打包上线**
```bash
# 服务器上产物在 /opt/fazhi/fe-build/.next/{standalone,static}
# 用 Dockerfile.prebuilt 打镜像（基础镜像用现有的，无需联网）：
docker build -f Dockerfile.prebuilt -t fe-prebuilt:tmp .
docker tag fe-prebuilt:tmp fazhi-frontend:latest
# 重建前端容器（compose 期望的镜像名是 fazhi-frontend:latest）
docker compose up -d --force-recreate frontend
```
⚠️ **镜像名必须对齐**：compose 项目名取自目录名（`/opt/fazhi` ⇒ `fazhi`），
所以 compose 找的是 `fazhi-frontend:latest`，不是 `ai-legal-helper-frontend:latest`。
**标签不对 ⇒ compose 判定镜像缺失 ⇒ 触发 build ⇒ 拉 Docker Hub 超时**（2026-10-28 实际踩过）。

**路径 ④：绕过构建，改用已有镜像**
若只是想先让「深入分析」按钮可用：本地 `node_modules` + 本机 `next dev` 起开发服务器，
用 `next.config.js` 的 rewrites 代理到后端 8000 验证功能，**镜像上线可以推后**。

### 1.5 任务 A 验收标准

1. `docker images` 里 `ai-legal-helper-frontend:latest` 的 `CreatedSince` 是今天
2. 云端首页能加载，输入框旁出现「深入分析」按钮（节点连线图标）
3. 点开按钮 → 激活态高亮 → 发一条消息 → **请求体带 `force_agent: true`**
   （用浏览器 F12 Network 面板看 `/api/chat` 的 payload）
4. 窄屏（<768px）下发送按钮**贴右侧**（本次修的 `ml-auto`）
5. `curl --noproxy '*' http://8.156.78.5:8080/api/health` 仍 200
6. 重新跑 §5 验收脚本，**24/24 仍全过**

---

## 2. 任务 B：Agent 质量门禁频繁拒绝

### 2.1 现象（2026-10-28 实测，非推断）

Agent 链路**技术上完全跑得通**：
```
agent_status: processing → waiting_user
clarification: "是否存在故意或重大过失挑逗、激怒动物的情形"   run_id=… state_version=4
resume 续跑：state_version 4 → 6 → 8  ✅
writer 产出过：{"reason":"DRAFT_VALIDATED","claims_proposed":3,"claims_accepted":3}
```

但**经常在最后的质量门禁被拒**，实测抓到三类：

| 错误码 | 含义 | 抛出位置 | 层级 |
|---|---|---|---|
| `QUALITY_CHECK_FAILED:no_citation_while_hit` | 检索到条文，但答案正文没引用 | `quality.py:76` → `main.py:1160` | **终稿级** |
| `NON_CANONICAL_CITATION` | 法条引用格式不规范 | `agent/verifier.py:412` | 争点级 |
| `UNSUPPORTED_NUMERIC_TOKEN` | 用了无来源可核对的数字 | `agent/service.py:163` | 争点级 |

⚠️ **层级决定 partial 开关管不管用**：
- 争点级失败（后两个）⇒ `agent_partial_delivery_enabled` **能**降级为"部分交付"
- 终稿级失败（第一个）⇒ partial **管不到**，仍然整轮报错

**2026-10-28 17:48 开启 partial 后的实测（云端连跑 3 次，同一问题）**：
```
run1: 正文 1340 字  coverage=full   uncovered=[]
run2: 正文  861 字  coverage=full   uncovered=[]
run3: 失败  QUALITY_CHECK_FAILED:no_citation_while_hit
终态分布：完整(full) 2/3，失败 1/3
```
⇒ 相比开启前（0–1/3 拿到正文）有改善；⚠️ 但**生成是采样的**，3 次样本不足以断言因果，
接手助手应按 §2.4 的验收标准跑 5 次复核。

### 2.1b ⭐ 三个错误码的共同根因（最值得先查的方向）

`no_citation_while_hit` 与 `NON_CANONICAL_CITATION` **是同一个病**：法条引用的**书写形式**
不符合解析器期望。

- `retrieval.py:781` `extract_citations(answer)`：只认 `《法名》第X条` 这种**带书名号**的格式
  （支持合成引用「《法》第十七条、第五十八条」）
- 模型若写成「民法典第1249条」这类无书名号、或阿拉伯数字条号混写 ⇒ 解析器提取不到 ⇒
  - 终稿级：`context_present=True` 且 `cites` 为空 ⇒ `no_citation_while_hit`（`quality.py:74-77`）
  - 争点级：verifier 判引用不规范 ⇒ `NON_CANONICAL_CITATION`（`verifier.py:412`）

⚠️ **一处顺序疑点（未验证，接手助手优先查这个）**：
```
main.py:1157  quality_result = quality_checker(answer, True)   ← 先要求正文已有可解析引用
main.py:1164  normalized = expand_citations_fn(normalized)      ← 之后才把非规范写法规范化
```
若 `expand_citations` 本来就能把「民法典第1249条」转成规范形式，那么**先判后规范化**就可能
把"本该能救的答案"提前判死。**这可能是治本的切入点** —— 但**未经实测**，需先复现确认：
让模型故意写非规范引用 → 观察是否被判 `no_citation_while_hit` → 再确认 `expand_citations`
是否真能修正这种写法。⚠️ 注意**调整顺序有风险**：`quality_check` 同时是防"检索命中却无引用"
的防线（`quality.py:74` 的注释写明它要排除"诚实拒答"），放宽可能导致无据胡答漏网。


### 2.2 代码位置（照此定位，别全仓扫）

| 位置 | 作用 |
|---|---|
| `backend/agent/service.py:416` | 读 `partial` 开关 |
| `backend/agent/service.py:455-478` | 失败争点记 `uncovered`、继续其余争点（**开 partial 才走**） |
| `backend/agent/service.py:480-490` | **全部争点都失败 ⇒ 仍整轮失败**（"不得伪造部分交付"，有意为之） |
| `backend/agent/service.py:496-501` | `verifier.verify(..., covered_issues_exempt=未覆盖集合)` |
| `backend/agent/service.py:512+` | verifier 对**已写出内容**非 PASS ⇒ 仍整轮失败（fail-closed，有意） |
| `backend/agent/service.py:161-172` | 原因码 → 中文说明的映射表 |
| `backend/agent/verifier.py:285` | partial 模式下把未覆盖争点传给校验器，豁免其覆盖判定 |
| `backend/agent/verifier.py:412` | `NON_CANONICAL_CITATION` 抛出点 |
| **`backend/quality.py:50-83`** | `self_check` —— **终稿级**自检；`quality.py:74-77` 是 `no_citation_while_hit` 判定 |
| **`backend/retrieval.py:781`** | `extract_citations` —— 只认 `《法名》第X条`；**引用格式问题的根** |
| **`backend/main.py:1150-1170`** | 终稿 finalize 流程；`1157` quality_check → `1164` expand_citations（**顺序疑点**） |
| `backend/main.py:1160` | `QUALITY_CHECK_FAILED:{reason}` 的组装处 |


### 2.3 建议顺序（三步，成本递增）

**第 1 步 ✅ 已完成（2026-10-28 17:45）：`agent_partial_delivery_enabled=true`**
- 效果：某个争点写不出来 ⇒ 记为未覆盖、**继续写其余争点** ⇒ 交付部分答案 + 明确标注
- **前端展示已完整就绪**（不用改前端）：
  - `useChatStream.ts:181-185` 解析 final 帧的 `coverage_status`/`uncovered_issues`
  - `MessageBubble.tsx:114-125` 渲染琥珀色横幅「⚠ 部分交付：…另有 N 个争点…」
  - `lib/coverage.ts` 是纯函数，实时流与历史会话共用同一套文案
- ⚠️ 代价：失败请求的 LLM 调用数从 1 次升到 N 次（争点数）。配额已放到 1 亿，无压力
- ⚠️ **只对争点级失败有效**，终稿级 `no_citation_while_hit` 仍会整轮报错（见 §2.1 层级表）

> ⚠️ **踩坑警示（务必读）**：本项目 compose 用**显式 `environment:` 列表**而非 `env_file`，
> 所以**只往 `.env` 写新开关不会进容器**。2026-10-28 实测：
> `.env` 里 `AGENT_PARTIAL_DELIVERY_ENABLED=true`，容器内 `settings` 读到的是 `False`。
> **新增任何 settings 开关，必须同步在 `docker-compose.yml` 的 backend `environment:` 里加一行。**
> 已在 `docker-compose.yml` 补上 `AGENT_PARTIAL_DELIVERY_ENABLED` 与
> `AGENT_WRITER_CORRECTIVE_RETRY_ENABLED` 两行（2026-10-28）。同类事故此前已发生过一次
> （`RERANK_*` / `EMBEDDING_*`，见 2026-10-27 ADR-011 注释）。

**第 2 步：`agent_writer_corrective_retry_enabled=true`（谨慎）**
- 让 writer 自身可避免的失误（引用错 id / 非规范引用 / 无来源数字）**重采样重试一次**
- 依据：T3 的 1e9 实证 —— 同分布输入两次生成结果不同，重试**可能**改变结果
- ⚠️ **但 P5 两轮独立盲评点名 on 臂把核心争点整块排除**。建议单独开关、分批评估，别与第 1 步同时上
- ⚠️ compose 白名单已补（2026-10-28），可直接在 `.env` 打开即生效

**第 3 步：调提示词 / 校验口径（真正治本，工作量在这里）**
- 三个错误码都指向同一个问题：**模型写出的法条引用形式不稳定**（见 §2.1b）
- 排查入口（按优先级）：
  1. **先验 §2.1b 的顺序疑点**（`main.py:1157` vs `:1164`）—— 成本最低，可能一举多得
  2. `backend/agent/writer.py`（起草）
  3. `backend/agent/verifier.py`（校验判定）
  4. `backend/prompts.py` + `backend/domain_rules.py:321`（提示词）
- ⚠️ **提示词散落 4 处**：`backend/prompts.py` / `backend/domain_rules.py:321` /
  `backend/agent/runtime.py` / `backend/query_rewrite.py`；组装入口 `main.py:429` 与
  `backend/agent/writer.py:810`。改一处不够，**四都要看**。
- ⚠️ **`backend/prompts.py` 处于冻结状态**（见 §4.1）——动它前先确认解冻流程


### 2.4 任务 B 验收标准

1. 同一问题连续跑 5 次，**至少 4 次拿到正文**（当前基线：3 次里 2 次拿到正文）
2. 若仍失败，前端应显示**琥珀色「部分交付」横幅**而非红色报错
   （⚠️ 争点级失败才有横幅；终稿级 `no_citation_while_hit` 仍会红色报错 —— 这是当前的主要失败形态）
3. `docker compose logs backend` 里 `writer_render_summary` 的 `reason` 分布：
   `DRAFT_VALIDATED` 占比显著上升，`UNSUPPORTED_NUMERIC_TOKEN` / `NON_CANONICAL_CITATION` 下降
4. 抽查引用：`citation_status.in_context` 里的条文**确实在答案正文中被引用**
   （`no_citation_while_hit` 就是两者不一致）
5. **若 §2.1b 的顺序疑点被证实并修复**：终稿里的引用形态放宽后，
   `no_citation_while_hit` 应显著下降，同时 `cite_bad`（引用了库外条文）**不得上升**
   —— 两者是此消彼长的安全对，**必须同时看**

### 2.5 复现命令（实测脚本，已在服务器上）

```bash
# 云端：/opt/fazhi/agent_partial_test.py（连跑 3 次，统计 coverage 分布）
# 本地已有副本：_agent_partial_test.py（未跟踪）
# 用法：python3 agent_partial_test.py
```
脚本逻辑：自动回答 clarification 直到终态 → 抓 final 帧的 `coverage_status`/`uncovered_issues`
→ 统计「完整(full) / 部分交付(partial) / 失败:错误码」的分布。


---

## 3. 纪律与坑（本日实测，**先读再动手**）

### 3.1 权限与沙箱

| 现象 | 说明 |
|---|---|
| `Permission request rejected by user: read C:\Users\33393\.ssh\` | Agent 侧**读不到 SSH 私钥** ⇒ 无法自己发 SSH。策略收紧时出现，恢复条件是 Owner 点"允许" |
| `network 8.156.78.5` 被拒 | 同上，公网请求也会被拦 |
| `PROGRAM BLOCKED BY SECURITY POLICY: wsl.exe` | `wsl.exe` 在程序黑名单，**不可绕过**；vhdx 压缩只能由 Owner 以管理员执行 |
| `cmd.exe cannot be used from the PowerShell tool` | 用原生 PowerShell 语法替代 |
| PowerShell 里 `wsl.exe` / `docker.exe` 不能接管道 | "无法在管道中间运行文档"。改成 `$o = & exe args; $o` 先赋值再输出 |
| `docker compose` → `unknown command` | Docker Desktop 重启后插件扫描失效。**改用完整路径**：`"/c/Program Files/Docker/Docker/resources/cli-plugins/docker-compose.exe" -f docker-compose.yml ...`（v5.3.1 可用） |
| 本机 `next build` → `EPERM: .next/trace` | 沙箱拦截独占打开。**本机跑不了 next build**，只能容器内构建 |
| **`.env` 写了新开关但容器读不到** | compose 用**显式 `environment:` 列表**而非 `env_file`。⚠️ 新增 settings 开关**必须同步加进 `docker-compose.yml`**，否则"改了没生效"且**无任何报错**（2026-10-28 实测：`.env` 是 true、容器内读到 False） |
| **本机配置有三重来源，且优先级反直觉** | 本机存在 `docker-compose.override.yml`（bind-mount `./backend:/app`）。配置解析顺序：**① compose 注入的环境变量 > ② `/app/.env`（即 `backend/.env`）**。pydantic 是「环境变量优先」，所以**环境变量里的旧值会压过 `.env` 文件里的正确值**。2026-10-28 实测：`RERANK_API_KEY` 环境变量是 51 字符旧值、`backend/.env` 是 117 字符正确值 ⇒ 容器内取到 51 ⇒ rerank 真实调用 HTTP 401 ⇒ 前端横幅"rerank 已全部耗尽"。**排查此类问题时必须同时看容器 `docker inspect .Config.Env` 与容器内 `settings` 的实际值**，只看 `.env` 文件会误判 |
| **WorkBuddy 会话环境会带旧 `.env` 快照** | 我这条命令通道的环境变量里 `RERANK_API_KEY`/`SILICONFLOW_API_KEY` 是历史值（`env \| grep` 可查）。compose 插值 **shell > `.env` 文件** ⇒ 通过 Bash 跑 `compose up` 会注入旧值。⚠️ `env -u VAR` 在本机对 `docker-compose.exe`（Windows 原生）**实测清理不彻底**：`compose config` 显示已清理（117），但同一条命令的 `compose up` 建出的容器仍是旧值（51）。**结论：不要依赖 `env -u` 修本机 compose，改用 override 显式覆盖或重启 WorkBuddy 客户端** |
| 沙箱基础设施故障 `SandboxError 0xFFFFF826` | "center 规则快照不可用" ⇒ **Bash / PowerShell / Grep 全部拒绝执行**，但 **Read / Write / Edit 仍可用**。此时只能改文件、不能跑命令/git。等待基础设施恢复后补做提交与验证 |

### 3.2 网络

| 现象 | 说明 |
|---|---|
| **测公网必须加 `--noproxy '*'`** | 本机有 `http_proxy=127.0.0.1:59863`，否则测的是代理不是你的服务器。裸 TCP 探测（`/dev/tcp`）不受影响 |
| 区分"被安全组拦截" vs "服务没起" | 被拦截 = **超时丢弃**（8s）；服务没起 = **立即拒绝**（<1s）。这个区分法今天反复用到 |
| `scp` 偶发**静默失败** | 传完文件但目标不存在。**改用 `base64 -w0 file \| ssh "base64 -d > path"`**，今天稳定 |
| 容器内 npm 直连 registry.npmjs.org | ECONNRESET。容器**不继承**宿主机代理，`127.0.0.1` 在容器内不可达 |
| 服务器拉 Docker Hub | 被墙（`registry-1.docker.io` 超时）。**服务器上绝不 build**，用预构建镜像 |
| 家宽上行只有 **6Mbps** | 1.39GB 传了 30 分钟。**别按 30M 估时间** |

### 3.3 git 与工作树

- **移动被 git 跟踪的文件会污染状态**：本日移动 4 个快照目录到 D 盘，其中 4 个被跟踪的文件变成 `deleted`，
  导致 `git commit` 中断。修复：`git checkout -- <paths>` 恢复（记忆里有专门提醒：不要 `git clean` / `reset --hard` / `stash`）
- **提交后必须核对**：`git log -1` + `git status --short | grep "^ D"` 应为空
- **并行会话正频繁提交**：动手前 `git log -8 --oneline` + `git status` 确认 HEAD，不要假设

### 3.4 环境

- **沙箱重置会丢 PATH**：`docker` 找不到时补
  `export PATH="/c/Program Files/Docker/Docker/resources/bin:$PATH"`
- **PowerShell 工具在本机拿不到 stdout**（exit 0 但无输出）—— 实测本会话可用，但别依赖
- **Python 写文件必须 `newline=''`**（本项目 autocrlf=true，否则 `\n` 变 `\r\n`）
- **`os.walk` 统计大小恒为 0** → 统计磁盘占用必须先 `os.path.isfile` 分支
- **PowerShell 工具禁 `cmd /c start` / `Start-Process` 启 GUI**；`docker` 命令要用完整路径
- **PowerShell 管道给 `docker.exe` 会报"无法在管道中间运行文档"** → 先赋值再输出
- **pytest 每次启动会删掉已存在的 `--basetemp`** ⇒ 一个命令里串跑多次 pytest 会炸成大批 setup error。
  每跑次用唯一空目录

---

## 4. 不要做的事

1. ❌ 不要动 **`state_machine.py` / `prompts.py` / `gate5_judge.py`** —— 处于**冻结状态**
   （ruff exclude + `docs/code-review-standard.md` §2 B1：触碰即阻断）。任务 B 若要改 `prompts.py`，
   **先确认解冻流程**（删除 exclude + 接受 lint + 在 pyproject 留痕），先例见
   `docs/code-review-standard.md` 与 verifier/chat_integration（09-16）、repository.py（09-18）的解冻记录
2. ❌ 不要 `docker image prune -a` —— 25.55GB 是**回滚镜像**（`pre-reviewfix-20261021` / `adr021` / `p02`），
   本仓缺父提交 `0263bd5`、推不动也 fetch 不回，删了不好重建
3. ❌ 不要改**真实 quota 库**去"修"配额 —— 正确做法是调 `quota_total`（已在 2026-10-28 调到 1 亿）
4. ❌ 不要在服务器上 `docker compose build` —— 40G 盘会被构建缓存撑爆（本日实测构建缓存曾达 44.79GB）
5. ❌ 不要在**灵犀项目**（`C:\Users\33393\WorkBuddy\2026-08-15-00-39-34\backend`）上动手 ——
   它的 `lingxi-api` 起不来是**预先存在问题**（镜像里的 alembic 只到 `0012`，DB 已到 `0023`），
   与法智部署无关。**Owner 明确表示"没说要部署灵犀项目"**
6. ❌ 不要 `git clean` / `git reset --hard` / `git stash` —— 会毁掉其他助手的证据与产物
7. ⚠️ 不要在 Agent 路径上"顺手"改 `agent_max_steps` / `agent_max_tool_calls` ——
   Owner 明示"不自动放大"（2026-09-14 授权记录）

---

## 5. 验收脚本（已存在，可直接复用）

`C:\Users\33393\Desktop\ai-legal-helper\_acceptance.py` —— 全链路验收，**24/24 通过**为基线。

覆盖：两端 `/healthz`、`/api/health`、首页 HTML、前端静态 JS、登录、配额告警位、
**真实问答（SSE，走完整检索+LLM，no_cache=true）**、召回到条文数、引用可核对性、会话建立。

```bash
python _acceptance.py
```
- 口令从根 `.env` 读，**不打印**
- 本机代理已用 `ProxyHandler({})` 绕开（等价于 `curl --noproxy '*'`）
- ⚠️ 该文件是**未跟踪**的临时脚本，若被 `git clean` 清掉需重写（逻辑不长，可照上文 §5 描述重建）

---

## 6. 线上现状速查（2026-10-28 17:37 实测）

```
云端 http://8.156.78.5:8080
  fazhi-backend   Up (healthy)     fazhi-caddy  Up      fazhi-frontend  Up
  /healthz  → {"status":"ok","db":true,"vector":true,"llm_host":true}
  真实问答  → 1758 字，召回 13 条，in_context=13 / external=1 / unknown=1
  配额      → qwen38_flash left≈99,987,942 / total=100,000,000
  agent     → agent_enabled=True, agent_traffic_percent=0,
               agent_partial_delivery_enabled=True（2026-10-28 17:45 开启并复验）
  嵌入集合  → legal_provisions_te4（云端集合，2026-10-27 修的 EMBEDDING_* 注入 bug 未复现）

本机 http://127.0.0.1:8088
  真实问答  → 1171 字，召回 10 条，in_context=10 / external=0 / unknown=0
  agent     → 三个开关与云端一致

服务器  8.156.78.5  Ubuntu 22.04.5  2核4G经济型e  40G盘(剩24G)  内存实测3.6G
        Docker 29.6.2 + Compose v5.6.1  4G swap  ufw 放行 22/8080
        ⚠️ 试用实例 2026-11-08 到期释放（数据没，源在本机，重传约 30 分钟）
C 盘    67 GB 可用（vhdx 压缩后，92.2GB→49.8GB，回收 42.4GB）
```

**未上线的两项**（即本文的两项任务）：
- 前端旧镜像 ⇒ 无「深入分析」按钮、发送键不右对齐
- Agent 质量门禁 ⇒ 用户一旦能触发 Agent，仍有约 1/3 概率撞上终稿级报错

---

## 7. 交接时未完成的动作（接手助手需补做）

⚠️ 2026-10-28 18:18 收尾时，**WorkBuddy 沙箱基础设施故障**（`SandboxError 0xFFFFF826`），
Bash / PowerShell / Grep 全部不可用，只完成了文件编辑，**未能执行 git 提交**。
接手助手需补做：

1. `git status` 确认待提交文件（`docker-compose.yml` 与两份 docs 均有未提交改动）
2. 提交 `docker-compose.yml`（compose 白名单补两行 AGENT 开关）
3. 提交 `docs/process-archive/handoff-frontend-agent-quality-20261028.md`（本次补充内容）
4. 复验：`docker compose config | grep AGENT_` 确认两个新变量已注入
5. 复验云端：`docker compose exec backend python -c "from settings import settings; print(settings.agent_partial_delivery_enabled)"`
6. 清理未跟踪的临时脚本：`_acceptance.py` / `_agent_partial_test.py` / `_enable_agent.py`
   （⚠️ `_acceptance.py` 是 §5 的验收脚本，**建议保留**；其余可删）
