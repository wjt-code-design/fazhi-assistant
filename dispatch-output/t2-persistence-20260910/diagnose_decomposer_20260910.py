"""分解失败精确诊断（进程内复现，不改候选、不写 DB、不产 T7 产物）。

为什么需要它：探针回报 ISSUE_DECOMPOSITION_INVALID 后，唯一的诊断字段
`agent_failure_detail` 被 observability 日志白名单丢弃（见
independent-verification-20260910.md / 待办），DB 无 agent_run 记录、SSE 错误
文案是通用兜底、runner 只在非 200 时存 raw —— 现有链路对预运行失败零可诊断性。

做法：照生产路径装配（cwd=backend + `import main` 保证 dotenv 与 registry
按生产导入顺序初始化；llm=None 与 main.py 一致 → registry.get()），然后对
agent.runtime 的两个**模块全局**函数在内存里插桩（decompose 在调用时从模块
全局解析），从而在失败时也能拿到模型原始返回内容。

代价：1 次分解外呼（与探针同量级）。不创建 agent_run、不落库。
"""

from __future__ import annotations

import json
import pathlib
import sys
import traceback

HERE = pathlib.Path(__file__).resolve()
ROOT = HERE.parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

import os  # noqa: E402

os.chdir(BACKEND)

captured: dict[str, object] = {}

import main  # noqa: E402  —— 必须在 runtime/llm_registry 之前导入以复刻生产导入顺序
import agent.runtime as rt  # noqa: E402
from request_bootstrap import RequestBootstrap  # noqa: E402

_orig_response_text = rt._response_text
_orig_strict_json = rt._strict_json


def spy_response_text(response: object) -> str:
    try:
        text = _orig_response_text(response)
    except Exception as exc:  # noqa: BLE001
        captured["response_text_error"] = f"{type(exc).__name__}: {exc}"
        captured["response_type"] = type(response).__name__
        captured["response_content_repr"] = repr(getattr(response, "content", None))[:600]
        captured["response_public_attrs"] = [
            a for a in dir(response) if not a.startswith("_")
        ][:30]
        # 思考型模型可能把内容放在 additional_kwargs / response_metadata
        for extra in ("additional_kwargs", "response_metadata"):
            if hasattr(response, extra):
                captured[f"response_{extra}"] = repr(getattr(response, extra))[:600]
        raise
    captured["response_text_len"] = len(text)
    captured["response_text_head"] = text[:800]
    return text


def spy_strict_json(text: object) -> object:
    captured["strict_json_input_head"] = str(text)[:900]
    captured["strict_json_input_len"] = len(str(text))
    try:
        out = _orig_strict_json(text)
    except Exception as exc:  # noqa: BLE001
        captured["strict_json_error"] = f"{type(exc).__name__}: {exc}"
        raise
    captured["strict_json_ok"] = True
    captured["strict_json_top_keys"] = sorted(out.keys()) if isinstance(out, dict) else type(out).__name__
    return out


rt._response_text = spy_response_text
rt._strict_json = spy_strict_json


def load_case(case_id: str = "C01") -> str:
    path = ROOT / "release-evidence" / "legal-agent-v1-complex-v1-20260907" / "frozen-cases-v1.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = data if isinstance(data, list) else data.get("cases", data)
    case = cases[case_id] if isinstance(cases, dict) else next(c for c in cases if c.get("id") == case_id)
    return case["initial_question"]


def main_() -> None:
    question = load_case("C01")
    captured["input_len"] = len(question)

    bootstrap = RequestBootstrap(
        conv_id=0,
        summary="",
        recent=[],
        recent_messages=[],
        image=None,
        user_text=question,
        image_rel=None,
        thumb_rel=None,
        image_description="",
        raw_query=question,
        supplement_text="",
        intent="",
        is_exam=False,
        has_options=False,
        contract_mode=False,
        contract_text=None,
        client_truncated=False,
    )

    runtime = rt.build_agent_runtime(db=None, user_id=0, settings=main.settings)

    captured["default_model_key"] = None
    try:
        from llm_registry import registry

        captured["default_model_key"] = registry.default_key()
    except Exception as exc:  # noqa: BLE001
        captured["default_model_key_error"] = f"{type(exc).__name__}: {exc}"

    try:
        state = runtime.build_initial_state(bootstrap)
    except Exception as exc:  # noqa: BLE001
        captured["verdict"] = f"{type(exc).__name__}: {exc}"
        captured["traceback_tail"] = traceback.format_exc()[-1800:]
    else:
        captured["verdict"] = f"OK — 分解成功，issues={len(state.issues)}"
        captured["issues"] = [
            {"issue_id": i.issue_id, "question": i.question} for i in state.issues
        ]

    out = HERE.parent / "decomposer_diagnosis_20260910.log"
    out.write_text(json.dumps(captured, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for key, value in captured.items():
        print(f"{key}: {value}", flush=True)
    print(f"\n[log] {out}", flush=True)


if __name__ == "__main__":
    main_()
