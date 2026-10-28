"""F4 端点级证据（2026-10-27）：矛盾答案加提示且不写缓存；正常答案写缓存。"""

import json

from tests import _sse_harness as harness

NOTE = "提示：结论与所引条文不一致"


def _frames_text(frames: list[str]) -> str:
    parts = []
    for frame in frames:
        if frame.startswith("data: "):
            try:
                payload = json.loads(frame[6:])
            except json.JSONDecodeError:
                continue
            parts.append(payload.get("content") or "")
    return "".join(parts)


def test_light_contradiction_appends_note_and_skips_cache(monkeypatch):
    sink = []
    text = "依据《刑法》第二百三十四条，构成故意伤害罪。第二百三十四条未提供全文。"
    with harness.sse_client(
        monkeypatch,
        route="light_buffered",
        light_text=text,
        cache_put=lambda key, answer, sources, **kw: sink.append({"key": key, "answer": answer}),
    ) as client:
        token = harness.login(client)
        frames = harness.chat_frames(client, token, "故意伤害致人重伤怎么判？")

    body = _frames_text(frames)
    assert NOTE in body
    assert sink == [], "矛盾答案不得写答案缓存"


def test_light_clean_answer_skips_note_and_writes_cache(monkeypatch):
    sink = []
    text = "依据《刑法》第二百三十四条，故意伤害他人身体的，处三年以下有期徒刑、拘役或者管制。"
    with harness.sse_client(
        monkeypatch,
        route="light_buffered",
        light_text=text,
        cache_put=lambda key, answer, sources, **kw: sink.append({"key": key, "answer": answer}),
    ) as client:
        token = harness.login(client)
        frames = harness.chat_frames(client, token, "故意伤害致人重伤怎么判？")

    body = _frames_text(frames)
    assert NOTE not in body
    assert sink, "正常答案应写缓存（对照用例，证明闸门有区分度）"
