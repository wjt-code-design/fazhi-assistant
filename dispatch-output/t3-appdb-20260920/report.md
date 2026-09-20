# T3 · 两份 `app.db` 口径统一 + "宿主那份今天还在不在被写"

## 基线锚定（T3 必做，防结论对到旧版本）

- `git rev-parse HEAD` = `beb4d5c09a7a28e2987488b86031780f6ed7d8c5`（与 `baseline.json` 一致）
- `sha256(backend/retrieval.py)` = `59596c826ab11dc7c036242d90545fe2ddd77f387facb52e4f87f25f0dfc0476`（与 `baseline.json` 一致，稳定 = 提交版）
- `sha256(backend/main.py)` = `a31b7b4c34c71692f860e1730fe1e7188e6b49f46790ab8211b328137e50be83`
  - ⚠️ 漂移登记：`baseline.json`（22:36）记录的 `main.py` 哈希是 `6a320e42…`（size 136165）。本次实测为 `a31b7b4c…` ⇒ **ticket-I 在 22:36 之后又写了一次 `main.py`**。属 `baseline.json` 允许的"owner=ticket-I 漂移，需记录并重新锚定"，本结论已锚定到当前哈希。

读取方法：`open(path,'rb').read(100)` 纯字节读 SQLite 头（取 magic / page_size / read&write format / change_counter@24-27 / schema_cookie@40-43 / version-valid-for@92-95）+ `os.stat` 取 size/mtime。**未** import sqlite3、**未** connect、**未**开事务、**未** VACUUM、**未**改 schema。读库唯一副作用 = `st_atime` 刷新（与 `appdb-lastwrite-forensics-20260919` 同口径，可接受）。

---

## ① 结论（一句话）

**两份 `app.db` 今天（2026-09-20）都没有被写入**（此主答案经主会话独立复核认可，见文末"主会话独立复核"）。**生产真源是 `backend/data/app.db`** —— 它是 Docker 容器 DB（`docker-compose.yml:43` 写死 `DATABASE_URL=sqlite:////data/app.db`，`:50` 挂载 `./backend/data:/data`），自 `2026-09-17 02:37:31`（cc 10710）起停滞（生产零流量，Agent Path 关）。根目录 `backend/app.db`（cc 10784，末次写 `2026-09-19 00:28:25`）**不是生产真源**：它是宿主机本地进程的默认回落库（`database.py:9` 默认 `DATABASE_URL`），那次写入来自宿主机上跑的 **R15 三臂评测/演练批**，属非生产流量。**两份源文档对"宿主/容器内"的叫法正好相反，本报告按真实路径统一口径**（见"口径冲突"段）。

> ⚠️ 修订记录：初版把"最近被写"(09-19) 当作"生产真源"判据，错判根 `app.db` 为真源。经主会话复核，生产真源应以 compose 写死挂载 + `DATABASE_URL` 为准，已改判（详见"口径冲突"段）。读数层全部正确，未重跑。

---

## 统一口径表（按真实路径，不靠"宿主/容器内"这种会漂的标签）

| 文件 | 真实路径 | cc | size | mtime | WAL? | 谁在写（依据） | 生产真源是不是它 |
|---|---|---|---|---|---|---|---|
| `app.db`（根目录） | `C:\Users\33393\Desktop\ai-legal-helper\backend\app.db` | **10784** | 20205568 | 2026-09-19 00:28:25.716 | 否（回滚日志，write_format=1） | 宿主机本地进程的默认回落库（`database.py:9` 默认 `DATABASE_URL` → `sqlite:///backend/app.db`）；末次写者 = 宿主机上跑的 **R15 三臂评测/演练批**（非生产流量，见下方口径冲突段） | **否** —— 宿主机本地默认库，被评测/演练批写入，非生产流量 |
| `app.db`（data 下） | `C:\Users\33393\Desktop\ai-legal-helper\backend\data\app.db` | **10710** | 19939328 | 2026-09-17 02:37:31.913 | 否（write_format=1） | **Docker 容器**：`docker-compose.yml:43` 写死 `DATABASE_URL=sqlite:////data/app.db`，`:50` 挂载 `./backend/data:/data` ⇒ 生产运行时写这里；自 09-17 停滞（生产零流量，Agent Path 关） | **是** —— 生产真源（Docker 容器 DB，`/data/app.db` ← `./backend/data` 挂载），自 09-17 停滞 |
| `quota_used.sqlite` | `C:\Users\33393\Desktop\ai-legal-helper\backend\data\quota_used.sqlite` | 2 | 12288 | 2026-09-19 00:12:51.569 | **是（WAL，write_format=2）** | R15 第一臂（末次写 09-19 00:12） | 否 —— 配额库，独立用途，非 app 主库 |

> 三份文件 `magic_ok=true`、`header_synced=true`（change_counter == version-valid-for，头页未撕裂），读数可信。

### 口径冲突（必须点名的坑）

- **T3 卡"关键事实"**：宿主 `app.db` = cc 10710 / size 19939328 / mtime 2026-09-17 02:37；容器内那份 = 10784 / 20205568 / mtime 2026-09-19 00:28。
- **取证报告（第 179 行）**：`backend/app.db`（根）= cc 10784（标注为 live 主机文件）；`backend/data/app.db` = cc 10710（标注为"容器副本"）。
- **两者数值完全一致，但"宿主/容器内"的叫法正好相反** —— 这一事实发现层仍然成立，本表一律以路径为准。

**但"谁生产真源"的判据，初版是错的，已改判（主会话复核定案）：**

1. 初版错误：把"最近被写"(09-19 00:28) 当成"生产真源"的判据，从而把根 `app.db` 判成真源、把 `data/app.db` 判成"停滞副本（非真源）**。
2. 正解：`data/app.db` 才是生产真源；根 `app.db` 那次 09-19 写入的写者，是我自己判定的 **R15 三臂评测批**——它是**宿主机上跑的评测/演练脚本**用 `database.py:9` 默认回落路径打的库，**不是生产流量**。生产零流量（Agent Path 关）恰好解释了 `data/app.db` 自 09-17 停滞。
3. **生产真源判定依据（三件独立证据，非"最近被写"）**：
   - ① `docker-compose.yml:43` → `DATABASE_URL=sqlite:////data/app.db`（**写死，不从 env 取**）；`:50` → `- ./backend/data:/data`。⇒ 容器写的库 = 宿主 `backend/data/app.db`。
   - ② `docs/handoff-takeover-20260918.md:139` → 「生产运行时 = Docker（宿主 8088/Caddy）；容器 DB = `backend/data/app.db`」。
   - ③ S7 备份工具命名：`data_app.db` = "容器侧 app.db"，其 size `19939328` = cc 10710 那份。另：仓库根 `.env` **没有** `DATABASE_URL` 覆盖（主会话查过），也无 `docker-compose.override.yml`。

⇒ 取证报告把 `data/app.db` 标为"容器"（= 生产真源）的命名是对的；T3 卡的"宿主=cc10710"标签把"容器侧那份"误称成了"宿主"。**结论：两份源文档的宿主/容器标签相反这一发现成立，但应读作"取证报告的路径命名正确、T3 卡的标签反了"，且生产真源判定须以 compose 挂载 + `DATABASE_URL` 写死为准，而非"谁最近被写"。**

### "宿主那份今天还是不是被写的"——按路径分别答（主答案：两份今天都没被写，经主会话复核认可）

- **`backend/data/app.db`（生产真源，Docker 容器 `/data/app.db`）**：自 `2026-09-17 02:37:31`（cc 10710）后 cc 恒为 10710 —— 取证（09-19 23:55）已确认；我 09-20 两次读数（r1/r2）仍 10710、size/mtime 全同 ⇒ **今天（09-20）没有被写**，且自 09-17 起已约 3 天未被写（与生产零流量一致）。
- **`backend/app.db`（根，宿主机本地默认库）**：自 `2026-09-19 00:28:25`（cc 10784）后 cc 恒为 10784 —— 取证已确认；我 09-20 两次读数仍 10784、size/mtime 全同 ⇒ **今天也没有被写**（距末次写约 46 小时）。注意这次写入的写者是宿主机评测/演练批，非生产流量。
- 物理依据：两份 `app.db` 均 **非 WAL 模式**（write_format=1），回滚日志模式下**每提交一个事务 cc 必增**，故 `cc 不变` 即等价于"没有写事务发生"——这是比 size/mtime 更硬的判据（size 可巧合相同、mtime 可被索引器/杀软改写，cc 不能）。

---

## 主会话独立复核（跨实现交叉验证，非复用 T3 脚本）

主会话未复用本卡的 `probe_t3.py`，而是自行读 SQLite 头字节，得到三组读数，与本卡逐字一致 ⇒ **读数层无误，本次驳回仅触及"生产真源"归属判据，不触及数据**：

| 文件 | cc | size | write_format | 与 T3 读数 |
|---|---|---|---|---|
| `backend/app.db` | 10784 | 20205568 | 1（非 WAL） | 一致 |
| `backend/data/app.db` | 10710 | 19939328 | 1（非 WAL） | 一致 |
| `quota_used.sqlite` | 2 | — | 2（WAL） | 一致 |

主会话并独立确认：仓库根 `.env` 无 `DATABASE_URL` 覆盖、无 `docker-compose.override.yml`。

---

## ② 产物（绝对路径 + 关键读数）

- 报告：`C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\t3-appdb-20260920\report.md`（本文件）
- 读数汇总：`C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\t3-appdb-20260920\readings.json`
- 两次原始读数（对齐证据）：`…\t3-appdb-20260920\readings-r1.json`、`…\t3-appdb-20260920\readings-r2.json`
- 可复跑读数脚本：`…\t3-appdb-20260920\probe_t3.py`；汇总脚本：`…\t3-appdb-20260920\assemble_readings.py`
- 关键读数：`backend/app.db` cc=10784/size=20205568/mtime=2026-09-19 00:28:25.716；`backend/data/app.db` cc=10710/size=19939328/mtime=2026-09-17 02:37:31.913；`quota_used.sqlite` cc=2/size=12288/mtime=2026-09-19 00:12:51.569（WAL）。

---

## ③ 判据对照（T3 卡判据逐条）

| 判据 | 满足？ | 说明 |
|---|---|---|
| 给一张「文件→路径→cc/size/mtime→谁在写→生产真源是不是它」表 | ✅ | 已给，按真实路径分行，未混报 |
| 一条可复跑命令 | ✅ | 见 ④ |
| "容器那份必须真读到才许下结论" | ✅ | `backend/data/app.db` 已真读：cc=10710 / size=19939328 / mtime=2026-09-17 02:37:31，非推测 |
| "两份混在一句话里报" | ✅ 已规避 | 两份按路径独立成行 |
| 终止条件：一次读数 + 一次独立复核读数，对齐即止 | ✅ | r1 与 r2 全字段一致（diffs=[]），见 readings.json `alignment` |
| "绝不开事务/VACUUM/不改 schema/不写字节" | ✅ | 仅 `open('rb').read(100)` + `os.stat`；零 sqlite3 连接 |

---

## ④ 我复跑的命令（照抄可跑）

```bash
export PATH=/c/Users/33393/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH
PY="C:/Users/33393/Desktop/ai-legal-helper/backend/venv/Scripts/python.exe"
DIR="C:/Users/33393/Desktop/ai-legal-helper/dispatch-output/t3-appdb-20260920"

# 第一次读数
"$PY" "$DIR/probe_t3.py" r1
# 独立复核读数（同一脚本、不同标签，间隔任意）
"$PY" "$DIR/probe_t3.py" r2
# 汇总 + 对齐校验，生成 readings.json
"$PY" "$DIR/assemble_readings.py"

# 基线锚定（只读）
cd "C:/Users/33393/Desktop/ai-legal-helper"
git rev-parse HEAD
"$PY" -c "import hashlib,pathlib; [print(p, hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()) for p in ['backend/retrieval.py','backend/main.py']]"
```

读数脚本只读 `backend/app.db`、`backend/data/app.db`、`backend/data/quota_used.sqlite` 三个文件头 100 字节，不改任何字节。

---

## ⑤ 诚实登记

- **没做到的**：未做"实时写者进程归因"（如 `netstat` / `docker ps` / 进程表抓拍）。理由：两份 `app.db` 均非 WAL，`cc` 不变已足以证"今天无写事务"，进程归因非必需。若要对"此刻是否有人正连着写"做实时归因，需补上述只读命令。
- **读不到的**：**无**。三份文件全部 `exists=true`、`magic_ok=true`，头 100 字节均成功读入。
- **未证实的（初版，已更新）**：
  1. "`backend/data/app.db` 当前是否真有 docker 容器在跑并持有它"——cc 停滞只能证明它近期没被写，不能证明容器是否存在/是否挂了该卷（这一条维持未证实）。
  2. ~~"生产真源"判定基于 `database.py:9` 默认回落 + 取证证据 G 的**读码推断**，非本次执行观测~~ —— **经主会话复核，现已由 ① `docker-compose.yml` 写死 `DATABASE_URL=sqlite:////data/app.db` + ② 挂载 `./backend/data:/data` + ③ `handoff-takeover-20260918.md:139` 原文 + ④ S7 备份命名(size 19939328=cc10710) 四点定案，不再是推断**。初版错在把"最近被写"当判据，已改正。
  3. `main.py` 哈希相对 `baseline.json` 漂移（`6a320e42…`→`a31b7b4c…`），属 ticket-I 在途，已在上文登记并重新锚定。
- **越界写声明**：**无**。本卡只写入交付目录 `dispatch-output/t3-appdb-20260920/` 下的文件（report.md、readings.json、readings-r1/r2.json、probe_t3.py、assemble_readings.py）。**未改 `backend/**`、未碰 `backend/main.py` / `backend/retrieval.py`、未碰 `docs/code-review-report-02e3851-20260918.md`；未做任何 git 写操作（add/commit/stash/checkout/push/reset 均无）；未开事务、未 VACUUM、未改 schema。** 读库仅 `open('rb')`，副作用仅 `st_atime` 刷新。
