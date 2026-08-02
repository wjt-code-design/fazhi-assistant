"""结构化切分（阶段6）：法律文档按条号边界切分，章节前缀注入，目录页跳过。

纯函数模块：只依赖 stdlib + langchain_text_splitters（不加载模型/向量库），可单测。

设计要点：
- 条号正则**行首锚定 + 条后边界断言**，防正文误伤（「第十九条的…」不出现在行首）。
- 条号变体：中文数字/〇/阿拉伯/全角、「第X条之一」。
- 章节（第X章/编/节/部分、总则/附则）作为前缀注入每个 chunk，**不是** chunk 边界。
- 目录页跳过（TOC 是整篇切分最大误伤源）。
- 超长条句切（。；\\n 分隔，500/60），子 chunk 共用同一条号 metadata。
- 短条**不做跨条合并**（跨条会破坏 metadata.article 单值 → recall_at_k 精确匹配失效）。
- 降级链：全文无条号 → 回退段落优先 600/80 切分（与旧 upload 行为一致）。
"""

import re
from dataclasses import dataclass, field
from typing import TypedDict

from langchain_text_splitters import RecursiveCharacterTextSplitter


class _ArticleBuf(TypedDict):
    no: str
    chapter: str
    lines: list[str]


ARTICLE_RE = re.compile(
    r"^第([零〇○一二三四五六七八九十百千万0-9０-９]+)条"
    r"(?:之[一二三四五六七八九十百千万0-9０-９]+)?"
    r"(?=[\s，。；：、）】]|$)"
)
CHAPTER_RE = re.compile(r"^第([零〇○一二三四五六七八九十百千万0-9０-９]+)[编篇章部分](?=[\s　，。]|$)")
FREE_CHAPTER_RE = re.compile(r"^(总则|附则|序言|前言)(?=[\s　，。]|$)")
TOC_RE = re.compile(r"^目\s*录$")

CHUNK_MAX = 800  # 条文超过此长度触发句切
SENT_CHUNK = 500  # 句切 chunk 大小
SENT_OVERLAP = 60
MIN_ARTICLE = 10  # 短于此的「条文」视为 TOC 残留/误识别，丢弃
TOC_MAX_SKIP = 500  # 目录跳过安全上限（防无退出条件的文档被整篇跳过；重复标题退出为主机制）

_PARA_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=600, chunk_overlap=80, separators=["\n\n", "\n", "。", "；", ". ", " ", ""]
)
_SENT_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=SENT_CHUNK, chunk_overlap=SENT_OVERLAP, separators=["。", "；", "\n", " ", ""]
)


@dataclass
class Chunk:
    page_content: str
    meta: dict = field(default_factory=dict)


def _strip_toc(lines: list[str]) -> list[str]:
    """剔除目录页区域：遇「目 录」行进入 TOC 态，跳过条目行。

    退出条件（按可靠性排序）：
    1. **章节标题重复出现** = 正文开始（TOC 里的「第一章 总则」在正文必然再次出现，
       这是最可靠的结构信号——比"长内容行"启发式稳，短条文（如第一条仅 50 字）不会被吞）。
    2. 「正文」显式标记。
    3. 长内容行（>60 字且含句号）——兜底（目录行通常很短）。
    4. TOC_MAX_SKIP 安全上限（防止无退出条件的文档被整篇跳过）。
    """
    out: list[str] = []
    i, n = 0, len(lines)
    in_toc = False
    skipped = 0
    seen_headings: set[str] = set()
    while i < n:
        line = lines[i]
        s = line.strip()
        if not in_toc:
            if TOC_RE.match(s):
                in_toc = True
                seen_headings.clear()
                i += 1
                continue
            out.append(line)
            i += 1
            continue
        skipped += 1
        if skipped > TOC_MAX_SKIP:
            in_toc = False
            out.append(line)
            i += 1
            continue
        if s == "正文":
            in_toc = False
            out.append(line)
            i += 1
            continue
        if CHAPTER_RE.match(s) or FREE_CHAPTER_RE.match(s):
            if s in seen_headings:
                in_toc = False  # 章节标题重复出现 = 正文开始
                out.append(line)
                i += 1
                continue
            seen_headings.add(s)
            # 仍是首次出现的目录条目；向后看长内容行（无重复标题文档的兜底）
            j = i + 1
            while j < n and not lines[j].strip():
                j += 1
            if j < n and len(lines[j].strip()) > 60 and "。" in lines[j]:
                in_toc = False
                out.append(line)
                i += 1
                continue
            i += 1
            continue
        if ARTICLE_RE.match(s):
            if len(s) > 60 and "。" in s:
                in_toc = False  # 目录里出现完整条文 = 正文开始
                out.append(line)
                i += 1
                continue
            i += 1  # 目录条目（短行）：跳过
            continue
        # 其他行（目录标题/页码/说明）：长内容行退出，短行跳过
        if len(s) > 60 and "。" in s:
            in_toc = False
            out.append(line)
            i += 1
            continue
        i += 1
    return out


def split_law_document(text: str) -> list[Chunk]:
    """整篇文档结构化切分。未识别到任何条号时回退段落切分（meta 无 article）。"""
    if not (text or "").strip():
        return []
    lines = _strip_toc(text.splitlines())

    articles: list[_ArticleBuf] = []
    cur: _ArticleBuf | None = None
    chapter = ""
    for raw in lines:
        line = raw.strip()
        if not line:
            if cur is not None:
                cur["lines"].append("")
            continue
        if CHAPTER_RE.match(line) or FREE_CHAPTER_RE.match(line):
            if cur is not None:  # 章节边界必须 flush 在途条文，否则章节前的条文会丢
                articles.append(cur)
                cur = None
            chapter = line
            continue
        m = ARTICLE_RE.match(line)
        if m:
            if cur is not None:
                articles.append(cur)
            cur = {"no": m.group(0), "chapter": chapter, "lines": [line]}
            continue
        if cur is not None:
            cur["lines"].append(line)
    if cur is not None:
        articles.append(cur)

    if not articles:
        return _fallback_paragraph(text)

    out: list[Chunk] = []
    for a in articles:
        body = "\n".join(a["lines"]).strip()
        if len(body) < MIN_ARTICLE:
            continue  # TOC 残留/误识别（如「第一条 立法目的」）
        out.extend(split_article_text(body, article=a["no"], chapter=a["chapter"]))
    return out if out else _fallback_paragraph(text)


def split_article_text(content: str, article: str = "", chapter: str = "") -> list[Chunk]:
    """单条条文切分：章节前缀 + 条号头行保留（BM25 条号查询的精确匹配载荷）；超长条句切。"""
    body = (content or "").strip()
    if not body:
        return []
    prefix = (chapter + "\n") if chapter else ""
    if len(body) <= CHUNK_MAX:
        return [Chunk(prefix + body, {"article": article, "chapter": chapter})]
    out = []
    for p in _SENT_SPLITTER.split_text(body):
        if p.strip():
            out.append(Chunk(prefix + p.strip(), {"article": article, "chapter": chapter}))
    return out


def _fallback_paragraph(text: str) -> list[Chunk]:
    """无条号边界时回退：段落优先切分（与旧 upload 行为一致）。"""
    return [Chunk(p, {}) for p in _PARA_SPLITTER.split_text(text) if p.strip()]
