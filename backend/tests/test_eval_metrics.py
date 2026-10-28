from eval_metrics import citation_correct, citation_present, recall_at_k


def test_recall_at_k():
    assert recall_at_k(["第十九条", "第二十条"], ["第十九条"]) == 1.0
    assert recall_at_k(["第二十条"], ["第十九条"]) == 0.0
    assert recall_at_k(["第十九条", "第二十条"], ["第十九条", "第一百八十八条"]) == 0.5
    assert recall_at_k([], ["第十九条"]) == 0.0
    assert recall_at_k(["第十九条"], []) == 0.0


def test_citation_correct():
    assert citation_correct("根据《劳动合同法》第十九条，最长六个月。", ["第十九条"]) is True
    assert citation_correct("依据《民法典》第一百八十八条，三年。", ["第一百八十八条"]) is True
    assert citation_correct("大概六个月吧，没查条文。", ["第十九条"]) is False


def test_citation_correct_composite():
    # 合成引用：同一书名号后顿号续写的条号也要算命中（回归 q119 的 cite_ok 假阴性——
    # 旧正则只取书名号紧跟的首个条号，第六十九条明明写了却判未命中）
    ans = "依据《海事诉讼特别程序法》第十七条、第五十八条、第六十九条。"
    assert citation_correct(ans, ["第六十九条"]) is True
    assert citation_correct(ans, ["第十七条"]) is True
    assert citation_correct(ans, ["第七十条"]) is False


def test_citation_correct_thousand_articles():
    # 千位条号（民法典 1000 条以后）：旧正则字符集漏了「千」，1127/1195/1213 一律匹配不到，
    # 明明引对也判 cite_ok=0（2026-10-26 重跑基线时实测：4 道千位题全部假阴性）
    assert citation_correct("依据《民法典》第一千一百二十七条。", ["第一千一百二十七条"]) is True
    assert citation_correct("依据《民法典》第一千二百一十三条。", ["第一千二百一十三条"]) is True
    assert citation_correct("《刑法》第一百三十三条之一。", ["第一百三十三条之一"]) is True


def test_citation_present():
    assert citation_present("见《民法典》第一百八十八条") is True
    assert citation_present("没有引用任何条文") is False
