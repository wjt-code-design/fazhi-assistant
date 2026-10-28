"""多问试题结构断言（四层验收的第 4 层，2026-10-25 整改对齐会）。

为什么单独一个脚本：`eval_quality.py` 只落盘 recall@4 / cite_ok，不保存答案正文，
而本轮的整改目标（逐问闭环、时间轴、金额核算、覆盖表、分歧披露）全是**文本形态**，
检索与引用指标碰不到。没有这条断言，"改完提示词到底有没有用"就无法证伪。

用法（需后端已启动、.env 有管理员口令）：
    cd backend && python scripts/check_issue_structure.py [--id 159]

退出码 0 = 全部通过；1 = 有断言失败（便于接门禁）。
口径说明：**只看结构与格式，不判法律结论对错**——结论对错由人工/第三方评审负责，
脚本不假装能判。Q1 特意不断言"选哪条路径"：实务本身有分歧，只要求两条并列且各带条件。
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

# override=True 与 main.py 一致：防 Machine 作用域旧 RERANK_API_KEY 压过 backend/.env（2026-10-26）
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"), override=True)

import _client  # noqa: E402

DATA = os.path.join(os.path.dirname(__file__), "..", "..", "data", "eval_external_v1.json")

# 四小节：不要求逐字一致，允许「## 一、时间轴」这类标题前缀
SECTIONS = {
    "时间轴": re.compile(r"时间轴"),
    "金额核算": re.compile(r"金额核算|金额计算"),
    "逐问分析": re.compile(r"逐问|问题\s*1|问题一|第\s*1\s*问|第1问"),
    "覆盖表": re.compile(r"覆盖表|覆盖情况"),
}


def load_case(case_id: int) -> dict:
    cases = json.load(open(DATA, encoding="utf-8"))
    for c in cases:
        if c.get("id") == case_id:
            return c
    raise SystemExit(f"题集里没有 id={case_id}")


def _has_unnegated(ans: str, keywords: tuple[str, ...], window: int = 12) -> bool:
    """关键词出现过，且至少一处前方 window 字内没有否定词。

    只做关键词匹配会把「而非另行起诉…」当成并列路径（2026-10-26 基线实测假阳性），
    所以在命中位置前取一小段上下文排掉否定式表述。
    """
    negations = ("而非", "不是", "无需", "无须", "不必", "不应", "不得", "不宜")
    for kw in keywords:
        start = 0
        while (i := ans.find(kw, start)) >= 0:
            if not any(n in ans[max(0, i - window) : i] for n in negations):
                return True
            start = i + len(kw)
    return False


def _q1_scope(ans: str) -> str:
    """只取「逐问分析」里第一个小问（一、）到第二个小问（二、）之间的正文。

    全局搜关键词会把 Q6 里讨论「需另诉王五」的句子算进 Q1，导致只给一条路径也判通过
    （2026-10-26 离线回测实测）。
    """
    base = ans.find("逐问分析")
    if base < 0:
        return ans
    start = ans.find("一、", base)
    if start < 0:
        return ans[base:]
    end = ans.find("二、", start + 1)
    return ans[start:end] if end > 0 else ans[start:]


def check(ans: str) -> list[tuple[str, bool, str]]:
    results: list[tuple[str, bool, str]] = []
    for name, pat in SECTIONS.items():
        m = pat.search(ans)
        results.append((f"小节存在:{name}", bool(m), "" if m else "未找到对应小节标题"))

    # 格式：全角/半角星号强调都算违规（OUTPUT_FORMAT_RULE）
    stars = ans.count("**")
    results.append(("无**强调", stars == 0, f"出现 {stars} 处 **"))

    # Q1 分歧披露：两条路径并列，不要求选边。
    # 「执行异议之诉」「许可执行之诉」是追加被驳回后的救济，不算并列的第二条路径
    # （2026-10-26 基线复核：旧断言把救济误当路径，答案只给一条路也判 PASS＝假阳性）。
    # 关键词出现还不够：基线答案写的是「而非另行提起…股东损害公司债权人利益责任纠纷诉讼」，
    # 用它**否掉**另一条路；且 Q6 的「需另诉」会被误算进来。
    # 故限定在 Q1 小节内、且命中词前 12 字无否定（2026-10-26 二次收紧）。
    q1 = _q1_scope(ans)
    has_append = "追加" in q1
    has_other = _has_unnegated(q1, ("另行起诉", "另行提起", "另诉", "股东损害公司债权人利益"))
    results.append(
        ("Q1两路径并列", has_append and has_other, "Q1 内缺少未被否定的「另行起诉/另行提起股东损害公司债权人利益」")
    )

    # 结论不得当场推翻：同一小问写到后面另起「结论修正」等于给了两个相反结论
    reversals = [k for k in ("结论修正", "前述结论有误", "前文结论", "更正结论") if k in ans]
    results.append(("结论不自我推翻", not reversals, "出现当场推翻：" + "、".join(reversals)))

    # 覆盖表必须在后段：防止模型把清单前移到开头当目录
    tail = ans[int(len(ans) * 0.6) :]
    results.append(("覆盖表在文末", bool(SECTIONS["覆盖表"].search(tail)), "覆盖表未出现在正文后 40%"))

    return results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", type=int, default=159, help="对外集里的题号（默认 159=六问争点题）")
    ap.add_argument("--out", default="", help="可选：把答案落盘到该路径")
    args = ap.parse_args()

    case = load_case(args.id)
    token = _client.login()
    ans = _client.chat(token, case["question"])

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(ans)

    print(f"[{args.id}] 答案长度={len(ans)}")
    failed = 0
    for name, ok, detail in check(ans):
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  —— {detail}" if detail and not ok else ""))
        failed += 0 if ok else 1
    print(f"\n结果：{'全部通过' if failed == 0 else f'{failed} 项失败'}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
