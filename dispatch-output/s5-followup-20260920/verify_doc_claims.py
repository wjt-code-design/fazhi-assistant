"""逐条复验本轮写进 ADR-018 / 票 C 的 file:line 事实（不引用记忆，只读当下文件）。

每条给：断言 + 实测读数 + PASS/FAIL。任何一条 FAIL 都要回头改文档，不许"差不多"。
"""

import hashlib
import re
import subprocess
from datetime import date
from pathlib import Path

B = Path("backend")
MAIN = (B / "main.py").read_text(encoding="utf-8")
SETTINGS = (B / "settings.py").read_text(encoding="utf-8")
AC = (B / "answer_cache.py").read_text(encoding="utf-8")
RC = (B / "retrieval_core.py").read_text(encoding="utf-8")
TFQ = (B / "tests" / "test_flagship_quality.py").read_text(encoding="utf-8")

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
check("开关定义在 settings.py:96 且默认 False", n == 96, f"实测行号={n}")
check(
    "settings 注释仍写「只覆盖缓冲轻量出口」",
    "只覆盖" in SETTINGS and "_light_buffered_locked" in SETTINGS,
    f"命中「只覆盖」={('只覆盖' in SETTINGS)}",
)

# --- 2. answer_cache: 进程内 LRU(512) + TTL 6h + 只有 clear() 一个删除口 ---
check("answer_cache 用 rc.LRU(maxsize=512)", "_cache = rc.LRU(maxsize=512)" in AC, f"行 {line_of(AC, '_cache = rc.LRU')}")
check("TTL = 6 小时", "TTL = timedelta(hours=6)" in AC, f"行 {line_of(AC, 'TTL = timedelta(hours=6)')}")
defs = re.findall(r"^def (\w+)", AC, re.M)
check(
    "删除口只有 clear()，无按 model 删除",
    "clear" in defs and not any("delete" in d or "remove" in d or "pop" in d for d in defs),
    f"公开函数={defs}",
)
check("LRU 是 OrderedDict 无磁盘后端", "OrderedDict" in RC and "sqlite" not in RC.lower()[: 4000], "")

# --- 3. main.py 各坐标 ---
c1883 = line_of(MAIN, "bad = citation_verify(answer)")
c1886 = line_of(MAIN, 'answer_cache.put(cache_key, answer, pre["sources"], model="contract_review")')
check("合同: bad 算出在 :1883", c1883 == 1883, f"实测={c1883}")
check("合同: put 在 :1886", c1886 == 1886, f"实测={c1886}")
check("合同: put 早于注记追加", c1886 < line_of(MAIN, 'answer += note'), f"put={c1886} answer+=note={line_of(MAIN, 'answer += note')}")
g_light = line_of(MAIN, 'if cache_key and res.verdict == "pass" and not res.law_version_hit:')
g_stream = line_of(MAIN, "if cache_key and not flag_degraded and _cache_write_ok(pre, answer) and not multi_bad:")
check("轻量写闸在 :1933", g_light == 1933, f"实测={g_light}")
check("流式写闸在 :2071 且是 4 条 and", g_stream == 2071 and MAIN.splitlines()[2070].count(" and ") == 3, f"实测={g_stream}")
LQ = line_of(MAIN, 'v.reason or "low_quota"')
check("配额耗尽分支把 verdict 写成 low_quota（:1249-1251 区间）", 1249 <= LQ <= 1251, f"实测={LQ}")
check("multi_incomplete 全文只在 :2030 调用", line_of(MAIN, "quality.multi_incomplete(") == 2030, f"实测={line_of(MAIN, 'quality.multi_incomplete(')}")
sc_lines = [i for i, ln in enumerate(MAIN.splitlines(), 1) if "quality.self_check(" in ln]
check("self_check 只在 :1240/:1265/:2066", sc_lines == [1240, 1265, 2066], f"实测={sc_lines}")
NPUT = MAIN.count("answer_cache.put(")
check("全仓三处 answer_cache.put", NPUT == 3, f"实测次数={NPUT}")

# --- 4. _qa_direct_return 是持久语料、三道护栏无版本判定 ---
q = line_of(MAIN, "def _qa_direct_return")
check("_qa_direct_return 定义在 :1100", q == 1100, f"实测={q}")
body = "\n".join(MAIN.splitlines()[q - 1 : q + 25])
check(
    "其 docstring 称「持久」且护栏无 version/watershed",
    "持久" in body and "law_version" not in body and "watershed" not in body,
    f"含「持久」={'持久' in body} 含版本判定={'law_version' in body or 'watershed' in body}",
)

# --- 5. 无任何运行时改写该开关（非测试文件） ---
hits = subprocess.run(
    ["grep", "-rn", r"settings\.fast_path_law_version_check\s*=", "--include=*.py", "backend"],
    capture_output=True,
    text=True,
).stdout
non_test = [h for h in hits.splitlines() if h and "/tests/" not in h and "\\tests\\" not in h and "backend\\tests" not in h]
check("非测试代码里没有任何改写该开关的赋值", non_test == [], f"命中={non_test or '无'}")

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
    text=True,
    encoding="utf-8",
    errors="replace",
).stdout
check("该行早于本轮（966a769~1 里就在）", "text 无 light 档" in old, f"966a769~1 命中={'text 无 light 档' in old}")

# --- 7. gate2_runner sha256 ---
h = hashlib.sha256((B / "scripts" / "gate2_runner.py").read_bytes()).hexdigest()
check(
    "gate2_runner sha256 仍是票面要求的 ae2e4120…47e295",
    h == "ae2e412059ed68ac1514c62727cee61c50b8a2d6fe7e38a77c7e05631847e295",
    h[:16] + "…" + h[-6:],
)

# --- 8. 锚点 13 个、且注册表 13 行 ---
REG = (B / "gate_exit_registry.py").read_text(encoding="utf-8")
ANCH = len(re.findall(r"#\s*gate-exit:", MAIN))
ROWS_N = len(re.findall(r'"id": "E\d+"', REG))
check("main.py 里 gate-exit 锚点 = 13", ANCH == 13, f"实测={ANCH}")
check("注册表 EXITS 行数 = 13", ROWS_N == 13, f"实测={ROWS_N}")
check("今天仍是 2026-09-20（票面日期自洽）", str(date.today()) == "2026-09-20", str(date.today()))

w = max(len(n) for n, _, _ in rows)
bad = 0
for name, ok, reading in rows:
    if not ok:
        bad += 1
    print(("PASS  " if ok else "FAIL  ") + name.ljust(w) + "  | " + str(reading))
print(f"\n合计 {len(rows)} 条，FAIL={bad}")
