# 修复聊天页等待回复时整体页面滚动 Bug

> **状态：已实施**（2026-08-02）。落地见 `app/chat/page.tsx`（`scrollRef` / `isNearBottom` / 流式 `auto`）与 `globals.css` 的 `.scroll-contain`。

## 现象

用户提问后等待 AI 回复期间，鼠标滚轮向下滚动时，**整个页面**跟随上移，而不是只滚动聊天内容区。

## 根因

`app/chat/page.tsx` 的 `useEffect` 使用了 `bottomRef.current?.scrollIntoView({ behavior: "smooth" })`：

```js
// 第 80-82 行
useEffect(() => {
  bottomRef.current?.scrollIntoView({ behavior: "smooth" });
}, [messages]);
```

`scrollIntoView` 会沿 DOM 树向上查找**所有可滚动祖先**。当发送消息后 `messages` 变化，而消息流容器 `flex-1 overflow-y-auto` 内容尚少、未溢出时，浏览器找不到内部可滚动区域，就冒泡滚动到 `<html>` 元素 → 整页被顶上。

`globals.css` 第 54 行 `html { scroll-behavior: smooth }` 会放大这个页面级平滑滚动。

## 修复目标

- 等待回复时滚轮只影响聊天消息流容器，不影响整体页面。
- 流式输出自动跟随到底，但不打断用户向上阅读。
- 兼容 `prefers-reduced-motion`。
- 不影响登录页、管理后台页。

## 修改清单

### 1. `app/chat/page.tsx`

**a) 新增一个 ref，绑定到消息流容器**（替换掉仅做锚点的 `bottomRef` 用法）：

```ts
const scrollRef = useRef<HTMLDivElement>(null);
```

`bottomRef` 可保留（仍被底部占位符 `<div ref={bottomRef} />` 使用），但滚动逻辑改用 `scrollRef`。

**b) 重写滚动 useEffect**，并新增"是否在底部附近"判断：

```ts
const [isNearBottom, setIsNearBottom] = useState(true);

useEffect(() => {
  const el = scrollRef.current;
  if (!el) return;
  // 仅当用户已在底部附近时才自动跟随，避免打断阅读
  if (!isNearBottom) return;
  // 减少动效：即时滚动，否则平滑
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  el.scrollTo({ top: el.scrollHeight, behavior: reduced ? "auto" : "smooth" });
}, [messages, isNearBottom]);
```

**c) 在消息流容器上绑定 scrollRef 与 onScroll，并加 overscroll 抑制**：

```jsx
<div
  ref={scrollRef}
  className="scroll-contain flex-1 overflow-y-auto px-4 py-6 md:px-8"
  onScroll={(e) => {
    const el = e.currentTarget;
    setIsNearBottom(el.scrollHeight - el.scrollTop - el.clientHeight < 80);
  }}
  onDrop={onDrop}
  onDragOver={(e) => e.preventDefault()}
>
```

**d) 说明（不需要额外改动）**：
- 聊天根容器已有 `flex h-screen overflow-hidden`，body 上本来就没有滚动条，**不要**再给 body 加 `overflow: hidden`（多余且可能污染其它页面）。
- 不要在 `html/body` 上加 `height:100%; overflow:hidden`，会破坏登录页/管理后台的页面级滚动。

### 2. `app/globals.css`

新增一个局部工具类（仅用于聊天消息流容器，拦截滚轮连锁滚动到外层）：

```css
.scroll-contain {
  overscroll-behavior: contain;
}
```

## 关键点

- 真正治本的是把 `scrollIntoView` 换成容器自身的 `scrollTo`（不再冒泡到 html）。
- `overscroll-behavior: contain` 只是辅助加固，拦截滚轮在容器边界处连锁滚动父级。
- 移除 `scrollIntoView` 后无需保留，逻辑完全由 `scrollRef.scrollTo` 接管。
- 不要改 `globals.css` 里的全局 `scroll-behavior: smooth`（会影响其它页面）。
