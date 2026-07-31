"""多模态：图片校验 / 存盘 / 缩略图 / 视觉 content 构造 / 图像→文本描述桥接。

说明：单一全模态模型负责"看图产描述/要点"（检索桥接）与"带图作答"；
base64 不写库，只存盘；过小图片会被部分平台拒绝，故校验尺寸下限。
"""
import base64
import io
import os
import re
import uuid
from typing import Optional, Tuple

from PIL import Image
from langchain_core.messages import HumanMessage

BASE = os.path.dirname(os.path.abspath(__file__))
MEDIA_DIR = os.path.join(BASE, "media")
os.makedirs(MEDIA_DIR, exist_ok=True)

_DATA_URL_RE = re.compile(r"^data:(image/[a-zA-Z0-9.+-]+);base64,([A-Za-z0-9+/=\s]+)$", re.S)

IMAGE_LIMITS = {
    "max_image_mb": 5,
    "max_px": 6000,
    "min_px": 10,
    "formats": ["image/jpeg", "image/png"],
}


def _abs(rel: str) -> str:
    return os.path.join(BASE, *rel.split("/"))


def _decode_data_url(data_url: str) -> Tuple[str, bytes]:
    m = _DATA_URL_RE.match(data_url.strip())
    if not m:
        raise ValueError("图片格式不支持：需 data URL（data:image/...;base64,...）")
    mime = m.group(1).lower()
    try:
        raw = base64.b64decode(m.group(2), validate=True)
    except Exception as e:
        raise ValueError(f"图片 base64 解码失败：{e}")
    if not raw:
        raise ValueError("图片内容为空")
    return mime, raw


def validate_image(image: Optional[str]) -> Optional[str]:
    """校验格式/大小/尺寸（用 IMAGE_LIMITS）；通过返回原 data URL，无图返回 None。"""
    if not image:
        return None
    cfg = IMAGE_LIMITS
    mime, raw = _decode_data_url(image)
    formats = cfg["formats"]
    if mime not in formats:
        raise ValueError(f"图片类型 {mime} 不支持，请用 JPEG/PNG")
    max_mb = cfg["max_image_mb"]
    if len(raw) > max_mb * 1024 * 1024:
        raise ValueError(f"图片过大（>{max_mb}MB）")
    try:
        with Image.open(io.BytesIO(raw)) as im:
            im.verify()
        with Image.open(io.BytesIO(raw)) as im:
            w, h = im.size
    except Exception as e:
        raise ValueError(f"图片无法解析（可能损坏）：{e}")
    min_px = cfg.get("min_px", 10)
    max_px = cfg.get("max_px", 6000)
    if w < min_px or h < min_px:
        raise ValueError(f"图片太小（边长需 ≥ {min_px}px，否则部分平台会拒绝）")
    if w > max_px or h > max_px:
        raise ValueError(f"图片过大（边长需 ≤ {max_px}px）")
    return image


def persist_image(data_url: str) -> Tuple[str, str]:
    """存原图 + 生成缩略图，返回 (原图相对路径, 缩略图相对路径)，相对 backend/，用 '/' 分隔。"""
    mime, raw = _decode_data_url(data_url)
    ext = "jpg" if "jpeg" in mime else "png"
    uid = uuid.uuid4().hex
    rel = f"media/{uid}.{ext}"
    with open(_abs(rel), "wb") as f:
        f.write(raw)
    with Image.open(io.BytesIO(raw)) as im:
        im = im.convert("RGB")
        im.thumbnail((240, 240))
        tbuf = io.BytesIO()
        im.save(tbuf, format="JPEG", quality=80)
        thumb_rel = f"media/{uid}_thumb.jpg"
        with open(_abs(thumb_rel), "wb") as f:
            f.write(tbuf.getvalue())
    return rel, thumb_rel


def build_vision_content(text: str, data_url: str) -> list:
    """OpenAI 兼容的视觉 content 数组。"""
    parts = []
    if text and text.strip():
        parts.append({"type": "text", "text": text})
    parts.append({"type": "image_url", "image_url": {"url": data_url}})
    return parts


def describe_image(vision_llm, data_url: str, user_text: str = "") -> str:
    """视觉模型产描述/要点，作为检索桥接 + 上下文。失败返回空串（降级，不阻断）。"""
    prompt = "请用不超过150字，客观描述图片中的文字与关键内容，便于检索相关法律条文。"
    if user_text and user_text.strip():
        prompt += f" 用户附言：{user_text.strip()}"
    try:
        resp = vision_llm.invoke([HumanMessage(content=build_vision_content(prompt, data_url))])
        return (resp.content or "").strip()
    except Exception:
        return ""
