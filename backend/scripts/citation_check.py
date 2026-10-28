"""机械引用核验：把「答案引用了哪些条」和「检索到了哪些条 / 库里有哪些条」做集合运算。

为什么需要：LLM judge 的 faithfulness 把两类问题混为一谈——
  A. 引用库里根本没有的条文/数字（真幻觉，严重）
  B. 引用库里真实存在、但不在本次检索上下文里的条文（grounding 泄漏，可修）
前者是信任问题，后者是策略问题。本脚本用确定性规则把两者拆开，不依赖任何模型判断。

用法（在仓库根目录）：
  python backend/scripts/citation_check.py --set data/eval_set_gen_v1.json --out docs/benchmark_results/citation_x.json
  python backend/scripts/citation_check.py --set data/eval_set.json --out ... [--llm]

输出指标（分母为答案中的引用数，均为机械计算）：
  citation_precision       引用落在检索上下文内的比例（越高越好）
  grounding_leak_rate      引用真实存在但不在上下文内的比例（策略问题）
  citation_hallucination_rate 引用在库中不存在的比例（幻觉问题）
  citation_recall          上下文条文被答案引用的比例（越高说明上下文被用满）

局限（诚实标注）：只解析《法名》后紧跟的「第X条」；未加书名号的引用（如「刑法第四十六条」）
不会计入，可能低估引用总量。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

import chromadb

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
REPO = os.path.dirname(BACKEND)
sys.path.insert(0, BACKEND)
sys.path.insert(0, HERE)
os.chdir(BACKEND)

from dotenv import load_dotenv  # noqa: E402

# override=True 与 main.py 一致：防 Machine 作用域旧 RERANK_API_KEY 压过 backend/.env（2026-10-26）
load_dotenv(os.path.join(BACKEND, ".env"), override=True)

import _client  # noqa: E402

from rag_chain import format_docs  # noqa: E402
from retrieval import retrieve  # noqa: E402

COLLECTION = "legal_provisions_te4"
CHROMA_DIR = os.path.join(BACKEND, "chroma_db")

_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_UNITS = {"十": 10, "百": 100, "千": 1000}
_NUM = r"[一二三四五六七八九十百千零〇两\d]+"
_ART_RE = re.compile(rf"第({_NUM})条")
# 款项级引用：第X条[第Y款][第Z项]，款/项均可缺省。113 题的「第八十七条第一款第一项」
# 只有解析到款/项才能发现「该款下无项」这类错误；旧的条级正则永远判它正常。
_REF_RE = re.compile(rf"第(?P<art>{_NUM})条(?:第(?P<para>{_NUM})款)?(?:第(?P<item>{_NUM})项)?")
# 书名号内可能再嵌 〈〉（如《最高人民法院关于适用〈中华人民共和国民法典〉有关担保制度的解释》），
# 首版正则会在此处提前截断，把条号算到错误的法名下（实测 131 题出现 1 条假幻觉）。
_BOOK_RE = re.compile(r"《((?:[^《》]|〈[^〉]*〉)+)》")


def cn2num(s: str) -> int | None:
    """中文数字 → 整数（仅用于条号：十/百/千 + 阿拉伯数字混写）。"""
    if s.isdigit():
        return int(s)
    section = num = 0
    for ch in s:
        if ch in _DIGITS:
            num = _DIGITS[ch]
        elif ch in _UNITS:
            section += (num or 1) * _UNITS[ch]
            num = 0
        else:
            return None
    return section + num


def canon_article(article: str) -> str | None:
    """'第三百九十六条' → '第396条'；用于跨中文/阿拉伯写法比对。"""
    m = _ART_RE.search(article or "")
    if not m:
        return None
    n = cn2num(m.group(1))
    return f"第{n}条" if n else None


def canon_source(source: str) -> str:
    """法名归一：《中华人民共和国刑法》→ 刑法；宪法（1982年）→ 宪法。"""
    s = (source or "").strip().strip("《》")
    s = re.sub(r"（[^）]*）|\([^)]*\)", "", s)
    s = s.replace("中华人民共和国", "").replace("最高人民法院关于", "")
    return re.sub(r"\s+", "", s)


def extract_citation_refs(answer: str) -> set[tuple[str, int, int | None, int | None]]:
    """从答案抽 (法名归一, 条号, 款号, 项号)，款/项缺省为 None。

    切段规则与 `extract_citations` 相同：只认本书名号后、下一个书名号之前的引用。
    「第八十七条第二款第一项」→ (source, 87, 2, 1)；
    「第六百五十八条」→ (source, 658, None, None)。
    """
    out: set[tuple[str, int, int | None, int | None]] = set()
    books = list(_BOOK_RE.finditer(answer or ""))
    for i, m in enumerate(books):
        end = books[i + 1].start() if i + 1 < len(books) else len(answer)
        tail = answer[m.end() : end]
        for am in _REF_RE.finditer(tail):
            n = cn2num(am.group("art"))
            if not n:
                continue
            para = cn2num(am.group("para")) if am.group("para") else None
            item = cn2num(am.group("item")) if am.group("item") else None
            out.add((canon_source(m.group(1)), n, para, item))
    return out


def extract_citations(answer: str) -> set[tuple[str, int]]:
    """从答案抽 (法名, 条号整数)，供现有条级指标继续使用（口径不变）。

    只认书名号后、**下一个书名号之前**的条号。首版用「书名号后 60 字窗口」，
    会把下一部法的条号算到前一部名下（如「《民法典》第二百五十八条及《刑法》第三百九十六条」
    被解析成 宪法第396条），已改为按书名号切段。
    """
    return {(s, a) for s, a, _, _ in extract_citation_refs(answer)}


def article_structure(text: str) -> list[dict] | None:
    """把条文原文切成「款 → 项」结构：返回 [{"text": 款文本, "items": [项号...]}, ...]。

    只在能定位到「第X条」开头时返回；章节标题（第X章/第X节）和后续条文会被忽略。
    文本按行切分，以「（一）」开头的行归到上一款，符合中文法条排版习惯。
    """
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    start = next((i for i, ln in enumerate(lines) if re.match(rf"^第{_NUM}条", ln)), None)
    if start is None:
        return None
    paras: list[dict] = []
    for j, ln in enumerate(lines[start:]):
        if j and re.match(rf"^第{_NUM}条", ln):  # 下一篇条文，停止
            break
        if re.match(rf"^第{_NUM}[章节]", ln):  # 章节标题（切片可能带进来），跳过
            continue
        items = [cn2num(x) for x in re.findall(rf"（({_NUM})）", ln)]
        items = [x for x in items if x]
        if ln.startswith("（") and items and paras:
            paras[-1]["items"].extend(items)
        else:
            paras.append({"text": ln, "items": items})
    return paras


def validate_subdivision(text: str, para: int | None, item: int | None) -> bool | None:
    """校验「第Y款第Z项」是否存在于条文原文。无法解析原文 → None。"""
    if para is None and item is None:
        return None
    paras = article_structure(text)
    if not paras:
        return None
    if para is not None and len(paras) < para:
        return False
    target = paras[(para or 1) - 1]
    if item is not None and item not in target["items"]:
        return False
    return True


def load_db_index() -> dict[tuple[str, int], tuple[str, str]]:
    """全库 (法名归一, 条号) → (原始 source, 原始 article)。同条多写法时保留首个。"""
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    col = client.get_collection(COLLECTION)
    got = col.get(include=["metadatas"], limit=col.count())
    idx: dict[tuple[str, int], tuple[str, str]] = {}
    for meta in got["metadatas"]:
        src, art = (meta or {}).get("source") or "", (meta or {}).get("article") or ""
        key_s, key_a = canon_source(src), canon_article(art)
        if not key_s or not key_a:
            continue
        idx.setdefault((key_s, int(key_a[1:-1])), (src, art))
    return idx


def resolve(c: tuple[str, int], db: dict) -> tuple[str, int]:
    """法名别名归一到库内写法：「适用〈民法典〉有关担保制度的解释」→「担保制度解释」。

    只在条号相同、且一方法名包含另一方时才归一，避免把错误条号「修」成正确条号。
    """
    if c in db:
        return c
    src, n = c
    cands = [k for k in db if k[1] == n and (k[0] in src or src in k[0])]
    return max(cands, key=lambda k: len(k[0])) if cands else c


def classify(cited: set[tuple[str, int]], ctx: set[tuple[str, int]], db: dict) -> dict:
    """三分类：在上下文 / 在库不在上下文 / 库中不存在（幻觉）。"""
    fixed = {resolve(c, db) for c in cited}
    in_ctx = {c for c in fixed if c in ctx}
    in_db = {c for c in fixed if c in db}
    leak = in_db - in_ctx
    fabricated = fixed - in_db
    return {"in_ctx": in_ctx, "leak": leak, "fabricated": fabricated}


def _fmt(s: set[tuple[str, int]]) -> list[str]:
    return sorted(f"{s_}第{a}条" for s_, a in s)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 题（调试用）")
    ap.add_argument("--llm", action="store_true", help="额外调用拆分后的 judge（需 _judge.grounding_verdict）")
    args = ap.parse_args()

    cases = json.load(open(args.set, encoding="utf-8"))
    if args.limit:
        cases = cases[: args.limit]
    db = load_db_index()
    token = _client.login()
    judge = _judge_loader() if args.llm else None

    rows = []
    tot_cited = tot_ctx_hit = tot_leak = tot_fab = tot_ctx = 0
    for c in cases:
        q = c["question"]
        docs = retrieve(q, k=6)
        ctx_text = format_docs(docs)
        ctx = {
            (canon_source(d.metadata.get("source", "")), int(canon_article(d.metadata.get("article", ""))[1:-1]))
            for d in docs
            if canon_article(d.metadata.get("article", ""))
        }
        ans = _client.chat(token, q)
        cited = extract_citations(ans)
        cls = classify(cited, ctx, db)
        row = {
            "id": c.get("id"),
            "question": q,
            "answer": ans,
            "ctx": _fmt(ctx),
            "cited": _fmt(cited),
            "in_ctx": _fmt(cls["in_ctx"]),
            "leak": _fmt(cls["leak"]),
            "fabricated": _fmt(cls["fabricated"]),
        }
        if judge is not None:
            row["grounding"] = judge(ans, ctx_text, cls)
        if cited:
            tot_cited += len(cited)
            tot_ctx_hit += len(cls["in_ctx"])
            tot_leak += len(cls["leak"])
            tot_fab += len(cls["fabricated"])
        tot_ctx += len(ctx)
        rows.append(row)
        time.sleep(1.2)
        print(
            f"[{row['id']}] cited={len(cited)} in_ctx={len(cls['in_ctx'])} leak={len(cls['leak'])} fab={len(cls['fabricated'])}"
        )

    agg = {
        "n": len(rows),
        "avg_cited": round(tot_cited / max(1, len(rows)), 2),
        "citation_precision": round(tot_ctx_hit / tot_cited, 4) if tot_cited else None,
        "grounding_leak_rate": round(tot_leak / tot_cited, 4) if tot_cited else None,
        "citation_hallucination_rate": round(tot_fab / tot_cited, 4) if tot_cited else None,
        "citation_recall": round(tot_ctx_hit / tot_ctx, 4) if tot_ctx else None,
        "totals": {"cited": tot_cited, "in_ctx": tot_ctx_hit, "leak": tot_leak, "fabricated": tot_fab, "ctx": tot_ctx},
    }
    payload = {
        "ts": time.strftime("%Y%m%d-%H%M%S"),
        "dataset": os.path.basename(args.set),
        "note": "机械口径：只解析《法名》后的第X条；未加书名号的引用不计入",
        "summary": agg,
        "rows": rows,
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("\n" + json.dumps(agg, ensure_ascii=False))
    print(f"落盘：{args.out}")


def _judge_loader():
    """惰性加载：没有 --llm 时不引入 judge 依赖。"""
    import _judge

    llm = _judge.pick_text_llm()

    def run(answer: str, ctx_text: str, cls: dict) -> dict:
        return _judge.grounding_verdict(llm, answer, ctx_text, cls)

    return run


if __name__ == "__main__":
    main()
