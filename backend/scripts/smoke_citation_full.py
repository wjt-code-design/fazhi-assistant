"""选引行为全量门禁（含 LLM，release 前跑，有 token 成本）。

断言 8 个高频场景的回答引对操作性条文 + 无含糊话 + 无误报注解，
并加负向用例：无匹配条文应诚实说"未覆盖"而非编造。

前置：后端已启动（manage.py start），API key 已配。用法：
  cd backend && python scripts/smoke_citation_full.py
"""

import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
sys.path.insert(0, BACKEND)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(BACKEND, ".env"))

BASE = "http://localhost:8000"
# 管理员凭据从 backend/.env 读取，不硬编码进仓库（本项目将公开上 GitHub）
ADMIN_USER = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASSWORD", "")
if not ADMIN_PASS:
    print("缺少 ADMIN_PASSWORD（backend/.env 未配置），无法跑 full 门禁", file=sys.stderr)
    sys.exit(2)
ADMIN = (ADMIN_USER, ADMIN_PASS)


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


POSITIVE = [
    (
        "网购退货格式条款",
        "网购相机，商家标注“拆封不退”，买家要求七天无理由退货被拒。商家免责条款有效吗？",
        ["第四百九十六条", "第四百九十七条"],
    ),
    ("违法解除赔偿金", "公司违法解除劳动合同，赔偿金怎么算？", ["第八十七条"]),
    ("合法解除经济补偿", "公司合同到期不续签，经济补偿金怎么算？", ["第四十七条"]),
    ("试用期上限", "劳动合同试用期最长能约定多久？", ["第十九条"]),
    ("周末加班费", "周末加班，加班费怎么算？", ["第四十四条"]),
    ("交强险赔偿顺序", "机动车发生交通事故，交强险先赔还是商业险先赔？", ["第一千二百一十三条"]),
    ("定金退不退", "交了定金又不想买了，定金能退吗？", ["第五百八十六条", "第五百八十七条"]),
    ("七天无理由退货", "网购商品七天无理由退货需要满足什么条件？", ["第二十五条"]),
]

# 负向：知识库未覆盖 → 应诚实拒答而非编造
NEGATIVE = [
    ("库外部门规章", "网络借贷信息中介机构业务活动的部门规章有哪些要求？"),
    ("库外司法解释", "最高人民法院关于民间借贷的司法解释对利率上限怎么规定？"),
]


def main():
    token = json.loads(post(BASE + "/api/auth/login", {"username": ADMIN[0], "password": ADMIN[1]}).read())["token"]
    n = fail = 0

    def check(ok, label):
        nonlocal n, fail
        n += 1
        if not ok:
            fail += 1
            print(f"  [FAIL] {label}")
        else:
            print(f"  [PASS] {label}")

    print("=== 正向 8 场景：引对条文 / 无含糊话 / 无误报 ===")
    for label, q, expects in POSITIVE:
        c = chat(token, q)
        ok_cite = any(e in c for e in expects)
        ok_vague = ("法律基本原则" not in c) and ("相关规定" not in c)
        ok_note = "未在知识库中检索到" not in c
        check(ok_cite and ok_vague and ok_note, f"{label}: 引用={ok_cite} 含糊无={ok_vague} 误报无={ok_note}")

    print("=== 负向：库外问题应诚实拒答（不编造）===")
    for label, q in NEGATIVE:
        c = chat(token, q)
        ok_honest = ("未覆盖" in c) or ("无法完整回答" in c) or ("未收录" in c) or ("司法解释" in c and "当前库" in c)
        check(ok_honest, f"{label}: 诚实拒答={ok_honest} | 前80字: {c[:80].replace(chr(10), ' ')}")

    print(f"\nfull 门禁：{n - fail}/{n} 通过" + ("，FAIL!" if fail else ""))
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
