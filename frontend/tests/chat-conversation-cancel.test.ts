import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { streamChat, type ChatMeta } from "@/lib/api";
import { useChatStream } from "@/lib/hooks/useChatStream";

// Controlled hook scheduling only: this executes the actual hook, not React rendering.
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
      owner.slots[index] = typeof initial === "function" ? initial() : initial;
    }
    return [
      owner.slots[index],
      (next: unknown) => {
        owner.slots[index] =
          typeof next === "function" ? next(owner.slots[index]) : next;
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
vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  // Keep convApi.create/request real. Replace streaming only at the API boundary.
  streamChat: vi.fn(),
}));

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
}

const unmounts: (() => void)[] = [];
function mount() {
  const owner = { slots: [] as unknown[], cursor: 0, effects: [] as (() => void | (() => void))[] };
  const opts = { onConversationId: vi.fn(), onStreamEnd: vi.fn() };
  const cleanups: (() => void)[] = [];
  function read() {
    runtime.current = owner;
    owner.cursor = 0;
    const result = useChatStream(opts);
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
  return { read, unmount, ...opts };
}

function createResponse(id: unknown) {
  return new Response(JSON.stringify({ id }), { status: 200 });
}

function pendingCreate() {
  const response = deferred<Response>();
  const fetch = vi.fn((_url: string, init: RequestInit) => {
    const signal = init.signal;
    if (signal?.aborted) return Promise.reject(signal.reason);
    signal?.addEventListener("abort", () => response.reject(signal.reason), { once: true });
    return response.promise;
  });
  vi.stubGlobal("fetch", fetch);
  return { fetch, response, signal: () => fetch.mock.calls[0]?.[1].signal };
}

function pendingStream() {
  const completion = deferred<void>();
  vi.mocked(streamChat).mockReturnValueOnce(completion.promise);
  return completion;
}

function callbacks(index = 0) {
  const call = vi.mocked(streamChat).mock.calls[index];
  return {
    payload: call[0],
    chunk: call[1],
    meta: call[2],
    error: call[3],
    steps: call[4]!,
    restart: call[5]!,
    signal: call[6]!,
  };
}

async function flush() {
  for (let i = 0; i < 12; i++) await Promise.resolve();
}

beforeEach(() => {
  vi.mocked(streamChat).mockReset().mockResolvedValue(undefined);
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(createResponse(41)));
});
afterEach(() => {
  for (const unmount of unmounts.splice(0)) unmount();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

it("creates the first conversation before streaming and uses its id in the payload", async () => {
  const create = pendingCreate();
  const timeout = vi.spyOn(AbortSignal, "timeout");
  const hook = mount();
  const sending = hook.read().doSend("first");
  expect(hook.read().streaming).toBe(true);
  expect(streamChat).not.toHaveBeenCalled();
  expect(create.fetch.mock.calls.map(([url, init]) => [url, init.method, init.body])).toEqual([
    ["/api/conversations", "POST", undefined],
  ]);
  expect(timeout).toHaveBeenCalledWith(180_000);
  expect(create.signal()).toBeInstanceOf(AbortSignal);
  create.response.resolve(createResponse(41));
  await sending;
  expect(callbacks().payload).toEqual({
    conversationId: 41,
    content: "first",
    image: undefined,
    truncated: undefined,
    agentRunId: undefined,
    agentStateVersion: undefined,
  });
  expect(hook.read().conversationId).toBe(41);
  expect(hook.read().streaming).toBe(false);
  expect(hook.onConversationId.mock.calls).toEqual([[41]]);
  expect(hook.onStreamEnd).toHaveBeenCalledOnce();
});

it("uses a selected id synchronously even through an earlier send closure", async () => {
  const hook = mount();
  const earlierSend = hook.read().doSend;
  hook.read().setConversationId((id) => (id === null ? 73 : id));
  await earlierSend("history");
  expect(fetch).not.toHaveBeenCalled();
  expect(callbacks().payload.conversationId).toBe(73);
  expect(hook.read().conversationId).toBe(73);
});

it("keeps the created id after a partial first answer is stopped and asked again", async () => {
  const first = pendingStream();
  const hook = mount();
  const oldSend = hook.read().doSend;
  const sending = oldSend("first");
  await flush();
  callbacks().chunk("partial");
  hook.read().stop();
  expect(callbacks().signal.aborted).toBe(true);
  expect(hook.read().messages.at(-1)?.content).toBe("partial\n\n（已停止生成，以上为未完成回答。）");
  await oldSend("again");
  expect(vi.mocked(streamChat).mock.calls.map(([payload]) => [payload.content, payload.conversationId])).toEqual([
    ["first", 41],
    ["again", 41],
  ]);
  expect(fetch).toHaveBeenCalledOnce();
  first.resolve(undefined);
  await sending;
  expect(hook.onStreamEnd).toHaveBeenCalledTimes(2);
});

it("unlocks immediately on stop and shares the unresolved create with a direct retry", async () => {
  const create = pendingCreate();
  const hook = mount();
  const first = hook.read().doSend("first");
  hook.read().stop();
  expect(hook.read().streaming).toBe(false);
  expect(hook.read().messages.at(-1)?.content).toBe("已停止生成。");
  expect(create.signal()?.aborted).toBe(false);
  const second = hook.read().doSend("again");
  expect(create.fetch).toHaveBeenCalledOnce();
  expect(streamChat).not.toHaveBeenCalled();
  create.response.resolve(createResponse(52));
  await Promise.all([first, second]);
  expect(vi.mocked(streamChat).mock.calls.map(([payload]) => [payload.content, payload.conversationId])).toEqual([
    ["again", 52],
  ]);
  expect(hook.read().conversationId).toBe(52);
  expect(hook.onConversationId.mock.calls).toEqual([[52]]);
  expect(hook.onStreamEnd).toHaveBeenCalledTimes(2);
});

it("retains a create that finishes after stop without sending the cancelled question", async () => {
  const create = pendingCreate();
  const hook = mount();
  const first = hook.read().doSend("cancelled");
  hook.read().stop();
  create.response.resolve(createResponse(62));
  await first;
  expect(streamChat).not.toHaveBeenCalled();
  expect(hook.read().conversationId).toBe(62);
  expect(hook.read().streaming).toBe(false);
  expect(hook.onConversationId.mock.calls).toEqual([[62]]);
  expect(hook.onStreamEnd).toHaveBeenCalledOnce();
});

it("reports a create response failure and permits an explicit retry without null chat", async () => {
  const fetch = vi.fn()
    .mockResolvedValueOnce(new Response('{"detail":"create failed"}', { status: 503 }))
    .mockResolvedValueOnce(createResponse(64));
  vi.stubGlobal("fetch", fetch);
  const hook = mount();
  await hook.read().doSend("first");
  expect(hook.read().messages.at(-1)?.content).toBe("出错了：create failed");
  expect(hook.read().conversationId).toBeNull();
  expect(hook.read().streaming).toBe(false);
  expect(streamChat).not.toHaveBeenCalled();
  await hook.read().doSend("retry");
  expect(callbacks().payload.conversationId).toBe(64);
  expect(fetch).toHaveBeenCalledTimes(2);
  expect(hook.onStreamEnd).toHaveBeenCalledTimes(2);
});

it("bounds create at 180 seconds with a native timeout signal and permits retry", async () => {
  const nativeTimeout = AbortSignal.timeout.bind(AbortSignal);
  // Use the real native timeout event promptly; verify the production requested duration separately.
  const timeout = vi.spyOn(AbortSignal, "timeout").mockImplementation(() => nativeTimeout(0));
  const create = pendingCreate();
  const hook = mount();
  const first = hook.read().doSend("first");
  await new Promise((resolve) => setTimeout(resolve, 10));
  await first;
  expect(timeout.mock.calls).toEqual([[180_000]]);
  expect(create.signal()?.aborted).toBe(true);
  expect(hook.read().messages.at(-1)?.content).toContain("出错了：");
  expect(hook.read().conversationId).toBeNull();
  expect(hook.read().streaming).toBe(false);
  expect(streamChat).not.toHaveBeenCalled();
  timeout.mockRestore();
  create.fetch.mockResolvedValueOnce(createResponse(65));
  await hook.read().doSend("retry");
  expect(callbacks().payload.conversationId).toBe(65);
  expect(create.fetch).toHaveBeenCalledTimes(2);
});

it.each([0, -1, 1.5, "7", undefined, Number.MAX_SAFE_INTEGER + 1])(
  "rejects invalid created id %s without sending chat and permits retry",
  async (id) => {
    const fetch = vi.fn().mockResolvedValueOnce(createResponse(id)).mockResolvedValueOnce(createResponse(66));
    vi.stubGlobal("fetch", fetch);
    const hook = mount();
    await hook.read().doSend("invalid");
    expect(streamChat).not.toHaveBeenCalled();
    expect(hook.read().conversationId).toBeNull();
    expect(hook.read().streaming).toBe(false);
    expect(hook.read().messages.at(-1)?.content).toContain("出错了：");
    await hook.read().doSend("retry");
    expect(callbacks().payload.conversationId).toBe(66);
    expect(fetch).toHaveBeenCalledTimes(2);
  }
);

it("invalidates the old create on a new view and does not clear that view's pending create", async () => {
  const oldResponse = deferred<Response>();
  const newResponse = deferred<Response>();
  const fetch = vi.fn().mockReturnValueOnce(oldResponse.promise).mockReturnValueOnce(newResponse.promise);
  vi.stubGlobal("fetch", fetch);
  const hook = mount();
  const oldSend = hook.read().doSend("old view");
  hook.read().stop();
  hook.read().setConversationId(null);
  hook.read().setMessages([]);
  const newSend = hook.read().doSend("new view");
  oldResponse.resolve(createResponse(81));
  await oldSend;
  expect(hook.read().conversationId).toBeNull();
  expect(hook.onConversationId).not.toHaveBeenCalled();
  expect(hook.read().streaming).toBe(true);
  hook.read().stop();
  const retry = hook.read().doSend("new retry");
  expect(fetch).toHaveBeenCalledTimes(2);
  newResponse.resolve(createResponse(82));
  await Promise.all([newSend, retry]);
  expect(vi.mocked(streamChat).mock.calls.map(([payload]) => [payload.content, payload.conversationId])).toEqual([
    ["new retry", 82],
  ]);
  expect(hook.onConversationId.mock.calls).toEqual([[82]]);
});

it("does not replace a selected historical id with a late create result", async () => {
  const create = pendingCreate();
  const hook = mount();
  const first = hook.read().doSend("old view");
  hook.read().stop();
  hook.read().setConversationId(91);
  create.response.resolve(createResponse(92));
  await first;
  expect(hook.read().conversationId).toBe(91);
  expect(hook.onConversationId).not.toHaveBeenCalled();
  await hook.read().doSend("history");
  expect(callbacks().payload.conversationId).toBe(91);
  expect(create.fetch).toHaveBeenCalledOnce();
});

it("does not publish a pending create or stream after unmount", async () => {
  const create = pendingCreate();
  const hook = mount();
  const first = hook.read().doSend("first");
  const before = hook.read().messages;
  hook.unmount();
  create.response.resolve(createResponse(93));
  await first;
  expect(streamChat).not.toHaveBeenCalled();
  expect(hook.read().conversationId).toBeNull();
  expect(hook.read().messages).toEqual(before);
  expect(hook.onConversationId).not.toHaveBeenCalled();
  expect(hook.onStreamEnd).not.toHaveBeenCalled();
});

it("ignores late callbacks and old completion while a newer answer remains active", async () => {
  const first = pendingStream();
  const second = pendingStream();
  const hook = mount();
  const oldSend = hook.read().doSend("first");
  await flush();
  const old = callbacks();
  old.chunk("partial");
  hook.read().stop();
  const newSend = hook.read().doSend("again");
  await flush();
  callbacks(1).chunk("current answer");
  const before = hook.read().messages;
  const sideEffects = hook.onStreamEnd.mock.calls.length;
  old.chunk("late");
  old.meta({ conversation_id: 999, agent_event: "clarification", agent_run_id: "late", agent_state_version: 4 });
  old.error("late error");
  old.steps([{ label: "late", detail: "late" }]);
  old.restart();
  first.resolve(undefined);
  await oldSend;
  expect(hook.read().messages).toEqual(before);
  expect(hook.read().conversationId).toBe(41);
  expect(hook.read().pendingAgentRun).toBeNull();
  expect(hook.read().clarifyRounds).toBe(0);
  expect(hook.read().streaming).toBe(true);
  expect(hook.onConversationId.mock.calls).toEqual([[41]]);
  expect(hook.onStreamEnd.mock.calls).toHaveLength(sideEffects);
  second.resolve(undefined);
  await newSend;
  expect(hook.read().streaming).toBe(false);
});

it("blocks duplicate sends synchronously while the initial create is pending", async () => {
  const create = pendingCreate();
  const hook = mount();
  const send = hook.read().doSend;
  const first = send("first");
  await send("duplicate");
  expect(create.fetch).toHaveBeenCalledOnce();
  expect(hook.read().messages.map((message) => message.content)).toEqual(["first", ""]);
  create.response.resolve(createResponse(95));
  await first;
  expect(vi.mocked(streamChat).mock.calls.map(([payload]) => payload.content)).toEqual(["first"]);
});

it("preserves Agent clarification/resume metadata, steps, restart and final coverage", async () => {
  const first = pendingStream();
  const second = pendingStream();
  const hook = mount();
  hook.read().setConversationId(101);
  const sending = hook.read().doSend("agent");
  const firstCallbacks = callbacks();
  firstCallbacks.chunk("clarify this");
  const clarification: ChatMeta = {
    conversation_id: 101,
    agent_event: "clarification",
    agent_run_id: "run-1",
    agent_state_version: 2,
    sources: [{ source: "law", article: "article" }],
  };
  firstCallbacks.meta(clarification);
  first.resolve(undefined);
  await sending;
  expect(hook.read().pendingAgentRun).toEqual({ runId: "run-1", stateVersion: 2 });
  expect(hook.read().clarifyRounds).toBe(1);
  expect(hook.read().messages.at(-1)?.agentNote).toEqual({ kind: "clarification", round: 1 });
  expect(hook.read().messages.at(-1)?.sources).toEqual(clarification.sources);
  const resumed = hook.read().doSend("resume", "data:image/png;base64,AA", "shown", true);
  const next = callbacks(1);
  expect(next.payload).toEqual({
    conversationId: 101,
    content: "resume",
    image: "data:image/png;base64,AA",
    truncated: true,
    agentRunId: "run-1",
    agentStateVersion: 2,
  });
  next.chunk("before restart");
  next.restart();
  next.chunk("final answer");
  next.steps([{ label: "checked", detail: "complete" }]);
  next.meta({ agent_event: "final", coverage_status: "full", conversation_id: 101 });
  second.resolve(undefined);
  await resumed;
  expect(hook.read().messages.at(-1)).toMatchObject({
    content: "final answer",
    steps: [{ label: "checked", detail: "complete" }],
    coverage: { status: "full", uncovered: [] },
  });
  expect(hook.read().pendingAgentRun).toBeNull();
  expect(hook.read().clarifyRounds).toBe(0);
  expect(fetch).not.toHaveBeenCalled();
});
