# G 单：现用本地依赖环境的归属核实与升级可达性（2026-10-10）

结论先给：**本书 G 单要升级的那个"现用本地依赖环境"，经归属核实后并不存在**——
现役运行的是 **Docker 容器（三周前的镜像）**，宿主机上没有任何进程在跑产品。
⇒ G 的"升级 + 回退实测"落到本书授权之外（要重建镜像并重启容器＝部署动作），
本轮把 G 判为 **BLOCKED（理由已换成现量证据，不再是"归属未核"）**，并留下一条**合并后必须处理的连带后果**。

全部读数只来自只读命令；未停、未启、未改任何容器或进程。

---

## 1. 归属核实（G.1）：谁在提供这个应用

| 问题 | 现量 | 命令 |
|---|---|---|
| 8088 上有没有东西在服务？ | **有**，`http://127.0.0.1:8088/` → `http=200 time=0.16s`（`/healthz` 在该入口 404，它是后端路径不是 Caddy 根） | `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8088/` |
| 是谁在监听 8088 / 80 | **`com.docker.backend.exe`（PID 8636）** 持有转发端口；宿主机上**没有** `python.exe`/`node.exe` 在监听 8000/3000 | `netstat -ano \| grep LISTENING` + 逐 PID 反查进程名 |
| 哪些容器在跑 | `fazhi-backend`、`fazhi-frontend`、`fazhi-caddy`（`docker ps`：`Up`，`0.0.0.0:8088->80/tcp`） | `docker ps --format ...` |
| 它们是谁启的 | compose project = `ai-legal-helper`，config = `c:\Users\33393\Desktop\ai-legal-helper\docker-compose.yml`（**主仓**，不是候选），三个容器 `restart=unless-stopped`，容器**创建于 09-17**、本次**启动于 2026-10-10 07:08:51Z（本地 15:08）** | `docker inspect --format '{{.Name}} created={{.Created}} started={{.State.StartedAt}} restart={{.HostConfig.RestartPolicy.Name}} project={{index .Config.Labels "com.docker.compose.project.working_dir"}}'` |
| 跑的是哪个版本 | 镜像 `ai-legal-helper-backend:latest` = `cbdadf43a40b`，`docker images` 显示 **created = 3 weeks ago**；另有 `:audit-current-20260923`（2 weeks）等标签 | `docker images --format ...` |

三点判断（都写清依据，不写成"我觉得"）：

1. **启动者不是我/我的 agent**。`restart=unless-stopped` + "容器创建于三周前、今天 15:08 被拉起"这个组合，
   与 Docker Desktop 重启后自动复活旧容器的行为一致；D 单的派单边界里明确禁了 compose，且
   `evidence/d-browser/logs`、`scripts` 里 grep `docker|compose` **0 命中**（我当时查过）。
   我**没有停它**——那是你的运行态，可能是你自己在用。
2. **现役运行的源码≠本轮候选**。镜像是 09 月中旬构建的，而本轮改动从未进过任何镜像。
3. **宿主机 `backend/venv` 不是"产品正在使用的环境"**，它是开发/测试环境（本书 §0.2 与 G.1 就要求我不要按目录名猜）。

## 2. 因此 G 单的"升级"在授权内不可达

要按本书 G 的口径升级"现役环境"，动作必须是：`docker compose build` 重建两镜像 → 停旧容器 → 起新容器。
这三步合起来就是本书"明确不执行"那一栏里的**部署/运行原 compose 栈**；而且它启动时
`main.py` 会 import 触发初始化、按现配置**挂载真实库**（`backend/chroma_db` 被 compose bind-mount 进容器，
这是在册事实）⇒ 直接撞上本书"不读写真实业务库/向量库"的红线。
⇒ **G 判 BLOCKED**，并把"若你要升级现役环境"的具体选择交回给你（见 `reports/decisions-needed-20261010.md` D-5）。

顺带一条本书要求的检查我做不了、也不该绕：G.1 说"不能以 `VIRTUAL_ENV`、某助手跑过 pytest 或签字推断实际服务归属"。
我这里用的全是**端口持有者 + 容器标签 + 镜像创建时间**三类现场证据，没有用任何"目录名/习惯"推断。

## 3. 一条合并后必须处理的连带后果（现在就有读数）

本轮把 `backend/requirements.txt` 的 SQLAlchemy 下限提到 `>=2.1`（mypy 那两条 `Row` 泛型红的归因轴，
见 `reports/dependency-decision.md`）。但**宿主机开发环境的现量是 2.0.51**：

| 项 | `backend/venv` 现量 | 候选声明 |
|---|---|---|
| SQLAlchemy | **2.0.51** | `>=2.1,<3.0` ⇒ **该环境已在声明区间之下** |
| torch | `2.6.0+cpu` | `==2.13.0`（CPU 构建） ⇒ 同样越界 |
| fastapi / starlette | 0.110.3 / **0.36.3** | — |
| `pip check`（只读） | **两条不一致**：`fastapi 0.110.3 requires starlette<0.38.0,>=0.37.2`、`sse-starlette 3.4.8 requires starlette>=0.49.1`，实际都是 0.36.3 | 候选闭包 `pip check` rc=0 |

命令（只读，不会改任何东西）：

```bash
cd /c/Users/33393/Desktop/ai-legal-helper
backend/venv/Scripts/python.exe -m pip show sqlalchemy fastapi starlette chromadb torch | grep -E "^Name|^Version" | paste - -
backend/venv/Scripts/python.exe -m pip check
```

含义说准：**这不是"环境坏了所以不能合并"**，而是"合并后，凡继续用 `backend/venv` 跑测试/起服务的人，
跑的就是一个不满足 requirements 的环境，而且 mypy 那两条 `Row` 红会在这个环境里复现"。
处理它需要动那个 venv（安装/升级包），本书把"更新经事实确认的现用本地依赖环境"的授权给的是
**现役环境**，而现役环境已核实为容器 ⇒ 对宿主 venv 的写操作需要另一次具体授权（同一题，见 D-5）。

## 4. 回退预案（本轮只准备，不执行）

若你批准动 `backend/venv`，最小可回退路径我已经能给出，但**尚未实测**，所以它现在是预案不是证据：

1. 先 `pip freeze --all > <运行根>/evidence/venv-freeze-before.txt`（只读导出，不写 venv）；
2. 只装解析闭包所需的那几只，逐个 `--no-deps` 单变量隔离（本轮在候选环境验过这套手法有效）；
3. 回退 = 按 before 清单原样重装，装完复跑 `pip check` 与全量非 slow 对账。
   **不做**整树 `--force-reinstall`，也不删 venv 重建（那会洗掉"哪些包本来就在"的事实）。

## 5. 本轮未做 / 射程外

- 未 `docker compose build/up/down`、未重启任何容器、未改任何启动配置。
- 未在宿主 `backend/venv` 里安装/升级/卸载任何包。
- 未读 `.env`、未打开真实 `backend/app.db`/`backend/chroma_db`/`backend/data`（本书禁区）；
  因此也**没有**核过现役容器实际连的是哪份库文件——那需要读 `.env` 或进容器，都越界。
