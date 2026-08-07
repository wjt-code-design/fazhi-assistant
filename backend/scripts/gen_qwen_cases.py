"""qwen3.5-flash 生成 5 法 × 10 题法考重难点情景题，交叉验证召回精准率（2026-08-07）。
每法一次生成 10 题（题干+选项+答案+法条依据），解析 basis → 检查 [检索 top10 ∪ 补充] 命中。
用法：停后端，venv 运行：python scripts/gen_qwen_cases.py
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from settings import settings  # noqa: E402
from retrieval import retrieve, scenario_supplement_docs  # noqa: E402

LAWS = ["著作权法", "商标法", "专利法", "消费者权益保护法", "合伙企业法"]

PROMPT = """你是法考出题专家。为《{law}》生成 10 道法考高频重难点单选题（必须是具体情景应用题，不能是法条背诵/概念题），覆盖该法最常考的 10 个不同重难点考点，每题考点不能重复。
每道题输出一行，格式固定，用英文分号 ; 分隔 7 个字段，不要输出序号、不要空行、不要任何解释：
情景题干;选项A;选项B;选项C;选项D;正确答案字母(A-D);法条依据
法条依据格式必须为：{law} 第X条。例：{law} 第五十七条
现在开始，严格只输出 10 行："""


def gen(law, client):
    import openai
    resp = client.chat.completions.create(
        model="qwen3.5-flash-2026-02-23",
        messages=[{"role": "user", "content": PROMPT.format(law=law)}],
        temperature=0.7,
        max_tokens=3500,
    )
    text = resp.choices[0].message.content.strip()
    qs = []
    for line in text.splitlines():
        parts = line.split(";")
        if len(parts) < 7:
            continue
        scenario, oa, ob, oc, od, ans, basis = parts[:7]
        qs.append({
            "scenario": scenario.strip(),
            "options": {"A": oa.strip(), "B": ob.strip(), "C": oc.strip(), "D": od.strip()},
            "answer": ans.strip(),
            "basis": basis.strip(),
        })
    return qs


def parse_basis(basis):
    m = re.search(r"第([零〇○一二三四五六七八九十百千万0-9０-９]+)条", basis)
    if not m:
        return None, None
    art = "第" + m.group(1) + "条"
    src = re.sub(r"^《|》$", "", basis)
    src = re.sub(r"第[零〇○一二三四五六七八九十百千万0-9０-９]+条.*$", "", src).strip()
    src = re.sub(r"^中华人民共和国", "", src)
    return src, art


CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qwen_cases_cache.json")


def main():
    import openai
    base = settings.llm_base_url or settings.zhipu_base_url
    key = settings.llm_api_key or settings.zhipuai_api_key
    client = openai.OpenAI(base_url=base, api_key=key)

    if os.path.exists(CACHE):
        all_qs = json.load(open(CACHE, encoding="utf-8"))
        print("使用缓存题目（跳过 qwen 生成）")
    else:
        all_qs = {}
        json.dump(all_qs, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
        print("初始化缓存")
    # 缓存缺失/为空的法律 → 重新生成该法
    for law in LAWS:
        if not all_qs.get(law):
            print(f"重新生成 {law}（缓存缺失）")
            all_qs[law] = gen(law, client)
            json.dump(all_qs, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)

    total_hit = total_miss = total_unknown = 0
    for law in LAWS:
        qs = all_qs.get(law, [])
        print(f"=== {law}: {len(qs)} 题 ===")
        for q in qs:
            basis = q.get("basis", "")
            src, art = parse_basis(basis)
            if not src or not art:
                total_unknown += 1
                print(f"  [依据不可解析] {basis}")
                continue
            docs = retrieve(q["scenario"], k=10) + scenario_supplement_docs(q["scenario"])
            got = set((d.metadata.get("source", ""), d.metadata.get("article", "")) for d in docs)
            if (src, art) in got:
                total_hit += 1
            else:
                total_miss += 1
                print(f"  [MISS] 目标 {src} {art} | {q['scenario'][:34]}... 依据: {basis}")
        print()
    allq = total_hit + total_miss
    print(f"=== 召回: {total_hit}/{allq} ({total_hit/allq*100:.0f}%) | 依据不可解析 {total_unknown} ===")


if __name__ == "__main__":
    main()
