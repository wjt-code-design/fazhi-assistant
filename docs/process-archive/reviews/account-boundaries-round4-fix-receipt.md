# 账号边界第 4 轮 B01–B05 修复回执

日期：2026-10-24。上游报告：[account-boundaries-readonly-review-round4.md](account-boundaries-readonly-review-round4.md)（受审候选 HEAD `69577e94`）。
本回执在 master `b752a11b` + 本次提交上复核与修复；**未修改候选工作树、旧报告或其他助手的改动**。

## 0. 结论总表

| 编号 | 状态 | 一句话 |
|---|---|---|
| B01 | **已修复** | 密码按 UTF-8 字节在 schema 层拒绝 >72 字节；API 返回 422 而不是 500；CLI 共用同一检查 |
| B02 | **已修复** | 失败计数读改写加锁；16 线程 ×100 次并发计数精确为 1600；锁不包 bcrypt |
| B03 | **已修复** | 登录用户名上限 32；未知用户名不落失败状态；过期记录阈值回收 |
| B04 | **未修复（阻塞）** | 需先确认生产入口是直连 Caddy 还是 Tunnel-only；盲目删 CF 头会把 Tunnel 用户聚成一个限流桶 |
| B05 | **已修复** | 普通请求与流式请求都只在“请求发出时的 token 仍是当前 token”时清凭据/跳登录 |

## 1. 复核方法

- 逐条对照当前 master 代码；上游报告绑定候选 HEAD `69577e94`，主仓已演进的项按当前代码重新判断。
- 定向单测 + 一红控制 + 全量差分；前端 vitest 全量 + `tsc --noEmit`。
- **未运行**真实 HTTP 集成、浏览器、Caddy、容器或部署入口；本轮不声称部署验收。

## 2. B01：密码字节边界

位置：[schemas.py:20](../../backend/schemas.py)、[auth.py:34](../../backend/auth.py)。

改动：
- `RegisterIn.password` 新增 `field_validator`：`len(value.encode("utf-8")) > 72` 即报输入错误；注释从“bcrypt 会静默截断”更正为“bcrypt 5 抛 ValueError”。
- `hash_password()` 增加同一字节检查（覆盖 seed_admin / reset_admin_password 这类绕过 schema 的 CLI），超过 72 字节给出可读 `ValueError`，不创建半个用户。

验证（[test_account_boundaries_b01_b03.py](../../backend/tests/test_account_boundaries_b01_b03.py)）：
- 24 汉字（72 字节）、18 个四字节 emoji（72 字节）、64 ASCII：接受且能散列/回验。
- 25 汉字（75 字节）、19 个 emoji（76 字节）：schema 拒绝。
- `hash_password` 对 75 字节：`ValueError`。
- `POST /api/auth/register` 传 75 字节密码：**422**（原缺陷是未捕获异常推导出的 500）。
- 定向：`pytest tests/test_account_boundaries_b01_b03.py -q` → **14 passed**。

未覆盖：没有跑 seed/reset CLI 的端到端命令；只验证了共用函数。管理员重置若走其他未发现的入口，需另行核对。

## 3. B02：并发失败计数

位置：[main.py:198](../../backend/main.py)、`_login_locked` / `_record_login_failure` / `_clear_login_failures`、登录 `_do`。

改动：
- 失败状态 `dict[str, tuple[int, float]]` + `threading.Lock`；读、+1、写回在同一临界区。
- 锁只包内存读改写，**不包 bcrypt**，不会拖住其他用户的密码校验。
- 登录先 `_login_locked` 判锁，失败时 `_record_login_failure`，成功时 `_clear_login_failures`；成功清零与并发失败各自原子。

验证：
- 16 线程 × 100 次、固定切换间隔：计数精确 `(1600, 1000.0)`，`_login_locked` 为 True。
- 一红控制：把锁换成 no-op 后同一负载只记 **649/1600**（丢 60% 更新）——测试确实能暴露原缺陷。
- 窗口边界：`now < ts + 300` 仍锁；到期解锁；过期项被清理。
- 主仓当前没有 `test_login_lockout_window.py`（该文件仅在上游候选线）；全量鉴权相关用例无新增失败（见 §7）。

未覆盖：多 worker 不在本项目并发模型内（compose 固定单 worker）；跨进程共享锁未做。

## 4. B03：未知用户名与状态生命周期

位置：[schemas.py:37](../../backend/schemas.py)、[main.py:198](../../backend/main.py) 失败分支。

改动：
- `LoginIn.username` 增加 `min_length=1, max_length=32`，与 `RegisterIn` 对齐，长用户名在入口被拒。
- **只为真实存在的账号记账**：`user is None` 时直接 401，不创建失败键；随机用户名不再让字典无界增长。
- 失败字典超过 256 项时清理已过锁定窗口的条目；正常账号的未过期锁定不受影响。

验证：
- 33 字符用户名：`ValidationError`。
- 5 次不存在用户名的 `POST /api/auth/login` 全 401，且该用户名不在 `_LOGIN_FAILURES`。
- 过期项被 purge 删除，未过期的活跃锁定保留。

未覆盖：未知用户名的登录不再累计锁定（这是有意的：不存在账号无锁定对象），仅靠每 IP 限流；若产品要求对未知用户名也限速，需要单独定义，不与账号锁定混用。

## 5. B04：Caddy → 后端的 CF 头信任链（未修复，阻塞）

现状（复核）：
- [Caddyfile](../../Caddyfile) 的 `/api/*` 只有 `flush_interval -1`，没有 `header_up` 清理或重建客户端头。
- [docker-compose.yml:92](../../docker-compose.yml) 发布 `8088:80` 到宿主，局域网可直接访问 Caddy；注释同时说明可选 `cloudflared tunnel --url http://host.docker.internal:8088`。
- [main.py:177](../../backend/main.py) 的 `_rate_key` 无条件优先信任 `CF-Connecting-IP`。

结论：B04 仍成立。能访问 Caddy 的客户端可以自带任意 `CF-Connecting-IP`，后端看到的是可信私网代理，于是按该值分桶；这不绕过登录，但可轮换限流桶、削弱爆破防护。

为什么本轮不改：两种部署形态互斥，且本机无法运行 Caddy/隧道验证：
- 直接删 `CF-Connecting-IP` 并重建 `X-Forwarded-For`：能修复直连入口，但 Tunnel 场景会把所有公网用户聚到 cloudflared 的一个 IP，10/min 限流变成全站共享。
- 保留 CF 只收窄后端白名单：后端 peer 永远是 Caddy，收窄无效。

需要你方决策（任一）：
1. 生产入口是否 **只** 经 Cloudflare Tunnel？若是，8xxx 端口应只绑环回/内网，不发布到 LAN；并确认 Tunnel 是唯一入口。
2. 若直连 Caddy 与 Tunnel 并存：在 Caddy 用 `remote_ip` 匹配 cloudflared 来源，仅对该来源保留 CF，其余请求删除 CF 并由 Caddy 重建 XFF；需要给出 cloudflared 的固定 IP/CIDR。
3. 若只用直连 Caddy：直接 `header_up -CF-Connecting-IP` + 用 `{remote_host}` 重建 XFF，并在后端停止优先信任 CF。

在决策前不改 [Caddyfile](../../Caddyfile) 与 `_rate_key`，避免用未验证的改动换掉一个已知但可利用条件未确认的风险。

## 6. B05：迟到 401 清掉新会话

位置：[api.ts:61](../../frontend/lib/api.ts)、[api.ts:209](../../frontend/lib/api.ts)。

改动：
- `request()` 捕获请求发出时的 token；401 时只有 `getToken() === token` 才清凭据并跳登录页。
- `streamChat()` 同口径：旧会话的迟到 401 不再 `onError`、不再清 token。
- 无 token 的 401（如密码错误）不再执行“登录过期”跳转，错误文案改为“用户名或密码错误”。

验证（[auth-401-session.test.ts](../../frontend/tests/auth-401-session.test.ts)）：
- A 发出请求 → 切到 B → A 的 401 迟到：token 仍为 B、不跳转。
- 当前 token 自己的 401：清 token、跳 `/login`。
- 流式请求同两场景：旧 401 不通知、当前 401 通知。
- `npx vitest run` → **10 files / 91 tests passed**；`npx tsc --noEmit` 无输出。

未覆盖：没有真实浏览器/React 交互验收；多标签 storage 同步仍是观察项（未在本轮票内）；旧请求仍会把 `ApiError` 抛给调用方，页面级 toast 是否出现取决于组件，未纳入断言。

## 7. 全量回归

- 后端：`pytest -q -m "not slow"` → **19 failed / 2033 passed / 2 skipped / 19 deselected**，402.85s。
- 与修复前基线逐条比对：失败集合**完全一致，0 新增、0 修复**（19 个均为既有基线失败：`test_stream_cancellation` 15、`test_cancel_boundaries` 1、`test_llm_lifecycle` 3）。
- 前端：`npx vitest run` → 91 passed；`npx tsc --noEmit` → 通过。
- 定向：B01–B03 14 passed；B02 一红控制 649/1600。

## 8. 未覆盖边界（总）

1. 没有真实 HTTP、真实账号、浏览器、Caddy、容器或部署入口验收。
2. B04 的运行时可利用性仍取决于生产入口拓扑；本回执只复核了源码与 compose 暴露面。
3. 多 worker、跨进程共享失败计数不在本项目并发模型内，未实现。
4. 多标签身份同步、管理员自停用等观察项未纳入本轮改动。
5. 较早的候选工作树（`69577e94`，含其他人的未提交修改）保持原样，未触碰。

## 9. 本次改动

提交：`e7394b85`（代码 + 测试）；本回执提交 `ce4ac382`。

- `backend/schemas.py`：密码 UTF-8 字节校验；`LoginIn.username` 长度上限。
- `backend/auth.py`：`hash_password` 防御性字节检查。
- `backend/main.py`：登录失败状态加锁、原子累计、未知用户不记账、过期清理。
- `frontend/lib/api.ts`：普通/流式 401 的会话归属判断。
- 新增 `backend/tests/test_account_boundaries_b01_b03.py`、`frontend/tests/auth-401-session.test.ts`。
- 本回执。旧报告与候选工作树未改。
