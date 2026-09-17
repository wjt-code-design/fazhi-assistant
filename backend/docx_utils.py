"""docx 文本提取（零依赖）：zipfile + ElementTree 解析 word/document.xml。

- 段落 w:p 与表格 w:tbl（逐行逐格，| 分隔）按文档顺序提取，保留段落结构。
- **修订处理**：跳过 w:del 子树（删除文本不提取）；检测 w:ins 节点 → WARN
  （文档以"原始"视图保存时插入文本缺失，需人工确认视图）。
- **域代码处理**：跳过 w:instrText（指令文本如 TOC/PAGEREF 残留）；检测 w:fldSimple → WARN。
- **异常即 FAIL**：坏 XML / 声明 UTF-8 实为乱码 → 抛 ValueError（调用方标 FAIL），
  不依赖 U+FFFD 文本特征（后者仅作二级检查）。
- 页眉/页脚/批注/嵌入对象不提取（法律文本正文在 document.xml）。
"""

import zipfile
from xml.etree import ElementTree as ET

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _tag(name: str) -> str:
    return _W + name


def _para_text(p: ET.Element) -> str:
    """段落文本：w:t 拼接；w:tab→空格；w:br→换行（w:del 已在树级剔除）。"""
    parts: list[str] = []
    for node in p.iter():
        if node.tag == _tag("t"):
            parts.append(node.text or "")
        elif node.tag == _tag("tab"):
            parts.append(" ")
        elif node.tag == _tag("br"):
            parts.append("\n")
    return "".join(parts)


def _table_text(tbl: ET.Element) -> str:
    """表格文本：每行单元格用 | 分隔，行之间换行（表格前空行由调用方补）。"""
    rows: list[str] = []
    for tr in tbl.iter(_tag("tr")):
        cells: list[str] = []
        for tc in tr.iter(_tag("tc")):
            cells.append("".join((t.text or "") for t in tc.iter(_tag("t"))))
        rows.append(" | ".join(cells))
    return "\n".join(rows)


def extract(data: bytes, filename: str = "") -> tuple[str, list[str]]:
    """从 docx 字节提取正文。返回 (text, warnings)；非法/损坏抛 ValueError。"""
    try:
        zf = zipfile.ZipFile(__import__("io").BytesIO(data))
    except zipfile.BadZipFile as e:
        raise ValueError(f"不是有效的 docx（zip 损坏）：{e}") from e
    if "word/document.xml" not in zf.namelist():
        raise ValueError("不是有效的 docx（缺少 word/document.xml）")
    raw = zf.read("word/document.xml")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        raise ValueError(f"document.xml 解析失败（可能编码损坏）：{e}") from e

    warnings: list[str] = []
    # 修订/域代码检测（先于剔除，报告后处理）
    if root.find(f".//{_tag('ins')}") is not None:
        warnings.append("文档含修订插入标记(w:ins)——若以原始视图保存，插入文字可能缺失，请确认")
    if root.find(f".//{_tag('fldSimple')}") is not None:
        warnings.append("文档含域代码(w:fldSimple)——目录/页码/交叉引用可能残留，请检查")

    # 剔除 w:del 子树与 instrText 指令文本（原地修改内存树）
    for d in list(root.iter(_tag("del"))):
        d.clear()  # 移除子树内容
    for it in list(root.iter(_tag("instrText"))):
        it.text = ""

    body = root.find(_tag("body"))
    if body is None:
        raise ValueError("document.xml 缺少 body")

    blocks: list[str] = []
    for child in body:
        if child.tag == _tag("p"):
            t = _para_text(child).strip("\n")
            if t.strip():
                blocks.append(t.strip())
        elif child.tag == _tag("tbl"):
            t = _table_text(child)
            if t.strip():
                blocks.append(t.strip())
    text = "\n".join(blocks)
    if not text.strip():
        raise ValueError("提取文本为空（可能是扫描件或无文字内容）")
    return text, warnings
