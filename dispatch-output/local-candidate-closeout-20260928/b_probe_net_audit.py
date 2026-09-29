"""对读数里**全部**网络事件键做主机归类，不用截断窗口；并自带「这把尺子能红」的对照。

为什么单独写这个：上一轮我用运行器打印的前 25 条键得出"外联全是环回"，而 dict 是插入序、
`[:25]` 只覆盖了 ctypes.dlopen 与一部分 http.client.connect —— 那是**用截断集当全集**得出的结论。

三类读数分开计，绝不把"键里没有主机字段"算进"环回"：
  loopback / non-loopback / no-host-field。

判据方向是 **non-loopback 优先**（独立评审抓出前一版在这里有三处静默漏判，都朝"看起来更安全"的方向漏）：
IPv6 四元组、十进制整数 IP、`os.system` 里带的 URL，前一版统统落进"无主机字段"。
现在只有**确实认不出主机**才进那一档，认得出的非环回地址一律 non-loopback。

`--selftest` 用合成键证明归类器真的会红：公网 IPv4/IPv6、云厂商元数据 IP、十进制 IP 绕过、
外网域名、带 URL 的命令行与 `os.system`，同时钉两条"不该误判成外网"的（`::1` 与十进制 127.0.0.1）。
"""

from __future__ import annotations

import ipaddress
import json
import re
import sys
from collections import Counter
from pathlib import Path

LOOPBACK_NAMES = {"localhost", "localhost."}
EVIDENCE = Path(__file__).resolve().parent

HOSTPORT = re.compile(r"^\((?P<h>[^,()]+)(?:,[^,()]+){0,3}\)$")
URLHOST = re.compile(r"^\w+://(?P<h>\[[^\]]+\]|[^/:]+)")
CMDURL = re.compile(r"\b(?:https?|ftp|file|gopher)://\S+|\bsk-[A-Za-z0-9]{8,}")


def is_loopback_host(host: str) -> bool:
    """环回判定。认不出的地址**按非环回算**（宁可多报，不许静默放过）。"""
    h = host.strip().strip("[]")
    if not h:
        return False
    if h.lower() in LOOPBACK_NAMES:
        return True
    if h.isdigit():  # 十进制整数形态的 IPv4（SSRF 常用绕过写法）
        try:
            return ipaddress.IPv4Address(int(h)).is_loopback
        except (ValueError, ipaddress.AddressValueError):
            return False
    try:
        return ipaddress.ip_address(h).is_loopback
    except ValueError:
        return False


def _verdict(host: str) -> tuple[str, str]:
    if not host:
        return "no-host-field", ""
    return ("loopback" if is_loopback_host(host) else "non-loopback"), host


def classify(kind: str, detail: str) -> tuple[str, str]:
    """返回 (归类, 依据)。归类 ∈ {loopback, non-loopback, no-host-field}。

    键形状是实测的（见 README G.1 打印样本）：
      http.client.connect :: <类名>|<host>|<port>
      socket.connect      :: socket|(<host>,<port>[,<flowinfo>,<scopeid>])   ← IPv6 是四元组
      socket.getaddrinfo  :: <host>|<port>|<flags>                            ← host 可能是十进制整数 IP
      urllib.Request      :: <url> method=<m> headers[<键名>]
      subprocess.Popen    :: <p0>|<cmdline>|<cwd>   —— 无主机字段，但命令行里可能藏 URL
      os.system           :: <命令>                 —— 同上，命令行里可能藏 URL
      ctypes.dlopen       :: <库名或路径>           —— 无主机字段
    """
    parts = [p.strip() for p in detail.split("|")]
    if kind == "http.client.connect":
        host = parts[1] if len(parts) > 1 else ""
        cls, basis = _verdict(host)
        return cls, basis or detail[:70]
    if kind == "socket.connect":
        for p in parts:
            m = HOSTPORT.match(p)
            if m:
                return _verdict(m.group("h"))
        return "no-host-field", detail[:70]
    if kind == "socket.getaddrinfo":
        host = parts[0] if parts else ""
        if host in ("socket", ""):
            return "no-host-field", detail[:70]
        return _verdict(host)
    if kind == "urllib.Request":
        m = URLHOST.match(detail)
        host = m.group("h") if m else ""
        cls, basis = _verdict(host)
        return cls, basis or detail[:70]
    if kind in ("subprocess.Popen", "os.system"):
        hit = CMDURL.search(detail)
        if hit:
            return "non-loopback", f"命令行含 URL/密钥形态: {hit.group(0)[:60]}"
        return "no-host-field", "本地命令行（无主机字段）"
    if kind == "ctypes.dlopen":
        return "no-host-field", "本地动态库（无主机字段）"
    return "no-host-field", detail[:70]


# —— 归类器自证：前 7 条**必须**判成非环回（含前一版会漏的三种形态），
#    后 4 条钉"不许误伤"（真环回与本地库不能被算成外联），最后一条钉"认不出就单列"。
SYNTH = [
    ("socket.connect", "socket|(8.8.8.8,53)", "non-loopback"),
    ("socket.connect", "socket|(2606:4700:40:5515::1,443,0,0)", "non-loopback"),  # IPv6 四元组（旧版漏）
    ("socket.connect", "socket|(169.254.169.254,80)", "non-loopback"),  # 云元数据地址
    ("socket.getaddrinfo", "2130706433|443|0", "loopback"),  # 十进制 127.0.0.1：认得出发往环回 ⇒ 不误伤
    ("socket.getaddrinfo", "2852065534|80|0", "non-loopback"),  # 十进制 169.254.169.254（旧版漏）
    ("socket.getaddrinfo", "10.0.0.5|6379|0", "non-loopback"),
    ("urllib.Request", "https://api.openai.com/v1/embeddings method=POST headers[Authorization]", "non-loopback"),
    ("http.client.connect", "HTTPConnection|dashscope.aliyuncs.com|443", "non-loopback"),
    ("subprocess.Popen", "NoneType|curl https://example.com/x|.", "non-loopback"),
    ("os.system", "wget http://169.254.169.254/latest/meta-data", "non-loopback"),  # 旧版完全不扫
    ("socket.connect", "socket|(127.0.0.1,50177)", "loopback"),
    ("socket.connect", "socket|(127.0.0.1,50177,0)", "loopback"),  # 三元组形态的环回
    ("urllib.Request", "http://[::1]:8080/x method=GET headers[]", "loopback"),  # IPv6 环回不误伤
    ("ctypes.dlopen", "kernel32", "no-host-field"),
    ("subprocess.Popen", "NoneType|C:\\venv\\Scripts\\python.exe -B t.py|.", "no-host-field"),
]


def selftest() -> int:
    bad = []
    for kind, detail, want in SYNTH:
        got, basis = classify(kind, detail)
        flag = "ok" if got == want else "MISMATCH"
        if got != want:
            bad.append((kind, detail, want, got))
        print(f"  {flag:8s} want={want:14s} got={got:14s} {kind} :: {basis}")
    n_non = sum(1 for _, _, w in SYNTH if w == "non-loopback")
    n_loop = sum(1 for _, _, w in SYNTH if w == "loopback")
    n_none = sum(1 for _, _, w in SYNTH if w == "no-host-field")
    print(f"  合成键 {len(SYNTH)} 条：非环回 {n_non} / 环回不误伤 {n_loop} / 无主机字段单列 {n_none}")
    if bad:
        print(f"SELFTEST FAIL: {len(bad)} 条归类不符 —— 归类器不可信，读数结论作废")
        return 1
    print(
        "SELFTEST PASS: 归类器能红（公网 IPv4/IPv6 四元组、云元数据 IP、十进制 IP 绕过、外网域名、"
        "带 URL 的命令行与 os.system 全部被判非环回；真环回与本地库不误伤）"
    )
    return 0


def injected_selftest(pattern: str = "b-probe-readings-pytest-*.json") -> int:
    """数据侧对照：往一份**真实读数的副本**里注入两条外发事件，看这套判据抓不抓得到。

    为什么合成键不够：`--selftest` 只证"归类函数认得这些形状"，证不了
    "整条读数→归类→汇总→rc 的链路会在真数据上红"。评审指出期望侧变异只证明
    "主张是数据的函数"，不证明"主张测的是正确谓词"——这一条就是补那个缺口。
    注入后**同步把 kinds/total 改成新值**，这样"自洽"那一轴保持绿，红的只能是非环回判定本身
    （一次只动一个判据，否则红了不知道是谁红的）。
    """
    cands = [p for p in sorted(EVIDENCE.glob(pattern)) if not p.name.endswith(".INVALID")]
    if not cands:
        print(f"INJECTED FAIL: 找不到 {pattern}")
        return 2
    src = cands[-1]
    d = json.loads(src.read_text(encoding="utf-8"))
    net = dict(d.get("net_events") or {})
    inject = {
        "socket.connect :: socket|(169.254.169.254,80)": 3,  # 云元数据地址
        "socket.getaddrinfo :: 2852065534|443|0": 2,  # 十进制写法的 169.254.169.254
    }
    before_non = sum(c for k, c in net.items() if classify(*k.split(" :: ", 1))[0] == "non-loopback")
    net.update(inject)
    d["net_events"] = net
    d["net_event_kinds"] = len(net)  # 只动这一处配套，保持"自洽"轴不干扰本次判据
    d["net_event_total"] = sum(net.values())
    tmp = src.parent / "_injected_net_audit_reading.json"
    try:
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8", newline="\n")
        rc = main([str(tmp)])
        out = json.loads(tmp.read_text(encoding="utf-8"))
        flagged = [k for k in out["net_events"] if classify(*k.split(" :: ", 1))[0] == "non-loopback"]
        hit_meta = any("169.254.169.254" in k for k in flagged)
        hit_dec = any("2852065534" in k for k in flagged)
        print(f"\nINJECTED: 源读数 {src.name} 注入 2 类外发（注入前非环回事件 {before_non} 次）")
        print(f"  判为非环回的键数 = {len(flagged)}；抓到元数据地址 = {hit_meta}；抓到十进制 IP 绕过 = {hit_dec}")
        if rc == 0 or not (hit_meta and hit_dec):
            print("INJECTED FAIL: 真数据上的外发没被这条链路抓住 ⇒ '0 条非环回'不可信")
            return 1
        print("INJECTED PASS: 真数据形态的外发会被判红，且红的正是外发判定（自洽轴未受影响）")
        return 0
    finally:
        tmp.unlink(missing_ok=True)


def main(argv: list[str]) -> int:
    if argv and argv[0] == "--selftest":
        return selftest()
    if argv and argv[0] == "--injected-selftest":
        return injected_selftest()
    files = argv or sorted(str(p) for p in EVIDENCE.glob("b-probe-readings-*.json"))
    files = [f for f in files if not f.endswith(".INVALID")]
    if not files:
        print("没有可读的读数文件")
        return 2

    total_by_class: Counter[str] = Counter()
    nonloop: list[str] = []
    nohost_kinds: Counter[str] = Counter()
    rc = 0
    for f in files:
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        net = d.get("net_events") or {}
        c: Counter[str] = Counter()
        for key, cnt in net.items():
            kind, _, detail = key.partition(" :: ")
            cls, basis = classify(kind, detail)
            c[cls] += cnt
            total_by_class[cls] += cnt
            if cls == "non-loopback":
                nonloop.append(f"{Path(f).name} host={basis} key={key[:130]}")
            if cls == "no-host-field":
                nohost_kinds[kind] += cnt
        kinds = len(net)
        summed = sum(net.values())
        declared_kinds = d.get("net_event_kinds")
        declared_total = d.get("net_event_total")
        self_consistent = kinds == declared_kinds and summed == declared_total
        print(
            f"{Path(f).name}\n    loopback={c['loopback']} non-loopback={c['non-loopback']} "
            f"no-host-field={c['no-host-field']}\n"
            f"    键数={kinds} 声明 kinds={declared_kinds} | 计数求和={summed} 声明 total={declared_total} "
            f"-> 自洽 {'PASS' if self_consistent else 'FAIL'}"
        )
        if not self_consistent:
            rc = 1

    print(
        f"\n合计: loopback={total_by_class['loopback']} non-loopback={total_by_class['non-loopback']} "
        f"no-host-field={total_by_class['no-host-field']}"
    )
    print(f"无主机字段的事件按 kind: {dict(nohost_kinds)}")
    if nonloop:
        print("非环回事件逐条：")
        for line in nonloop[:40]:
            print("  " + line)
        rc = 1
    else:
        print("非环回事件：0 条")
    print("\nNET AUDIT " + ("FAIL" if rc else "PASS") + ": 含主机字段的事件全部指向环回")
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
