"""替身向量自身必须满足的性质（C15 分流，2026-10-16；第二版按复核改）。

为什么要有这个文件：`_fake_embeddings` 被二十几条 CI 用例共用，而它一旦"不像假向量"，
后果不是红而是**更绿**——

* 旧实现用内置 `hash()` 做种子，CPython 按进程加盐 ⇒ 同文本每次运行向量不同，
  docstring 却写"确定性"（跨运行无法复算）；
* 旧实现在 `[0,1)` 取正值 ⇒ 任意两段无关法律文本余弦 0.72–0.77（复核实测复现过这个区间），
  高于产品自己的 QA 命中线（`knowledge_service.search_qa` threshold=0.7）、也高于
  `retrieval.vector_top` 实际存在的任何下限（那里根本没有分数下限）⇒ 替身文档会排到真实条文
  之前，而任何"QA 命中"式断言会由替身自己证明。

第一版里有两条断言被复核判为"永远不会红"，已换掉（记录在报告补记 C-2 的 D-3 表里）：
- "同文本两次相等"在同一进程内对旧实现也成立（`hash()` 在进程内是稳定的）⇒ 换成立项跨进程检查；
- `cos(v, v) == 1` 对任意非零向量恒真 ⇒ 换成"批量接口与逐条接口必须一致"这种真能红的判据。
"""

from __future__ import annotations

import math
import os
import subprocess
import sys

import pytest

from tests._fake_embeddings import FakeEmbeddings

TEXTS = {
    "tort": "从建筑物中抛掷物品造成他人损害的，由侵权人依法承担侵权责任。",
    "contract": "当事人一方不履行合同义务或者履行合同义务不符合约定的，应当承担违约责任。",
    "labor": "用人单位与劳动者建立劳动关系，应当订立书面劳动合同。",
    "company": "股东未履行或者未全面履行出资义务，公司或者其他股东可以请求其向公司依法全面履行出资义务。",
}

_PROBE = (
    "import hashlib,sys;"
    "from tests._fake_embeddings import FakeEmbeddings;"
    "v=FakeEmbeddings().embed_query(sys.argv[1]);"
    "print(hashlib.sha256(','.join(f'{x:.12f}' for x in v).encode()).hexdigest()[:16])"
)


def _fingerprint(text: str, seed: str) -> str:
    """在**独立进程**里取同一文本的向量指纹（跨进程才测得出 `hash()` 加盐这件事）。

    只覆盖 PYTHONHASHSEED，其余环境原样传：Windows 上抹掉 `SYSTEMROOT` 之类会让子 python 起不来，
    那时错的是探针而不是被测物。
    """
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = seed
    proc = subprocess.run(
        [sys.executable, "-B", "-c", _PROBE, text],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    assert proc.returncode == 0, f"探针进程失败：{proc.stderr[-300:]}"
    return proc.stdout.strip().splitlines()[-1]


def test_vectors_are_reproducible_across_processes_with_different_hash_seeds():
    """钉住旧实现真正的缺陷：`hash()` 按进程加盐 ⇒ 跨运行不可复算。

    同一文本、两个不同 PYTHONHASHSEED 的子进程必须给出同一指纹。旧实现下这两者必然不同
    （复核实测 `d470cf94…` vs `bbd1af55…`），新实现走 sha256 播种所以相等。
    """
    text = TEXTS["tort"]
    a, b = _fingerprint(text, "1"), _fingerprint(text, "98765")
    assert a == b, f"同一文本跨进程指纹漂移：{a} != {b} ⇒ 种子又被换成了进程相关的 hash()"


def test_documents_api_matches_query_api_for_the_same_text():
    """`embed_documents([t])` 与 `embed_query(t)` 必须给同一个向量。

    两条接口分别实现时很容易漂（一个归一化一个没归一化、一个换 seed 一个不换），
    而漂了不会立刻红——只会让"同一条文两次写入向量不同"这类真实缺陷被掩盖。
    """
    text = TEXTS["company"]
    one = FakeEmbeddings().embed_query(text)
    batch = FakeEmbeddings().embed_documents([text])[0]
    assert one == batch, "批量与单条接口不一致"


def test_vectors_are_unit_norm_and_correct_dim():
    vec = FakeEmbeddings().embed_query(TEXTS["labor"])
    assert len(vec) == 768, f"维度漂移：{len(vec)}（产品真实模型是 768，见 config.json hidden_size）"
    assert abs(math.sqrt(sum(x * x for x in vec)) - 1.0) < 1e-9, "未归一化会让余弦口径失真"


@pytest.mark.parametrize("name_x", sorted(TEXTS))
def test_unrelated_texts_are_close_to_orthogonal(name_x):
    """无关法律文本之间必须"不像"。阈值 0.2 远低于产品的 0.7 命中线。

    这条就是旧实现会红的判据（实测旧分布 max|cos| = 0.777）。
    """
    vx = FakeEmbeddings().embed_query(TEXTS[name_x])
    for name_y, text_y in TEXTS.items():
        if name_y == name_x:
            continue
        vy = FakeEmbeddings().embed_query(text_y)
        cos = sum(x * y for x, y in zip(vx, vy, strict=True))
        assert abs(cos) < 0.2, f"{name_x} vs {name_y} 余弦={cos:.3f}——高到会冒充相关"
