"""选引行为全量门禁（含 LLM，release 前跑，有 token 成本）。

断言 8 个高频场景的回答**按 (法名, 条号) 配对**引对操作性条文 + 无含糊话 + 无误报注解，
并加负向用例：无匹配条文应诚实说"未覆盖"而非编造。配对是必须的：主集合里 第十九条 被 97 部法共用、
第四十四条 87 部，回答里出现一个裸条号根本不构成"引对了这部法的这条"。

判据本体（`citation_pairs` / `answer_cites`）由 `tests/test_smoke_citation_assertions.py`
用假回答钉住；本文件**不 import `retrieval`**——那道门在 release 阶段只走 HTTP，
把 BGE 与 Chroma 拉进 import 期会为一次网络检查付模型加载成本。法名归一因此自带一份窄口径，
由测试钉住它不许与 `retrieval._source_key` 漂移；条号写法由场景表逐条列出可接受形式
（避免复制生产端的中文数字换算器）。

引用形状**先过生产同一对纯函数**再匹配：`output_normalize.expand_law_names` / `expand_citations`
（只依赖 stdlib）。必须门自己做，是因为这两个归一在服务器上跑在**流式之后**的写库路径（`main._post`）里，
而 E5/E8 两条流式出口逐块直发模型原文（那两行的 `# gate-exit:` 注记）⇒ 门累加到的 SSE 文本没被补过。

前置：后端已启动（manage.py start），API key 已配。用法：
  cd backend && python scripts/smoke_citation_full.py
"""

import json
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
sys.path.insert(0, BACKEND)

import output_normalize  # noqa: E402

BASE = "http://localhost:8000"

_PREFIX_CN = "中华人民共和国"
_YEAR_NOTE_RE = re.compile(r"（[^）]*）\s*$")
# 与生产 `retrieval._ART_FULL_RE` 同一截条号形状；两处字面量必须共存，由
# `test_full_citation_pattern_cannot_drift_from_retrieval` 钉住不许分叉。
_ART_CORE = r"第[零〇○一二三四五六七八九十百千万0-9０-９]+条(?:之[一二三四五六七八九十百千万0-9０-９]+)?"
_CITE_RE = re.compile(r"《([^》]{1,24}?)》\s*(" + _ART_CORE + r")")


def norm_law_name(name: str) -> str:
    """法名归一：去"中华人民共和国"前缀、剥尾部年份/修正括注（与 `retrieval._source_key` 同口径）。"""
    name = (name or "").strip()
    if name.startswith(_PREFIX_CN):
        name = name[len(_PREFIX_CN) :]
    return _YEAR_NOTE_RE.sub("", name).strip()


def citation_pairs(answer: str):
    """抽出回答里成对出现的引用，返回 {(归一法名, 条号原文)}。

    先按**生产写库时的同一顺序**过两个纯函数（`main._post`：先补书名号、再展开连续省略条号），
    再按《法名》第X条 邻接抽取。散文里隔开、不在续接形状上的裸条号**不补**——与生产同界，
    门不自己发明"最近书名"归属（`output_normalize` 的注释记着那样做会把合同条款号误补成《最近书名》）。
    """
    text = output_normalize.expand_citations(output_normalize.expand_law_names(answer or ""))
    return {(norm_law_name(m.group(1)), m.group(2)) for m in _CITE_RE.finditer(text)}


def answer_cites(answer: str, expected_source: str, expected_articles):
    """回答是否把 `expected_source` 与其中任一 `expected_articles` 引用成了对（"任中一条"语义保留）。"""
    want = norm_law_name(expected_source)
    pairs = citation_pairs(answer)
    return any(src == want and art in set(expected_articles) for src, art in pairs)


def post(url, payload, token=None):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + token} if token else {})},
    )
    return urllib.request.urlopen(req, timeout=90)


def chat(token, q):
    body = json.dumps({"question": q}).encode()
    req = urllib.request.Request(
        BASE + "/api/chat",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + token},
    )
    c = ""
    for raw in urllib.request.urlopen(req, timeout=120):
        line = raw.decode("utf-8").strip()
        if line.startswith("data:"):
            p = line[5:].strip()
            if p == "[DONE]":
                continue
            try:
                j = json.loads(p)
                if "content" in j:
                    c += j["content"]
            except Exception:
                pass
    return c


# (label, question, 法名, 可接受条号写法)
# 两种写法都得列：提示词与库各用一种，且**同一段提示词里就混着写**
# （`domain_rules.CITATION_SELECTION_RULE` 里「引用《劳动合同法》第八十七条」与「先依《民法典》第496条」同段混写）。
# 不在门里再写一份中文数字↔阿拉伯换算器——那会是第四份判据（`retrieval._normalize_article` 才是真源）。
POSITIVE = [
    (
        "网购退货格式条款",
        "网购相机，商家标注“拆封不退”，买家要求七天无理由退货被拒。商家免责条款有效吗？",
        "民法典",
        ["第四百九十六条", "第496条", "第四百九十七条", "第497条"],
    ),
    ("违法解除赔偿金", "公司违法解除劳动合同，赔偿金怎么算？", "劳动合同法", ["第八十七条", "第87条"]),
    ("合法解除经济补偿", "公司合同到期不续签，经济补偿金怎么算？", "劳动合同法", ["第四十七条", "第47条"]),
    ("试用期上限", "劳动合同试用期最长能约定多久？", "劳动合同法", ["第十九条", "第19条"]),
    ("周末加班费", "周末加班，加班费怎么算？", "劳动法", ["第四十四条", "第44条"]),
    ("交强险赔偿顺序", "机动车发生交通事故，交强险先赔还是商业险先赔？", "民法典", ["第一千二百一十三条", "第1213条"]),
    (
        "定金退不退",
        "交了定金又不想买了，定金能退吗？",
        "民法典",
        ["第五百八十六条", "第586条", "第五百八十七条", "第587条"],
    ),
    ("七天无理由退货", "网购商品七天无理由退货需要满足什么条件？", "消费者权益保护法", ["第二十五条", "第25条"]),
]

# 负向：知识库未覆盖 → 应诚实拒答而非编造（判据是"诚实"，不参与引用配对）
NEGATIVE = [
    ("库外部门规章", "网络借贷信息中介机构业务活动的部门规章有哪些要求？"),
    ("库外司法解释", "最高人民法院关于民间借贷的司法解释对利率上限怎么规定？"),
]

# 轻量准入场景（短+命中+单轮+无高利害词）：验证「省配额走轻量」不降质——
# 轻量答对则直接 PASS；轻量答错会升级旗舰，仍应引对。整体证明路由保质量。
LIGHT_POSITIVE = [
    ("轻量-试用期", "试用期最长多久", "劳动合同法", ["第十九条", "第19条"]),
    ("轻量-七天退货", "七天无理由退货条件", "消费者权益保护法", ["第二十五条", "第25条"]),
]


def main():
    # 凭据与 .env 读取留在 main()：import 期 `sys.exit(2)` 会让"本机没有 .env"的 CI 在测试收集阶段就炸，
    # 而引用判据本体必须能在无凭据、无后端、无模型的环境下被单测 import。
    sys.path.insert(0, BACKEND)
    from dotenv import load_dotenv

    load_dotenv(os.path.join(BACKEND, ".env"))
    admin_pass = os.getenv("ADMIN_PASSWORD", "")
    if not admin_pass:
        print("缺少 ADMIN_PASSWORD（backend/.env 未配置），无法跑 full 门禁", file=sys.stderr)
        sys.exit(2)
    admin = (os.getenv("ADMIN_USERNAME", "admin"), admin_pass)
    token = json.loads(post(BASE + "/api/auth/login", {"username": admin[0], "password": admin[1]}).read())["token"]
    n = fail = 0

    def check(ok, label):
        nonlocal n, fail
        n += 1
        if not ok:
            fail += 1
            print(f"  [FAIL] {label}")
        else:
            print(f"  [PASS] {label}")

    print("=== 正向 8 场景：按 法名×条号 配对引对条文 / 无含糊话 / 无误报 ===")
    for label, q, source, expects in POSITIVE:
        c = chat(token, q)
        ok_cite = answer_cites(c, source, expects)
        ok_vague = ("法律基本原则" not in c) and ("相关规定" not in c)
        ok_note = "未在知识库中检索到" not in c
        check(
            ok_cite and ok_vague and ok_note,
            f"{label}: 引用 {source}×{expects}={ok_cite} 含糊无={ok_vague} 误报无={ok_note}",
        )

    print("=== 负向：库外问题应诚实拒答（不编造）===")
    for label, q in NEGATIVE:
        c = chat(token, q)
        ok_honest = (
            ("未覆盖" in c)
            or ("无法完整回答" in c)
            or ("未收录" in c)
            or ("未涵盖" in c)
            or ("仅能依据" in c)
            or ("未包含" in c)  # S9 改进后的诚实措辞
            or ("司法解释" in c and "当前库" in c)
        )
        check(ok_honest, f"{label}: 诚实拒答={ok_honest} | 前80字: {c[:80].replace(chr(10), ' ')}")

    print("=== 轻量准入场景：省配额走轻量，质量不降（轻量错则升级旗舰，仍应引对）===")
    for label, q, source, expects in LIGHT_POSITIVE:
        c = chat(token, q)
        ok_cite = answer_cites(c, source, expects)
        ok_vague = ("法律基本原则" not in c) and ("相关规定" not in c)
        ok_note = "未在知识库中检索到" not in c
        check(
            ok_cite and ok_vague and ok_note,
            f"{label}: 引用 {source}×{expects}={ok_cite} 含糊无={ok_vague} 误报无={ok_note}",
        )

    print(f"\nfull 门禁：{n - fail}/{n} 通过" + ("，FAIL!" if fail else ""))
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
