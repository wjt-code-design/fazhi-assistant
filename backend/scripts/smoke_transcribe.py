"""语音转文字冒烟门禁（M2 前置）：确认语音模型能否收音频并转写。

用户指定语音模型（优先 livetranslate 做转写；qwen-tts-* 是文本→语音，登记备用不测转写）：
  qwen3-livetranslate-flash-2025-12-01        非实时 livetranslate（首选）
  qwen3-livetranslate-flash-realtime-2025-09-22  realtime livetranslate（备选）
  qwen-tts-2025-05-22 / qwen-tts-realtime-latest / qwen-tts-realtime-2025-07-15  TTS（登记，不测）

用法：
  python scripts/smoke_transcribe.py                # 合成 1s 正弦 WAV 测"接受性"
  python scripts/smoke_transcribe.py 录音.wav       # 传真人录音测"正确性"

判定：任一 wav 变体返回非空文本 = 通过；全挂 = 后端实现须降级（保留 Web Speech 或换 paraformer ASR）。
绝不打印 API key。超时 30s，单轮成本极小。
"""
import base64
import math
import os
import struct
import sys
import time
import wave

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

LLM_BASE = os.getenv("LLM_BASE_URL", "").rstrip("/")
LLM_KEY = os.getenv("LLM_API_KEY", "")
DASH_BASE = "https://dashscope.aliyuncs.com/api/v1"

MODEL_LT = "qwen3-livetranslate-flash-2025-12-01"  # 非实时 livetranslate（首选 STT）
MODEL_LT_RT = "qwen3-livetranslate-flash-realtime-2025-09-22"  # realtime（备选）


def make_wav(path: str, seconds: float = 1.0, rate: int = 16000, freq: float = 440.0) -> None:
    """合成 1s 正弦 WAV（16kHz mono 16bit）——只验接受性，不验转写质量。"""
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = b"".join(
            struct.pack("<h", int(12000 * math.sin(2 * math.pi * freq * i / rate)))
            for i in range(int(rate * seconds))
        )
        w.writeframes(frames)


def openai_compatible(model: str, b64: str, data_prefix: str, stream: bool = True) -> tuple[int, str]:
    """OpenAI 兼容 /chat/completions + input_audio（DashScope Qwen 系要求 stream=true）。

    已实测（2026-08-06 门禁）：livetranslate 非实时模型必须带 top-level `translation_options`
    （source_lang/target_lang 均 zh 即转写），否则报 InvalidParameter: translation_options。
    """
    url = f"{LLM_BASE}/chat/completions"
    content = [
        {"type": "input_audio", "input_audio": {"data": data_prefix + b64, "format": "wav"}},
        {"type": "text", "text": "请把这段音频中的语音完整转写为带标点的中文文本，只输出转写结果。"},
    ]
    body = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "stream": stream,
        "translation_options": {"source_lang": "zh", "target_lang": "zh"},
    }
    headers = {"Authorization": f"Bearer {LLM_KEY}", "Content-Type": "application/json"}
    with httpx.Client(timeout=30) as c:
        try:
            r = c.post(url, json=body, headers=headers)
        except Exception as e:
            return 0, f"请求异常: {type(e).__name__}: {e}"
        if r.status_code != 200:
            return r.status_code, r.text[:400]
        if stream:
            text = ""
            for line in r.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    import json

                    d = json.loads(payload)
                    for ch in d.get("choices", []):
                        text += (ch.get("delta") or {}).get("content") or ""
                except Exception:
                    continue
            return r.status_code, text[:600] or "(空)"
        return r.status_code, r.json().get("choices", [{}])[0].get("message", {}).get("content", "")[:600]


def dash_native_mm(model: str, b64: str, key: str) -> tuple[int, str]:
    """DashScope 原生 multimodal-generation（HTTP，audio in content）。"""
    url = f"{DASH_BASE}/services/aigc/multimodal-generation/generation"
    body = {
        "model": model,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"audio": f"data:audio/wav;base64,{b64}"},
                        {"text": "请把这段音频中的语音完整转写为带标点的中文文本，只输出转写结果。"},
                    ],
                }
            ]
        },
        "parameters": {"result_format": "message"},
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    with httpx.Client(timeout=30) as c:
        try:
            r = c.post(url, json=body, headers=headers)
        except Exception as e:
            return 0, f"请求异常: {type(e).__name__}: {e}"
        if r.status_code != 200:
            return r.status_code, r.text[:400]
        try:
            j = r.json()
            out = j.get("output", {})
            msg = (out.get("choices") or [{}])[0].get("message", {})
            content = msg.get("content", "")
            if isinstance(content, list):
                content = "".join(x.get("text", "") for x in content if isinstance(x, dict))
            return r.status_code, str(content)[:600] or "(空)"
        except Exception as e:
            return r.status_code, f"解析失败: {e}"


def dash_asr_paraformer(b64: str, key: str) -> tuple[int, str]:
    """DashScope 专用 ASR 端点（paraformer-realtime-v2，兜底）。"""
    url = f"{DASH_BASE}/services/asr/recognition"
    body = {
        "model": "paraformer-realtime-v2",
        "input": {"file_urls": [], "base64": b64, "format": "wav", "language_hints": ["zh"]},
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    with httpx.Client(timeout=30) as c:
        try:
            r = c.post(url, json=body, headers=headers)
        except Exception as e:
            return 0, f"请求异常: {type(e).__name__}: {e}"
        if r.status_code != 200:
            return r.status_code, r.text[:400]
        j = r.json()
        txt = (j.get("output", {}) or {}).get("text", "") or ""
        return r.status_code, txt[:600] or "(空)"


def main() -> int:
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        wav_path = sys.argv[1]
        print(f"用真人录音: {wav_path}")
    else:
        wav_path = os.path.join(os.path.dirname(__file__), "_smoke_tone.wav")
        make_wav(wav_path)
        print(f"用合成 1s 正弦: {wav_path}")

    with open(wav_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    print(f"\nLLM_BASE_URL: {LLM_BASE or '(空)'}  (key 长度 {len(LLM_KEY)}，不打印值)\n")

    results: list[tuple[str, str]] = []
    attempts = [
        ("OpenAI兼容 input_audio data:;base64, · livetranslate 非实时",
         lambda: openai_compatible(MODEL_LT, b64, "data:;base64,")),
        ("OpenAI兼容 input_audio 裸base64 · livetranslate 非实时",
         lambda: openai_compatible(MODEL_LT, b64, "")),
        ("OpenAI兼容 input_audio data:;base64, · livetranslate realtime",
         lambda: openai_compatible(MODEL_LT_RT, b64, "data:;base64,")),
        ("DashScope原生 multimodal-generation · livetranslate 非实时",
         lambda: dash_native_mm(MODEL_LT, b64, LLM_KEY)),
        ("DashScope原生 multimodal-generation · livetranslate realtime",
         lambda: dash_native_mm(MODEL_LT_RT, b64, LLM_KEY)),
        ("DashScope原生 ASR paraformer-realtime-v2（兜底）",
         lambda: dash_asr_paraformer(b64, LLM_KEY)),
    ]

    passed = False
    for name, fn in attempts:
        t0 = time.time()
        code, out = fn()
        ok = code == 200 and out.strip() and out not in ("(空)",)
        passed = passed or ok
        verdict = "✅ 通过" if ok else ("❌ 失败" if code != 200 else "⚠️ 空返回")
        results.append((name, verdict))
        print(f"[{verdict}] {name}  (HTTP {code}, {time.time()-t0:.1f}s)")
        if ok:
            print(f"        转写结果: {out[:200]}")
        else:
            print(f"        响应: {out[:200]}")

    print("\n" + "=" * 60)
    if passed:
        print("门禁结论: 存在可用语音转写路径 ✅（采用上方第一个 ✅ 的方案写后端实现）")
        for name, v in results:
            if v == "✅ 通过":
                print(f"  - {name}")
        return 0
    print("门禁结论: 全部失败 ❌ → 后端实现须降级（保留 Web Speech 或改走 paraformer 专用 ASR）")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
