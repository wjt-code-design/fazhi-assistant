"""逐条复验本轮写进 ADR-018 / 票 C 的 file:line 事实（不引用记忆，只读当下文件）。

每条给：断言 + 实测读数 + PASS/FAIL。任何一条 FAIL 都要回头改文档，不许"差不多"。
"""

import hashlib
import re
import subprocess
from datetime import datetime
from pathlib import Path

B = Path("backend")
MAIN = (B / "main.py").read_text(encoding="utf-8")
SETTINGS = (B / "settings.py").read_text(encoding="utf-8")
AC = (B / "answer_cache.py").read_text(encoding="utf-8")
RC = (B / "retrieval_core.py").read_text(encoding="utf-8")
TFQ = (B / "tests" / "test_flagship_quality.py").read_text(encoding="utf-8")
ADR = Path("docs/ADR.md").read_text(encoding="utf-8")
REG = (B / "gate_exit_registry.py").read_text(encoding="utf-8")

# 含双引号的needle 一律先命名，别塞进 f-string（3.11 的 f-string 里不许有反斜杠）。
# ⚠️ CONTRACT_PUT 必须是**整句**：只写 `model="contract_review"` 会同时命中下面那条
#    `log_account(model="contract_review", ...)` ⇒ "唯一性"判据当场失真（本脚本第一次跑就是这样）。
CONTRACT_PUT = (
    'answer_cache.put(cache_key, answer, pre["sources"], model="contract_review")'
)
LOW_QUOTA = 'v.reason or "low_quota"'
LIGHT_GUARD = 'if cache_key and res.verdict == "pass" and not res.law_version_hit:'


def stream_guard_block(text: str) -> str:
    """定位**流式那条写缓存闸**并返回整块文本 —— 认形状，不认字面行。

    票 C 之前它是单行 `if cache_key and … and not multi_bad:`；加上第五条件后被 `ruff-format`
    拆成多行 `if ( … ):` 块 ⇒ 任何"整行字面匹配"都变成**恒假**（更糟的是它还会绿着骗过评审，
    如果断言写成"字面常量里有 3 个 and"那种自我比对的话）。本轮就把那种写法换掉了。
    唯一稳定形状：全文件里**恰好一块**包含 `_cache_write_ok(pre, answer)` 的 `if (` 块。
    """
    lines = text.splitlines()
    hits = [i for i, ln in enumerate(lines) if "_cache_write_ok(pre, answer)" in ln]
    if len(hits) != 1:
        raise SystemExit(
            f"_cache_write_ok(pre, answer) 命中 {len(hits)} 行，无法唯一定位写缓存闸"
        )
    i = hits[0]
    start = max(j for j in range(i, -1, -1) if lines[j].strip() == "if (")
    end = min(j for j in range(i, len(lines)) if lines[j].strip().startswith("):"))
    return "\n".join(lines[start : end + 1]).strip()


rows: list[tuple[str, bool, str]] = []


def line_of(text: str, needle: str) -> int:
    for i, ln in enumerate(text.splitlines(), 1):
        if needle in ln:
            return i
    return -1


def check(name: str, ok: bool, reading: str) -> None:
    rows.append((name, ok, reading))


# --- 1. settings.py:96 开关定义 + 默认 False + 范围注释 ---
n = line_of(SETTINGS, "fast_path_law_version_check: bool = False")
check(
    "开关定义存在、唯一、默认 False（行号只作读数，不断言）",
    SETTINGS.count("fast_path_law_version_check: bool = False") == 1,
    f"实测行号={n}",
)
check(
    "settings 范围注释已按票 C §5-8 改写（旧的「只覆盖缓冲轻量出口」必须消失）",
    "只覆盖" not in SETTINGS and "生成型" in SETTINGS and "缓存复用型" in SETTINGS,
    f"仍含「只覆盖」={'只覆盖' in SETTINGS} 含「生成型」={'生成型' in SETTINGS} 含「缓存复用型」={'缓存复用型' in SETTINGS}",
)

# --- 2. answer_cache: 进程内 LRU(512) + TTL 6h + 只有 clear() 一个删除口 ---
check(
    "answer_cache 用 rc.LRU(maxsize=512)",
    "_cache = rc.LRU(maxsize=512)" in AC,
    f"行 {line_of(AC, '_cache = rc.LRU')}",
)
check(
    "TTL = 6 小时",
    "TTL = timedelta(hours=6)" in AC,
    f"行 {line_of(AC, 'TTL = timedelta(hours=6)')}",
)
defs = re.findall(r"^def (\w+)", AC, re.MULTILINE)
check(
    "删除口只有 clear()，无按 model 删除",
    "clear" in defs
    and not any("delete" in d or "remove" in d or "pop" in d for d in defs),
    f"公开函数={defs}",
)
check(
    "LRU 是 OrderedDict 无磁盘后端",
    "OrderedDict" in RC and "sqlite" not in RC.lower()[:4000],
    "",
)


# --- 3. main.py 各锚点：**钉"形状唯一"而不是钉行号** ---
# 本仓行号已漂过五次（最近一次 2026-09-20，被一次 5 行的 docstring 改动整体挤掉 +5），
# 而 ADR-018 自己定的 R4 就是"只用符号锚点"。⇒ 判据必须是"这个形状在全文出现几次"，
# 行号只作为**读数**打印出来供人核对，不进断言。
def count_of(needle: str) -> int:
    return sum(1 for ln in MAIN.splitlines() if needle in ln)


check(
    "合同: bad = citation_verify(answer) 形状唯一",
    count_of("bad = citation_verify(answer)") == 1,
    f"次数={count_of('bad = citation_verify(answer)')} 行={line_of(MAIN, 'bad = citation_verify(answer)')}",
)
check(
    "合同: 三处 answer_cache.put 且合同那处带 contract_review 标记",
    MAIN.count("answer_cache.put(") == 3 and count_of(CONTRACT_PUT) == 1,
    f"put={MAIN.count('answer_cache.put(')} 行={line_of(MAIN, CONTRACT_PUT)}",
)
check(
    "合同: put 早于 answer += note（顺序判据，与行号无关）",
    line_of(MAIN, CONTRACT_PUT) < line_of(MAIN, "answer += note"),
    f"put={line_of(MAIN, CONTRACT_PUT)} +=note={line_of(MAIN, 'answer += note')}",
)
check(
    "两条写缓存闸各自可唯一定位（轻量=单行字面，流式=多行 if ( 块）",
    count_of(LIGHT_GUARD) == 1 and stream_guard_block(MAIN).startswith("if ("),
    f"轻量={line_of(MAIN, LIGHT_GUARD)} 流式首行={line_of(MAIN, '_cache_write_ok(pre, answer)')}",
)
# ⚠️ 这条以前是**自我比对**（拿字面常量 STREAM_GUARD 数 `and`），文件里那条闸没了它照样绿 ——
# 正是本 ADR 要防的"能骗过评审的空枪"。现在条件数从**文件里那块**数出来。
_SG = stream_guard_block(MAIN)
check(
    "流式那条闸从四条件变成**五**条件，且第五条就是 `not law_version_hit`（票 C §5-6）",
    _SG.count(" and ") == 4 and "and not law_version_hit" in _SG,
    f"块内 and 数={_SG.count(' and ')} 含第五条={'and not law_version_hit' in _SG}",
)
check(
    "except QuotaExhausted 那一支把 verdict 写成 v.reason or low_quota",
    count_of(LOW_QUOTA) == 1,
    f"次数={count_of(LOW_QUOTA)} 行={line_of(MAIN, LOW_QUOTA)}",
)
check(
    "quality.multi_incomplete 全文只有一个调用点",
    count_of("quality.multi_incomplete(") == 1,
    f"次数={count_of('quality.multi_incomplete(')} 行={line_of(MAIN, 'quality.multi_incomplete(')}",
)
sc_lines = [
    i for i, ln in enumerate(MAIN.splitlines(), 1) if "quality.self_check(" in ln
]
check(
    "quality.self_check 调用点恰 3 处",
    len(sc_lines) == 3,
    f"实测行={sc_lines}（只作读数，不断言位置）",
)

# --- 4. _qa_direct_return 是持久语料、三道护栏无版本判定 ---
q = line_of(MAIN, "def _qa_direct_return")
check(
    "_qa_direct_return 存在且唯一",
    count_of("def _qa_direct_return") == 1,
    f"行={q}（只作读数）",
)
body = "\n".join(MAIN.splitlines()[q - 1 : q + 25])
check(
    "其 docstring 称「持久」且护栏无 version/watershed",
    "持久" in body and "law_version" not in body and "watershed" not in body,
    f"含「持久」={'持久' in body} 含版本判定={'law_version' in body or 'watershed' in body}",
)

# --- 5. 无任何运行时改写该开关（非测试文件） ---
hits = subprocess.run(
    [
        "grep",
        "-rn",
        r"settings\.fast_path_law_version_check\s*=",
        "--include=*.py",
        "backend",
    ],
    capture_output=True,
    check=False,
    text=True,
).stdout
non_test = [
    h
    for h in hits.splitlines()
    if h and "/tests/" not in h and "\\tests\\" not in h and "backend\\tests" not in h
]
check(
    "非测试代码里没有任何改写该开关的赋值", non_test == [], f"命中={non_test or '无'}"
)

# --- 6. test_flagship_quality docstring 第 3 行（且早于本轮） ---
l3 = TFQ.splitlines()[2]
check(
    "第 3 行含「text 无 light 档，use_light=False」",
    "text 无 light 档" in l3 and "use_light=False" in l3,
    repr(l3[:60]),
)
old = subprocess.run(
    ["git", "show", "966a769~1:backend/tests/test_flagship_quality.py"],
    capture_output=True,
    check=True,
    text=True,
    encoding="utf-8",
    errors="replace",
).stdout
check(
    "该行早于本轮（966a769~1 里就在）",
    "text 无 light 档" in old,
    f"966a769~1 命中={'text 无 light 档' in old}",
)

# --- 7. gate2_runner sha256 ---
h = hashlib.sha256((B / "scripts" / "gate2_runner.py").read_bytes()).hexdigest()
check(
    "gate2_runner sha256 仍是票面要求的 ae2e4120…47e295",
    h == "ae2e412059ed68ac1514c62727cee61c50b8a2d6fe7e38a77c7e05631847e295",
    h[:16] + "…" + h[-6:],
)

# --- 8. 锚点数与注册表行数**同源**（票 C 加 E14 之后，写死 13 的那版会自己变红）---
# 旧写法 `ANCH == 13` / `ROWS_N == 13` 把两张不同的表各抄了一份常数，正是本 ADR 立的规矩要防的
# "同一契约两处写法"：出口一多，先红的是仪器，而它一红就会被下一个人当成"过时断言"删掉。
# 现在钉的是**等式**（锚点数 == 登记行数）+ 一条只增不减的下界。
ANCH = len(re.findall(r"#\s*gate-exit:", MAIN))
ROWS_N = len(re.findall(r'"id": "E\d+"', REG))
check(
    "锚点数 == 登记表行数（两计数同源，不许各抄常数）",
    ANCH == ROWS_N,
    f"锚点={ANCH} 行={ROWS_N}",
)
check(
    "出口数 ≥ 13（本表立起来时的量；变小=有人删了出口）", ROWS_N >= 13, f"实测={ROWS_N}"
)
TODAY = datetime.now().astimezone().date()
check("今天仍是 2026-09-20（票面日期自洽）", str(TODAY) == "2026-09-20", str(TODAY))

# --- 9. **禁行号**：ADR 与登记表里不许再出现 `:NNNN` 形式的取证引用 ---
# 这一条是本轮第五次行号漂移换来的：ADR-018 自己写了"只用符号锚点"，正文里却引了 15 个行号，
# 而一次 5 行的 docstring 改动就把它们全部作废（其中 7 条是我这台仪器自己先发现的）。
# ⇒ 规矩要落成能炸的东西，否则它只是一句写在文档里的自觉。
# 两种形状：`x.py:285` 与被反引号包住的 `:2071`。**已知量程外**：散文里裸写"第 1921 行"抓不到——
# 之所以不放宽到 `:\d+`，是因为 "TTL=6h / 05:43" 这类合法读数会被误伤；量程说清比假装全管好。
LN_RE = re.compile(r"\.py:\d|`:\d{3,5}`")
_PROBE = [
    "见 `main.py:1921` 那一条闸",
    "取证在 clarify.py:285-286 注释",
    "两条闸各在 `:1938` / `:2076`",
]
_missed = [p for p in _PROBE if not LN_RE.search(p)]
sec = (
    ADR.split("## ADR-018", 1)[1].split("\n## ADR-", 1)[0]
    if "## ADR-018" in ADR
    else ""
)
adr_ln = [ln for ln in sec.splitlines() if LN_RE.search(ln)]
reg_ln = [ln for ln in REG.splitlines() if LN_RE.search(ln)]
check(
    "ADR-018 这一节里没有 `:NNNN` 取证引用",
    bool(sec) and adr_ln == [],
    f"节长={len(sec)} 残留={adr_ln[:2]}",
)
check("登记表真源里没有 `:NNNN` 取证引用", reg_ln == [], f"残留={reg_ln[:2]}")
check("禁行号正则不是空枪（三种违规形状必须全抓到）", _missed == [], f"漏={_missed}")

w = max(len(n) for n, _, _ in rows)
bad = 0
for name, ok, reading in rows:
    if not ok:
        bad += 1
    print(("PASS  " if ok else "FAIL  ") + name.ljust(w) + "  | " + str(reading))
print(f"\n合计 {len(rows)} 条，FAIL={bad}")
