import json, sys, urllib.request, uuid
BASE = "http://127.0.0.1:18003"
sfx = uuid.uuid4().hex[:8]
def post(path, payload, token=None, timeout=180):
    headers = {"Content-Type": "application/json"}
    if token: headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(), headers=headers, method="POST")
    return urllib.request.urlopen(req, timeout=timeout)
try:
    u, p = f"sc_{sfx}", f"Sc-{sfx}-Pass1"
    post("/api/auth/register", {"username": u, "password": p}, timeout=60)
    token = json.loads(post("/api/auth/login", {"username": u, "password": p}, timeout=60).read().decode())["token"]
    r = post("/api/chat", {"content": "试用期最长不能超过多久？", "no_cache": True}, token=token)
    raw = r.read().decode("utf-8")
    events = []
    for line in raw.splitlines():
        if line.startswith("data: ") and line[6:] != "[DONE]":
            try: events.append(json.loads(line[6:]))
            except Exception: pass
    chars = sum(len(e.get("content","")) for e in events if isinstance(e.get("content"), str))
    errors = [e.get("code") or e.get("msg","")[:40] for e in events if e.get("type") in ("error",)]
    print("HTTP:", r.status, "| chars:", chars, "| errors:", errors)
except urllib.error.HTTPError as e:
    print("HTTP-ERROR:", e.code, e.read().decode()[:120])
