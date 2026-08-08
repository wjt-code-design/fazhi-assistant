"""Qwen Omni 多模态 MCP server（法智 · 开发期验收工具）。

把阿里云百炼 qwen3.5-omni-plus 包成两个 MCP 工具，供 Claude Code 在开发/验收时直接调用：
- describe_image(image_path)：合同/文书等文字图片逐字转写全文，普通图片给客观描述
- transcribe_audio(audio_path)：中文语音 → 带标点文本

复用 backend/.env 的 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL（百炼兼容 OpenAI 端点）。
运行：python mcp_server.py（stdio 传输，由项目根 .mcp.json 拉起）。绝不打印 API key。
"""
import base64
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("qwen-omni")

BASE = os.getenv("LLM_BASE_URL", "").rstrip("/")
KEY = os.getenv("LLM_API_KEY", "")
MODEL = os.getenv("LLM_MODEL", "qwen3.5-omni-plus-2026-03-15")

_PROMPT_IMAGE = (
    "你是法律文档录入助手。若图片中是合同、协议、判决书等含条文条款的文字图片，"
    "请逐字转写其中全部文字，保留条款编号、甲方乙方、金额等细节，尽量完整不要省略；"
    "否则请用不超过150字客观描述图片内容。只转写/描述图片中原本就有的内容，不要添加评论或解释。"
)
_PROMPT_AUDIO = (
    "你是一个中文语音转文字引擎。请把音频中的话完整、准确转写为带标点的中文文本，"
    "保留数字与专有名词；只输出转写结果，不要任何解释。"
)
_AUDIO_EXTS = ("wav", "mp3", "m4a", "flac", "ogg")


def _call_omni(content: list) -> str:
    """OpenAI 兼容流式调用 qwen3.5-omni-plus，聚合 SSE content 返回。"""
    import httpx

    if not KEY:
        raise RuntimeError("缺少 LLM_API_KEY，请检查 backend/.env")
    body = {"model": MODEL, "messages": [{"role": "user", "content": content}], "stream": True}
    headers = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
    with httpx.Client(timeout=120) as c:
        r = c.post(f"{BASE}/chat/completions", json=body, headers=headers)
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
        text = ""
        for line in r.iter_lines():
            if not line or not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                d = json.loads(payload)
                for ch in d.get("choices", []):
                    text += (ch.get("delta") or {}).get("content") or ""
            except Exception:
                continue
        return text.strip()


@mcp.tool()
def describe_image(image_path: str) -> str:
    """识别图片内容。合同/文书等文字图片会逐字转写全部文字（供合同评估），普通图片给客观描述。

    参数：本地图片绝对路径（JPEG/PNG）。
    """
    p = Path(image_path).expanduser()
    if not p.exists():
        return f"文件不存在: {image_path}"
    mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
    b64 = base64.b64encode(p.read_bytes()).decode()
    content = [
        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
        {"type": "text", "text": _PROMPT_IMAGE},
    ]
    try:
        return _call_omni(content) or "(模型无输出)"
    except Exception as e:
        return f"describe_image 调用失败：{e}"


@mcp.tool()
def transcribe_audio(audio_path: str) -> str:
    """把中文语音转写为带标点文本。

    参数：本地音频绝对路径（wav/mp3/m4a/flac/ogg）。
    """
    p = Path(audio_path).expanduser()
    if not p.exists():
        return f"文件不存在: {audio_path}"
    fmt = p.suffix.lstrip(".").lower()
    if fmt not in _AUDIO_EXTS:
        return f"仅支持 {'/'.join(_AUDIO_EXTS)}，收到 .{fmt}"
    b64 = base64.b64encode(p.read_bytes()).decode()
    content = [
        {"type": "input_audio", "input_audio": {"data": f"data:;base64,{b64}", "format": fmt}},
        {"type": "text", "text": _PROMPT_AUDIO},
    ]
    try:
        return _call_omni(content) or "(模型无输出)"
    except Exception as e:
        return f"transcribe_audio 调用失败：{e}"


if __name__ == "__main__":
    mcp.run()
