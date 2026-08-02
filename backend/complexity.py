"""复杂度分级路由（M1 准入 + 路由决策）：纯函数、零 LLM。

- assess(...) -> (modality, tier)：模态（text/vision）+ 等级（light/flag）。
- admit_light(...) -> bool：轻量准入闸——全部条件满足才放行轻量，宁误伤不误放
  （误伤只多花配额；误放由 quality.self_check + 升级旗舰兜住）。

意图与等级：
- cheating_request → 固定 light（短拒答模板，省配额）
- study_aid → 固定 flag（学习引导需推理质量）
- legal_query → 按长度 / 高利害词 / 多轮判断

图片（vision）：默认保守走旗舰，由路由层「Flash 看图 → 描述简单才降轻量」两级预判细化。
"""
from domain_rules import COMPLEX_KEYWORDS, LIGHT_SHORT_LEN


def _len_complex(text: str) -> bool:
    return len(text or "") > LIGHT_SHORT_LEN


def _keyword_hit(text: str) -> bool:
    t = text or ""
    return any(k in t for k in COMPLEX_KEYWORDS)


def _multi_turn(recent) -> bool:
    return bool(recent)  # 有历史消息 = 多轮 = 隐含复杂


def assess(text: str, has_image: bool, intent: str, recent) -> tuple[str, str | None]:
    """返回 (modality, tier)。图片 tier 为 None（待路由层预判后定）。"""
    if has_image:
        return "vision", None  # 保守交给两级预判
    if intent == "cheating_request":
        return "text", "light"
    if intent in ("study_aid", "chitchat"):
        # study_aid 需推理质量；chitchat 固定旗舰流式（不走 light 缓冲与自检，避免闲聊被质检/升级误伤）
        return "text", "flag"
    # legal_query
    complex = _len_complex(text) or _keyword_hit(text) or _multi_turn(recent)
    return "text", ("flag" if complex else "light")


def admit_light(
    text: str,
    has_image: bool,
    intent: str,
    recent,
    context_hit: bool,
) -> bool:
    """轻量准入闸：全部满足才放行（法律咨询 + 无图 + 单轮 + 检索命中 + 短文本 + 无高利害词）。"""
    if intent != "legal_query":
        return False
    if has_image:
        return False
    if not context_hit:  # 检索必须命中（有据可答），防轻量凭空编造
        return False
    if _multi_turn(recent):
        return False
    if _len_complex(text):
        return False
    if _keyword_hit(text):
        return False
    return True
