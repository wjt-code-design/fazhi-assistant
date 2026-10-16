"""部署侧健康等待窗与 `/healthz` 的**接线判据**（C17 已按推荐执行：`start_period` 60s ⇒ 120s）。

为什么要这两条：
① `prewarm()` 现在会解析嵌入模型（A12，2026-10-16 更优解轮把"补回嵌入预热"折进启动路径），
   本机代理读数把启动墙推到**约 53 s**（拆解与"没在真机/真语料上量过"的交底见
   `reports/w01-w02-delivery.md:373` 与 `gates.md:83-84`）。原 `start_period: 60s` 只剩 7 s 余量，
   而目标机是 2 核 4G——**只会更慢**。等待窗一小于启动墙，容器就被标 unhealthy，
   而 `frontend.depends_on.backend.condition=service_healthy` 让下游跟着等 ⇒
   这是一个**会自己撒谎的监控读数**（`记忆：撒谎的监控比没有监控更危险`）。
② 更要紧的是第二只文件里那条**接线**：compose 的健康检查是按**字符串 URL** 打 `/healthz` 的，
   应用侧改路由名不会让 compose 变红——它只会在真机上表现为"永远 unhealthy"。
   所以这里钉的是"两边指的是同一个路径"，不是"compose 写对了"。

⚠️ 这两条都是**防漂移钉子**：它们不证明真机启动时间（那个数只能在目标机上量），
   也不证明健康检查真能通过（`/healthz` 还要求 DB＋向量库＋LLM 主机三项，见 `main.py:329-348`）。
   在册的 53 s 是代理值 ⇒ 下界按"两倍于代理值"取，真机读数出来后要一起复核这个数。
"""

import os
import re
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import main  # noqa: E402

COMPOSE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), os.pardir, "docker-compose.yml")

# 在册代理读数（本机＋合成语料）：约 53 s。下界＝两倍，向上取整到 10 的倍数。
_PROXY_BOOT_S = 53.0
_MIN_START_PERIOD_S = 120


def _compose_backend_healthcheck() -> dict:
    with open(COMPOSE, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    return doc["services"]["backend"]["healthcheck"]


def _duration_to_seconds(text: str) -> int:
    """compose 的时长写法是字符串（`60s`/`1m`）；只认 `<整数><单位>`，其它一律抛。

    这里刻意不做"猜单位"的兼容层：静默把一个读不懂的值当成 0 或 60，
    就等于让判据在它最该红的时候绿。
    """
    m = re.fullmatch(r"\s*(\d+)\s*([smh]?)\s*", str(text))
    if not m:
        raise AssertionError(f"读不懂的 compose 时长写法：{text!r}")
    n, unit = int(m.group(1)), m.group(2)
    return n * {"": 1, "s": 1, "m": 60, "h": 3600}[unit]


def test_start_period_has_margin_over_the_measured_boot():
    """① 等待窗必须 ≥ 2× 已量到的启动墙（代理值 53 s ⇒ 下界 120 s）。"""
    hc = _compose_backend_healthcheck()
    start_period = _duration_to_seconds(hc["start_period"])
    assert start_period >= _MIN_START_PERIOD_S, (
        f"start_period={start_period}s 低于下界 {_MIN_START_PERIOD_S}s："
        f"预热后的启动墙代理读数是 {_PROXY_BOOT_S}s（本机＋合成语料，真机只会更慢），"
        "窗口小于启动墙 ⇒ 容器被标 unhealthy，而前端 depends_on 会跟着永久等待"
    )
    # 另一侧的下界也要钉：抬到"无穷大"不是解决办法——它会把真故障的发现时间一起抹掉
    assert start_period <= 600, f"start_period={start_period}s 已经大到会让真故障永远不被报告"


def test_compose_health_url_points_at_a_route_the_app_registers():
    """② 接线钉子：compose 里那个 URL 的路径必须真是应用注册的路由（改名不会让 compose 变红）。"""
    hc = _compose_backend_healthcheck()
    cmd = " ".join(hc["test"][1:]) if isinstance(hc["test"], list) else str(hc["test"])
    m = re.search(r"https?://[^/']*(/[^'?\" ]*)", cmd)
    assert m, f"健康检查命令里读不出 URL：{cmd!r}"
    path = m.group(1)

    registered = {getattr(r, "path", None) for r in main.app.routes}
    assert path in registered, (
        f"compose 打的 {path!r} 不在应用路由里 ⇒ 真机上表现为『永远 unhealthy』，而这里曾经能绿（因为只比字符串）"
    )
    # 正对照：/healthz 必须在注册集合内（否则上面那条会因为"路由表读空"而假绿）
    assert "/healthz" in registered
