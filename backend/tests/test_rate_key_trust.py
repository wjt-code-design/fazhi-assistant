"""R03（2026-10-20）：限流转发头只在可信代理对端时才采信。

**这条审查项的形状**：`_rate_key` 原来的实现**无条件**优先读 `CF-Connecting-IP`，注释自称
"不可伪造"——那只在经 cloudflared 正式入口时成立。backend 端口一旦被直连/被其它容器直连，
对端不是可信代理，客户端就能自己塞 `CF-Connecting-IP`/`X-Forwarded-For`，用**任意键**给限流
分桶（每桶各拿满配额）⇒ 限流形同虚设。修复：仅当直连对端是私网/环回地址（可信代理）时才采信
这两个头；否则一律用 socket 对端。

三条腿成对：
1. `test_spoofed_forwarded_header_from_public_peer_is_ignored`——公网对端伪造头必须被忽略。
2. `test_forwarded_headers_honored_behind_trusted_proxy`——私网对端（现役 Caddy）仍按 CF→XFF
   优先级取值，证明加固没有破坏真实部署口径。
3. `test_non_ip_peer_falls_back_to_socket_peer`——非 IP 对端（如 TestClient 的 "testclient"）
   不作可信判定，回落 socket 对端，避免把测试基建的名字当代理。
"""

from __future__ import annotations

from types import SimpleNamespace

import main

# 93.184.216.34（example.com）是真正的公网地址：不得用 203.0.113.0/24 之类文档保留段——
# ipaddress 把 TEST-NET 也算 is_private，那样这条腿会假绿。
PUBLIC_PEER = "93.184.216.34"
TRUSTED_PEER = "172.18.0.5"
CF_HEADER = {"CF-Connecting-IP": "1.2.3.4"}


def _request(peer: str | None, headers: dict[str, str] | None = None) -> SimpleNamespace:
    client = SimpleNamespace(host=peer) if peer is not None else None
    return SimpleNamespace(client=client, headers=headers or {})


def test_spoofed_forwarded_header_from_public_peer_is_ignored():
    """对端是公网地址 ⇒ 客户端自设的 CF/XFF 头不得进入限流分桶键。"""
    req = _request(PUBLIC_PEER, {**CF_HEADER, "X-Forwarded-For": "5.6.7.8"})
    key = main._rate_key(req)
    assert key == PUBLIC_PEER, f"公网对端伪造头被采信（键={key}）⇒ 可按任意键绕过限流"
    assert not main._is_trusted_proxy_peer(PUBLIC_PEER)


def test_forwarded_headers_honored_behind_trusted_proxy():
    """对端是私网代理（现役 Caddy）⇒ 仍按 CF-Connecting-IP 优先取值（真实部署口径不变）。"""
    assert main._is_trusted_proxy_peer(TRUSTED_PEER)
    assert main._rate_key(_request(TRUSTED_PEER, CF_HEADER)) == "1.2.3.4"
    # CF 头缺失时回落 XFF 最右段；攻击者伪造的中间段被忽略。
    xff_only = _request(TRUSTED_PEER, {"X-Forwarded-For": "9.9.9.9, 8.8.8.8"})
    assert main._rate_key(xff_only) == "8.8.8.8"
    # 无转发头时用对端地址（原行为）。
    assert main._rate_key(_request(TRUSTED_PEER)) == TRUSTED_PEER


def test_non_ip_peer_falls_back_to_socket_peer():
    """非 IP 对端（TestClient 的 "testclient"、空串）不作可信判定，回落 socket 对端。"""
    assert not main._is_trusted_proxy_peer("testclient")
    assert not main._is_trusted_proxy_peer("")
    assert not main._is_trusted_proxy_peer(None)
    assert main._rate_key(_request("testclient", CF_HEADER)) == "testclient"


def test_loopback_peer_is_trusted():
    """环回对端（同机反代）算可信代理。"""
    assert main._is_trusted_proxy_peer("127.0.0.1")
    assert main._rate_key(_request("127.0.0.1", CF_HEADER)) == "1.2.3.4"
