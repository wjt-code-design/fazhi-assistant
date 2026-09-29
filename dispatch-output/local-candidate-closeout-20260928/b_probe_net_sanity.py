"""负向对照：证明修好的 urllib.Request 记录键里落不进请求体。

做法：装桩后向一个**必然连不上**的环回端口发一条带哨兵口令的 POST 请求 ——
审计事件在 OpenerDirector.open 里、连接之前就发出，所以异常不影响事件被记录。
断言两件事：① 记录键里出现 URL/方法/头键名（说明这一层真的在被记）；
② 整个读数 JSON 里哨兵串 0 命中（说明体没有被记）。只断言"没命中"会被"这条根本没记录"蒙过去。
"""

from __future__ import annotations

import json
import sys

sys.path.insert(0, r"C:/Users/33393/Desktop/ai-legal-helper/dispatch-output/local-candidate-closeout-20260928")

import b_runtime_probe as probe  # noqa: E402

SENTINEL_BODY = "SENTINEL-BODY-SECRET-DO-NOT-LOG"
SENTINEL_HEADER_VALUE = "SENTINEL-HEADER-VALUE-DO-NOT-LOG"
SENTINEL_URL_MARK = "sentinel-url-marker"


def main() -> int:
    probe.install()
    if not probe.STATE["audit_hooked"]:
        print("FAIL: 审计钩子没装上，本对照不成立")
        return 1

    import urllib.error
    import urllib.request

    url = f"http://127.0.0.1:9/{SENTINEL_URL_MARK}"
    body = json.dumps({"username": "t6-fake-admin", "password": SENTINEL_BODY}).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-type": "application/json", "Authorization": f"Bearer {SENTINEL_HEADER_VALUE}"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=2)
    except BaseException as exc:  # 端口 9 必然拒绝/超时，事件早已发出
        print(f"  请求如期失败（不影响事件记录）: {type(exc).__name__}")

    keys = list(probe.STATE["net"])
    urllib_keys = [k for k in keys if k.split(" :: ")[0] == "urllib.Request"]
    print(f"  net 记录键 {len(keys)} 条，其中 urllib.Request {len(urllib_keys)} 条")
    for k in urllib_keys:
        print(f"    {k}")

    dump = json.dumps({"net": probe.STATE["net"]}, ensure_ascii=False)
    checks = [
        ("键里含 URL（这一层确实在被记）", any(SENTINEL_URL_MARK in k for k in urllib_keys)),
        ("键里含方法 POST", any("method=POST" in k for k in urllib_keys)),
        ("键里含头**键名** Authorization", any("headers[" in k and "Authorization" in k for k in urllib_keys)),
        ("键里含头键名 Content-type", any("Content-type" in k for k in urllib_keys)),
        ("读数里 0 命中哨兵请求体", SENTINEL_BODY not in dump),
        ("读数里 0 命中哨兵头值", SENTINEL_HEADER_VALUE not in dump),
        ("读数里 0 命中裸键 password", "password" not in dump),
    ]
    bad = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    if bad:
        print(f"SELFCHECK FAIL -> {bad}")
        return 1
    print("SELFCHECK PASS: 请求体与头值都不进读数，URL/方法/头键名照常可判")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
