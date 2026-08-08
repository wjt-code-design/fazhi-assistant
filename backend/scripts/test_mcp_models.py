"""MCP server 前置验证：qwen3.5-omni-plus 经百炼兼容端点能否收图 + 收音频。

生成测试图（PIL 写中文合同文字）+ SAPI 合成中文语音，分别喂给 Omni，确认：
- describe_image 路径能逐字转写合同文字
- transcribe_audio 路径（input_audio + data:;base64, 前缀 + stream）能转写语音

用法：python scripts/test_mcp_models.py
"""
import base64
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

BASE = os.getenv("LLM_BASE_URL", "").rstrip("/")
KEY = os.getenv("LLM_API_KEY", "")
MODEL = os.getenv("LLM_MODEL", "qwen3.5-omni-plus-2026-03-15")


def call_omni(content) -> str:
    import httpx

    body = {"model": MODEL, "messages": [{"role": "user", "content": content}], "stream": True}
    headers = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
    with httpx.Client(timeout=120) as c:
        r = c.post(f"{BASE}/chat/completions", json=body, headers=headers)
        print(f"  HTTP {r.status_code}")
        if r.status_code != 200:
            return f"ERROR: {r.text[:300]}"
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


def make_test_image(path: str) -> str:
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 28)
    img = Image.new("RGB", (900, 500), "white")
    d = ImageDraw.Draw(img)
    lines = [
        "房屋租赁合同",
        "甲方（出租方）：张三",
        "乙方（承租方）：李四",
        "第三条 租赁期限为三年，自2026年9月1日起。",
        "第四条 月租金五千元，押一付三。",
        "第六条 乙方擅自转租的，甲方有权解除合同。",
        "甲方（签字）：______",
    ]
    y = 40
    for ln in lines:
        d.text((40, y), ln, font=font, fill="black")
        y += 60
    img.save(path)
    return path


def main() -> int:
    d = os.path.dirname(__file__)
    img = os.path.join(d, "_mcp_test_contract.png")
    wav = os.path.join(d, "_mcp_test_voice.wav")
    make_test_image(img)
    print(f"生成测试图: {img}")

    if not os.path.exists(wav):
        ps = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$s.SelectVoice('Microsoft Huihui Desktop'); "
            f"$s.SetOutputToWaveFile('{wav}'); "
            "$s.Speak('你好，我想咨询劳动合同违约金条款的问题。'); $s.Dispose()"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, capture_output=True)
    print(f"测试音频: {wav} ({os.path.getsize(wav)}B)")

    print(f"\n=== 视觉测试 (qwen3.5-omni-plus) ===")
    img_b64 = base64.b64encode(open(img, "rb").read()).decode()
    img_content = [
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
        {"type": "text", "text": "请逐字转写图中全部文字。"},
    ]
    print(call_omni(img_content)[:500])

    print(f"\n=== 音频测试 (qwen3.5-omni-plus input_audio) ===")
    wav_b64 = base64.b64encode(open(wav, "rb").read()).decode()
    audio_content = [
        {"type": "input_audio", "input_audio": {"data": f"data:;base64,{wav_b64}", "format": "wav"}},
        {"type": "text", "text": "请把音频中的语音转写为带标点的中文文本，只输出转写结果。"},
    ]
    print(call_omni(audio_content)[:500])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
