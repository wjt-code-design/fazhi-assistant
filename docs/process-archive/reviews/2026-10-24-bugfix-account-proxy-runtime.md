# 2026-10-24 账户、代理与运行时修复回执

本回执接续 `2026-10-24-combined-work-summary.md` 的审阅。用户授权 bug 排查和漏洞修复，并明确当前保留本机、局域网浏览器访问，以后再部署服务器。本轮没有提交、推送或部署，也没有改写历史评测结果。

原汇报的发布建议需要保留安全验收条件：不能在未确认实际入口的情况下把 B04 排除在发布门外。本轮仅为已确认的本机/局域网拓扑提供修复和回环证据；原汇报中的法律质量待办仍须按其各自要求验收。

## 修复内容

### 1. 登录锁定窗口到期后不再重新锁定

`backend/main.py::_record_login_failure` 原来沿用已过期记录的时间戳。小规模账户集合不会触发字典清理，因此第一次窗口过期后继续输错密码，后续锁定判断一直得到“已过期”。

现于锁内检查窗口到期，重新从本次失败计数、计时。新增到期前累计 4 次、5 次两种回归：到期后的第一次失败必须为 `(1, now)`，再累计到阈值必须重新锁定。

- 修复前正确失败：`outputs/bugfix-20261024-session01a16/login-window-red.log`，2 failed。
- 修复后账户测试：`login-window-green.log`，16 passed。

### 2. 伪造代理头绕过 IP 限流（B04）

原 `_rate_key` 无条件信任来访者可提交的 `CF-Connecting-IP`，可通过轮换此头取得不同限流桶。修复后应用只使用服务端认定的 `request.client.host`。

当前访问链路：浏览器 → 本机/局域网 `:8088` → Caddy → 不发布宿主端口的 backend。Caddy 删除 CF 头，并将 XFF 重写为连接对端地址；Uvicorn 负责解析来自代理的 XFF。`docker-compose.yml` 设置 `FORWARDED_ALLOW_IPS=*`，其成立条件是 backend 仅处于可信 Compose 网络内、没有发布端口。以后若直接暴露 backend 或接入其他代理，必须重新配置代理白名单和入口清洗规则。

这保留现有本机/局域网入口。Cloudflare Tunnel 不属于当前验收拓扑，不能把本回执当作其安全验收。

- 新增 `backend/tests/test_proxy_rate_key.py`：实际登录请求轮换 CF/XFF，仍只能收到 10 次 401，随后 429；验证可信/不可信代理地址以及缺失客户端的兜底桶。
- 修复前证据：`proxy-red.log`。其中 4 个失败是预期的安全缺陷；另 1 个由测试替身缺少属性造成，已改用真实 Request，不能计作漏洞证据。
- 账户、代理、上传边界合并测试：`account-proxy-green.log`，23 passed。
- 实际 Caddy 2.11.7 + Uvicorn 回环链路：`caddy-smoke-result.json`，10 个案例通过。两个不同源地址各覆盖空头、伪造 CF、伪造 XFF、多段 XFF、重复 XFF，服务端身份始终为真实源地址。
- `compose-security-contract.json`：backend 无 published ports，Caddy 为 `8088:80`。该检查不需要运行 Docker daemon。

Caddy 的头删除、覆盖语义参照[官方 reverse_proxy 文档](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)。实际执行的便携版来自官方发行包，执行前已核对官方 SHA512；来源、校验值见 `outputs/bugfix-20261024-session01a16/tools/download-receipt.json`。

### 3. LLM 注册表之间共用连接池、关闭时相互影响

新版 LangChain 默认缓存底层 HTTP 客户端，导致两个独立 registry 共用连接池。关闭第一个 registry 后，第二个仍持有的池也已关闭。新增隔离测试亲见原实现失败（`client-ownership-red.log`）。

`backend/llm_registry.py::_build` 现在为每个独立 entry 创建自己的 HTTP 客户端；variant 和 model reload 继续复用所属 entry 的 SDK 根。若配置 `OPENAI_PROXY`，沿用 LangChain 自带的非缓存代理客户端构造，避免新版拒绝“代理 + 自定义 HTTP 客户端”，并保留旧版代理选路语义。

新增三种离线代理组合：只有系统代理、只有 OPENAI_PROXY、二者并存。检查 HTTP/HTTPS/NO_PROXY 选路、SDK 实际请求超时、variant/reload 复用和 registry 关闭隔离；不向模型或代理发请求。两种已安装依赖版本的原生代理优先级不同，测试对照各自原生行为，不强行改变项目原有配置含义。细节、失败证据和精确命令见 `outputs/bugfix-20261024-session01a16/llm-proxy-verification.md`。

### 4. 新依赖环境的 19 个测试失败

修复前隔离运行生命周期与取消测试，在 `venv-new` 重现 19 failed / 47 passed；旧环境同批 66 passed。主要原因是测试替身混用 Pydantic v1 Field 与 v2 Runnable、假定旧版 callback 序列化结构及旧版 extra_body 存放位置。

修正测试以匹配当前依赖的公开行为：按 Runnable 版本选择 Field；允许库附加元数据，同时保留项目元数据断言和真实模型元数据不变断言；通过 callback 的 name 确认解析器；检查实际请求参数中的 extra_body。真实 socket 取消、对端断开早于 SDK 客户端关闭等关键断言仍保留。没有为使测试变绿而修改流取消业务实现。

## 验证与复现

命令均从仓库根目录运行；原始输出位于 `outputs/bugfix-20261024-session01a16/`。

| 范围 | 命令 | 结果/证据 |
| --- | --- | --- |
| 最终集成后端回归 | `backend/venv-new/Scripts/python.exe -m pytest backend/tests -q -m "not slow" --tb=short --junitxml=outputs/bugfix-20261024-session01a16/backend-nonslow-integrated.xml` | 2068 passed / 2 skipped / 19 deselected / 196 warnings，217.76 秒，退出 0 |
| 旧依赖取消/生命周期兼容 | `backend/venv/Scripts/python.exe -m pytest backend/tests/test_llm_lifecycle.py backend/tests/test_cancel_boundaries.py backend/tests/test_stream_cancellation.py --noconftest -q --tb=short` | 70 passed，退出 0；`lifecycle-legacy-integrated.log` |
| 实际 Caddy 代理链路 | `backend/venv-new/Scripts/python.exe outputs/bugfix-20261024-session01a16/smoke_caddy.py` | 10 个案例 PASS，退出 0；`caddy-smoke-result.json` |
| Python 静态/格式 | `backend/venv-new/Scripts/python.exe -m ruff check <下列7个Python文件>`；同文件 `ruff format --check` | 均退出 0；7 files already formatted；`integrated-ruff-*.log`、`integrated-static-exits.json` |
| 补丁空白检查 | `git diff --check` | 退出 0；仅 Git 行尾提示；`integrated-diff-check.log` |

本轮 Python 文件共 7 个：`backend/main.py`、`backend/llm_registry.py`、`backend/tests/test_account_boundaries_b01_b03.py`、`backend/tests/test_proxy_rate_key.py`、`backend/tests/test_cancel_boundaries.py`、`backend/tests/test_llm_lifecycle.py`、`backend/tests/test_stream_cancellation.py`。另修改 `Caddyfile`、`docker-compose.yml`。工作区原有的 `dispatch-output/round67-q1-20261023/support-review-green.out` 改动与本轮无关。

上述 9 个源码/配置文件的 SHA256 已记录于 `integrated-source-sha256.json`。最终集成测试的日志和 JUnit 分别为 `backend-nonslow-integrated.log`、`backend-nonslow-integrated.xml`；此前的 `backend-nonslow-final.*` 是代理兼容补丁前的中间结果，不作为最终完成依据。

依赖环境：旧环境 LangChain OpenAI 0.1.7 / OpenAI 1.109.1 / httpx 0.27.2；新环境 LangChain OpenAI 1.7.0 / OpenAI 2.54.0 / httpx 0.28.1。此次没有升级依赖或更改 requirements。

## 验收边界

- 本轮验证覆盖上述具体缺陷，不能据此声明整个仓库没有漏洞。
- 后端回归排除 `slow`；未重跑真实模型、真实知识库质量或付费评测，历史评测数字未重新背书。
- 两个 skipped 是未设置 `FZ_DUMP_FRAMES` / `S6_DUMP_FRAMES` 的逐帧证据采集用例；19 个 deselected 为 slow 标记用例。不能将本次结果写成“所有测试均已执行”。
- Docker daemon 未启动，未重建镜像、未进行真实容器启动及其他局域网设备访问；Caddy 实测仅为回环网络。服务器部署尚未验收。
- mypy 检查两个生产文件报 4 个 `[var-annotated]` 错误，位于 `main.py` 的 image_ref/thumb_ref 列表推导；对应源码在 HEAD 已存在且本轮未改。未重放 HEAD 的 mypy 基线，不将其宣称为已验证的基线通过。详见 `static-mypy.txt`、`static-mypy-attribution.txt`。Ruff 通过不代表类型检查通过。
- 旧版 multipart 弃用、新版 extra_body/model_kwargs 等警告仍可见，没有通过屏蔽警告制造通过结果。
