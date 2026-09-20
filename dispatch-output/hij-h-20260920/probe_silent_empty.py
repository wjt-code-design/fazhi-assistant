"""分枝 5 的前提核验：合同分支"三次全空"之后，控制流到底去哪？（只读，不写库）

票 H 的取证用例断言 `_contents(empty)==[] 且 _errors(empty)==[]` ⇒ 得出「用户一片空白」。
但缩进显示 `if answer:`（16 格）**没有 else**，其 body 末尾是 `return`（只在**非空**时执行）
⇒ 空答会**落到分支1/分支2**（12 格的兄弟分支）⇒ 测试里的静默可能只是**桩的假象**
（`_FakeChainEmpty` 在回落路径里同样不产内容）。

判据（决定性的、可观测的）：回落路径**必有副作用** —— `routing_metrics.record`（tier=flag/light）
与分支1/2 的 `log_account`（tier 不是 contract_review）。把 `log_account` 换成记录器，
看收到的 tier 序列即可判定：
  - 若出现 `flag`/`light` ⇒ **确实回落**（"静默空"的真实形态是"静默降级成普通回答"）；
  - 若只有 `contract_review` ⇒ 真的静默（票 H 的前提成立）。
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "backend" / "tests"))

from dotenv import load_dotenv

load_dotenv(REPO / "backend" / ".env")

from tests._sse_harness import chat_frames, login, sse_client
from tests.test_contract_exit_gates import _FakeChainEmpty

QUESTION = "帮我审一下这份租赁合同"


class _FakeMP:
    """pytest `monkeypatch` 的最小替身（探针一次性跑完就退，不需要 undo）。

    覆盖 `_sse_harness` 用到的三类方法：setattr / setenv / delattr。
    """

    def setattr(self, target, name, value, raising=True):
        setattr(target, name, value)

    def setenv(self, name, value):
        os.environ[name] = value

    def delenv(self, name, raising=True):
        os.environ.pop(name, None)

    def delattr(self, target, name, raising=True):
        delattr(target, name)


def main() -> int:

    recs: list[dict] = []
    out: dict = {"log_tiers": None, "contents": None, "errors": None}

    with sse_client(_FakeMP(), route="contract_review") as c:  # type: ignore[arg-type]
        import main as m2

        m2.log_account = lambda **kw: recs.append(kw)  # type: ignore[assignment]
        m2.make_chain = lambda llm: _FakeChainEmpty()  # 三次全空（与票 H 取证同桩）
        token = login(c)
        frames = chat_frames(c, token, QUESTION)

    out["log_tiers"] = [r.get("tier") for r in recs]
    out["log_kinds"] = [r.get("kind") for r in recs if r.get("kind")]
    payload = [
        json.loads(f[len("data: ") :])
        for f in frames
        if f.startswith("data: ") and f[len("data: ") :].strip() not in ("", "[DONE]")
    ]
    payload = [p for p in payload if isinstance(p, dict)]
    out["contents"] = [p.get("content") for p in payload if "content" in p]
    out["errors"] = [p.get("error") for p in payload if "error" in p]
    out["frame_keys"] = [sorted(p.keys()) for p in payload]

    (HERE / "24-silent-empty-probe.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8", newline=""
    )
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
