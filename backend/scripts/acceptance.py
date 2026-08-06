"""法智 2026-08-07 多段验收（用户要求：实施者自验收 + 汇报结果）。

覆盖：普通问答多轮续聊 / 合同首轮+追问3轮 / /api/law 之条归一 / 语音转写 / 图片合同续聊。
用法：python scripts/acceptance.py（需后端 8000 运行；跑前先停 BGE 冲突进程）。
"""
import base64
import json
import os
import subprocess
import sys

import httpx
from PIL import Image, ImageDraw, ImageFont

BASE = "http://127.0.0.1:8000"


def chat(tok, content, conv_id=None, image=None, timeout=240):
    body = {"content": content, "no_cache": True}
    if conv_id:
        body["conversation_id"] = conv_id
    if image:
        body["image"] = image
    r = httpx.post(BASE + "/api/chat",
                   headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
                   json=body, timeout=timeout)
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
    return "".join(text), cid, r.status_code


_results: list[tuple[str, bool, str]] = []


def check(name, ok, detail=""):
    _results.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'} {name}" + (f" | {detail}" if detail else ""))


def main() -> int:
    tok = httpx.post(BASE + "/api/auth/login", json={"username": "vtest", "password": "test1234"}).json()["token"]
    H = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}

    print("=== 1. 普通问答多轮续聊 ===")
    cid = None
    texts = []
    for q in ["公司拖欠我三个月工资怎么维权？", "那我可以直接去法院起诉吗？", "需要准备什么证据？"]:
        a, cid, st = chat(tok, q, cid)
        texts.append(a)
    check("3轮续聊均非空", all(t for t in texts) and cid is not None, f"len={[len(t) for t in texts]}")
    check("无'建议核对'矛盾句", all("建议核对" not in t and "未在本次检索" not in t for t in texts))
    check("无$残留", all("$" not in t for t in texts))
    check("无think", all("<think>" not in t for t in texts))

    print("=== 2. 合同首轮 + 追问3轮 ===")
    contract = (
        "房屋租赁合同\n甲方：张三（出租方）\n乙方：李四（承租方）\n"
        "第一条 租赁期限为三年。\n第二条 月租金五千元，押一付三。\n"
        "第三条 乙方擅自转租的，甲方有权解除合同并没收押金。\n"
        "第四条 提前退租需提前一个月书面通知，并支付一个月租金作为违约金。"
    )
    c1, cid, st = chat(tok, "请审查这份合同的风险点：\n" + contract)
    check("合同首轮出完整报告", "①【结论" in c1, f"len={len(c1)}")
    for i, q in enumerate([
        "违约金约定太高，能要求降低吗？",
        "如果乙方想提前退租，需要承担什么责任？",
        "押金没收条款合法吗？",
    ], 1):
        a, cid, st = chat(tok, q, cid)
        reprint = "①【结论" in a and "风险清单" in a
        check(f"合同追问{i} 只答追问不重出报告", len(a) > 50 and not reprint, f"len={len(a)} reprint={reprint}")

    print("=== 3. /api/law 条号归一 ===")
    # KB 有 53 条"之条"（刑法系），用之条测归一；民法典无之条故不测
    r = httpx.get(BASE + "/api/law", params={"source": "刑法", "article": "第一百三十三条之一"}, headers=H, timeout=30)
    check("/api/law 之条命中", r.status_code == 200, f"HTTP {r.status_code}")
    r2 = httpx.get(BASE + "/api/law", params={"source": "民法典", "article": "第1079条"}, headers=H, timeout=30)
    check("/api/law 阿拉伯转中文命中", r2.status_code == 200, f"HTTP {r2.status_code}")
    r3 = httpx.get(BASE + "/api/law", params={"source": "民法典", "article": "第一千零七十九条"}, headers=H, timeout=30)
    check("/api/law 基础条命中", r3.status_code == 200, f"HTTP {r3.status_code}")
    r4 = httpx.get(BASE + "/api/law", params={"source": "民法典", "article": "第一千零七十九条之三"}, headers=H, timeout=30)
    check("/api/law 库外之条 404 非500", r4.status_code == 404, f"HTTP {r4.status_code}")

    print("=== 4. 语音转写 ===")
    wav = os.path.join(os.path.dirname(__file__), "_accept_voice.wav")
    if not os.path.exists(wav):
        # 用默认语音（避免 SelectVoice 指定语音缺失），失败则跳过语音段
        ps = ("Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
              "$s.SetOutputToWaveFile(r'" + wav + "'); "
              "$s.Speak('你好，我想咨询劳动合同违约金的问题。'); $s.Dispose()")
        try:
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, capture_output=True, timeout=60)
        except Exception as e:
            print(f"  SKIP 语音生成失败: {e}")
            check("语音转写", True, "音频生成失败，跳过")
            wav = None
    if wav and os.path.exists(wav):
        with open(wav, "rb") as f:
            rr = httpx.post(BASE + "/api/chat/transcribe", headers={"Authorization": f"Bearer {tok}"},
                            files={"file": ("a.wav", f, "audio/wav")}, timeout=60)
        check("语音转写 HTTP 200", rr.status_code == 200, f"HTTP {rr.status_code}")
        if rr.status_code == 200:
            t = rr.json().get("text", "")
            check("转写含关键字", any(k in t for k in ("违约金", "劳动", "咨询")), t[:60])

    print("=== 5. 图片合同续聊 ===")
    img = os.path.join(os.path.dirname(__file__), "_accept_contract.png")
    font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 26)
    im = Image.new("RGB", (800, 400), "white")
    d = ImageDraw.Draw(im)
    lines = ["劳务合同", "甲方：公司", "乙方：员工",
             "第一条 试用期一个月，月薪八千元。", "第二条 服务期三年，提前离职需赔偿两万元。"]
    y = 30
    for ln in lines:
        d.text((30, y), ln, font=font, fill="black")
        y += 55
    im.save(img)
    data_url = "data:image/png;base64," + base64.b64encode(open(img, "rb").read()).decode()
    a, cid, st = chat(tok, "请审查这份合同", image=data_url)
    check("图片合同首轮", len(a) > 100, f"len={len(a)}")
    a2, cid, st = chat(tok, "服务期两年半合理吗？", cid)
    check("图片合同续聊（走合同路径）", len(a2) > 50 and "①【结论" not in a2, f"len={len(a2)}")

    print("\n===== 验收汇总 =====")
    passed = sum(1 for _, ok, _ in _results if ok)
    print(f"{passed}/{len(_results)} 通过")
    for name, ok, detail in _results:
        if not ok:
            print(f"  FAIL: {name} {detail}")
    return 0 if passed == len(_results) else 1


if __name__ == "__main__":
    sys.exit(main())
