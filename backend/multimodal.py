"""多模态：图片校验 / 存盘 / 缩略图 / 视觉 content 构造 / 图像→文本描述桥接。

说明：单一全模态模型负责"看图产描述/要点"（检索桥接）与"带图作答"；
base64 不写库，只存盘；过小图片会被部分平台拒绝，故校验尺寸下限。
"""

import base64
import io
import os
import re
import uuid
from collections.abc import Callable
from typing import Any

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


AUDIO_PROMPT = (
    "你是一个中文语音转文字引擎。请把音频中的话完整、准确转写为带标点的中文文本，"
    "保留数字与专有名词；只输出转写结果，不要任何解释、不要重复问题。"
)

# livetranslate 语音模型接受的音频格式（2026-08-06 门禁：webm/opus 不收）
AUDIO_EXTS = ("wav", "mp3", "m4a", "flac", "ogg")

# 票 W07 §1 ④：语音的**传输词表**。值的闭集由 llm_registry 的 cfg 白名单定义（§1 ②），
# 这里那三个字面量与它是两处——由 tests/test_multimodal_transport_impl.py::
# test_transport_names_are_the_same_words_on_both_sides 钉成同一套词（先例：conftest 里
# chroma 集合名那两处字面量的处理）。故意不在 multimodal 里 import llm_registry：
# 那只模块 import 期就构造 registry（要求凭据），会把「只想用图片工具」的调用点拖进配置依赖。
CHAT_TRANSPORT = "chat"
MULTIPART_TRANSPORT = "audio_transcriptions"
NO_TRANSPORT = "none"
VOICE_TRANSPORTS: tuple[str, ...] = (CHAT_TRANSPORT, MULTIPART_TRANSPORT, NO_TRANSPORT)

# multipart `file` 部件的 MIME；键与 AUDIO_EXTS 同一批格式（AUDIO_EXTS 本体不许动——跨面 MIME 判据钉着）
_AUDIO_MIME = {
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
    "m4a": "audio/mp4",
    "flac": "audio/flac",
    "ogg": "audio/ogg",
}


def build_audio_content(text: str, b64: str, fmt: str) -> list:
    """OpenAI 兼容的语音 content 数组。

    data 必须带 `data:;base64,` 空 MIME 前缀（DashScope Qwen 系实测，裸 base64 返回空）。
    """
    return [
        {"type": "input_audio", "input_audio": {"data": f"data:;base64,{b64}", "format": fmt}},
        {"type": "text", "text": text},
    ]


def _transcribe_chat(voice_llm, b64: str, fmt: str, *, client: Any | None = None) -> str:
    """chat 腿：`chat/completions` ＋ input_audio 部件（现役 Qwen livetranslate 那条，逐字保持）。"""
    resp = voice_llm.invoke([HumanMessage(content=build_audio_content(AUDIO_PROMPT, b64, fmt))])
    return (resp.content or "").strip()


def _transcribe_multipart(voice_llm, b64: str, fmt: str, *, client: Any | None = None) -> str:
    """audio_transcriptions 腿：multipart `POST {base}/audio/transcriptions`（`file`＋`model`）。

    不经过 ChatOpenAI 的聊天抽象，但**复用 entry 自己那只根客户端**（`root_client`）——
    每次新建连接池就得同步扩 `LLMRegistry.aclose` 的资源归属（见 llm_registry._build 的
    「传输参数不同不得共用同一客户端」那条注释），那不属于本票范围。
    异常一律向上抛：票 §2 末明令 ASR 分支不许在调用处降级。
    """
    sdk = client if client is not None else voice_llm.root_client
    if sdk is None:
        raise ValueError("audio_transcriptions 需要模型客户端才能拼出 /audio/transcriptions 端点")
    raw = base64.b64decode(b64)
    mime = _AUDIO_MIME.get(fmt, "application/octet-stream")
    resp = sdk.audio.transcriptions.create(
        model=voice_llm.model_name,
        file=(f"audio.{fmt}", raw, mime),
    )
    return (getattr(resp, "text", None) or "").strip()


def _refuse_voice_transport(voice_llm, b64: str, fmt: str, *, client: Any | None = None) -> str:
    """none 腿：entry 声明了「没有语音传输路」⇒ 显式拒，**不许静默回退到 chat**。"""
    raise ValueError(f"该模型 transport=none，不接受语音转写调用（model={voice_llm.model_name}）")


# 票 §5 红线：分派点只此一处——按 transport 值查表，不在支路里各比一次。
_VOICE_DISPATCH: dict[str, Callable[..., str]] = {
    MULTIPART_TRANSPORT: _transcribe_multipart,
    NO_TRANSPORT: _refuse_voice_transport,
    CHAT_TRANSPORT: _transcribe_chat,
}


def transcribe_audio(
    voice_llm, b64: str, fmt: str, *, transport: str = CHAT_TRANSPORT, client: Any | None = None
) -> str:
    """语音→文字（M2）。**唯一**按 transport 分派的地方；缺省 chat＝今天那条路，旧行为逐字不变。

    两条腿的失败纪律一致：异常向上抛（前端据此回退 Web Speech，管理台据此分账）。
    """
    try:
        handler = _VOICE_DISPATCH[transport]
    except KeyError as exc:
        raise ValueError(f"未知 transport：{transport!r}（可用 {sorted(_VOICE_DISPATCH)}）") from exc
    return handler(voice_llm, b64, fmt, client=client)


def describe_image(vision_llm, data_url: str, user_text: str = "") -> str:
    """视觉模型产描述/要点，作为检索桥接 + 上下文。

    2026-08-06 图片识别合同（二期）：合同/文书等文字图片 → 逐字转写全文
    （供合同评估确定性骨架使用，150 字摘要不够切条款）；普通图片 → 150 字客观描述。
    由模型按内容自我路由，单次调用。

    2026-10-17 票 W07（C04＝甲 已裁）：**不再吞异常**。改前 `except Exception: return ""`
    把鉴权/形状/超时/本地异常四类失败与「模型返回空内容」收敛成同一个空串（现量见
    tests/test_image_failure_visibility.py 改前那版），于是下游无法区分、任何降级声明都无处落脚。
    现在：调用失败 ⇒ 异常原样向上抛；图片里确实没字 ⇒ 返回空串。两个出口由
    request_bootstrap 分键落归因日志、并由 main 的 HTTP 层把失败那一条变成明确报错。
    """
    prompt = (
        "你是法律文档录入助手。若图片中是合同、协议、判决书等含条文条款的文字图片，"
        "请逐字转写其中全部文字，保留条款编号、甲方乙方、金额等细节，尽量完整不要省略，"
        "以便后续逐条法律风险评估；否则请用不超过150字客观描述图片内容，便于检索相关法律条文。"
        "注意：只转写图片中原本就有的文字，不要添加任何评论、解释或风险提示。"
    )
    if user_text and user_text.strip():
        prompt += f" 用户附言：{user_text.strip()}"
    resp = vision_llm.invoke([HumanMessage(content=build_vision_content(prompt, data_url))])
    return (resp.content or "").strip()
