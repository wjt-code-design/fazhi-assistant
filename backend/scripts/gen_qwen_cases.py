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

PROMPT = """你是法考出题专家。请为《{law}》生成 10 道法考高频重难点单选题（必须是具体情景应用题，不能是法条背诵/概念题），覆盖该法最常考的 10 个重难点考点，每题考点不能重复。
每道题包含：① 题干（含具体人物与情景，80-150 字）；② 四个选项 A/B/C/D；③ 正确答案；④ 法条依据（格式："{law} 第X条"，必须是该情景的裁判依据核心条文）。
只输出一个 JSON 对象（除 JSON 外不要输出任何其他内容、不要 markdown 代码块）：
{{"law":"{law}","questions":[{{"scenario":"...","options":{{"A":"...","B":"...","C":"...","D":"..."}},"answer":"B","basis":"{law} 第五十七条"}}]}}"""


def gen(law, client):
    import openai
    resp = client.chat.completions.create(
        model="qwen3.5-flash-2026-02-23",
        messages=[{"role": "user", "content": PROMPT.format(law=law)}],
        temperature=0.7,
        max_tokens=3000,
    )
    text = resp.choices[0].message.content.strip()
    # 剥 markdown 代码块
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    return json.loads(text)


def parse_basis(basis):
    m = re.search(r"第([零〇○一二三四五六七八九十百千万0-9０-９]+)条", basis)
    if not m:
        return None, None
    art = "第" + m.group(1) + "条"
    src = re.sub(r"^《|》$", "", basis)
    src = re.sub(r"第[零〇○一二三四五六七八九十百千万0-9０-９]+条.*$", "", src).strip()
    src = re.sub(r"^中华人民共和国", "", src)
    return src, art


def main():
    import openai
    base = settings.llm_base_url or settings.zhipu_base_url
    key = settings.llm_api_key or settings.zhipuai_api_key
    client = openai.OpenAI(base_url=base, api_key=key)

    total_hit = total_miss = total_unknown = 0
    for law in LAWS:
        data = gen(law, client)
        qs = data.get("questions", [])
        print(f"=== {law}: 生成 {len(qs)} 题 ===")
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
