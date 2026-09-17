"""整法 txt 批量导入（37 部导入用）。

- 读 data/laws_clean/*.txt（清洗后）；source 短名 = 文件名去「中华人民共和国」前缀 + 去 _日期 后缀。
- **批量路径**：每部法一次 chunking → 一次 add_chunks + 一次 invalidate（避免逐条写放大）。
- **file_hash 幂等**：同 hash 已导入则跳过（重跑安全）。
- **seed 取代**：切分结果中的 (source, article) 若存在 origin=seed 碎片 → 删除（整法版取代）。
- **导入后自动断言**：7 个种子碎片（origin=seed）必须全部被取代，否则退出码非 0。
- **purge**（导入前，按 source 精确匹配 + 默认 --dry-run）：清理历史上传残留。

用法：
  cd backend
  python scripts/import_docs.py --dry-run                       # 全量预检
  python scripts/import_docs.py --only 劳动法,民法典            # 只导入指定短名
  python scripts/import_docs.py --purge-source 个人所得税法     # 清理残留（先 --dry-run）
  python scripts/import_docs.py                                  # 全量导入
"""

import argparse
import hashlib
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
sys.path.insert(0, BACKEND)
os.chdir(BACKEND)

import chunking  # noqa: E402
import knowledge_service as ks  # noqa: E402
from rag_chain import vectorstore  # noqa: E402

CLEAN_DIR = os.path.join(BACKEND, "..", "data", "laws_clean")
_DATE_SUFFIX_RE = re.compile(r"_\d{8}$")
_PREFIX = "中华人民共和国"

# 7 个种子碎片（source, article）：整法导入后必须被取代
SEED_FRAGMENTS = {
    ("劳动合同法", "第十九条"),
    ("劳动合同法", "第二十条"),
    ("民法典", "第一百四十三条"),
    ("民法典", "第一百八十八条"),
    ("消费者权益保护法", "第二十五条"),
    ("刑法", "第十三条"),
    ("道路交通安全法", "第九十一条"),
}


def short_source(fname: str) -> str:
    name = os.path.splitext(fname)[0]
    name = _DATE_SUFFIX_RE.sub("", name)
    if name.startswith(_PREFIX):
        name = name[len(_PREFIX) :]
    return name


def _col():
    return vectorstore._collection


def purge_source(source: str, dry_run: bool) -> int:
    """删除指定 source 的历史残留（origin=upload 或任何无 file_hash 的旧数据）。按 source 精确匹配。"""
    ids = _col().get(where={"source": source})["ids"]
    if not ids:
        print(f"  purge：{source} 无条目")
        return 0
    print(f"  purge：{source} 将删除 {len(ids)} 条{'（dry-run，未执行）' if dry_run else ''}")
    if not dry_run:
        _col().delete(ids=ids)
        ks.retrieval.invalidate()
    return len(ids)


def import_one(fname: str, dry_run: bool) -> dict:
    path = os.path.join(CLEAN_DIR, fname)
    text = open(path, encoding="utf-8").read()
    source = short_source(fname)
    fh = hashlib.sha256(text.encode("utf-8")).hexdigest()

    # file_hash 幂等：同内容已导入 → 跳过
    exist = _col().get(where={"file_hash": fh}, include=["metadatas"])["ids"]
    if exist:
        return {"source": source, "skipped_hash": True, "chunks": 0, "seed_replaced": 0}

    chunks = chunking.split_law_document(text)
    articles = {c.meta["article"] for c in chunks if c.meta.get("article")}

    # seed 取代：删除本文件覆盖范围内的 origin=seed 碎片
    seed_replaced = 0
    if articles:
        seed_hits = _col().get(where={"$and": [{"source": source}, {"origin": "seed"}]}, include=["metadatas"])
        to_del = [
            cid for cid, m in zip(seed_hits["ids"], seed_hits["metadatas"], strict=True) if m.get("article") in articles
        ]
        if to_del:
            print(f"  {source}：seed 取代 {len(to_del)} 条碎片{'(dry-run)' if dry_run else ''}")
            seed_replaced = len(to_del)
            if not dry_run:
                _col().delete(ids=to_del)

    if dry_run:
        return {"source": source, "skipped_hash": False, "chunks": len(chunks), "seed_replaced": seed_replaced}

    pairs = [
        (c.page_content, {"article": c.meta.get("article", ""), "chapter": c.meta.get("chapter", "")}) for c in chunks
    ]
    n = ks.add_chunks(pairs, source=source, origin="upload", extra_meta={"status": "现行"}, file_hash_value=fh)
    return {"source": source, "skipped_hash": False, "chunks": n, "seed_replaced": seed_replaced}


def assert_seed_replaced() -> None:
    """7 个种子碎片必须全部被整法取代（origin=seed 且 (source, article) 匹配 = 0）。"""
    bad = []
    for src, art in sorted(SEED_FRAGMENTS):
        n = len(_col().get(where={"$and": [{"source": src}, {"article": art}, {"origin": "seed"}]})["ids"])
        if n:
            bad.append(f"{src} {art}({n})")
    if bad:
        print(f"FAIL：seed 取代断言未通过：{bad}", file=sys.stderr)
        sys.exit(1)
    print("seed 取代断言通过：7 个种子碎片已被整法取代")


def main():
    ap = argparse.ArgumentParser(description="整法 txt 批量导入")
    ap.add_argument("--dir", default=CLEAN_DIR)
    ap.add_argument("--only", default="", help="只导入短名匹配的部法（逗号分隔）")
    ap.add_argument("--purge-source", default="", help="导入前按 source 精确清理残留（配合 --dry-run 预览）")
    ap.add_argument("--dry-run", action="store_true", help="只报告不写入")
    args = ap.parse_args()

    if not os.path.isdir(args.dir):
        print(f"目录不存在：{args.dir}（先跑 convert_docx.py + clean_law_text.py）", file=sys.stderr)
        sys.exit(1)

    if args.purge_source:
        purge_source(args.purge_source, args.dry_run)

    files = sorted(f for f in os.listdir(args.dir) if f.endswith(".txt"))
    if args.only:
        wanted = {s.strip() for s in args.only.split(",") if s.strip()}
        files = [f for f in files if short_source(f) in wanted or any(w in f for w in wanted)]
    if not files:
        print("没有匹配的 txt 文件", file=sys.stderr)
        sys.exit(1)

    # 同名多版本检测（防御）
    seen = {}
    for f in files:
        src = short_source(f)
        if src in seen:
            print(f"FAIL：同名多版本 {src}：{seen[src]} 与 {f}——只保留一个", file=sys.stderr)
            sys.exit(1)
        seen[src] = f

    print(f"共 {len(files)} 部，开始{'预检' if args.dry_run else '导入'}（--dir {args.dir}）：")
    total_chunks = total_skipped = 0
    t0 = time.time()
    for f in files:
        st = time.time()
        r = import_one(f, args.dry_run)
        total_chunks += r["chunks"]
        total_skipped += 1 if r["skipped_hash"] else 0
        flag = "（hash 幂等跳过）" if r["skipped_hash"] else ""
        print(f"  {r['source']:<24} {r['chunks']:>5} 片段 {time.time() - st:>5.1f}s{flag}")
    print(f"\n总计：{total_chunks} 片段（跳过 {total_skipped}），耗时 {time.time() - t0:.1f}s")

    # seed 取代断言：5 部种子法全部在本次范围（仅导入模式执行）
    if not args.dry_run:
        imported = {short_source(f) for f in files}
        if {"劳动合同法", "民法典", "消费者权益保护法", "刑法", "道路交通安全法"} <= imported:
            assert_seed_replaced()


if __name__ == "__main__":
    main()
