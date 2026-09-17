"""docx 提取与直传上传测试（Step 3）。

用 zipfile 构造最小 docx fixture（word/document.xml），覆盖：
- 段落/表格提取与顺序；w:del 删除文本跳过；修订/域代码 WARN。
- 非法输入（坏 zip / 缺 document.xml）抛 ValueError。
- validate_upload 白名单 + 魔数；parse_uploaded .docx 往返。
"""

import io
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 先加载 .env 再 import knowledge_service（→settings 单例），避免空 LLM 配置污染后续测试
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import pytest

import knowledge_service as ks
from docx_utils import extract

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _doc_xml(body_inner: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{W}"><w:body>{body_inner}</w:body></w:document>'
    ).encode()


def _para(text: str) -> str:
    return f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"


def _table(cells_per_row):
    rows = []
    for row in cells_per_row:
        tcs = "".join(f"<w:tc><w:p><w:r><w:t>{c}</w:t></w:r></w:p></w:tc>" for c in row)
        rows.append(f"<w:tr>{tcs}</w:tr>")
    return f"<w:tbl>{''.join(rows)}</w:tbl>"


def build_docx(body_inner: str, extra_files=None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("word/document.xml", _doc_xml(body_inner))
        for name, data in (extra_files or {}).items():
            zf.writestr(name, data)
    return buf.getvalue()


# ---------------- docx_utils.extract ----------------
def test_extract_paragraphs_order():
    data = build_docx(_para("第一条 甲") + _para("第二条 乙"))
    text, warns = extract(data)
    assert "第一条 甲" in text and "第二条 乙" in text
    assert text.index("第一条") < text.index("第二条")
    assert warns == []


def test_extract_table_pipe_separated():
    data = build_docx(_para("附表") + _table([["税率", "级数"], ["3%", "一"]]))
    text, _ = extract(data)
    assert "税率 | 级数" in text
    assert "3% | 一" in text


def test_extract_skips_wdel():
    body = (
        _para("保留文字")
        + "<w:p><w:r><w:t>前</w:t></w:r><w:del><w:r><w:t>删除文本</w:t></w:r></w:del><w:r><w:t>后</w:t></w:r></w:p>"
    )
    data = build_docx(body)
    text, _ = extract(data)
    assert "删除文本" not in text
    assert "保留文字" in text and "前" in text and "后" in text


def test_extract_warns_on_revision_insert():
    body = _para("正文") + "<w:p><w:ins><w:r><w:t>插入</w:t></w:r></w:ins></w:p>"
    _, warns = extract(build_docx(body))
    assert any("w:ins" in w for w in warns)


def test_extract_warns_on_field_code():
    body = _para("正文") + "<w:p><w:fldSimple><w:r><w:t>1</w:t></w:r></w:fldSimple></w:p>"
    _, warns = extract(build_docx(body))
    assert any("fldSimple" in w for w in warns)


def test_extract_bad_zip_raises():
    with pytest.raises(ValueError):
        extract(b"not a zip at all")


def test_extract_missing_document_xml_raises():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("other.xml", "<x/>")
    with pytest.raises(ValueError):
        extract(buf.getvalue())


def test_extract_empty_body_raises():
    with pytest.raises(ValueError):
        extract(build_docx(""))  # 无任何段落 → 空文本


# ---------------- validate_upload / parse_uploaded ----------------
def test_validate_accepts_valid_docx():
    data = build_docx(_para("第一条 内容"))
    assert ks.validate_upload("民法典.docx", data) == ".docx"


def test_validate_rejects_bad_magic():
    with pytest.raises(ValueError, match="zip 容器"):
        ks.validate_upload("fake.docx", b"%PDF-1.4 not a docx")


def test_validate_rejects_zip_without_document_xml():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.txt", "hi")
    with pytest.raises(ValueError, match="word/document.xml"):
        ks.validate_upload("壳.docx", buf.getvalue())


def test_parse_uploaded_docx_roundtrip():
    data = build_docx(_para("第一条 劳动者享有权利") + _para("第二条 适用本法"))
    text = ks.parse_uploaded("劳动法.docx", data)
    assert "第一条 劳动者享有权利" in text
    assert "第二条 适用本法" in text


def test_allowed_ext_includes_docx():
    assert ".docx" in ks._ALLOWED_EXT
