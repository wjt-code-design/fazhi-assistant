"""多模态：图片校验 / 存盘 / 缩略图 / 视觉 content 构造 / 图像→文本描述桥接。

说明：单一全模态模型负责"看图产描述/要点"（检索桥接）与"带图作答"；
base64 不写库，只存盘；过小图片会被部分平台拒绝，故校验尺寸下限。
"""

import base64
import io
import os
import re
import uuid

from langchain_core.messages import HumanMessage
from PIL import Image

BASE = os.path.dirname(os.path.abspath(__file__))
MEDIA_DIR = os.path.join(BASE, "media")
os.makedirs(MEDIA_DIR, exist_ok=True)

_DATA_URL_RE = re.compile(r"^data:(image/[a-zA-Z0-9.+-]+);base64,([A-Za-z0-9+/=\s]+)$", re.S)

from settings import settings

IMAGE_LIMITS = {
    "max_image_mb": settings.image_max_mb,
    "max_px": settings.image_max_px,
    "min_px": settings.image_min_px,
    "formats": ["image/jpeg", "image/png"],
}


def _abs(rel: str) -> str:
    return os.path.join(BASE, *rel.split("/"))


def _decode_data_url(data_url: str) -> tuple[str, bytes]:
    m = _DATA_URL_RE.match(data_url.strip())
    if not m:
        raise ValueError("图片格式不支持：需 data URL（data:image/...;base64,...）")
    mime = m.group(1).lower()
    try:
        raw = base64.b64decode(m.group(2), validate=True)
    except Exception as e:
        raise ValueError(f"图片 base64 解码失败：{e}") from e
    if not raw:
        raise ValueError("图片内容为空")
    return mime, raw


def validate_image(image: str | None) -> str | None:
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
        raise ValueError(f"图片无法解析（可能损坏）：{e}") from e
    min_px = cfg.get("min_px", 10)
    max_px = cfg.get("max_px", 6000)
    if w < min_px or h < min_px:
        raise ValueError(f"图片太小（边长需 ≥ {min_px}px，否则部分平台会拒绝）")
    if w > max_px or h > max_px:
        raise ValueError(f"图片过大（边长需 ≤ {max_px}px）")
    return image


def persist_image(data_url: str) -> tuple[str, str]:
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
    """视觉模型产描述/要点，作为检索桥接 + 上下文。失败返回空串（降级，不阻断）。

    2026-08-06 图片识别合同（二期）：合同/文书等文字图片 → 逐字转写全文
    （供合同评估确定性骨架使用，150 字摘要不够切条款）；普通图片 → 150 字客观描述。
    由模型按内容自我路由，单次调用。
    """
    prompt = (
        "你是法律文档录入助手。若图片中是合同、协议、判决书等含条文条款的文字图片，"
        "请逐字转写其中全部文字，保留条款编号、甲方乙方、金额等细节，尽量完整不要省略，"
        "以便后续逐条法律风险评估；否则请用不超过150字客观描述图片内容，便于检索相关法律条文。"
        "注意：只转写图片中原本就有的文字，不要添加任何评论、解释或风险提示。"
    )
    if user_text and user_text.strip():
        prompt += f" 用户附言：{user_text.strip()}"
    try:
        resp = vision_llm.invoke([HumanMessage(content=build_vision_content(prompt, data_url))])
        return (resp.content or "").strip()
    except Exception:
        return ""
