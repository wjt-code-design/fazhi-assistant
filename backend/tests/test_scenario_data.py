"""scenario_supplements.json 数据一致性校验（非 slow，CI 必跑；零 BGE 零检索）。

对抗审计 v2 #16：补充组数据文件此前只有 @slow 测试覆盖（CI 用 -m 'not slow' 跳过），
数据误改（关键词删除/条文缺字段/跨组重复膨胀）零 CI 防护。本文件只做纯 JSON 结构断言：
  (a) 每组 ≥1 关键词、≥1 条文；
  (b) 条文 (source, article) 字段完整、条号为中文数字格式；
  (c) 关键词不跨组重复（白名单 = 故意共享的法律领域词，如交通/治安/刑诉/民诉共同词）。
在库（exact_article_lookup）校验仍在 @slow 的 test_scenario_supplement.py 中（需拉 BGE）。
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scenario_supplements.json")

# 故意共享的领域词（交通刑事/行政、刑诉/民诉共同程序词、刑法/治安重叠词）——允许跨组，白名单防误报
SHARED_WHITELIST = {
    "二审",
    "再审",
    "简易程序",
    "罚款",
    "社保",
    "超速",
    "追尾",
    "逃逸",
    "逆行",
    "酒驾",
    "醉驾",
    "闯红灯",
    "交通事故",
    "撞人",
    "殴打",
    "寻衅滋事",
    "骚扰",
}

_ART_RE = re.compile(r"^第[零〇○一二三四五六七八九十百千万0-9０-９]+条(?:之[一二三四五六七八九十百千万0-9０-９]+)?$")


def _load():
    with open(DATA, encoding="utf-8") as f:
        return json.load(f)


def test_each_group_has_keywords_and_articles():
    data = _load()
    assert data, "补充组数据不应为空"
    for g in data:
        assert g.get("scenario"), f"组缺 scenario: {g}"
        assert g.get("keywords"), f"{g['scenario']} 缺关键词"
        assert g.get("articles"), f"{g['scenario']} 缺条文"


def test_articles_field_shape():
    data = _load()
    for g in data:
        for a in g["articles"]:
            assert a.get("source") and a.get("article"), f"{g['scenario']} 条文缺字段: {a}"
            assert _ART_RE.match(a["article"]), f"{g['scenario']} 条号应为中文数字: {a['article']}"


def test_no_cross_group_keyword_duplication():
    from collections import defaultdict

    data = _load()
    kw2grp = defaultdict(list)
    for g in data:
        for k in g["keywords"]:
            kw2grp[k].append(g["scenario"])
    dups = {k: v for k, v in kw2grp.items() if len(set(v)) > 1}  # 组内重复不算（无害冗余）
    unexpected = {k: v for k, v in dups.items() if k not in SHARED_WHITELIST}
    assert not unexpected, f"关键词跨组重复（非白名单）: {unexpected}"


def test_undetermined_period_groups_keep_510_511():
    """2026-10-21 评审案：未定期限的借贷/时效题必须定向补充 510/511。

    锁的是"可修性"而非具体实现：510（补充确定履行期限）与 511（期限不明确的兜底）
    是"未写还款日期→时效起算点"这条链上唯一在库的入口条文；删掉它们，模型仍会退回
    "直接套 188 条三年 + 用 195 条当中断"的老病灶（见 docs 评审报告 5.1）。
    纯数据断言，零 BGE，CI 必跑。
    """
    data = _load()
    by_scenario = {g["scenario"]: g for g in data}
    for name in ("private_lending", "limitation_period"):
        assert name in by_scenario, f"缺场景组 {name}"
        arts = {a["article"] for a in by_scenario[name]["articles"]}
        assert {"第五百一十条", "第五百一十一条"} <= arts, f"{name} 缺 510/511: {sorted(arts)}"


def test_civil_procedure_carries_burden_of_proof_article():
    """民诉法举证责任条文必须是第 67 条，不是第 68 条（2026-10-21 评审案 5.3）。

    现场缺陷：civil_procedure 组配了 66（证据种类）与 68（举证期限），唯独漏 67
    （"当事人对自己提出的主张，有责任提供证据"）⇒ 答案里出现"依第 68 条，谁主张谁举证"
    的条号错配。68 保留无妨（举证期限确属同一场景），但 67 不得再缺。
    """
    data = _load()
    by_scenario = {g["scenario"]: g for g in data}
    arts = {a["article"] for a in by_scenario["civil_procedure"]["articles"]}
    assert "第六十七条" in arts, f"civil_procedure 缺民诉法 67 条（举证责任）: {sorted(arts)}"
