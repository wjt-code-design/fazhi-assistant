# 开发/构建工具那一轴（计划 A-3，2026-09-29 现量，全程不花凭据）

**为什么单列一件**：这 5 条**不在 `residual-risk-review.md` 那 26 行分母里**（它们只在"实装集"命中，
`requirements.txt` 解析集里根本没有 `pytest`、`setuptools` 这两个包）。把它们折进运行时那 26 行会同时弄脏
分母和 D2 的签字射程——与 `torch` 那一轴同样的处理方式。

**复算件**：`python b_scope_recount.py --write`（三轴对账，闭合判定 `26 + 5 == 31`，对不上 rc=1）。
本件的 5 行就是它「表外 5」那一档的展开；`python b_no_fix_union.py` 只算运行时那根轴，本件不共用它的分母。

---

## 一、两个环境的现量对照（这决定下面每一条能不能算"暴露"）

| 环境 | 是什么 | pytest | setuptools | 来源核证据 |
|---|---|---|---|---|
| **被扫的那套** | 副本树 venv `…\Temp\legal-closeout-20260928\venv`（宽套件与 pip-audit 都跑在它上面） | **8.4.2** | **65.5.0** | `pip show` 实测；`site-packages` 里 `pytest-8.4.2.dist-info`、`setuptools-65.5.0.dist-info` 存在 |
| **日常开发那套** | `backend/venv`（未入库，`git ls-files backend/venv` = 0） | **9.1.1** | 65.5.0 | `python -m pip show pytest` → `Version: 9.1.1`，`Required-by: pytest-cov` |

⇒ **同一台机器上 pytest 有两个版本并存**，任何"pytest 这条没关系"的说法必须先说清指的是哪一套。

`setuptools` 在两处都是 **65.5.0 且 `Required-by:` 为空** ⇒ 没有任何包声明依赖它；它是 venv 引导时 `ensurepip`
带进来的那一份，**不是本项目的依赖**。

## 二、逐条处置（5 条；每条都给"触发前提"而不是只给版本号）

| 通报 | 包/版本 | 修复版本 | 公告要求的触发前提 | 本项目具备吗（证据） | 助手能证到的边界 |
|---|---|---|---|---|---|
| CVE-2022-40897 | setuptools 65.5.0 | **65.5.1** | `package_index` 的正则被恶意 HTML 触发 ReDoS：需要走 PyPI/自定义 **PackageIndex 下载** | **不具备**：仓库无 `setup.py`/`setup.cfg`/`MANIFEST.in`；`backend/pyproject.toml` **只有工具配置**（实测章节全是 `[tool.*]`，**无 `[build-system]`、无 `[project]`** ⇒ 它不是一个可被构建的发行包）；`setup_requires`/`easy_install`/`pkg_resources` 在码与配置里 **0 命中** | 构建期专用，且该下载路径不在任何构建/部署命令里；**有可升版本** |
| CVE-2024-6345 | setuptools 65.5.0 | **70.0.0** | `package_index` 的下载函数被喂**用户可控 URL** ⇒ RCE | **不具备**：同上；依赖安装全部走 `pip install -r requirements.txt`（`backend/Dockerfile:45`） | 同上——这是四条里后果最重的一条，但前提同样落在没人走的模块上 |
| CVE-2025-47273 | setuptools 65.5.0 | **78.1.1** | `PackageIndex._download_url` 路径穿越（`..` 归一化） | **不具备**：同上 | 同上 |
| CVE-2026-59890 | setuptools 65.5.0 | **83.0.0** | 构建 sdist（`python -m build --sdist` / `setup.py sdist`）时 `MANIFEST.in` 的 NFC/NFD 归一化漏排除，**且文件系统为 macOS APFS/HFS+** | **两个条件都不具备**：仓库无 `MANIFEST.in`、无任何 sdist 构建步骤；宿主是 Windows（开发）+ `ubuntu-latest`（CI）。⚠️ **但别把"工具没装"当成依据**：`build` 1.3.0 **确实装着**（`pip show build` → `Required-by: chromadb`，是传递依赖）⇒ 这条不成立靠的是"**没人调它 + 没有可漏排除的 `MANIFEST.in` + 平台不是 macOS**"，不是靠"环境里没有构建工具" | 双重不适用：既不在调用面上，也不在该平台上 |
| CVE-2025-71176 | pytest 8.4.2 | **9.0.3** | **UNIX** 上 `/tmp/pytest-of-{user}` 目录名可预测 ⇒ 本地用户 DoS / 提权 | ⚠️ **前提成立**：`.github/workflows/ci.yml:11` 是 `ubuntu-latest`，`:24` 装 `requirements-dev.txt`，`:34` 跑 `pytest` | **这条不能记成"构建期专用 ⇒ 无风险"**，见下面第三节 |

## 三、pytest 这条：钉子上限正好挡住了修复（本轴唯一要 Owner 动的东西）

`backend/requirements-dev.txt` 写的是 **`pytest>=7.4,<9`**，而该通报的修复版本是 **9.0.3**。实测判据：

```
pin: >=7.4,<9
8.4.2 in-pin: True   | >=fix 9.0.3: False      ← 被扫那套 / CI 会装到的那套
9.0.3 in-pin: False  | >=fix 9.0.3: True
9.1.1 in-pin: False  | >=fix 9.0.3: True       ← 日常开发那套已经越过 <9
```

⇒ 三个后果，按严重度排：

1. **`pip install -r requirements-dev.txt` 永远解析到受影响的 pytest**（上限 `<9` 把 9.0.3 排除在外）。
   CI 在 Linux 上跑 pytest ⇒ 通报要求的两个前提（UNIX + 真的跑 pytest）**都成立**，这不是"够不着"而是"每次都在跑"。
2. 反过来，`backend/venv` 已经是 **9.1.1**（`>=9.0.3`，修复已在），**但它违反在册的 `<9`** ⇒
   这个 pin 在实践中已被某套环境绕过。**两套状态并存**这件事本身比 CVE 更值得先解决：
   它意味着"实装集读数"和"按 requirements-dev 全新装一套"会得到不同答案（上面的 8.4.2 vs 9.1.1 就是这一条）。
   ⚠️ **我手上没有的证据**：本会话**没有**在 `pytest 9.1.1` 那套上跑过全量套件 ⇒ 不能把"9 已经验证过"当既成事实用。
   若 Owner 选"放宽"，第一步应当是在 9.x 上跑一次全量门禁（那才是先例证据），而不是直接改 pin。
3. 该通报的实际危害面是**同一台机器上的本地用户**（提权/DoS 靠抢 `/tmp` 目录名）。GitHub 托管 runner 是一次性、
   单租户环境 ⇒ 现实暴露低。**但这是部署形态给的缓解，不是版本给的**，与 Chroma 那两条同一个性质，别混着说。

**要 Owner 决定的一件事（一词可答）**：把 `pytest>=7.4,<9` 的上限放宽到 `>=9.0.3`（或去掉上限）？
- 选"放宽"：一条数字改动，CI 与全新环境都落在修复版本上；代价是 pytest 9 的破坏性变更要过一遍全量测试
  （`backend/venv` 已经在 9.1.1 上跑过全量，可作为先例证据）。
- 选"保持 `<9`"：这一条**长期版本适用**，只能作为"CI 平台为一次性 runner"的使用限制由 Owner 显式接受，
  并接受"任何把 CI 换到多租户/自建 Linux runner 的动作都会削弱这条限制"。

⚠️ 本计划明令**不自动授权新增依赖升级**，所以这里只把判据和两条路摆出来，**不动 `requirements-dev.txt`**。

## 四、这一轴现在的状态

⚠️ **读数来自哪套环境，先说清楚**：上面所有版本都是**本机那两套 venv** 的实测（副本树 venv + `backend/venv`）。
**生产镜像里 `setuptools`/`pytest` 是什么版本，本会话未核**——没有构建镜像、也没进容器（`docker exec` 在本机被拦，
且构建/部署不在本次授权内）。能确定的是**镜像里根本不该有它们**：`backend/Dockerfile` 只 `COPY requirements.txt`
并 `pip install -r requirements.txt`（:20、:45），`requirements-dev.txt` 只被 `.github/workflows/ci.yml:24` 安装
⇒ **pytest 是 CI 面**；setuptools 若出现在镜像里，那来自基础镜像 `python:3.11-slim` 的引导层，**这一条是推断，不是读数**。

- **setuptools 4 条**：触发前提均不具备（构建下载/ sdist 路径无人走，59890 另加平台条件），
  且**四条都有可升版本**（65.5.1 / 70.0.0 / 78.1.1 / 83.0.0）⇒ 与运行时轴那 4 条"并集为空、无升级可消"**正好相反**，
  这一轴不存在"只能等上游"的死结。若要清零，`pip install -U setuptools` 之类的一次引导环境刷新即可，
  但它**不属于应用运行时**，也不在 D2 射程内。
- **pytest 1 条**：版本适用、平台适用、**被在册 pin 挡住修复** ⇒ **未处置**，等上面第三节那一个决定。
- **共同状态仍不改变**：本文件是"助手能证到的边界 + 待 Owner 落笔的处置建议"，**不是签字**；
  写在这里不等于任何一条被接受或被排除。登记表 26 行分母、`pip-audit` 的红读数、D2 的射程，均不因本件变化。
