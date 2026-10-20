// R05/R06（2026-10-20）：会话视图身份护栏——切/新建会话时作废在途详情与文件解析结果。
//
// **这两条审查项的形状**：
//   R05：`selectConv` 先改 activeId/conversationId，`await detail` 后**无身份校验**直接 setMessages；
//        旧会话的系统详情可能盖到新会话上；异常分支也会把**新视图**的消息误清成空。
//   R06：文件附件状态（fileInfo/fileContent）是**页面级**、未随会话切换重置；`send` 用
//        `fileContent ?? text` ⇒ 残留文档压过新输入；异步解析完成也无视图校验。
//
// 修复：hook 内加视图版本号 `viewSeq`——每次切/新建/删除当前视图都 +1，异步结果落地前比对；
// 并新增 `clearFile` 回调，切会话时清页面级文件状态。
//
// 本文件跑的是**真 hook**（React 替身只调钩子、不渲染），钉的是消费侧接线本身。

import { afterEach, beforeEach, expect, it, vi } from "vitest";

const runtime = vi.hoisted(() => ({
  current: null as null | {
    slots: unknown[];
    cursor: number;
    effects: (() => void | (() => void))[];
  },
}));

vi.mock("react", () => ({
  useState(initial: unknown) {
    const owner = runtime.current!;
    const index = owner.cursor++;
    if (!(index in owner.slots)) {
      owner.slots[index] = typeof initial === "function" ? (initial as () => unknown)() : initial;
    }
    return [
      owner.slots[index],
      (next: unknown) => {
        owner.slots[index] =
          typeof next === "function"
            ? (next as (prev: unknown) => unknown)(owner.slots[index])
            : next;
      },
    ];
  },
  useRef(initial: unknown) {
    const owner = runtime.current!;
    const index = owner.cursor++;
    if (!(index in owner.slots)) owner.slots[index] = { current: initial };
    return owner.slots[index];
  },
  useEffect(effect: () => void | (() => void)) {
    const owner = runtime.current!;
    const index = owner.cursor++;
    if (!(index in owner.slots)) {
      owner.slots[index] = true;
      owner.effects.push(effect);
    }
  },
}));

vi.mock("@/lib/api", () => ({
  convApi: {
    list: vi.fn().mockResolvedValue([]),
    detail: vi.fn(),
    remove: vi.fn().mockResolvedValue(undefined),
  },
}));

import { convApi } from "@/lib/api";
import { useConversations } from "@/lib/hooks/useConversations";
import type { AuthUser } from "@/lib/auth";
import type { ConversationItem } from "@/lib/types";

const USER: AuthUser = { id: 1, username: "u", role: "user" };

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
}

function item(id: number): ConversationItem {
  return {
    id,
    title: `t${id}`,
    preview: "",
    message_count: 1,
    has_image: false,
    created_at: "2026-01-01",
  };
}

const unmounts: (() => void)[] = [];

function mount() {
  const owner = {
    slots: [] as unknown[],
    cursor: 0,
    effects: [] as (() => void | (() => void))[],
  };
  const opts = {
    user: USER,
    streaming: false,
    setMessages: vi.fn(),
    setConversationId: vi.fn(),
    setPendingAgentRun: vi.fn(),
    setClarifyRounds: vi.fn(),
    setSelectedScope: vi.fn(),
    setInput: vi.fn(),
    setPendingImage: vi.fn(),
    setSidebarOpen: vi.fn(),
    setIsNearBottom: vi.fn(),
    clearExpandedLaw: vi.fn(),
    resetFeedback: vi.fn(),
    clearFile: vi.fn(),
  };
  const cleanups: (() => void)[] = [];
  function read() {
    runtime.current = owner;
    owner.cursor = 0;
    const result = useConversations(opts);
    runtime.current = null;
    for (const effect of owner.effects.splice(0)) {
      const cleanup = effect();
      if (cleanup) cleanups.push(cleanup);
    }
    return result;
  }
  function unmount() {
    for (const cleanup of cleanups.splice(0)) cleanup();
  }
  read();
  unmounts.push(unmount);
  return { read, unmount, opts };
}

async function flush() {
  for (let i = 0; i < 12; i++) await Promise.resolve();
}

beforeEach(() => {
  vi.mocked(convApi.list).mockReset().mockResolvedValue([]);
  vi.mocked(convApi.detail).mockReset();
  vi.mocked(convApi.remove).mockReset().mockResolvedValue({ ok: true });
});
afterEach(() => {
  for (const unmount of unmounts.splice(0)) unmount();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

it("R05: discards a stale conversation detail once the view has been replaced by a new chat", async () => {
  const detail = deferred<{ messages: { role: string; content: string }[] }>();
  vi.mocked(convApi.detail).mockReturnValueOnce(detail.promise);
  const hook = mount();

  const switching = hook.read().selectConv(item(7));
  hook.read().newChat();
  hook.opts.setMessages.mockClear(); // newChat 自己会清空消息；只观察旧详情是否**再次**落地

  detail.resolve({ messages: [{ role: "user", content: "旧会话历史" }] });
  await switching;

  expect(hook.opts.setMessages).not.toHaveBeenCalled();
});

it("R05: the latest selection wins; an earlier detail resolving late is dropped", async () => {
  const detailB = deferred<{ messages: { role: string; content: string }[] }>();
  const detailC = deferred<{ messages: { role: string; content: string }[] }>();
  vi.mocked(convApi.detail)
    .mockReturnValueOnce(detailB.promise)
    .mockReturnValueOnce(detailC.promise);
  const hook = mount();

  const selectB = hook.read().selectConv(item(11));
  const selectC = hook.read().selectConv(item(12));
  hook.opts.setMessages.mockClear();

  detailB.resolve({ messages: [{ role: "user", content: "B 历史" }] });
  await selectB;
  expect(hook.opts.setMessages).not.toHaveBeenCalled(); // B 过期被丢

  detailC.resolve({ messages: [{ role: "user", content: "C 历史" }] });
  await selectC;
  expect(hook.opts.setMessages).toHaveBeenCalledTimes(1);
  expect(hook.opts.setMessages.mock.calls[0][0]).toEqual([
    expect.objectContaining({ content: "C 历史" }),
  ]);
});

it("R05: a failed stale detail never clears the newer view's messages", async () => {
  const detail = deferred<{ messages: { role: string; content: string }[] }>();
  vi.mocked(convApi.detail).mockReturnValueOnce(detail.promise);
  const hook = mount();

  const switching = hook.read().selectConv(item(21));
  hook.read().newChat();
  hook.opts.setMessages.mockClear();

  detail.reject(new Error("boom"));
  await switching;

  expect(hook.opts.setMessages).not.toHaveBeenCalled(); // 过期失败不得把新视图清成空
});

it("R06: switching and new chat clear the page-level file attachment", async () => {
  vi.mocked(convApi.detail).mockResolvedValueOnce({ messages: [] });
  const hook = mount();

  hook.read().newChat();
  expect(hook.opts.clearFile).toHaveBeenCalledTimes(1);

  await hook.read().selectConv(item(31));
  expect(hook.opts.clearFile).toHaveBeenCalledTimes(2);
});

it("R05/R06: the view token advances on new chat and on switching a conversation", async () => {
  vi.mocked(convApi.detail).mockResolvedValueOnce({ messages: [] });
  const hook = mount();

  const before = hook.read().viewSeq.current;
  hook.read().newChat();
  expect(hook.read().viewSeq.current).toBe(before + 1);

  await hook.read().selectConv(item(41));
  expect(hook.read().viewSeq.current).toBe(before + 2);
});

it("R05/R06: deleting the active conversation also invalidates in-flight work", async () => {
  vi.stubGlobal("window", { confirm: () => true });
  vi.mocked(convApi.detail).mockResolvedValueOnce({ messages: [] });
  const hook = mount();

  await hook.read().selectConv(item(51));
  const afterSelect = hook.read().viewSeq.current;

  await hook.read().deleteConv(51);
  await flush();
  expect(hook.read().viewSeq.current).toBe(afterSelect + 1);
});
