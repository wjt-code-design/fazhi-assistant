# 手机端公网访问：Cloudflare Tunnel 用法（2026-08-08，2 人场景）

> 目标：让手机（任何网络）通过 HTTPS 访问法智，无需服务器、无需域名备案。
> 拓扑：`手机 ──https──► Cloudflare ──隧道──► 本地 Caddy(:80) ──► frontend:3000 / backend:8000`

## 前置

1. docker compose 已起（`docker compose up -d --build`），本地 `http://localhost` 正常。
   - Caddy 模式：不设 `DOMAIN`（默认）→ Caddy 监听 `:80`，供隧道连接。
2. 安装 `cloudflared`（Windows 下载 cloudflared-windows-amd64.exe，放入 PATH）。

## 方式 A：临时隧道（最快，无 Cloudflare 账号）

```bash
cloudflared tunnel --url http://localhost:80
```
启动后终端输出一个随机 `https://xxx.trycloudflare.com`，手机浏览器打开即可。
**注意**：每次重启隧道 URL 会变，需重新分享；适合临时体验/测试。

## 方式 B：固定子域名（需 Cloudflare 账号 + 域名，长期稳定）

1. Cloudflare 控制台登录 → 左侧 **Zero Trust → Networks → Tunnels → Create a tunnel**（选 Cloudflared）。
2. 按提示在本机安装并运行 cloudflared，或手动配置：复制 tunnel token / credentials。
3. 配置 **Public Hostname**：
   - Subdomain: `fazhi`，Domain: `你的域名.com`
   - Service: `http://localhost:80`（指向本地 Caddy）
4. 完成后 `https://fazhi.你的域名.com` 永久可访问（DNS 由 Cloudflare 托管）。

## 安全要点（2 人场景已覆盖）

- 端口收紧：公网只暴露 443（Caddy），8000/3000 不对公网开（docker-compose 已改）。
- 限流穿透：后端按 `CF-Connecting-IP` 取真实 IP，登录/聊天限流不失效。
- 登录锁定：连续 5 次错密码锁 5 分钟。
- 注册关闭：账号由 admin 在管理端创建（方案C）。
- 不要公开分享 URL；二维码/链接只给两位使用者。

## 回退：同一 WiFi 局域网（不上公网）

手机连同一 WiFi，改 Caddy 端口映射后访问 `http://<电脑局域网IP>:80`（需把 Caddy 端口从 80 换别的避免冲突，或直接用原 3000）。不推荐长期用，仅无网络时自测。

## 验证清单

- [ ] 手机打开 https 链接 → 登录页正常
- [ ] admin 已建第 2 个账号 → 2 个账号都能登录
- [ ] 发一条法律问答 → 流式回答正常（SSE 经隧道）
- [ ] 手机上传图片/语音 → 正常
- [ ] 浏览器菜单「添加到主屏幕」→ 出现「法智」图标，独立窗口打开
