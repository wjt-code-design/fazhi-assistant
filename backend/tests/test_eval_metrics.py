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


def test_citation_present():
    assert citation_present("见《民法典》第一百八十八条") is True
    assert citation_present("没有引用任何条文") is False
