# 法智：账号边界与登录并发只读审查（第 4 轮）

**本文件为本轮独立新建报告，没有追加或修改前几轮报告。**

本轮得到 **4 项新增或扩展发现**，并确认 **原 R03 在直接访问 Caddy 的入口条件下仍未闭环**。主要问题是密码输入与加密边界不一致、登录失败计数丢失和长期积累，以及旧请求清除新账号凭据。业务代码未修改。

## 1. 对象、分工与证据边界

- 候选根目录：`C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010`。
- 受审 HEAD：`69577e941eabaf4b1a38697f9b684ede1e2ff775`。实际字节另由 SHA-256 固定，不能只用 HEAD 还原受审状态。
- 主代理：密码 schema、密码散列、登录失败窗口的并发和生命周期。冻结 14 个选定源码、配置、现有测试文件；执行函数级观察。
- 只读子代理一：反代转发头与限流信任链，核对 R03 原入口及官方 Caddy 语义。
- 只读子代理二：前端登录、退出及迟到请求，使用真实 TypeScript 源转译和合成 Promise 核对状态。
- 不修改候选源码、测试、配置、Git 引用或原报告；不启动服务、浏览器或容器，不调用模型、不安装依赖、不访问真实账号、数据库或媒体。
- 新增内容仅为本报告和各自独占证据目录内的小型副本、观察脚本及结果。

主代理复现使用已安装的 `backend/venv-new/Scripts/python.exe`，实际版本为 bcrypt `5.0.0`、Pydantic `2.14.1`、FastAPI `0.141.1`、Starlette `1.7.0`。bcrypt/Pydantic 与受审 requirements/constraints 对应项相符。没有导入完整项目模块、`.env` 或数据库初始化代码。

函数级复现从副本 AST 提取实际定义，跳过端点装饰器及依赖注入；数据库查询使用内存替身。并发观察使用真实 Starlette 线程池，并在密码验证位置放置屏障以固定交错顺序。因此以下结果证明特定函数和交错存在问题，**不等于真实 HTTP、安全负载、React 浏览器或部署验收**。

## 2. 发现总表

| 编号 | 严重度 / 置信度 | 问题 | 证据与历史关系 |
| --- | --- | --- | --- |
| B01 | P2 / 高 | 合法字符长度的多字节密码在开户时触发未处理异常 | 新增；实际 schema、bcrypt 和开户函数体复现 |
| B02 | P2 / 高 | 并发失败覆盖彼此记录，账号锁定阈值失效 | 新增并发情景；扩展 R04，未否定其串行过期窗口修复 |
| B03 | P2 / 高 | 不存在账号的失败记录按任意长用户名永久增长 | 新增；短时小输入证明未回收，不做内存压测 |
| B04 / 原 R03 | P2 / 高（逻辑），部署利用有条件 | Caddy 透传客户端 CF 头，后端因私网对端继续信任 | 原票未闭环；源码、官方代理契约与纯函数观察 |
| B05 | P2 / 高（受控交错） | 旧账号迟到 401 注销新账号 | 新增；真实 TS 源转译后的 Promise 复现 |

排序按修复关联组织。B02、B03、B04 可共同削弱登录防护，但各有独立根因；不能只修其中一项就声称整个登录边界通过。

## 3. B01：字符数上限没有守住 bcrypt 的字节上限

**位置**：[schemas.py:20](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/schemas.py:20)、[auth.py:59](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/auth.py:59)、[main.py:3415](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/main.py:3415)。

`RegisterIn.password` 限制 8–64 个字符，注释以此解释对 bcrypt 72 字节限制的防护。但 UTF-8 字符可能占多个字节；`hash_password()` 直接编码并交给 bcrypt，没有统一的字节长度校验。受审依赖明确锁定 `bcrypt==5.0.0`，超过 72 字节会抛出 `ValueError`，不能继续沿用“静默截断”的旧注释作为行为依据。[bcrypt 官方说明](https://github.com/pyca/bcrypt#maximum-password-length)。

实际结果：

| 合成密码 | 字符 / UTF-8 字节 | Schema | 散列与回验 |
| --- | --- | --- | --- |
| 64 个 ASCII 字符 | 64 / 64 | 接受 | 成功 |
| 24 个汉字 | 24 / 72 | 接受 | 成功 |
| 25 个汉字 | 25 / 75 | 接受 | `ValueError` |
| 19 个锁形 emoji | 19 / 76 | 接受 | `ValueError` |

调用实际 `admin_create_user()` 的函数体、传入已经通过实际 `RegisterIn` 校验的 25 汉字密码后，观察到 **未捕获 ValueError，commit 次数为 0**。端点和本轮检查到的应用异常注册没有把它转为输入错误；真实 HTTP 500 是由该未处理异常推导的结果，本轮没有发真实请求。

**影响**：管理员给用户设置此类密码时，界面允许提交，开户却失败。公开注册开启时存在同一散列调用；管理员初始化和重置 CLI 也共用该函数，但它们是否使用超限配置，本轮没有调查。没有证据表明此次异常创建了半个用户。

**最小修复方向**：在共同密码边界明确 UTF-8 字节规则，返回可理解的输入错误；API、初始化及重置入口保持一致。不应通过静默裁掉密码尾部来消除异常，也不应顺便更换密码算法而忽略旧散列兼容。

**验收建议**：覆盖 72/73 字节边界、多字节和 ASCII；超限输入在散列/写库前被明确拒绝；合法密码照常创建和登录。注释与错误文案同步更正。

## 4. B02：6 次并发失败只留下 1 次记录

**位置**：[main.py:431](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/main.py:431)，关键读写为第 436、443、444 行。

`login()` 把 `_do()` 交给线程池。每个线程先从 `_LOGIN_FAILURES` 读取列表，经 `_recent_login_failures()` 生成自己的新列表，再查询用户、校验密码、追加和覆盖写回。整段读改写没有同步保护；多个请求可以读到相同旧值并相互覆盖。

受控观察使用同一个合成账号、同一时钟：

| 情景 | 实际输出 |
| --- | --- |
| 串行 6 次失败 | `401, 401, 401, 401, 401, 429` |
| 6 个线程在读取旧列表后同步进入失败路径 | 6 次均为 `401` |
| 6 次全部结束后的持久进程内计数 | **1** |
| 随后第 7 次失败 | 仍为 `401`，没有锁定 |

这里使用密码验证替身固定交错，并未对真实密码做并发爆破，也未测量自然运行时的触发频率。即便允许已经在途的请求完成，**已完成 6 次失败后，后续请求仍因计数丢失而未锁定**，足以说明阈值不可靠。一次 6 请求的情景本身也没有超过路由声明的每 IP 每分钟 10 次上限。

**与 R04 的关系**：现有 `test_login_lockout_window.py` 验证串行窗口过期后重新锁定和时间裁剪；它没有调度多个线程读取同一旧列表。这是新的并发失败面，不把它描述为旧“首次窗口过期”错误重新出现。

**最小修复方向**：在进程内对失败状态的读取/合并写入建立明确的原子边界；至少失败写回时应基于最新状态累计。全局锁不应包住整个 bcrypt 校验，从而拖住所有用户。成功清零与同时失败的先后语义也需明确，避免只防止 append 丢失而留下相反竞态。

**验收建议**：用可控屏障固定交错，检查所有失败结束后计数达到阈值、下一次被锁定；另覆盖成功清零与并发失败，以及现有串行窗口边界。

## 5. B03：未知用户名的失败状态没有生命周期上限

**位置**：[schemas.py:26](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/schemas.py:26)、[main.py:220](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/main.py:220)、[main.py:440](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/main.py:440)。

`LoginIn.username` 没有长度上限。即使查不到用户，失败分支也将该原始字符串作为 `_LOGIN_FAILURES` 的键。窗口裁剪只在同一个用户名再次登录时计算，且不会全局删除过期键；唯一常规 pop 位于登录成功路径。随机构造的不存在用户名不可能通过成功登录来释放这些状态。

小输入观察：先让 5 个不同的不存在用户名失败，再让一个 100,000 字符的合成用户名失败。实际 `LoginIn` 接受长用户名，函数返回 401，字典有 6 个键。推进合成时钟 601 秒，再尝试一个新的不存在用户名：字典有 **7 个键，其中 6 个只含早已过期的失败时间**。

**影响**：未认证请求能持续引入新键，且每个键本身可很长。每 IP 限流降低增长速度，但没有设置进程内状态的总量或保留期限上限。此次只用了一个约 100 KB 的字符串；没有发送大请求或测量实际 RSS、耗尽时间，不能据此给出“多少分钟崩溃”的数字。

**最小修复方向**：明确登录用户名的合法长度，并兼容已存在账号及初始化管理员的命名规则；为失败状态设置实际回收和容量边界。可优先避免为根本不存在的账号永久分配账号锁定状态，继续保留 IP 限流和统一错误响应。不要为此引入一套复杂的新分布式缓存，也不要泄露账号是否存在。

**验收建议**：未知用户名批次、窗口推进、容量边界和长用户名均有可观察结果；正常账号锁定不能因清理策略被提前绕过。

## 6. B04：原 R03 没有覆盖“客户端 → Caddy → 后端”

**位置**：[Caddyfile:16](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/Caddyfile:16)、[main.py:191](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/main.py:191)、[main.py:204](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/main.py:204)。

候选已改为在私网/环回对端下采信 CF/XFF，能够拒绝一部分公网直接后端的伪造头。但原报告的入口是直接访问 **Caddy**：该代理转发后，后端看到的是真实私网代理，因此依然优先使用入站的 `CF-Connecting-IP`。

受审 Caddyfile 没有清理或重建该 CF 头。Caddy 官方说明普通请求头默认透传，只有三种 `X-Forwarded-*` 受到特殊处理；因此不能把它对 XFF 的防伪语义套到 CF 头上。[Caddy 官方默认请求头行为](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy#defaults)。

子代理固定后端 peer=`172.18.0.5`、固定代理重建的 XFF=`93.184.216.34`，只改变 CF 头，实际纯函数键依次变成：

```text
CF=1.2.3.4               -> key=1.2.3.4
CF=8.8.8.8               -> key=8.8.8.8
CF=arbitrary-bucket-003  -> key=arbitrary-bucket-003
```

**入口条件**：子代理读取的 Compose 第 89–91 行明确提到局域网访问并发布 `8088:80`。该文件当时存在其他工作者的未提交修改，结论绑定其读取指纹。若不可信客户端能访问这个 Caddy 入口，即具备上述换桶条件；如果网络已经强制所有请求只经受保护的 Cloudflare Tunnel、上游正确注入客户端头，则需按该排他拓扑另验。

**本轮未证明**真实防火墙、隧道及入口可达性，没有发送真实请求、运行 Caddy 或探测公网。结论是支持的直接 Caddy 入口仍存在防护缺口，不是“所有现役部署都可利用”。

现有 `test_rate_key_trust.py` 的公网对端用例针对直接后端；其私网用例直接假设 CF 头可信，没有验证 Caddy 是否已经清除客户端提供的值。**建议重新打开原 R03，附本轮证据，不重复建一张相同风险的新票。**

**最小修复方向**：在入口区分直接访问和受保护的 Tunnel 来源，优先利用代理原生的可信代理及客户端地址解析能力，统一重建可信身份；后端仅信任明确代理来源。只收窄后端代理 IP 白名单，仍不能解决真正的 Caddy 转发客户端伪造 CF 头；盲目删除所有 CF 头又可能把正常 Tunnel 用户聚合到同一个桶。

## 7. B05：旧请求的迟到 401 会清掉新登录凭据

**位置**：[api.ts:60](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/frontend/lib/api.ts:60)、[api.ts:67](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/frontend/lib/api.ts:67)、[auth.tsx:46](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/frontend/lib/auth.tsx:46)。

共用 `request()` 发请求时读取 token；响应为 401 时无条件清除当前 token 并导航登录页。它没有检查这条响应是否仍属于当前登录会话。

子代理追踪到可达顺序：A 已登录并发出会话列表请求 → 请求仍在途时退出 → B 登录及 `/auth/me` 成功 → A 的请求迟到返回 401。A 的令牌过期、账号被禁用等情况均可能产生该旧响应；普通列表请求没有因为页面离开而自动作废该全局错误处理。

真实 TS 源转译、合成 Promise 调度得到：

```json
{"oldRequestAuthorization":"Bearer A","currentUser":{"username":"bob"},"token":null,"redirect":"/login"}
```

**影响**：B 刚建立的会话被 A 的旧请求清掉，界面显示错误的登录过期、需要重新登录。本轮没有后端越权证据。

**最小修复方向**：清凭据与导航之前，验证响应对应的请求身份仍是当前登录会话；优先复用请求开始时捕获的 token 做必要比对，统一普通请求与流式请求中的同类失效处理。不要只对某个页面吞掉 401。

**验收建议**：A 的迟到 401 不改变 B 的凭据、身份及导航；当前会话自己的 401 仍正确失效。复现使用 React 状态替身和源转译，没有运行真实浏览器，因此仍需独立的浏览器交互证据。

## 8. 未单列为确认缺陷的观察

- **多标签身份同步**：两个标签都显示 A；另一标签退出并登录 B 后，localStorage 已是 B，但旧标签的 AuthProvider 不监听 storage，可能继续显示 A，而新 API 请求附上 B token。子代理合成结果为 `firstTabVisibleUser=alice, actualAuthorization=Bearer B`。后端仍按 B 鉴权，不能称为权限绕过；真实双标签行为及产品策略待验。
- **初始恢复的理论竞态被排除为本轮票项**：登录、聊天、管理页面的 loading gate 阻止普通同标签 UI 在初始 `/me` 恢复未完成时直接登录/退出，没有找到足够的普通操作可达性证据，不单列“旧恢复响应复活身份”。
- **错误密码被提示为登录过期**：共用 401 文案覆盖服务端“用户名或密码错误”。子代理已定位历史 `audit_report_20260807.md` 的相同提醒，故不算新增。
- **管理员自停用 API 的防误操作边界**：后端 toggle 没有同自删一样的保护，但前端明确隐藏管理员禁用按钮。本轮没有把需要直接构造管理员请求的行为包装成普通 UI 可误触的漏洞。

## 9. 证据位置、指纹与命令

三个证据目录位于同一独占输出根：

`C:/Users/33393/.codex/visualizations/2026/10/18/01a14fe1-dd41-7e83-a8f6-c4c2d27b6be7/`

| 子目录 / 文件 | 内容 |
| --- | --- |
| `fazhi-account-review-round4/source-manifest.json` | 主代理冻结的 14 个文件的 SHA-256 |
| `fazhi-account-review-round4/snapshot-meta.json` | 候选根、HEAD 和 UTC 时间 |
| `fazhi-account-review-round4/source-drift.json` | 复现后逐项对照候选文件的变化列表 |
| `fazhi-account-review-round4/observe_account_boundaries.py` | B01–B03 的函数级观察脚本 |
| `fazhi-account-review-round4/observations.json` | B01–B03 本次实际输出，含运行时依赖版本 |
| `round4-proxy-agent/pure-function-cases.json` | B04 的纯函数观察、方法限制和源文件指纹 |
| `round4-frontend-auth-agent/probe.cjs` | B05 的真实 TS 源转译、状态替身和 Promise 调度 |
| `round4-frontend-auth-agent/probe-output.txt` | B05 本次实际输出及 api/auth 指纹 |

关键文件 SHA-256：

| 文件 | SHA-256 |
| --- | --- |
| backend/main.py | `776EAB226DC05ED1E78C8304BD76B629E5DF6EE9A04964277208C3C79BA884B5` |
| backend/auth.py | `F165F73111DDE48FF184187E62B23F24839C90E2DDA26D5903517D496A261550` |
| backend/schemas.py | `31374F69CBD78EAE405A7B139FDC5149DF6DAF26F7D1762D1B5CF068300BF8B2` |
| frontend/lib/api.ts | `9322F91C90E047A9F8A648B31792970BAAFADAB29570F0799E2929279244AF8D` |
| frontend/lib/auth.tsx | `DF568CE954B60F4866493B987CBFEA9BB45F0FE4BF21C16ACB7AB1577427D009` |
| Caddyfile | `0A34656EF0E13851D263EC4C11A917A570272E4C866BB8D1A8E37A6B6F6DFC28` |
| docker-compose.yml（子代理读取时为脏文件） | `E893DAB494DCBC5E07655B941567317D564E532187A44B081150FAECE948B813` |

主代理 B01–B03 观察命令：

```powershell
& 'C:\Users\33393\Desktop\ai-legal-helper\backend\venv-new\Scripts\python.exe' -B 'C:\Users\33393\.codex\visualizations\2026\10\18\01a14fe1-dd41-7e83-a8f6-c4c2d27b6be7\fazhi-account-review-round4\observe_account_boundaries.py'
```

本次退出码 0，表示成功记录缺陷及对照输出，**不是产品测试通过**。脚本只改独立证据目录中的结果文件。

前端子代理执行 `node <独占目录>/probe.cjs`，本次退出码 0。该脚本从候选读取 TS 源及已有 TypeScript 依赖；复跑前必须核对当次源文件指纹，不能把后来改过的候选输出混作本报告版本。

未运行项目测试套件、完整 HTTP 集成、浏览器或部署入口验收。没有发布就绪或全仓通过的结论。

## 10. 交给修复助手的提示词

```text
请独立确认本报告，再在你获准的工作树中最小化修复；不要在主仓混入其他人的脏修改。
本报告绑定候选 HEAD 69577e941eabaf4b1a38697f9b684ede1e2ff775 和文内字节指纹，先判断当前代码是否变化。

B01：按 UTF-8 字节核对 bcrypt 5 的 72 字节边界。超限是输入问题，不是500；不得静默截断密码。
B02：固定多个线程读到同一旧失败列表的交错，复现计数丢失及随后不锁定。
     修复状态更新边界，保留窗口语义；不要让全局锁包住所有用户的慢 bcrypt 校验。
B03：未知、随机、长用户名不应让锁定状态永久无界增长；清理不得放松正常账号锁定或泄露账号存在性。
B04：重新打开原 R03。必须验证客户端→Caddy→后端，不能用公网直连后端的单测代替。
     先确认真实入口是否允许直接 Caddy；让代理重建身份并正确区分受保护 Tunnel 来源。
B05：旧账号请求迟到401不能清掉新账号 token 或重定向；当前账号自己的401仍应生效。

复现脚本不导入完整后端，跳过装饰器/认证，前端用了状态和网络替身；不要把这些结果冒充完整端点或浏览器验收。
若获准修复，请给出能在旧代码上暴露问题的定向证据，按实际改动补相应隔离集成检查。
避免以通用catch、关锁定、移除限流、静默截密码、增加重试等方式掩盖根因。
同根因的普通请求/流式请求401应统一处理，避免每个页面各写一套。

逐项交付：是否仍成立、最小改动、验证命令和原始结果、未覆盖条件。
多标签同步、管理员自停用策略等观察先明确契约；不要借本报告自动扩展范围。
```
