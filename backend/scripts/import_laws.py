"""批量导入条文（阶段5）：读 data/laws_extra.json，校验后幂等入库。

- 模板见 data/laws_extra.example.json（复制为 data/laws_extra.json 后填写）。
- 逐条校验（必填字段 / 日期格式 / status 白名单），报全量错误，不 fail-fast。
- 幂等：按 (title, article_number) 删旧再写；与 origin=seed 种子重叠时警告并跳过
  （那种内容应改 data/laws.json 后运行 knowledge_base.py 重建）。
- origin 固定为 "import"（区别于 seed/manual/upload，管理端可显示第三态徽章）。

用法：cd backend && python scripts/import_laws.py [--input 路径] [--dry-run]
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
sys.path.insert(0, BACKEND)
os.chdir(BACKEND)

from rag_chain import vectorstore  # noqa: E402
import knowledge_service as ks  # noqa: E402
from retrieval_core import STATUS_WHITELIST  # noqa: E402

DEFAULT_INPUT = os.path.join(BACKEND, "..", "data", "laws_extra.json")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_REQUIRED = ("title", "article_number", "content")


def validate_entry(e: dict) -> list:
    errors = []
    for k in _REQUIRED:
        if not (e.get(k) or "").strip():
            errors.append(f"缺少必填字段 {k}")
    status = (e.get("status") or "现行").strip()
    if status not in STATUS_WHITELIST:
        errors.append(f"status 必须是 {'/'.join(STATUS_WHITELIST)}，当前为 {status!r}")
    for k in ("effective_from", "effective_to"):
        v = (e.get(k) or "").strip()
        if v and not _DATE_RE.match(v):
            errors.append(f"{k} 格式必须为 YYYY-MM-DD（当前 {v!r}）")
    return errors


def _load_entries(path: str) -> list:
    data = json.load(open(path, encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("entries"), list):
        return data["entries"]
    raise ValueError("文件格式错误：应为条文数组，或含 entries 数组的对象（见模板）")


def _seed_conflict(title: str, article: str) -> bool:
    ids = vectorstore._collection.get(
        where={"$and": [{"source": title}, {"article": article}]}, include=["metadatas"]
    )["ids"]
    if not ids:
        return False
    # 存在 seed 即视为冲突（重建会覆盖 import 版本）
    metas = vectorstore._collection.get(ids=ids[:1], include=["metadatas"])["metadatas"]
    return bool(metas) and metas[0].get("origin") == "seed"


def main():
    ap = argparse.ArgumentParser(description="批量导入法律条文（幂等）")
    ap.add_argument("--input", default=DEFAULT_INPUT, help="条文 JSON 路径（默认 data/laws_extra.json）")
    ap.add_argument("--dry-run", action="store_true", help="只出报告，不写入")
    args = ap.parse_args()

    if not os.path.isfile(args.input):
        print(f"未找到导入文件 {args.input}\n请复制 data/laws_extra.example.json 为 data/laws_extra.json 后填写。")
        sys.exit(1)

    entries = _load_entries(args.input)
    all_errors = [(e, validate_entry(e)) for e in entries]
    bad = [(e, errs) for e, errs in all_errors if errs]
    if bad:
        print(f"共 {len(bad)} 条校验失败（不写入任何内容）：")
        for e, errs in bad:
            print(f"  [{e.get('title', '?')} {e.get('article_number', '?')}] {'; '.join(errs)}")
        sys.exit(1)

    print(f"共 {len(entries)} 条，开始{'预检' if args.dry_run else '导入'}：")
    n_del = n_add = n_skip = 0
    for e in entries:
        title, article = e["title"].strip(), e["article_number"].strip()
        if _seed_conflict(title, article):
            print(f"  跳过（与种子冲突，请改 laws.json 后重建）：{title} {article}")
            n_skip += 1
            continue
        stale = vectorstore._collection.get(
            where={"$and": [{"source": title}, {"article": article}]}
        )["ids"]
        n_del += len(stale)
        n_add += 1
        if args.dry_run:
            print(f"  将替换 {len(stale)} 旧片段 + 新增：{title} {article}")
            continue
        # 旧片段删除由 add_text(origin="import") 内部按 (source, article) 幂等处理
        extra = {
            "category": e.get("category", ""),
            "effective_from": (e.get("effective_from") or "").strip(),
            "effective_to": (e.get("effective_to") or "").strip(),
            "status": (e.get("status") or "现行").strip(),
        }
        n = ks.add_text(e["content"], source=title, article=article, origin="import", extra_meta=extra)
        print(f"  已导入：{title} {article}（{n} 片段）")

    if args.dry_run:
        print(f"\n预检完成：将删除 {n_del} 旧片段，新增 {n_add} 条，跳过 {n_skip} 条。确认后去掉 --dry-run 实跑。")
    else:
        print(f"\n导入完成：替换 {n_del} 旧片段，新增 {n_add} 条，跳过 {n_skip} 条。")


if __name__ == "__main__":
    main()
