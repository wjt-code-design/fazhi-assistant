# T12-D · `<img>` → `next/image` 迁移评估（**结论：不建议迁移**）

> 卡面判据：评估迁移（含 PWA/离线影响），**先报告后改**。
> 本卡只评估，**未改任何前端源码**。

## 0. 一句话结论

**不建议迁移**——两处 `<img>` 的 `src` 在运行时都是 **`data:` 或 `blob:` URL**，
而 `next/image` **不支持**这两种 URL（官方只支持静态导入或配置好的远端主机）；
且 `ChatImage` 的图片来源接口 **需要 `Authorization` 头**，而 next/image 的服务端优化器
**不带用户令牌**去取图 ⇒ 迁过去会**直接 401 破图**。正确做法是**局部禁用该 lint 规则并写明理由**。

## 1. 现状（全仓只有 2 处 `<img>`，与 2 条 ESLint warning 一一对应）

| 位置 | `src` 来源 | 运行时形态 |
|---|---|---|
| `components/chat/ChatImage.tsx:33` | ①`dataURL` prop；②`loadMediaSrc(ref)` | `data:` 或 **`blob:`** |
| `components/chat/InputBar.tsx:53` | `pendingImage`（发送前本地预览） | `data:` / `blob:`（本地生成） |

**`loadMediaSrc` 的实现（`lib/api.ts:361-371`，逐行核对）**：

```ts
const res = await fetch(`${API_URL}/api/media/${ref}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
const blob = await res.blob();
const url = URL.createObjectURL(blob);   // ← 返回 blob: URL
```

## 2. 为什么 `next/image` 在这里**不可行**（三条硬约束）

1. **URL 形态不允许**：`next/image` 的 `src` 必须是静态导入的路径、同源路径或 `images.remotePatterns` 里配置过的远端 URL；
   `data:` / `blob:` **不在支持范围**（既无法被服务端优化，也无法被 `/_next/image` 代理）。
2. **鉴权断链**：`/api/media/{ref}` **要求 Bearer 令牌**；`next/image` 的优化请求由 **Next 服务器**发出（不带浏览器会话的 Authorization）
   ⇒ 优化器拿到 **401** ⇒ **图片全部破图**。要用就必须改造为"签名 URL / 公开媒体"，那是**架构级改动**。
3. **配置缺失**：`next.config.js` **没有 `images` 段**（无 `remotePatterns`/`domains`）⇒ 任何远端图片改造前都得先补配置。

## 3. PWA / 离线影响（卡面要求单列）

- **`/_next/image` 是服务端动态优化**：离线时该路径**不可用**；当前两处 `<img src=blob:>` 是**纯客户端资源**，
  离线预览（发图前/看图）**天然可用** ⇒ 迁移会**削弱离线能力**。
- **SW 缓存面**：`public/sw.js` 现策略 = 预缓存 SHELL（`/`、`/chat`、manifest、图标）+ 同源 GET 运行时缓存。
  若引入 `/_next/image?url=…&w=…&q=…`，**参数字符串会随尺寸/质量变化** ⇒ 缓存键爆炸、命中率低、占用增长，
  需要为它单写一套缓存规则（**净增复杂度**）。
- **产物基址遗留**：生产产物内联的是公网基址（见 T12-A），`/_next/image` 属同源路径不受影响，但这不构成迁移理由。

## 4. 替代方案对比

| 方案 | 行为变化 | 成本 | 结论 |
|---|---|---|---|
| **A. 局部 `eslint-disable-next-line` + 说明注释**（2 处） | **零** | 2 行注释 | **推荐** |
| B. 迁 `next/image` 且 `unoptimized` | 零（但组件语义"看似优化实际不优化"，误导后人） | 2 处改写 + 可能的属性补全 | 不推荐（假接线） |
| C. 迁 `next/image` 并改造媒体为可公开访问/签名 URL | **大**（鉴权模型改变、媒体暴露面变化） | 架构级 | 不建议（远超"消 warning"的收益） |
| D. 忽略 warning（不动） | 零 | 0 | 可接受，但 warning 会长期留在 CI 里当噪声 |

## 5. 推荐（若你批准，执行清单如下——**本卡未执行**）

1. 在 `ChatImage.tsx:33` 与 `InputBar.tsx:53` 的 `<img` 上一行各加：
   `{/* eslint-disable-next-line @next/next/no-img-element -- src 为 data:/blob: URL（本地预览或带鉴权取的媒体），next/image 不支持且其优化器不带令牌 */}
2. 跑 `npm run check` 复核：**warning 由 2 → 0**，且 `tsc`/`vitest` 保持全绿（预期零行为变化）。
3. 在 `docs/frontend-review-refactor-plan-20260915.md` 的 D 维度补一条：**"`<img>` warning 属有意保留，理由见 T12-D 报告"**。

**触发重估的条件**：若将来新增**静态大图**（如登录页插画）或**可公开的远端图片**，
则应先补 `next.config.js` 的 `images.remotePatterns`，**那一处**再改用 `next/image`（局部优化，不搞一刀切）。

## 6. 本卡没做的

- 未改 `next.config.js`、未动两处 `<img>`、未跑改造后的 `check`（卡面"先报告后改"）；
- 未量化"`next/image` 能省多少带宽"——因为**当前两处根本无法被优化**，该收益在本仓为 0，量化无意义。
