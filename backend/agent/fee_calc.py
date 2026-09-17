"""受控计算（T-A3(b)，Owner 授权 2026-09-17）：案件受理费确定性计算。

数据真源 = knowledge_base/fee_formulas.json（《诉讼费用交纳办法》第13条累计递进费率
+ 第16条简易程序减半）。纯函数、无 IO 副作用、无模型调用；加载失败返回 None（fail-open）。

接入口径（预注册，numeric_matching_v2 开启时生效）：
- 标的额 = 全 state 已确认事实 + 未决事实文本中**最大的货币金额**（T-A0 口径：
  诉讼请求金额取事实中最大货币额；提取错误 → 计算值与 claim 数字不匹配 → 拒，fail-closed 方向）。
- 放行集 = {normal, simplified} 两组金额 token——claim 数字命中其一即视为受控来源。
- 防幻觉边界不变：计算集之外的新数字仍拦。
"""

from __future__ import annotations

import json
import re
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from pathlib import Path

_FORMULAS_PATH = Path(__file__).resolve().parent.parent / "knowledge_base" / "fee_formulas.json"

_YUAN_RE = re.compile(r"(?:人民币\s*)?(\d[\d,]*(?:\.\d+)?|[零〇○一二两三四五六七八九十]+)\s*万?元")


@lru_cache(maxsize=1)
def _load_formulas() -> dict | None:
    try:
        data = json.loads(_FORMULAS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data.get("case_acceptance_fee"), dict):
        return None
    return data["case_acceptance_fee"]


def case_acceptance_fee(amount_yuan: Decimal) -> dict[str, int] | None:
    """标的额 → {"normal": 普通程序受理费, "simplified": 简易程序减半}；公式表缺失 → None。

    口径（办法第13条，锚点冒烟修正 2026-09-17）：每件 **50 元基础费固定收取**，
    超过 1 万元的部分按递进费率累加（如 5 万 = 50 + 40000×2.5% = 1050）。
    """
    spec = _load_formulas()
    if spec is None or amount_yuan < 0:
        return None
    brackets = spec["brackets"]
    base = Decimal(str(spec["base"]))
    lower = Decimal(str(spec["base_upto"]))
    fee = base
    if amount_yuan > lower:
        for b in brackets:
            upto = b["upto"]
            upper = Decimal(str(upto)) if upto is not None else None
            rate = Decimal(str(b["rate"]))
            if upper is None or amount_yuan <= upper:
                fee += (amount_yuan - lower) * rate
                break
            fee += (upper - lower) * rate
            lower = upper
    normal = int(fee.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    simplified = normal // 2 if spec.get("simplified_half") else normal
    return {"normal": normal, "simplified": simplified}


def largest_amount_yuan(texts: list[str]) -> Decimal | None:
    """一组文本中的最大货币金额（元）；无货币金额 → None。

    仅匹配「N元 / N万元」形态（受控口径）；口语「N万块」由调用方先经归一文本进入。
    """
    best: Decimal | None = None
    for text in texts or []:
        for m in _YUAN_RE.finditer(text):
            raw = m.group(1).replace(",", "")
            try:
                value = Decimal(raw)
            except Exception:  # noqa: BLE001 — 中文数字兜底
                continue
            if "万" in m.group(0):
                value *= Decimal(10000)
            if best is None or value > best:
                best = value
    return best


def controlled_fee_tokens(fact_texts: list[str]) -> set[str]:
    """受控计算放行集：标的额 → normal/simplified 两组金额 token（amount:N:万 / amount:N:元 / number:N）。

    numeric_matching_v2 开启时并入 writer 事实数字白名单与 verifier 验算。
    公式表缺失 / 事实无货币金额 → 空集（fail-open）。
    """
    spec = _load_formulas()
    if spec is None:
        return set()
    amount = largest_amount_yuan(fact_texts)
    if amount is None or amount <= 0:
        return set()
    fees = case_acceptance_fee(amount)
    if not fees:
        return set()
    tokens: set[str] = set()
    for value in fees.values():
        v = Decimal(value)
        if v >= 10000 and v % 10000 == 0:
            wan = v / 10000
            tokens.add(f"amount:{_fmt(wan)}:万")
        tokens.add(f"amount:{_fmt(v)}:元")
        tokens.add(f"number:{_fmt(v)}")
    return tokens


def _fmt(d: Decimal) -> str:
    d = d.normalize()
    s = format(d, "f")
    return s
