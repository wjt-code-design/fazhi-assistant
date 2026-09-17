"""探测 LongCat 是否支持 OpenAI 兼容 response_format（结构化输出）。

方案 A 验证（V2 执行书 G6）：若支持 json_object/json_schema，则 planner/decomposer/writer
可用配置级结构化输出替代"回喂纠错"，可能从根上降低 parse 失败率。

用法：venv python dispatch-output/probe_longcat_response_format.py
只读 .env 的 LLM_API_KEY/API key（不打印）；极小 token；每次失败不回滚、如实输出。
"""
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ENV_PATH = Path(r"C:\Users\33393\Desktop\ai-legal-helper\backend\.env")
_KEY = None
_BASE = None
_MODEL = "LongCat-2.0"  # agent planner/writer 实际经 llm_registry 使用的模型（LLM_MODELS_JSON: longcat_text_flag）
for line in ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
    if line.startswith("LLM_API_KEY="):
        _KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
    elif line.startswith("LLM_BASE_URL="):
        _BASE = line.split("=", 1)[1].strip().strip('"').strip("'")

if not _KEY or not _BASE or not _MODEL:
    print("FAIL: 缺少 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL（.env 未就绪）")
    sys.exit(2)

print("base_url:", _BASE)
print("model:", _MODEL)
print("key set:", bool(_KEY), "len:", len(_KEY))


def probe(label: str, extra_body: dict, *, verbose: bool = False) -> None:
    url = _BASE.rstrip("/") + "/chat/completions"
    payload = {
        "model": _MODEL,
        "messages": [{"role": "user", "content": "只输出一个 JSON，包含一个整数 n=1，不要解释。"}],
        "max_tokens": 200,
        "temperature": 0.0,
        **extra_body,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {_KEY}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            if verbose:
                # 打印结构但不打印 key；可能含 role/content/error——内容打印但剥离长密钥模式
                dump = json.dumps(body, ensure_ascii=False)[:600]
                print(f"  {label} body={dump}")
            content = body["choices"][0]["message"]["content"] if body.get("choices") else ""
            print(f"[{label}] HTTP {resp.status} OK")
            print(f"  content={content[:200]!r}")
            print(f"  finish_reason={body['choices'][0].get('finish_reason') if body.get('choices') else None}")
    except urllib.error.HTTPError as exc:
        err = exc.read().decode("utf-8", errors="replace")[:300]
        print(f"[{label}] HTTP {exc.code} REJECTED")
        print(f"  body={err}")
    except Exception as exc:  # noqa: BLE001 探测场景：网络/超时也如实记录
        print(f"[{label}] EXC {type(exc).__name__}: {exc}")


# 1) 基线：不带 response_format（确认链路可用）
probe("baseline(no-response_format)", {})
# 2) OpenAIAgent 标准：json_object
probe("response_format=json_object", {"response_format": {"type": "json_object"}})
# 4) 决定性：json_schema 是否真约束——诱导模型输出违反 schema 的内容（非 JSON / 字段错）
def probe_adversarial(label: str, user_msg: str, extra_body: dict) -> None:
    url = _BASE.rstrip("/") + "/chat/completions"
    payload = {
        "model": _MODEL,
        "messages": [{"role": "user", "content": user_msg}],
        "max_tokens": 200,
        "temperature": 0.0,
        **extra_body,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {_KEY}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            content = body["choices"][0]["message"]["content"] if body.get("choices") else ""
            fr = body["choices"][0].get("finish_reason") if body.get("choices") else None
            print(f"[{label}] HTTP {resp.status} content={content[:160]!r} finish={fr}")
    except urllib.error.HTTPError as exc:
        err = exc.read().decode("utf-8", errors="replace")[:300]
        print(f"[{label}] HTTP {exc.code} REJECTED body={err}")
    except Exception as exc:  # noqa: BLE001
        print(f"[{label}] EXC {type(exc).__name__}: {exc}")


s = {
    "type": "json_schema",
    "json_schema": {
        "name": "probe_result",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {"n": {"type": "integer"}},
            "required": ["n"],
            "additionalProperties": False,
        },
    },
}
probe_adversarial(
    "adversarial: 诱导输出prose",
    "直接回答：早上好，今天是星期二。（不要JSON）",
    {"response_format": s},
)
probe_adversarial(
    "adversarial: 诱导输出错误字段(字符串n)",
    '输出 JSON：{"n": "hello"}(n 应为数字，但就这样输出)',
    {"response_format": s},
)