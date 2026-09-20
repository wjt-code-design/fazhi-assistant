"""I-1 台架 B：E2 的**直返触发率**（本地 embedder，零 API、零 live 写入）。

先说清这台仪器**能**答什么、**不能**答什么，别在回报里越界：
- 能答：给定一份题面，E2 那条链路（`search_qa` → 0.92 门 → 指纹门 → 证据时效门 →
  `main._qa_direct_return`）会不会真的直返。判定的**被调函数就是真码本身**（从副本树 import），
  不是我照抄的第二份实现。
- 不能答：线上真实命中率。本地没有生产流量分布，所以 B1/B2/B3 各给一个**口径不同**的数，
  分开报，不合并成一句"x%"。
- `search_qa(query, threshold=0.0)` 与生产（默认 0.7）对"是否会直返"是**等价的**：
  下游硬门是 0.92 > 0.7，任何能过 0.92 的候选必然也过 0.7。用 0.0 只是为了看见分布。
"""

from __future__ import annotations

import json
import os
import pathlib
import random
import sys

HERE = pathlib.Path(__file__).resolve().parent
COPY_BACKEND = pathlib.Path(os.environ["I1_COPY_BACKEND"])
OUT = HERE / "probe-B-direct-return-rate.json"
sys.path.insert(0, str(COPY_BACKEND))
os.chdir(COPY_BACKEND)

THRESHOLD = 0.92  # 生产值；由 main._QA_DIRECT_RETURN_THRESHOLD 复核，不匹配就停

# B3 负例：产品另一条真实通道（用户自述式咨询）的形状，以及**语料未覆盖部门法**的题面。
# 这些是我手写的（不是从语料变出来的），所以它们测的是"误命中"，不是"覆盖"。
NEG_CONSULT = [
    "我租的房子到期了房东不肯退押金，还把我东西锁屋里，我能要求赔偿吗",
    "公司拖欠三个月工资没签合同，我现在离职还能要回工资吗",
    "老公出轨我要离婚，孩子归谁房子怎么分",
    "网上买的减肥吃了对身体造成伤害，我要退货退款还要赔医药费怎么办",
    "朋友借我两万块钱到现在不还，只有微信聊天记录能起诉吗",
    "楼上漏水把我家泡了，物业和业主互相推，我该找谁赔",
    "我被公司无故辞退了，经济补偿应该怎么算",
    "培训机构倒闭了剩下的课时费能退吗，他们说要走流程",
    "买车交了定金后来不想买了，定金能要回来吗",
    "邻居家的树长到我院子还挡光，能让他砍了吗",
    "我在健身房办了年卡现在想退，合同写着不退合法吗",
    "父母去世后房子登记在父亲一个人名下，母亲和子女怎么继承",
    "司机追尾我全责走保险，对方要的精神损失费我该不该给",
    "中介收了服务费不办事，投诉无果能起诉吗",
    "邻居养大型犬不牵绳咬伤我家孩子，赔偿谁负责",
    "工地受伤没有劳动合同，只有工友的证人证言，能认定工伤吗",
    "网贷平台砍头息加上违约金算下来年化超过24%，我还要不要还",
    "二手房卖家房价涨了宁可赔违约金也不过户，我能强制过户吗",
    "我在小区里被高空抛物砸到车，找不到具体是谁扔的，能要求全楼赔吗",
    "用人单位要求员工下班后回微信算加班吗",
    "合伙开店一方私自拿营业额，另一方可以要求返还吗",
    "车辆年检过期出了事故，保险公司可以据此拒赔吗",
    "遗嘱把房子只给小儿子，另外两个子女能要求必要份吗",
    "网购七天无理由退货，商家说拆封了不退，符合规定吗",
]
NEG_MCQ_OUTSIDE = [
    "根据《海商法》，承运人对集装箱装运货物的责任期间是？A.从装货港接收货物时起至卸货港交付货物时止 B.货物装上船时至卸下船时止 C.从货物进入承运人掌管时起至交付时止 D.自托运人交货时起至收货人提货时止",
    "根据《票据法》，下列哪一票据行为无效？A.附条件的背书 B.委托收款背书 C.质押背书 D.期后背书",
    "根据《企业破产法》，破产财产分配方案应由谁通过后执行？A.债权人会议 B.管理人 C.人民法院裁定 D.债务人",
    "根据《著作权法》，合理使用的情形不包括下列哪一项？A.为个人学习研究使用他人已发表作品 B.为报道新闻不可避免地再现作品 C.免费表演已发表作品且不向公众收费 D.将中文作品翻译成外文出版",
    "根据《反垄断法》，经营者集中达申报标准未申报的法律责任是？A.由反垄断执法机构责令停止实施并处上一年度销售额10%以下罚款 B.仅警告 C.处五十万元以下罚款 D.由工商部门撤销合同",
    "根据《证券法》，上市公司信息披露义务人未及时披露重大事件的，监管机构可采取的措施不包括？A.责令改正 B.警告并处罚款 C.吊销营业执照 D.市场禁入",
    "根据《民事诉讼法》，关于举证期限，下列哪一说法是正确的？A.由法院指定或当事人协商经法院准许 B.一律三十日 C.逾期举证一律不予采纳 D.只能由当事人协商",
    "根据《刑法》，关于正当防卫的限度条件，下列说法正确的是？A.不能明显超过必要限度造成重大损害 B.只要受到侵害即可无限防卫 C.对财产犯罪可以无限防卫 D.防卫过当一律负刑事责任但不处罚",
    "根据《行政诉讼法》，下列哪一行为属于行政诉讼受案范围？A.行政机关对工作人员的奖惩任免决定 B.行政指导 C.吊销许可证 D.国家行为",
    "根据《保险法》，投保人故意不履行如实告知义务的，保险人正确的处理方式是？A.解除合同且不退还保险费 B.解除合同并退还保险费 C.合同无效 D.承担部分保险责任",
    "根据《合伙企业法》，普通合伙人对合伙企业债务承担何种责任？A.有限责任 B.以其认缴出资为限 C.无限连带责任 D.按份责任",
    "根据《劳动合同法》关于竞业限制的规定，下列哪一说法错误？A.期限不得超过二年 B.应给予经济补偿 C.对所有劳动者均可约定 D.违约可约定违约金",
]

PERTURB_STEMS = [
    ("下列说法正确的是？", "下列哪一选项是正确的？"),
    ("下列说法正确的是？", "关于上述情形，正确的判断是？"),
    ("根据", "依据"),
]


def _perturb_drop_options(q: str) -> str:
    for mark in (" A.", " A、", " A．", "A."):
        if mark in q:
            return q.split(mark)[0].strip()
    return q.strip()


def _perturb_reword(q: str) -> str:
    out = q
    for a, b in PERTURB_STEMS:
        out = out.replace(a, b, 1)
    if out == q:
        out = "请问，" + q
    return out


def main() -> int:
    import knowledge_service as ks
    import main  # 副本树里那份，b40076b 已提交版本

    report: dict = {"threshold_in_main": main._QA_DIRECT_RETURN_THRESHOLD}
    if main._QA_DIRECT_RETURN_THRESHOLD != THRESHOLD:
        print(json.dumps({**report, "ABORT": "阈值与票面口径不符"}, ensure_ascii=False))
        return 4
    report["qa_is_cosine"] = ks._qa_is_cosine()

    col = ks._qa_store._collection
    got = col.get(include=["documents", "metadatas"])
    qs = [d or "" for d in (got["documents"] or [])]
    sources = {}
    for m in got["metadatas"] or []:
        ev = (m or {}).get("evidence", "") or ""
        s = ev.split("|", 1)[0].strip() if "|" in ev else ""
        if not s and ev.lstrip().startswith("["):
            try:
                s = ((json.loads(ev) or [{}])[0] or {}).get("source", "")
            except Exception:  # noqa: BLE001  坏 JSON 只让这一条归到 "?" 桶，不打断全量清点
                s = ""
        sources[s or "?"] = sources.get(s or "?", 0) + 1
    report["corpus_size"] = len(qs)
    report["corpus_evidence_sources_top"] = sorted(
        sources.items(), key=lambda kv: -kv[1]
    )[:12]

    def chain(query: str) -> dict:
        """一次 embed，两条读数：0.92 门的原始分 + 真码 `_qa_direct_return` 的最终决定。"""
        qa = ks.search_qa(query, threshold=0.0)
        pre = {"qa_hit": qa, "rewritten": query}
        fired = main._qa_direct_return(pre) is not None
        return {"score": (qa or {}).get("score", 0.0), "fired": fired}

    # B1 自问（仪器有效性 + 上限）
    rng = random.Random(20260920)
    self_scores = []
    for q in qs:
        r = chain(q)
        self_scores.append(r["score"])
        if r["score"] < 0.9:
            self_scores[-1] = r["score"]
    report["B1_selfquery"] = {
        "n": len(self_scores),
        "min": min(self_scores),
        "mean": round(sum(self_scores) / len(self_scores), 4),
        "ge_092": sum(1 for s in self_scores if s >= THRESHOLD),
    }
    report["B1_instrument_valid"] = bool(self_scores) and min(self_scores) >= 0.9
    if not report["B1_instrument_valid"]:
        print(json.dumps(report, ensure_ascii=False, indent=1))
        OUT.write_text(
            json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        return 5  # 语料向量与当前 embedder 不同空间 ⇒ 后面的数全部不可信

    # B2 覆盖探针：从语料题面出发做**确定性改写**（剥选项 / 换问法），模拟"同一问法的另一种说法"
    sample = rng.sample(qs, min(60, len(qs)))
    b2 = {"drop_options": [], "reword": []}
    for q in sample:
        b2["drop_options"].append(chain(_perturb_drop_options(q)))
        b2["reword"].append(chain(_perturb_reword(q)))
    report["B2_coverage_probe"] = {
        k: {
            "n": len(v),
            "fired": sum(1 for x in v if x["fired"]),
            "ge_092": sum(1 for x in v if x["score"] >= THRESHOLD),
            "mean_score": round(sum(x["score"] for x in v) / len(v), 4),
        }
        for k, v in b2.items()
    }

    # B3 误命中：手写咨询体 + 语料未覆盖部门法
    b3c = [chain(q) for q in NEG_CONSULT]
    b3m = [chain(q) for q in NEG_MCQ_OUTSIDE]
    report["B3_false_fire"] = {
        "consult": {
            "n": len(b3c),
            "fired": sum(1 for x in b3c if x["fired"]),
            "ge_092": sum(1 for x in b3c if x["score"] >= THRESHOLD),
            "max_score": max(x["score"] for x in b3c),
        },
        "mcq_outside": {
            "n": len(b3m),
            "fired": sum(1 for x in b3m if x["fired"]),
            "ge_092": sum(1 for x in b3m if x["score"] >= THRESHOLD),
            "max_score": max(x["score"] for x in b3m),
        },
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
