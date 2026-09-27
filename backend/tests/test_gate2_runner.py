"""V2-T6（2026-09-09）：gate2_runner 长跑可靠性——假 HTTP 服务离线测试（零真实模型调用）。

覆盖：唯一 run 占用/禁覆盖、逐题原子 checkpoint、resume 跳过已完成、CLIENT_TIMEOUT
暂停队列与 unknown_server_state 双门禁、HTTP 错误保留、非 SSE 记录。
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import scripts.gate2_runner as runner

INITIAL_OK_FINAL_SSE = (
    'data: {"type": "agent_status", "status": "completed"}\n\n'
    'data: {"type": "verification", "verdict": "PASS"}\n\n'
    'data: {"type": "token", "content": "已确认事实：\\n- 双方签署借款合同\\n\\n可执行建议与风险提示：\\n依据《民法典》第675条处理。"}\n\n'
    'data: {"type": "final", "run_id": "agent-run-x", "state_version": 6}\n\n'
    "data: [DONE]\n\n"
)
CLARIFY_SSE = (
    'data: {"type": "clarification", "prompt": "公司的内网安全制度有什么要求？",'
    ' "run_id": "agent-run-x", "state_version": 3, "conversation_id": 7}\n\n'
    "data: [DONE]\n\n"
)
SCOPE_CLARIFY_SSE = (
    'data: {"type": "clarification", "prompt": "本次请求分解出 8 个法律争点，超过单次可处理上限 5 个。'
    '请从中选择最多 5 个争点（输入编号，用逗号分隔，例如：1,3,5）：\\n1. 争点甲\\n2. 争点乙",'
    ' "run_id": "agent-run-x", "state_version": 3, "conversation_id": 7}\n\n'
    "data: [DONE]\n\n"
)
NOMATCH_CLARIFY_SSE = (
    'data: {"type": "clarification", "prompt": "对方是否具备司法鉴定资质？",'
    ' "run_id": "agent-run-x", "state_version": 4, "conversation_id": 7}\n\n'
    "data: [DONE]\n\n"
)
# 上述夹具共用同一个占位 run_id。`_ScriptedService` 会按 case 把它改写成唯一值，
# 使 resume 请求带上可归属的信号（改写发生在 `_reply()`；`_resolve_case` 做反向解析）。
_RUN_ID_PLACEHOLDER = "agent-run-x"


class _SseTestServer:
    """两个假服务的共同部分：SSE 传输、login 分支、请求记账、起停服务。

    ⚠️ 只拥有**传输**，不拥有**语义**：`handle_chat()` 的场景分派与应答内容留在子类。
    关键原因是 `_ScriptedService` 会按 case 改写响应里的 run_id，而 `_FakeGateService`
    不会——若把这层改写提到基类，那 10 条 harness 测试的 resume 归属行为就会被这次
    "行为保持型重构"改掉。

    `_lock` 用 RLock：子类需要在同一把锁里既记账又推进游标（旧代码正是这么做的），
    而 `_record()` 自身也要持锁，普通 `Lock` 会在嵌套处自锁。
    """

    def __init__(self) -> None:
        self.chat_requests: list[dict] = []
        self._lock = threading.RLock()

    def _record(self, payload: dict) -> None:
        with self._lock:
            self.chat_requests.append(dict(payload))

    def handle_chat(self, handler: BaseHTTPRequestHandler, payload: dict) -> None:
        raise NotImplementedError

    def start(self) -> ThreadingHTTPServer:
        service = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # 静默
                pass

            def _send_sse(self, body: str) -> None:
                data = body.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                if self.path == "/api/auth/login":
                    # login 必须是 JSON：runner 只取 token，给 SSE 会让它直接失败。
                    self.rfile.read(length)
                    body = b'{"token": "test-token"}'
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                if self.path != "/api/chat":
                    self.send_error(404)
                    return
                payload = json.loads(self.rfile.read(length) or b"{}")
                service.handle_chat(self, payload)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server


def _serve(tmp_path, monkeypatch, cls):
    """两个 fixture 的共同装配：换 EVID 目录 → 起假服务 → 收尾。

    收尾两个调用缺一不可，且**不是本批新增的**：两个 fixture 在本批开工时的 HEAD 版本里
    就已同时调 `shutdown()` + `server_close()`。`shutdown()` 只停 `serve_forever`，
    `server_close()` 才关监听 socket；这里只是把两份拷贝收成一份。
    """
    monkeypatch.setattr(runner, "EVID", tmp_path)
    # 假凭据（测试自带，不入库真值）：干净检出/发布物树没有 backend/.env（`.gitignore` 忽略），
    # runner 的 `_admin_credentials()` 按「文件存在则读文件，缺失的键回落进程环境变量」取值。
    # 这里显式给假用户名/口令，使长跑路径在无 .env 的副本树里也能登录取 token（假服务不校验凭据）；
    # 子进程路径（_subprocess_run）继承 os.environ，同样生效。
    monkeypatch.setenv("ADMIN_USERNAME", "t6-fake-admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "t6-fake-password")
    service = cls()
    server = service.start()
    try:
        yield tmp_path, service, server.server_port
    finally:
        server.shutdown()
        server.server_close()


class _FakeGateService(_SseTestServer):
    """可控假 HTTP 服务：按 case 注入**单一**场景；记录全部 chat 请求。

    行为保持论证（本类相对旧实现的两处删除，均已核对不可观测）：
    ① 旧 `do_POST` 在 login 分支里先 `_send_sse("SYNC")`，但整个 `Handler.do_POST` 随后被
      外层 wrapper 重写、login 提前返回 ⇒ 那一行**从未生效**；
    ② 旧代码对**任意**路径都先 `json.loads(body)` 再判 404，基类改成先判 login/404 再解析
      ⇒ 差异只在"向未知路径 POST 非 JSON"时才有意义，runner 不发这种请求（它只打
      `/api/auth/login` 与 `/api/chat`），故无测试覆盖该差异、也无测试受它影响。
    """

    def __init__(self) -> None:
        super().__init__()
        self.initial_scene: dict[str, str] = {}  # case_id → scene

    def set_scene(self, case_id: str, scene: str) -> None:
        self.initial_scene[case_id] = scene

    def handle_chat(self, handler: BaseHTTPRequestHandler, payload: dict) -> None:
        self._record(payload)
        content = str(payload.get("content", ""))
        case_id = next((cid for cid, c in runner.BY_ID.items() if c["initial_question"] == content), None)
        scene = self.initial_scene.get(case_id, "final")
        if scene == "http_500":
            body = b'{"detail": "internal error"}'
            handler.send_response(500)
            handler.send_header("Content-Length", str(len(body)))
            handler.send_header("Content-Type", "application/json")
            handler.end_headers()
            handler.wfile.write(body)
            return
        if scene == "timeout":
            handler.close_connection = True  # 不响应直接断开 → 客户端 OSError
            return
        if scene == "hang":
            import time as _time

            _time.sleep(15)  # 挂起：模拟长请求，供"中途 kill 进程"测试窗口
            handler._send_sse(INITIAL_OK_FINAL_SSE)
            return
        if scene == "non_sse":
            body = b"plain text, not an SSE stream"
            handler.send_response(200)
            handler.send_header("Content-Length", str(len(body)))
            handler.end_headers()
            handler.wfile.write(body)
            return
        if scene == "clarify_once":
            handler._send_sse(CLARIFY_SSE)
            return
        if scene == "scope":
            handler._send_sse(SCOPE_CLARIFY_SSE)
            return
        handler._send_sse(INITIAL_OK_FINAL_SSE)


@pytest.fixture
def harness(tmp_path, monkeypatch):
    yield from _serve(tmp_path, monkeypatch, _FakeGateService)


def _run(harness, *extra: str) -> int:
    _tmp, _service, port = harness
    # parse_args(argv) 的 argv 不含程序名
    argv = ["--run", "t6-run", "--base-url", f"http://127.0.0.1:{port}", *extra]
    return runner.run(argv)


def test_two_cases_complete_outputs_written_and_rerun_refuses(harness):
    tmp_path, service, _port = harness
    service.set_scene("C01", "clarify_once")  # C01: 澄清一轮（关键词"内网"命中事实）→ final
    service.set_scene("C02", "final")

    assert _run(harness, "--case", "C01,C02") == 0

    sessions = json.loads((tmp_path / "gate2-run-t6-run-sessions.json").read_text(encoding="utf-8"))
    checkpoint = json.loads((tmp_path / "gate2-run-t6-run-checkpoint.json").read_text(encoding="utf-8"))
    assert set(sessions["results"]) == {"C01", "C02"}
    assert all(r["agent_completed"] is True for r in sessions["results"].values())
    assert sessions["results"]["C01"]["final_chars"] > 0
    assert set(checkpoint["results"]) == {"C01", "C02"}
    assert not list(tmp_path.glob("*.tmp"))  # 原子写无残留

    # 旧 run 禁止覆盖：重跑同 run 直接拒绝且产物不变
    before = sessions
    assert _run(harness, "--case", "C01,C02") == 4
    after = json.loads((tmp_path / "gate2-run-t6-run-sessions.json").read_text(encoding="utf-8"))
    assert after == before


def test_create_refuses_when_claim_already_exists(harness):
    tmp_path, _service, _port = harness
    (tmp_path / "gate2-run-t6-run.claim.json").write_text(
        json.dumps({"run": "t6-run", "targets": ["C01"]}), encoding="utf-8"
    )

    assert _run(harness, "--case", "C01") == 4


def test_resume_skips_completed_cases_without_reissuing_requests(harness):
    tmp_path, service, _port = harness
    service.set_scene("C01", "final")

    assert _run(harness, "--case", "C01") == 0
    requests_after_first = len(service.chat_requests)

    # resume 同一题：已完成 → 跳过，不向服务端重发（防重复计费）
    assert _run(harness, "--resume", "--case", "C01") == 0
    assert len(service.chat_requests) == requests_after_first
    # nothing-to-do 分支幂等补写最终产物：sessions 必存在且结果与首次一致
    sessions = json.loads((tmp_path / "gate2-run-t6-run-sessions.json").read_text(encoding="utf-8"))
    assert sessions["results"]["C01"]["agent_completed"] is True


def test_client_timeout_pauses_queue_and_marks_unknown(harness):
    tmp_path, service, _port = harness
    service.set_scene("C01", "timeout")
    service.set_scene("C02", "final")

    exit_code = _run(harness, "--case", "C01,C02")
    assert exit_code == 3  # 暂停队列，非失败也非成功
    chat_initials = [r for r in service.chat_requests if r.get("content") == runner.BY_ID["C02"]["initial_question"]]
    assert chat_initials == []  # 未自动发下一题
    checkpoint = json.loads((tmp_path / "gate2-run-t6-run-checkpoint.json").read_text(encoding="utf-8"))
    assert checkpoint["results"]["C01"]["unknown_server_state"] is True
    assert not (tmp_path / "gate2-run-t6-run-sessions.json").exists()


def test_resume_refuses_unknown_without_manual_confirmation(harness):
    tmp_path, _service, _port = harness
    (tmp_path / "gate2-run-t6-run.claim.json").write_text(
        json.dumps({"run": "t6-run", "targets": ["C01"]}), encoding="utf-8"
    )
    (tmp_path / "gate2-run-t6-run-checkpoint.json").write_text(
        json.dumps(
            {"run": "t6-run", "targets": ["C01"], "results": {"C01": {"unknown_server_state": True, "rounds": []}}}
        ),
        encoding="utf-8",
    )

    assert _run(harness, "--resume", "--case", "C01") == 5


def test_resume_with_retry_unknown_reruns_marked_case(harness):
    tmp_path, service, _port = harness
    service.set_scene("C01", "final")
    (tmp_path / "gate2-run-t6-run.claim.json").write_text(
        json.dumps({"run": "t6-run", "targets": ["C01"]}), encoding="utf-8"
    )
    (tmp_path / "gate2-run-t6-run-checkpoint.json").write_text(
        json.dumps(
            {"run": "t6-run", "targets": ["C01"], "results": {"C01": {"unknown_server_state": True, "rounds": []}}}
        ),
        encoding="utf-8",
    )
    before = len(service.chat_requests)

    assert _run(harness, "--resume", "--retry-unknown", "--case", "C01") == 0
    assert len(service.chat_requests) > before  # 显式确认后重跑
    sessions = json.loads((tmp_path / "gate2-run-t6-run-sessions.json").read_text(encoding="utf-8"))
    assert sessions["results"]["C01"]["agent_completed"] is True
    assert "unknown_server_state" not in sessions["results"]["C01"]


def test_http_error_is_recorded_and_queue_continues(harness):
    tmp_path, service, _port = harness
    service.set_scene("C01", "http_500")
    service.set_scene("C02", "final")

    assert _run(harness, "--case", "C01,C02") == 0
    sessions = json.loads((tmp_path / "gate2-run-t6-run-sessions.json").read_text(encoding="utf-8"))
    assert sessions["results"]["C01"]["rounds"][0]["status"] == 500
    assert sessions["results"]["C01"]["agent_completed"] is False
    assert sessions["results"]["C02"]["agent_completed"] is True  # HTTP 错误是确定结果，不阻塞队列


def test_non_sse_response_is_recorded_without_agent_completion(harness):
    tmp_path, service, _port = harness
    service.set_scene("C01", "non_sse")

    assert _run(harness, "--case", "C01") == 0
    sessions = json.loads((tmp_path / "gate2-run-t6-run-sessions.json").read_text(encoding="utf-8"))
    r = sessions["results"]["C01"]
    assert r["final_chars"] == 0
    assert r["agent_completed"] is False  # final_chars>0 不得替代持久化成功；此处两者皆无


def _subprocess_run(harness, *extra: str, capture: bool = False):
    """子进程真实运行 runner（--out-dir 隔离产物，不经 monkeypatch）。"""
    _tmp, _service, port = harness
    argv = [
        sys.executable,
        "scripts/gate2_runner.py",
        "--run",
        "t6-run",
        "--base-url",
        f"http://127.0.0.1:{port}",
        "--out-dir",
        str(_tmp),
        *extra,
    ]
    if capture:
        return subprocess.run(argv, cwd=".", capture_output=True, text=True, timeout=60)
    return subprocess.Popen(argv, cwd=".", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def test_mid_run_process_kill_recovers_from_checkpoint(harness):
    """显式模拟"中途进程退出"（教学手册第七课）：C01 完成后进程被杀——
    checkpoint 保留 C01、sessions 不存在；resume 恢复并完成 C02。"""
    import time as _time

    tmp_path, service, port = harness
    service.set_scene("C01", "final")
    service.set_scene("C02", "hang")

    proc = _subprocess_run(harness, "--case", "C01,C02")
    checkpoint = tmp_path / "gate2-run-t6-run-checkpoint.json"
    deadline = _time.monotonic() + 20
    while _time.monotonic() < deadline:
        if checkpoint.exists():
            data = json.loads(checkpoint.read_text(encoding="utf-8"))
            if "C01" in data.get("results", {}):
                break
        _time.sleep(0.2)
    else:
        proc.kill()
        pytest.fail("checkpoint 未在时限内出现 C01")
    proc.kill()
    proc.wait(timeout=10)

    # 进程退出后的现场：C01 已在 checkpoint，最终产物不存在，run 仍被 claim 占用
    saved = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert "C01" in saved["results"] and "C02" not in saved["results"]
    assert not (tmp_path / "gate2-run-t6-run-sessions.json").exists()
    assert (tmp_path / "gate2-run-t6-run.claim.json").exists()

    # create 重入被拒；resume 恢复并完成 C02
    service.set_scene("C02", "final")
    create_rejected = _subprocess_run(harness, "--case", "C01,C02", capture=True)
    assert create_rejected.returncode == 4
    resumed = _subprocess_run(harness, "--resume", "--case", "C01,C02", capture=True)
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    sessions = json.loads((tmp_path / "gate2-run-t6-run-sessions.json").read_text(encoding="utf-8"))
    assert set(sessions["results"]) == {"C01", "C02"}
    assert all(r["agent_completed"] is True for r in sessions["results"].values())


# ---- 2026-09-13 题集自包含 fact_reveal（v2 新案例接入；付费基线授权）----

_V2_CASE = {
    "id": "E01",
    "fact_reveal": {
        "r1": [{"text": "合同与对账单齐全", "keywords": ["合同", "对账"]}],
        "r2": [{"text": "去年12月发过催款函", "keywords": ["催款", "函"]}],
        "bad": [{"text": "非法轮次键", "keywords": ["x"]}],
    },
}


def test_facts_from_case_set_extends_and_protects_base():
    base = {"C01-r1-f1": {"round": 1, "keywords": ["内网"], "text": "旧文本"}}
    facts = runner._facts_from_case_set(base, [{"id": "C01"}, _V2_CASE])
    assert facts["C01-r1-f1"]["text"] == "旧文本"  # fid 冲突 base 优先（v1 冻结零变化）
    assert facts["E01-r1-f1"] == {"round": 1, "keywords": ["合同", "对账"], "text": "合同与对账单齐全"}
    assert facts["E01-r2-f1"]["round"] == 2
    assert not [fid for fid in facts if "bad" in fid]  # 非法轮次键跳过
    assert "E01-r1-f1" not in base  # 不变更入参


def test_fact_reveal_round_isolation_via_shared_matcher():
    facts = runner._facts_from_case_set({}, [_V2_CASE])
    res = runner.match_revealable_facts(
        case_id="E01", prompt="当时签合同和送货对账了吗？", current_round=1, answered_fact_ids=set(), facts=facts
    )
    assert [m["fact_id"] for m in res.matched_facts] == ["E01-r1-f1"]  # 未来轮不提前披露
    res2 = runner.match_revealable_facts(
        case_id="E01", prompt="你们后来催款过吗？", current_round=2, answered_fact_ids={"E01-r1-f1"}, facts=facts
    )
    assert [m["fact_id"] for m in res2.matched_facts] == ["E01-r2-f1"]


def test_scope_clarification_replies_issue_numbers_not_no_match_reply(harness):
    """范围选择澄清（争点>上限）：runner 必须答编号选择；NO_MATCH_REPLY 会被服务端 409。"""
    tmp_path, service, _port = harness
    service.set_scene("C01", "scope")

    assert _run(harness, "--case", "C01") == 0
    resumes = [r for r in service.chat_requests if r.get("agent_run_id")]
    assert resumes, "scope 澄清后应有 resume 请求"
    assert resumes[0]["content"] == runner.SCOPE_REPLY
    assert all(r.get("content") != runner.NO_MATCH_REPLY for r in resumes)


# ---- 2026-09-17：scope 选择不得挤占事实澄清预算（E03/E04 空终稿根因）----

_MIXED_SEQ = ("scope", "nomatch_prompt", "clarify_once")


class _ScriptedService(_SseTestServer):
    """按"每 case 一串脚本化响应"返回：逐次 chat 请求消费下一条。"""

    # resume 请求的归属真源：run_id 由 case_id 唯一决定，于是"这个请求属于哪个 case"
    # 是**请求自身的纯函数**，不依赖任何跨请求状态。
    _RUN_ID_PREFIX = "gate2-run-"

    def __init__(self) -> None:
        super().__init__()
        self.script: dict[str, list[str]] = {}
        self._cursor: dict[str, int] = {}
        # 归不上 case 的请求在此记账并被显式断言之。P1-1 之前这里回退成"猜最近一个 case"
        # （`_last_case`），会把无主请求挂到别的 case 上、静默消费它的脚本游标。
        self.unattributed: list[dict] = []

    def set_script(self, case_id: str, scenes: tuple[str, ...]) -> None:
        self.script[case_id] = list(scenes)

    @classmethod
    def run_id_for(cls, case_id: str) -> str:
        return f"{cls._RUN_ID_PREFIX}{case_id}"

    def _resolve_case(self, content: str, agent_run_id: object) -> str | None:
        """把一次 /api/chat 归属到 case：初始题按文本，resume 按 run_id。归不上返回 None。"""
        for cid, case in runner.BY_ID.items():
            if case["initial_question"] == content:
                return cid
        run_id = str(agent_run_id or "")
        if run_id.startswith(self._RUN_ID_PREFIX):
            cid = run_id[len(self._RUN_ID_PREFIX) :]
            if cid in runner.BY_ID:
                return cid
        self.unattributed.append({"content": content, "agent_run_id": agent_run_id})
        return None

    def handle_chat(self, handler: BaseHTTPRequestHandler, payload: dict) -> None:
        with self._lock:
            self._record(payload)
            case_id = self._resolve_case(str(payload.get("content", "")), payload.get("agent_run_id"))
            seq = self.script.get(case_id, ["final"]) if case_id else ["final"]
            idx = self._cursor.get(case_id, 0) if case_id else 0
            # 脚本耗尽后默认 final（正常收敛）；需要"永不 finalize"的场景在脚本里显式写满
            scene = seq[idx] if idx < len(seq) else "final"
            if case_id:
                self._cursor[case_id] = idx + 1
        # 归属成功的 case 才有唯一 run_id；归不上时保留占位符，让下次同样归属失败并被记账。
        run_id = self.run_id_for(case_id) if case_id else _RUN_ID_PLACEHOLDER

        def _reply(body: str) -> None:
            handler._send_sse(body.replace(_RUN_ID_PLACEHOLDER, run_id))

        if scene == "scope":
            _reply(SCOPE_CLARIFY_SSE)
            return
        if scene == "clarify_once":
            # 事实澄清：prompt 命中 C01-r1-f1 关键词「内网」
            _reply(CLARIFY_SSE)
            return
        if scene == "nomatch_prompt":
            # 关键词不命中的事实追问 → runner 只能回 NO_MATCH_REPLY
            _reply(NOMATCH_CLARIFY_SSE)
            return
        if scene == "final_never":
            # 服务端永不 finalize（持续索要澄清）：runner 必须有限步退出，不得挂死
            _reply(CLARIFY_SSE)
            return
        _reply(INITIAL_OK_FINAL_SSE)


@pytest.fixture
def scripted(tmp_path, monkeypatch):
    yield from _serve(tmp_path, monkeypatch, _ScriptedService)


def _run_scripted(harness, *extra: str) -> int:
    _tmp, _service, port = harness
    argv = ["--run", "t6-run", "--base-url", f"http://127.0.0.1:{port}", *extra]
    return runner.run(argv)


def test_scripted_service_resume_attribution_is_order_independent():
    """P1-1：resume 归属必须是**请求自身的纯函数**，不依赖"上一个请求是谁"。

    旧实现用 `_last_case` 回退猜归属。今天所有 scripted 测试都只跑单个 case，猜的答案恰好
    正确，所以缺陷不可见；一旦 runner 引入并发或多 case 交替，无主请求就会被挂到别的 case 上、
    静默消费它的脚本游标，使该 case 的 `asked`（⇒ 红线判据的输入）失真且无从定位。
    本测试用一个**全新实例**（没有任何前置请求）直接归属 resume：靠猜的实现必然返回 None。

    watch-it-fail（2026-09-18 实测，`dispatch-output/ta5-arms-20260917/_p11_watch_it_fail.py`，
    在 `backend/` 下跑）：摘掉 `_resolve_case` 的 run_id 通道、还原"猜上一个 case" ⇒ 本测试变红
    `AssertionError: assert None == 'C02'`，同批 5 个端到端测试仍绿。
    ⚠️ 这条红**只能由该定向扰动产生**：把整个 `_ScriptedService` 回滚到 `7c7261c` 得到的是
    `AttributeError`（旧实现根本没有 `_resolve_case` 这个方法），不是本测试。
    """
    svc = _ScriptedService()
    other = next(cid for cid in runner.BY_ID if cid != "C01")
    reply = "对上述问题的补充说明"
    assert all(c["initial_question"] != reply for c in runner.BY_ID.values()), "夹具文本与某 case 初始题撞了"

    # 无前置请求，仅凭 run_id 就能归属；且必须归到 run_id 编码的那个 case，而非别的
    assert svc._resolve_case(reply, svc.run_id_for(other)) == other
    assert svc.unattributed == []

    # 初始题仍按文本归属
    assert svc._resolve_case(runner.BY_ID["C01"]["initial_question"], None) == "C01"

    # 归不上 ⇒ 返回 None **并记账**，绝不回退成某个 case
    assert svc._resolve_case(reply, _RUN_ID_PLACEHOLDER) is None
    assert svc.unattributed == [{"content": reply, "agent_run_id": _RUN_ID_PLACEHOLDER}]


def _assert_attribution_clean(service: _ScriptedService) -> None:
    """端到端绊线：真 HTTP 流程里每个请求都必须能归属。

    ⚠️ **必须紧跟在 `_run_scripted()` 之后调用**，挪到测试末尾就失去意义：实测漏掉 run_id
    改写的故障若由后面的行为断言先炸（`IndexError` / `agent_completed` / `asked` 计数），
    报错完全看不出是归属坏了；放最前面时 4 个测试都直接点名那条带占位 run_id 的应答。

    watch-it-fail（2026-09-18，`dispatch-output/ta5-arms-20260917/_p11_tripwire_probe.py`）：
    注掉 `_reply()` 的 run_id 改写 ⇒ 本绊线 4 例全部首先变红。
    """
    assert service.unattributed == [], f"存在无法归属的 chat 请求：{service.unattributed}"


def test_scope_menu_does_not_consume_fact_clarification_budget(scripted):
    """E03/E04 根因：争点选择（scope）与事实澄清共用 (1,2) 预算 → 答完菜单后事实轮只剩 1 格，
    第 3 次澄清无槽位应答 → 空终稿。修复后两层预算分离，事实轮仍有 2 格。"""
    tmp_path, service, _port = scripted
    service.set_script("C01", _MIXED_SEQ)

    assert _run_scripted(scripted, "--case", "C01") == 0
    _assert_attribution_clean(service)
    sessions = json.loads((tmp_path / "gate2-run-t6-run-sessions.json").read_text(encoding="utf-8"))
    r = sessions["results"]["C01"]

    # 三层追问都被应答（scope + 事实未命中 + 事实命中），最终跑到 final
    assert r["agent_completed"] is True, f"scope 不应挤占事实预算；实际 asked={r['asked']}"
    assert r["final_chars"] > 0
    answers = [req["content"] for req in service.chat_requests if req.get("agent_run_id")]
    assert answers[0] == runner.SCOPE_REPLY
    assert answers[1] == runner.NO_MATCH_REPLY
    assert answers[2] != runner.NO_MATCH_REPLY


def test_clarification_loop_terminates_when_server_never_finalizes(scripted):
    """终止性（loop-termination-preflight）：服务端永远回澄清时，runner 必须有限步退出。

    断言用「已发起的回复数」上界而非「是否达成 final」——后者在服务端无产出时恒 False。

    ⚠️ 护栏，非新功能证据（2026-09-18 代码审查，独立复核）：本测试**在修复前的代码上也通过**
    （语义回滚到 v1 共用预算 + 旧 over_rounds，逐测试独立 basetemp 实测仍绿，见
    `dispatch-output/ta5-arms-20260917/_verify_h1c.py`）。故它**不能**证明本次分层预算改动的
    正确性，只锁住"不会无界空转"这一既有性质。真正的回归证据是
    `test_scope_menu_does_not_consume_fact_clarification_budget`（回滚后变红）。

    ⚠️ 已知缺陷（同上审查，2026-09-18 **已修**）：原先写作 `len(chat_requests) < 50`，该界**形同虚设**
    ——实测实际值仅 3（2026-09-18 把本行临时改成 `== -1` 复读出 `assert 3 == -1`）：1 次初始题 +
    `FACT_CLARIFY_LIMIT`(=2) 次应答。脚本 `("clarify_once",)*50` 之所以只被消费 3 条，是 runner
    预算耗尽后自己停下，与请求归属方式无关（此段原先错记成"靠 `_last_case` 猜归属导致饿死"，
    该符号本批已删）。故 `< 50` 既未触界、也不能区分 `while` 与旧 `for`（正是本 repo
    `loop-termination-preflight` 警告的"探针撞自设阈值"反模式）。现已按"钉住确切值"改正。
    证据：`_verify_h2.py`。
    """
    tmp_path, service, _port = scripted
    service.set_script("C01", ("clarify_once",) * 50)

    assert _run_scripted(scripted, "--case", "C01") == 0
    _assert_attribution_clean(service)
    sessions = json.loads((tmp_path / "gate2-run-t6-run-sessions.json").read_text(encoding="utf-8"))
    r = sessions["results"]["C01"]
    assert r["agent_completed"] is False
    # 协议口径：服务端共发起 3 次追问（2 次已应答 + 末尾 1 次）> 上限 2 ⇒ 红线候选。
    assert r["redline_candidate_over_2_rounds"] is True
    assert len(r["rounds"]) <= 1 + runner.FACT_CLARIFY_LIMIT + runner.SCOPE_CLARIFY_LIMIT
    # 1 次初始题 + FACT_CLARIFY_LIMIT(=2) 次应答。写死字面量而**不**用 `1 + runner.FACT_CLARIFY_LIMIT`
    # 派生式：派生式会随预算常量被调大而自动放宽，正重演 `< 50` 的失效机制。
    assert len(service.chat_requests) == 3


def test_redline_counts_every_clarification_round_including_scope(scripted):
    """P0-1 回归（2026-09-18）：红线判据按**服务端发起的追问次数**计，scope 菜单同样占格。

    序列 (scope, scope, fact)：runner 应答 3 次后服务端才 finalize。此时**末尾已不是澄清**
    ——第 3 次追问已被应答消化。若判据只看"末尾是否仍澄清"，这次超限就会被抹掉。

    watch-it-fail：语义回滚到 2026-09-17 的
    `fact_clar_seen >= FACT_CLARIFY_LIMIT and any(末尾澄清)` 后，本测试**变红**（该谓词既把
    scope 轮排除计数、又依赖末尾快照）。真实证据：arm-off 的 E03/E04（asked=2, scope=1,
    fact=1, 末尾澄清）在旧谓词下被漏标——见 _t1_recompute_real.py 的"旧≠新"行。
    """
    tmp_path, service, _port = scripted
    service.set_script("C01", ("scope", "scope", "clarify_once"))

    assert _run_scripted(scripted, "--case", "C01") == 0
    _assert_attribution_clean(service)
    sessions = json.loads((tmp_path / "gate2-run-t6-run-sessions.json").read_text(encoding="utf-8"))
    r = sessions["results"]["C01"]

    assert len(r["asked"]) == 3, f"三次追问都应被应答；实际 asked={r['asked']}"
    assert r["agent_completed"] is True  # 脚本耗尽后服务端 finalize
    assert r["redline_candidate_over_2_rounds"] is True  # 追问 3 次 > 协议上限 2


def test_redline_not_triggered_when_server_stops_after_two_rounds(scripted):
    """反例护栏：只追问 2 次就 finalize 的会话**不得**记红线（防判据矫枉过正）。

    与上一测试成对——单有"该红时红"的测试，一个恒真的谓词也能通过。
    """
    tmp_path, service, _port = scripted
    service.set_script("C01", ("scope", "clarify_once", "final"))

    assert _run_scripted(scripted, "--case", "C01") == 0
    _assert_attribution_clean(service)
    sessions = json.loads((tmp_path / "gate2-run-t6-run-sessions.json").read_text(encoding="utf-8"))
    r = sessions["results"]["C01"]

    assert len(r["asked"]) == 2
    assert r["agent_completed"] is True
    assert r["redline_candidate_over_2_rounds"] is False


def test_multi_case_run_keeps_attribution_per_case(scripted):
    """多 case 交替时每个 case 的 `asked` 只能来自它自己的脚本——P1-1 的覆盖面补测。

    两条脚本**形态不同**（C01 首轮是争点菜单、其余案首轮是事实澄清），归属一旦串到别的 case，
    两案的 asked 序列就会互换，比"没有无主请求"的绊线多一层可观察判别量。

    ⚠️ 这是**覆盖面测试，不是 P1-1 的红绿锁**（2026-09-18 代码审查 (a)1 的如实定性，已实测确认）：
    `gate2_runner.py` 无任何线程/并发（grep 无 `Thread` / `max_workers`），串行多 case 下旧
    `_last_case` 每次遇到初始题都会刷新，于是猜的答案**照样正确**。实测
    （`_p11_watch_it_fail.py` 把归属改回猜法）：本测试仍绿，同批 5 个端到端测试全绿，
    只有顺序无关的那个单测变红。故本测试锁的是"将来引入并发或多 case 交替时不要串味"，
    不是"这次修对了"——真锁 P1-1 的是
    `test_scripted_service_resume_attribution_is_order_independent`。
    """
    tmp_path, service, _port = scripted
    other = next(cid for cid in runner.BY_ID if cid != "C01")
    service.set_script("C01", ("scope", "clarify_once", "final"))
    service.set_script(other, ("clarify_once", "nomatch_prompt", "final"))

    assert _run_scripted(scripted, "--case", f"C01,{other}") == 0
    _assert_attribution_clean(service)
    sessions = json.loads((tmp_path / "gate2-run-t6-run-sessions.json").read_text(encoding="utf-8"))
    asked1 = sessions["results"]["C01"]["asked"]
    asked2 = sessions["results"][other]["asked"]

    assert len(asked1) == len(asked2) == 2, f"两案应各应答 2 轮：C01={asked1} {other}={asked2}"
    prompts1 = [a["prompt"] for a in asked1]
    prompts2 = [a["prompt"] for a in asked2]
    # 争点菜单只属于 C01；事实追问只属于 other——串味时这两行必然同时炸。
    assert "争点" in prompts1[0] and "争点" not in prompts2[0], f"asked 串味：{prompts1} / {prompts2}"
    assert "司法鉴定资质" in prompts2[1], f"{other} 第 2 轮应是未命中的事实追问：{prompts2}"


def test_scope_budget_exhaustion_aborts_run_without_hanging(scripted):
    """P2-1（2026-09-18）：服务端连发 3 次 scope 索要时，runner 必须停在 `scope_used` 守卫上。

    覆盖对象 = `gate2_runner.py:496-498`（守卫判据文字：`scope_used >= SCOPE_CLARIFY_LIMIT`；
    行号会随文件漂移，认这段文字为准）。本测试之前全文件 6 处 `set_script` 实参（去重后 5 条序列）
    逐条枚举，**没有一条能走进这个守卫**：`(scope,nomatch_prompt,clarify_once)` 只有 1 次 scope、
    `(clarify_once,)*50` 与 `(clarify_once,nomatch_prompt,final)` 从未索要争点、
    `(scope,clarify_once,final)`×2 只有 1 次 scope；最接近的是 `(scope,scope,clarify_once)`——
    它第 3 轮确实带着满格的 `scope_used` 回到循环顶部，但那一条 prompt 是事实追问，走的是 `else`
    分支的 fact 守卫，scope 守卫仍然一次都没执行到。此处"零覆盖"是**按脚本枚举推定**，
    不是覆盖工具实测：本环境 `--cov` 两次尝试均 `Module was never imported`（见 handover §13.3），
    故证明力完全来自下一条的删守卫实验。

    ⚠️ 本测试**不是缺陷复现**：守卫行为本来就对，写完直接跑就是绿的，"先红"在这里做不到，
    也不必假装做到。它的证明力全部来自**定向删守卫**
    （`dispatch-output/ta5-arms-20260917/_p21_watch_it_fail.py`）：删掉 :496-498 ⇒ 第 3 次
    scope 索要被应答掉 ⇒ `asked` 2→3、`agent_completed` False→True ⇒ 本测试变红。

    为什么只能 `break`、不能 `continue`：循环靠"发应答→取新事件"推进，不应答第 3 次索要时
    同一个 clarification 会原地转到无限。所以"scope 预算耗尽即终态退出"是唯一不自指的走法，
    代价是同时放弃了剩余的 fact 预算（本测试把该后果一并钉住，防止将来被"顺手优化"掉）。
    """
    tmp_path, service, _port = scripted
    service.set_script("C01", ("scope", "scope", "scope"))

    assert _run_scripted(scripted, "--case", "C01") == 0
    _assert_attribution_clean(service)
    sessions = json.loads((tmp_path / "gate2-run-t6-run-sessions.json").read_text(encoding="utf-8"))
    r = sessions["results"]["C01"]

    assert len(r["asked"]) == 2, f"scope 预算 2 格耗尽后第 3 次索要不应被应答；实际 asked={r['asked']}"
    assert r["agent_completed"] is False, "服务端停在 scope 索要上，没有终稿可声称完成"
    assert r["redline_candidate_over_2_rounds"] is True, "已应答 2 次 + 未应答 1 次 = 第 3 次追问 → 红线"
    assert len(service.chat_requests) == 3, "请求数上界 = 初始题 + 2 次 scope 应答；再多即守卫失效在空转"
