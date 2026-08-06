"""B1/B2/B5 端到端冒烟（2026-08-07）：
- 普通问答：回答无"建议核对原文"矛盾句、无 $ 残留、无 <think>
- 合同首轮 → 追问×2：追问只答追问，不重出完整评估报告
用法：python scripts/smoke_b1b5.py（需后端在 8000 运行）
"""
import json
import sys

import httpx

BASE = "http://127.0.0.1:8000"


def chat(tok, content, conv_id=None, timeout=180):
    body = {"content": content, "no_cache": True}
    if conv_id:
        body["conversation_id"] = conv_id
    r = httpx.post(BASE + "/api/chat", headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
                   json=body, timeout=timeout)
    if r.status_code != 200:
        return "", None, f"HTTP {r.status_code}: {r.text[:200]}"
    text, cid = [], None
    for line in r.text.splitlines():
        if not line.startswith("data: "):
            continue
        payload = line[6:].strip()
        if payload == "[DONE]":
            continue
        try:
            d = json.loads(payload)
        except Exception:
            continue
        if "content" in d:
            text.append(d["content"])
        if "conversation_id" in d:
            cid = d["conversation_id"]
    return "".join(text), cid, None


def main() -> int:
    tok = httpx.post(BASE + "/api/auth/login", json={"username": "vtest", "password": "test1234"}).json()["token"]
    ok = True

    print("=== 1. 普通问答 ===")
    a, _, err = chat(tok, "公司拖欠我三个月工资，怎么维权？依据什么法律")
    if err:
        print("FAIL:", err); return 1
    checks = {
        "长度>200": len(a) > 200,
        "无'建议核对'": "建议核对" not in a and "未在本次检索" not in a,
        "无$残留": "$" not in a,
        "无think": "<think>" not in a,
    }
    print(f"长度 {len(a)} | 首80: {a[:80]}")
    for k, v in checks.items():
        print(f"  {'PASS' if v else 'FAIL'} {k}")
        ok = ok and v

    print("\n=== 2. 合同首轮 → 追问×2 ===")
    contract = (
        "房屋租赁合同\n甲方：张三（出租方）\n乙方：李四（承租方）\n"
        "第一条 租赁期限为三年。\n第二条 月租金五千元，押一付三。\n"
        "第三条 乙方擅自转租的，甲方有权解除合同并没收押金。"
    )
    c1, cid, err = chat(tok, "请审查这份合同的风险点：\n" + contract)
    if err:
        print("FAIL:", err); return 1
    print(f"首轮 长度 {len(c1)} | 含'①【结论']: {'①【结论' in c1} | conv_id={cid}")
    ok = ok and cid is not None and "①【结论" in c1

    followups = ["违约金约定太高，能要求降低吗？", "如果乙方想提前退租，需要承担什么责任？"]
    for i, q in enumerate(followups, 1):
        a2, _, err = chat(tok, q, conv_id=cid)
        if err:
            print(f"FAIL 追问{i}:", err); return 1
        reprints = "①【结论" in a2 and "风险清单" in a2
        print(f"追问{i} '{q[:12]}…' 长度 {len(a2)} | 重出完整报告: {reprints}")
        print(f"  首80: {a2[:80]}")
        ok = ok and not reprints

    print("\n结果:", "全部 PASS" if ok else "存在 FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
