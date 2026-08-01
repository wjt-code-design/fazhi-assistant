"""docx → txt 批量转换（零 token，纯脚本）。

用法：cd backend && python scripts/convert_docx.py [--src 目录] [--out data/laws_raw] [--only 文件名片段]
- 输出 UTF-8 无 BOM；保留段落结构（docx_utils.extract）。
- 每文件报告：字符数 / 行首条号数 / FAIL（解析异常·乱码·空）/ WARN（修订·域代码）。
- FAIL 文件不写 txt；报告打印并汇总。
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
sys.path.insert(0, BACKEND)
os.chdir(BACKEND)

from docx_utils import extract  # noqa: E402

DEFAULT_SRC = r"C:\Users\33393\Law content"
DEFAULT_OUT = os.path.join(BACKEND, "..", "data", "laws_raw")
MOJIBAKE_MARKS = ("\ufffd", "锟斤拷", "�")
ARTICLE_LINE_RE = re.compile(r"(?m)^第[零〇○一二三四五六七八九十百千万0-9０-９]+条")


def check_mojibake(text: str) -> bool:
    return any(m in text for m in MOJIBAKE_MARKS)


def main():
    ap = argparse.ArgumentParser(description="docx → txt 批量转换")
    ap.add_argument("--src", default=DEFAULT_SRC)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--only", default="", help="只转换文件名含此片段的一个/多个文件")
    args = ap.parse_args()

    if not os.path.isdir(args.src):
        print(f"源目录不存在：{args.src}", file=sys.stderr)
        sys.exit(1)
    files = sorted(f for f in os.listdir(args.src) if f.lower().endswith(".docx"))
    if args.only:
        files = [f for f in files if args.only in f]
    if not files:
        print("没有匹配的 docx 文件", file=sys.stderr)
        sys.exit(1)

    os.makedirs(args.out, exist_ok=True)
    print(f"{'文件':<40} {'字符':>7} {'条号行':>6}  状态")
    n_fail = 0
    for fname in files:
        path = os.path.join(args.src, fname)
        with open(path, "rb") as f:
            raw = f.read()
        warns = []
        try:
            text, warns = extract(raw, fname)
        except ValueError as e:
            print(f"{fname:<40} {'-':>7} {'-':>6}  FAIL {e}")
            n_fail += 1
            continue
        if check_mojibake(text):
            print(f"{fname:<40} {len(text):>7} {'-':>6}  FAIL 乱码特征")
            n_fail += 1
            continue
        out_name = os.path.splitext(fname)[0] + ".txt"
        with open(os.path.join(args.out, out_name), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        arts = len(ARTICLE_LINE_RE.findall(text))
        status = "OK" if not warns else "OK " + "; ".join(warns)[:60]
        print(f"{fname:<40} {len(text):>7} {arts:>6}  {status}")
    print(f"\n共 {len(files)} 个文件，FAIL {n_fail} 个。输出目录：{args.out}")
    if n_fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
