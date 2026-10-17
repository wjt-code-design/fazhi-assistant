"""Qwen Omni 多模态 MCP server（法智 · 开发期验收工具）。

把百炼全模态模型包成两个 MCP 工具，供 Claude Code 在开发/验收时直接调用：
- describe_image(image_path)：合同/文书等文字图片逐字转写全文，普通图片给客观描述
- transcribe_audio(audio_path)：中文语音 → 带标点文本

票 W7-FIX B4（2026-10-17）：这两个工具**不再自己拼请求体**。改前这里有一条独立的语音路——
自己拼聊天里的音频部件、自带一份音频扩展名白名单、无视 registry/transport，还把异常收敛成
一句返回字符串 ⇒「语音分派只有一处」这句话被击穿，`transport:"none"` 的 entry 在那里照样走 chat-ASR。
现在两者都走 `multimodal` 的那两条桥接函数，模型与 transport 都由 registry 那一份真源给出，
失败**向上抛**给 MCP 调用方（判据：tests/test_multimodal_transport_impl.py 的 mcp_server 那条 +
tests/test_image_failure_impl.py 的吞异常普查作用域）。

凭据来自 backend 配置（`llm_registry` 的 entry，经 backend/.env 或环境变量）。绝不打印 API key。
运行：python mcp_server.py（stdio 传输，由项目根 .mcp.json 拉起）。
"""

import base64
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from mcp.server.fastmcp import FastMCP

import multimodal
from llm_registry import registry

mcp = FastMCP("qwen-omni")


def _voice_call_args(audio_path: str, transport: str) -> tuple[str, str, str]:
    """语音工具真正交给分派点的三个值：`(b64, fmt, transport)`——**纯函数**，不发请求。

    R2-F9（复核第二轮）：`mcp_server` 在本机导不进来（没装 `mcp` 包），所以这条调用点过去**只有
    源码子串尺子**——参数顺序颠倒、`transport=` 退成位置参、fmt 没去点，全都没有判据咬得住
    （复核现量：把 b64 与 fmt 互换，门照样全绿）。抽成纯函数之后，测试可以把这一只函数从源文件里
    用 `ast` 摘出来单独装载（不需要 `mcp`），对返回值做**等值**判据；本文件里剩下的只有
    「调用它 ＋ 把返回值交给唯一那条分派腿」。
    刻意不做存在性/白名单检查：那两支持续返回给人看的句子，留在 tool 里（而且白名单外**不该**
    先把整只文件读进内存做 base64）。
    """
    p = Path(audio_path).expanduser()
    fmt = p.suffix.lstrip(".").lower()
    b64 = base64.b64encode(p.read_bytes()).decode()
    return b64, fmt, transport


def _image_call_args(image_path: str) -> str:
    """图片工具真正交给 `multimodal.describe_image` 的那一个值：`data:<mime>;base64,<b64>`。

    同样为 R2-F9 而抽出来（等值判据见 `test_r2_image_call_args_keeps_one_prompt_source`）。
    刻意**不**在这里拼提示词：提示词的唯一真源是 `multimodal.describe_image` 内部那一份，
    这里再抄一遍就是第二处措辞真源（W7-B4 的教训就是这条）。
    """
    p = Path(image_path).expanduser()
    mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
    b64 = base64.b64encode(p.read_bytes()).decode()
    return f"data:{mime};base64,{b64}"


@mcp.tool()
def describe_image(image_path: str) -> str:
    """识别图片内容。合同/文书等文字图片会逐字转写全部文字（供合同评估），普通图片给客观描述。

    参数：本地图片绝对路径（JPEG/PNG）。调用失败时异常原样抛出，不降级成一句字符串。
    """
    p = Path(image_path).expanduser()
    if not p.exists():
        return f"文件不存在: {image_path}"
    _key, vision_llm = registry.pick("vision", "flag")
    # 提示词与后端**同一份**（`multimodal.describe_image` 内部那份）：这里只交一个 data URL
    return multimodal.describe_image(vision_llm, _image_call_args(image_path)) or "(模型无输出)"


@mcp.tool()
def transcribe_audio(audio_path: str) -> str:
    """把中文语音转写为带标点文本。

    参数：本地音频绝对路径（wav/mp3/m4a/flac/ogg，白名单与后端 `multimodal.AUDIO_EXTS` 同一份）。
    transport 由 registry 给出：`audio_transcriptions` 走 multipart 那条腿，`none` 那条**显式拒**，
    这里不再自行决定走 chat。失败异常原样抛出（不吞成字符串）。
    """
    p = Path(audio_path).expanduser()
    if not p.exists():
        return f"文件不存在: {audio_path}"
    fmt = p.suffix.lstrip(".").lower()
    if fmt not in multimodal.AUDIO_EXTS:
        return f"仅支持 {'/'.join(multimodal.AUDIO_EXTS)}，收到 .{fmt}"
    key, voice_llm = registry.pick("voice", "flag")
    # 参数装配交给上面那只纯函数：这一行只负责「调用它 ＋ 按位置把三个值交给唯一那条分派腿」
    b64, fmt, transport = _voice_call_args(audio_path, registry.transport_of(key))
    text = multimodal.transcribe_audio(voice_llm, b64, fmt, transport=transport)
    return text or "(模型无输出)"


if __name__ == "__main__":
    mcp.run()
