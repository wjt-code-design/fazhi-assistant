"""宪法 2018 修正版替换（默认 dry-run）。

- 解析 constitution_2018.txt → 条号 + 章节 + 正文；
- 与库内 `宪法（1982年）` 的 138 条逐条对比：相同 / 变更 / 新增 / 缺失；
- `--apply` 才真正删除旧条并写入新条（metadata 带 2018-03-11 生效日）。

用法：cd backend && python scripts/fix_constitution.py [--apply]
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from langchain_core.documents import Document  # noqa: E402

from rag_chain import vectorstore  # noqa: E402
from retrieval_core import STATUS_WHITELIST  # noqa: E402

TXT = HERE.parent.parent / "dispatch-output/kb-constitution-fix-20261028/constitution_2018.txt"
META = json.loads(
    (HERE.parent.parent / "dispatch-output/kb-constitution-fix-20261028/constitution_meta.json").read_text(
        encoding="utf-8"
    )
)
OLD_SOURCE = META["old_source"]
NEW_SOURCE = META["source"]
EFFECTIVE_FROM = META["effective_from"]
# S0-b：`现行` 只能是显式签出的断言，从数据文件读取并过白名单，不在代码里写死
KB_STATUS = META["kb_status"]
assert KB_STATUS in STATUS_WHITELIST, f"kb_status 不在白名单：{KB_STATUS}"

_ARTICLE_RE = re.compile(r"^\s*第([一二三四五六七八九十百零〇]+)条\s*(.*)$")
_CHAPTER_RE = re.compile(r"^\s*第[一二三四五六七八九十]+章\s*\S+")
_SECTION_RE = re.compile(r"^\s*第[一二三四五六七八九十]+节\s*\S+")


def parse_articles(text: str) -> list[dict]:
    articles: list[dict] = []
    chapter = ""
    section = ""
    current: dict | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if _CHAPTER_RE.match(line):
            chapter = line.replace(" ", "　", 1) if " " in line else line
            section = ""
            continue
        if _SECTION_RE.match(line):
            section = line
            continue
        match = _ARTICLE_RE.match(line)
        if match:
            number = f"第{match.group(1)}条"
            current = {
                "article": number,
                "chapter": chapter,
                "section": section,
                "lines": [match.group(2).strip()],
            }
            articles.append(current)
        elif current is not None:
            current["lines"].append(line.replace("　　", "").strip())
    for item in articles:
        item["content"] = " ".join(part for part in item["lines"] if part).strip()
    return articles


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    articles = parse_articles(TXT.read_text(encoding="utf-8"))
    print(f"解析到 {len(articles)} 条")

    collection = vectorstore._collection
    existing = collection.get(where={"source": OLD_SOURCE}, include=["metadatas", "documents"])
    old_map: dict[str, list[tuple[str, str, dict]]] = {}
    for doc_id, meta, content in zip(existing["ids"], existing["metadatas"], existing["documents"], strict=False):
        old_map.setdefault(meta.get("article", ""), []).append((doc_id, content, meta))
    print(f"库内旧条：{sum(len(v) for v in old_map.values())} 条（{OLD_SOURCE}）")

    same, changed, added, removed = [], [], [], []
    for item in articles:
        old = old_map.get(item["article"])
        if not old:
            added.append(item["article"])
            continue
        old_text = normalize(old[0][1])
        new_text = normalize(f"{item['chapter']} {item['article']}　{item['content']}")
        (same if old_text == new_text else changed).append(item["article"])
    for article in old_map:
        if article not in {item["article"] for item in articles}:
            removed.append(article)

    print(f"相同 {len(same)} / 变更 {len(changed)} / 新增 {len(added)} / 库内独有 {len(removed)}")
    print("变更条号（前 30）：", changed[:30])
    print("新增条号：", added)
    print("库内独有：", removed)

    if not args.apply:
        print("\n[dry-run] 未写入。加 --apply 执行替换。")
        return

    old_ids = [doc_id for entries in old_map.values() for doc_id, _, _ in entries]
    if old_ids:
        collection.delete(ids=old_ids)
        print(f"已删除旧条 {len(old_ids)} 条")
    docs = [
        Document(
            page_content=f"{item['chapter']} {item['article']}　{item['content']}",
            metadata={
                "source": NEW_SOURCE,
                "article": item["article"],
                "chapter": item["chapter"],
                "section": item["section"],
                "effective_from": EFFECTIVE_FROM,
                "effective_to": "",
                "status": KB_STATUS,
                "origin": "import",
            },
        )
        for item in articles
    ]
    vectorstore.add_documents(docs)
    print(f"已写入新条 {len(docs)} 条（source={NEW_SOURCE}, effective_from={EFFECTIVE_FROM}）")


if __name__ == "__main__":
    main()
