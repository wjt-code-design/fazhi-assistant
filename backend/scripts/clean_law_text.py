"""数据清洗与质量门禁（37 部导入用）。

铁律：**清洗不改写条文文字**——只做行结构整理（空行/空白/页码残留行）与检测报告。

- clean_text：格式层清洗（保守，不碰内容字符）。
- 结构层检测（报告不自动改）：条号三类格式分布 / 重复条号 / 序列回退。
- verify_article_baseline：**期望条数基线**——行首条号集合 vs 切分后 chunk article 集合，
  差集即"被吞条号"（无空格变体等导致），是导入正确性的核心断言。
- 质量门禁三检：非空+无乱码 / 条号数>0 / 无重复异常。

用法：cd backend && python scripts/clean_law_text.py [--dry-run]
- 读 data/laws_raw/*.txt → 写 data/laws_clean/*.txt → 逐部报告 → FAIL 汇总。
- --dry-run：不写盘，只审计（将被删除的页码行 / 吞条 / 门禁），满足"删除前先看"。
"""

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
sys.path.insert(0, BACKEND)
os.chdir(BACKEND)

import chunking  # noqa: E402

RAW_DIR = os.path.join(BACKEND, "..", "data", "laws_raw")
CLEAN_DIR = os.path.join(BACKEND, "..", "data", "laws_clean")

# ---------------- 格式层清洗（保守，不改写内容字符） ----------------
_PAGE_LINE_RE = re.compile(r"^\s*[-—–]?\s*\d{1,4}\s*[-—–]?\s*$")
_PAGE_LINE_CN_RE = re.compile(r"^第\s*\d+\s*页\s*$")


def clean_text(text: str) -> str:
    """连续空行合并为单个空行；行首尾空白 strip；剔除整行页码残留。"""
    out: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            if out and out[-1] != "":
                out.append("")
            continue
        if _PAGE_LINE_RE.match(s) or _PAGE_LINE_CN_RE.match(s):
            continue
        out.append(s)
    while out and out[0] == "":
        out.pop(0)
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out)


def page_lines_to_remove(text: str) -> list:
    """返回将被剔除的整行页码残留：(行号, 行内容)。供 --dry-run 审计。"""
    removed = []
    for i, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if _PAGE_LINE_RE.match(s) or _PAGE_LINE_CN_RE.match(s):
            removed.append((i, s))
    return removed


# ---------------- 结构层检测（报告不自动改） ----------------
_ARTICLE_LINE_RE = re.compile(
    r"(?m)^第([零〇○一二三四五六七八九十百千万0-9０-９]+)条(?:之[一二三四五六七八九十百千万0-9０-９]+)?"
)
_ARTICLE_INLINE_RE = re.compile(
    r"第([零〇○一二三四五六七八九十百千万0-9０-９]+)条(?:之[一二三四五六七八九十百千万0-9０-９]+)?"
)


def article_line_set(text: str) -> set:
    """行首条号集合（完整匹配「第X条」「第X条之一」形态，非捕获组数字）。"""
    return {m.group(0) for m in _ARTICLE_LINE_RE.finditer(text)}


def _cn_to_int(s: str) -> int:
    """中文数字→int（用于序列检测；转换失败返回 -1 跳过）。"""
    digits = "零〇○一二三四五六七八九"
    units = {"十": 10, "百": 100, "千": 1000, "万": 10000}
    total, num = 0, 0
    for ch in s:
        if ch in digits:
            num = digits.index(ch)
            if num > 9:
                num = 0
        elif ch in units:
            total += (num or 1) * units[ch]
            num = 0
        else:
            return -1
    return total + num


def detect_duplicates(text: str) -> list:
    """同一条号出现多次（含之一变体区分）→ 返回重复条号列表。"""
    seen, dup = set(), []
    for m in _ARTICLE_LINE_RE.finditer(text):
        key = m.group(0)
        if key in seen and key not in dup:
            dup.append(key)
        seen.add(key)
    return dup


def detect_regression(text: str) -> list:
    """条号数字回退（忽略「第X条之一」变体）→ 返回 (回退处条号, 前一条号) 列表。"""
    prev = None
    regressions = []
    for m in _ARTICLE_LINE_RE.finditer(text):
        num = _cn_to_int(m.group(1))
        if num < 0:
            continue
        if prev is not None and num < prev:
            regressions.append((m.group(0), prev))
        prev = num
    return regressions


def no_space_variant_count(text: str) -> int:
    """条号后直接接内容字符（无空格变体，含全角空格 U+3000 判定）的行数。

    注意：str.strip() 会剔除 U+3000，必须用 str.isspace() 判断「是否空白」，
    否则会把「第X条　内容」（标准全角空格）误报为无空格变体。
    """
    n = 0
    for line in text.splitlines():
        m = _ARTICLE_LINE_RE.match(line)
        if m and m.end() < len(line) and not line[m.end()].isspace():
            n += 1
    return n


# ---------------- 期望条数基线（核心断言） ----------------
def verify_article_baseline(text: str, chunks: list) -> dict:
    """行首条号集合 vs chunk article 集合；差集即被吞条号。"""
    line_set = article_line_set(text)
    chunk_set = {c.meta.get("article", "") for c in chunks if c.meta.get("article")}
    missing = sorted(line_set - chunk_set)
    extra = sorted(chunk_set - line_set)
    return {
        "line_count": len(line_set),
        "chunk_count": len(chunk_set),
        "missing": missing,
        "extra": extra,
    }


# ---------------- 质量门禁 ----------------
MOJIBAKE_MARKS = ("�", "锟斤拷", "�")


def check_mojibake(text: str) -> bool:
    return any(m in text for m in MOJIBAKE_MARKS)


def main():
    parser = argparse.ArgumentParser(description="清洗法律文本（格式层，不改写条文文字）。")
    parser.add_argument("--dry-run", action="store_true", help="不写盘，只报告将被删除的页码残留行 / 吞条 / 门禁")
    args = parser.parse_args()

    if not os.path.isdir(RAW_DIR):
        print(f"raw 目录不存在：{RAW_DIR}（先跑 convert_docx.py）", file=sys.stderr)
        sys.exit(1)
    os.makedirs(CLEAN_DIR, exist_ok=True)
    files = sorted(f for f in os.listdir(RAW_DIR) if f.endswith(".txt"))
    if not files:
        print("raw 目录没有 txt", file=sys.stderr)
        sys.exit(1)

    print(f"{'文件':<34} {'字符':>7} {'条号':>5} {'重复':>3} {'回退':>3} {'无空格':>5} {'删行':>4}  门禁")
    fails = []
    total_removed = 0
    for fname in files:
        src = os.path.join(RAW_DIR, fname)
        text = open(src, encoding="utf-8").read()
        clean = clean_text(text)
        removed = page_lines_to_remove(text)
        total_removed += len(removed)
        chunks = chunking.split_law_document(clean)
        base = verify_article_baseline(clean, chunks)
        dups = detect_duplicates(clean)
        regr = detect_regression(clean)
        nospace = no_space_variant_count(clean)
        issues = []
        if check_mojibake(clean) or not clean.strip():
            issues.append("乱码/空")
        if base["line_count"] == 0:
            issues.append("无条号")
        if base["missing"]:
            issues.append(f"吞条{len(base['missing'])}")
        if dups:
            issues.append(f"重复{len(dups)}")
        if nospace:
            issues.append(f"无空格变体{nospace}")
        status = "PASS" if not issues else "FAIL " + ",".join(issues)
        if issues:
            fails.append((fname, issues, base, dups))
        print(
            f"{fname:<34} {len(clean):>7} {base['line_count']:>5} {len(dups):>3} {len(regr):>3} {nospace:>5} {len(removed):>4}  {status}"
        )
        if args.dry_run and removed:
            for lineno, content in removed[:8]:
                print(f"    - {fname}:{lineno}  删除 {content!r}")
            if len(removed) > 8:
                print(f"      ... 该文件共 {len(removed)} 行")
        if not args.dry_run:
            # 清洗后写盘（FAIL 也写——便于人工检查，但导入会拒绝 FAIL 文件）
            with open(os.path.join(CLEAN_DIR, fname), "w", encoding="utf-8", newline="\n") as f:
                f.write(clean)

    print(
        f"\n共 {len(files)} 部，FAIL {len(fails)} 部，页码残留行 {total_removed} 行。"
        + ("dry-run：未写盘。" if args.dry_run else f"输出目录：{CLEAN_DIR}")
    )
    if fails:
        for fname, issues, base, dups in fails:
            print(f"  [{fname}] {','.join(issues)} 吞条={base['missing'][:5]} 重复={dups[:5]}")
        sys.exit(1)


if __name__ == "__main__":
    main()
