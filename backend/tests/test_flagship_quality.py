"""回归测试：旗舰流式路径也必须写缓存 + 跑自检（S3/S6 对 text 路径不能死）。

背景：精简到 2 模型后 text 无 light 档，use_light=False，text 全走旗舰流式分支。
若该分支不写缓存、不跑自检，则 S3(缓存)/S6(自检) 对文字问题名存实亡。
本测试 mock LLM/检索，走真实 chat 编排，断言缓存写入与自检执行——修复前应 RED。

夹具已抽到 `_sse_harness.sse_client(route="flagship_stream")`（S5/1b）：桩点集合与抽提前一致，
本文件的断言一字未改 —— 抽提判据就是"抽前抽后同结果"。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import pytest

from tests._sse_harness import FLAGSHIP_PARTS, login, sse_client


@pytest.fixture
def client(monkeypatch):
    with sse_client(monkeypatch, flagship_parts=FLAGSHIP_PARTS) as c:
        yield c


def _login(client):
    return login(client)


def test_flagship_path_writes_cache_and_runs_selfcheck(client, monkeypatch):
    import answer_cache
    import quality
    import routing_metrics

    answer_cache.clear()
    routing_metrics.reset()
    self_check_calls = []

    def self_check(answer, context_present):
        self_check_calls.append((answer, context_present))
        return quality.Verdict(True)

    monkeypatch.setattr(quality, "self_check", self_check)
    tok = _login(client)
    q = "试用期最长多久"
    with client.stream("POST", "/api/chat", json={"content": q}, headers={"Authorization": f"Bearer {tok}"}) as r:
        assert r.status_code == 200
        body = "".join(r.iter_text())
    assert "第十九条" in body  # 答案正常返回

    # S6：旗舰流式路径必须对检索命中的答案执行自检。
    assert self_check_calls == [("根据《劳动合同法》第十九条，试用期最长六个月。", True)]
    assert routing_metrics.snapshot()["checked_count"] > 0, "旗舰流式路径未跑自检 → S6 对 text 死"
    # S3：旗舰流式路径必须写入缓存，且相同请求要实际命中缓存。
    assert answer_cache.__len__() == 1, "旗舰流式路径未写缓存 → S3 对 text 死"
    with client.stream("POST", "/api/chat", json={"content": q}, headers={"Authorization": f"Bearer {tok}"}) as r:
        assert r.status_code == 200
        cached_body = "".join(r.iter_text())
    assert "第十九条" in cached_body
    assert routing_metrics.snapshot()["cache_hit_rate"] == 0.5, "相同请求未命中旗舰缓存"
