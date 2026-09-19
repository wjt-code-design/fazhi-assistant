"""本轮 5 次自纠错的**系统性**收口：不给每条加一句提醒，而是造一台挡住这一整类的仪器，
并**先证明它挡得住**——每条腿跑两次：一次喂"我当初真写错的那种读数/口径"（必须红），
一次喂当下的真实文档与代码（必须绿）。没红过一次的腿等于没有腿。

根因（4/5 条同源）：**拿局部视图当整体证据** + **拿自己早先写下的字当事实来源**。
第 5 条（未转义双引号）是另一类，已由 ruff / pre-commit 在工具层挡住，不在此表。
"""

import re
import subprocess
import sys
from pathlib import Path

B = Path("backend")
ADR = Path("docs/ADR.md").read_text(encoding="utf-8")
MAIN = (B / "main.py").read_text(encoding="utf-8")
AC = (B / "answer_cache.py").read_text(encoding="utf-8")
CR, LF, CRLF = b"\r", b"\n", b"\r\n"

results: list[tuple[str, bool, str]] = []


def leg(name: str, ok: bool, reading: str) -> None:
    results.append((name, ok, reading))


# ============ 腿 A：枚举必须全量，禁止 tail -N 视图 ============
# 当初的错：`grep -n "^## ADR-" | tail -8` 只看到文件后半段的标题，而 ADR-016/017 在顶部块，
# 于是判定"最后一条是 ADR-015"，据此选了一个已被占用的编号。
heads = re.findall(r"^## (ADR-\d+)", ADR, re.MULTILINE)
maxnum = max(int(h.split("-")[1]) for h in heads)
tail_view = heads[-8:]
leg(
    f"A 全量枚举：ADR 共 {len(heads)} 条，最大 {maxnum}，而尾部 8 条视图里看不到它",
    len(heads) == 18 and maxnum == 18 and f"ADR-{maxnum}" not in "\n".join(tail_view),
    f"tail-8 视图前两项={tail_view[:2]}；编号 {maxnum} 缺席 ⇒ 视图法与全量法结论不同",
)
# 自证：把"只读尾部"的判据接到合成样本上，它必须给出**错**答案（证明这条腿不是同义反复）
synthetic = "## ADR-016 x\n## ADR-017 y\n" + "".join(
    f"## ADR-{i:03d} z\n" for i in range(1, 16)
)
syn_all = re.findall(r"^## (ADR-\d+)", synthetic, re.MULTILINE)
naive_num = int(syn_all[-1].split("-")[1])
true_max = max(int(h.split("-")[1]) for h in syn_all)
leg(
    f"A 自证：只读尾部在合成样本上得 {naive_num}，真值 {true_max} ⇒ 视图法确实会错",
    naive_num != true_max,
    f"tail 法={naive_num} vs 全量={true_max}",
)

# ============ 腿 B：自己写过的字不是证据来源 ============
# 当初的错：票 C 写"错版本答复在库一天"——那句来自我自己上一轮的手感，没查过存储介质。
persistence = re.findall(r"sqlite3|open\s*\(|pickle|shelve|\.db\b", AC)
cap = re.search(r"rc\.LRU\((.*?)\)", AC)
mttl = re.search(r"TTL\s*=\s*timedelta\(hours=(\d+)\)", AC)
real_hours = float(mttl.group(1)) if mttl else float("inf")
cap_txt = cap.group(1) if cap else "未量到"
leg(
    f"B answer_cache 无持久化写口 + TTL={real_hours:g}h + {cap_txt} ⇒ 票里那句「在库一天」是假的",
    persistence == [] and real_hours < 24.0,
    f"持久化命中={persistence or '无'}；docstring 自称「重启即空」={'重启即空' in AC}",
)
leg(
    f"B 自证：旧断言 24h 与实测 {real_hours:g}h 必须被判矛盾",
    abs(real_hours - 24.0) > 1e-9,
    f"Δ={24.0 - real_hours:g}h ⇒ 暴露窗被高估 4 倍",
)


# ============ 腿 C：集合差要用交并集算，不能用"我数了一下" ============
# 当初的错：写"轻量 3 条件 / 流式 4 条件 ⇒ 缺 2 件"，这句话自己不闭合（3+2≠4）。
def conjuncts(line: str) -> set[str]:
    return {
        c.strip()
        for c in line.strip().removeprefix("if ").removesuffix(":").split(" and ")
    }


g_light = next(
    ln for ln in MAIN.splitlines() if 'if cache_key and res.verdict == "pass"' in ln
)
g_stream = next(
    ln for ln in MAIN.splitlines() if "if cache_key and not flag_degraded" in ln
)
sl, ss = conjuncts(g_light), conjuncts(g_stream)
inter, sd = sl & ss, ss - sl
leg(
    f"C 实测：轻量 {len(sl)} 条、流式 {len(ss)} 条、交集只有 {sorted(inter)}",
    len(inter) == 1 and len(sl) == 3 and len(ss) == 4,
    f"交集={sorted(inter)}；差集 S∖L={sorted(sd)}",
)
leg(
    f"C 自证：旧稿点名「另含 2 件」，实测字面差 {len(sd)} 件 ⇒ 那句话必然错",
    len(sd) != 2,
    "第 3 件 not flag_degraded 由 verdict==pass 语义承担；现文档已把"
    "「字面差几件」与「语义谁承担」分两句写，这正是旧稿混在一起的地方",
)

# ============ 腿 D：零变化声明必须钉"改动前那一版"，且不得与自身比 ============
# 当初的错有两层：①写"与 HEAD 逐字节相同"——锚点已在 HEAD 里，那是自我比对；
# ②autocrlf 下 blob 存 LF、工作树是 CRLF，"逐字节"这个口径本身不成立。
# 二版又错一次：拿"当下工作树"比 fad2cee~1 ⇒ 后来 main.py 又有合法改动，这句话当场烂。
# ⇒ 「锚点没改代码」是**那一笔提交**的性质，两边都必须按 commit 取，与工作树无关。
MARK = re.compile(rb"[ \t]*#[ \t]*gate-exit:[ \t]*E\d+[^\r\n]*")
cur = (B / "main.py").read_bytes()
head_blob = subprocess.run(
    ["git", "show", "HEAD:backend/main.py"], capture_output=True, check=True
).stdout
with_m = subprocess.run(
    ["git", "show", "fad2cee:backend/main.py"], capture_output=True, check=True
).stdout
pre = subprocess.run(
    ["git", "show", "fad2cee~1:backend/main.py"], capture_output=True, check=True
).stdout
leg(
    "D 基线自洽性：HEAD 已含标记 ⇒ 拿 HEAD 当基线是自我比对，必须被拒绝",
    bool(MARK.search(head_blob)),
    f"HEAD blob 含 gate-exit 标记={bool(MARK.search(head_blob))}；正确基线=fad2cee~1",
)
leg(
    "D 口径：blob 对 blob，剥标记后相同、不剥则不同、行数相等 ⇒ 文档只能这么写",
    MARK.sub(b"", with_m) == pre
    and with_m != pre
    and with_m.count(LF) == pre.count(LF),
    f"with_m LF={with_m.count(LF)} pre LF={pre.count(LF)}；工作树当下 CRLF={cur.count(CRLF)}"
    "（工作树行数会随后续合法改动变，所以它不进判据）",
)

w = max(len(n) for n, _, _ in results)
bad = 0
for name, ok, reading in results:
    bad += 0 if ok else 1
    print(("PASS  " if ok else "FAIL  ") + name.ljust(w) + " | " + str(reading))
print(f"\n合计 {len(results)} 条腿，FAIL={bad}")
sys.exit(1 if bad else 0)
