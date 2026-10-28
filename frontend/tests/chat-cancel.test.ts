import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { streamChat } from "@/lib/api";

const cleanups: (() => void)[] = [];
beforeEach(() => vi.useFakeTimers());
afterEach(async () => {
  for (const cleanup of cleanups.splice(0)) cleanup();
  await Promise.resolve();
  vi.clearAllTimers();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

// Fetch is the only replacement: cancellation uses native signals/Response/ReadableStream.
function pendingFetch() {
  let signal: AbortSignal;
  let finish: (response: Response) => void;
  const fetch = vi.fn((_url: string, init: RequestInit) => {
    signal = init.signal!;
    return new Promise<Response>((resolve, reject) => {
      finish = resolve;
      signal.addEventListener("abort", () => reject(signal.reason), { once: true });
    });
  });
  vi.stubGlobal("fetch", fetch);
  cleanups.push(() => finish?.(new Response("")));
  return { fetch, signal: () => signal };
}

function liveStream(honorAbort = true) {
  let signal: AbortSignal;
  let sink: ReadableStreamDefaultController<Uint8Array>;
  let closed = false;
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      sink = controller;
    },
    cancel() {
      closed = true;
    },
  });
  vi.stubGlobal(
    "fetch",
    vi.fn((_url: string, init: RequestInit) => {
      signal = init.signal!;
      if (honorAbort)
        signal.addEventListener(
          "abort",
          () => {
            if (!closed) {
              closed = true;
              sink.error(signal.reason);
            }
          },
          { once: true }
        );
      return Promise.resolve(new Response(stream));
    })
  );
  const close = () => {
    if (!closed) {
      closed = true;
      sink.close();
    }
  };
  cleanups.push(close);
  return {
    signal: () => signal,
    write: (data: string) => sink.enqueue(new TextEncoder().encode(data)),
    close,
  };
}

it("stops before fetch returns without reporting a network error", async () => {
  const request = pendingFetch();
  const controller = new AbortController();
  const error = vi.fn();
  const running = streamChat(
    { content: "first" },
    vi.fn(),
    vi.fn(),
    error,
    undefined,
    undefined,
    controller.signal
  );
  controller.abort();
  expect(request.signal().aborted).toBe(true);
  await running;
  expect(error).not.toHaveBeenCalled();
  expect(vi.getTimerCount()).toBe(0);
});

it("stops a pending read after partial text without error", async () => {
  const response = liveStream();
  const controller = new AbortController();
  const chunk = vi.fn();
  const error = vi.fn();
  const running = streamChat(
    { content: "first" },
    chunk,
    vi.fn(),
    error,
    undefined,
    undefined,
    controller.signal
  );
  response.write('data: {"content":"partial"}\n\n');
  await vi.waitFor(() => expect(chunk).toHaveBeenCalledWith("partial"));
  controller.abort();
  expect(response.signal().aborted).toBe(true);
  await running;
  expect(error).not.toHaveBeenCalled();
  expect(vi.getTimerCount()).toBe(0);
});

it("drops late data from a transport that has not settled after abort", async () => {
  const response = liveStream(false);
  const controller = new AbortController();
  const chunk = vi.fn();
  const meta = vi.fn();
  const running = streamChat(
    { content: "first" },
    chunk,
    meta,
    vi.fn(),
    undefined,
    undefined,
    controller.signal
  );
  await Promise.resolve();
  controller.abort();
  response.write('data: {"content":"late","conversation_id":99}\n\n');
  response.close();
  await running;
  expect(chunk).not.toHaveBeenCalled();
  expect(meta).not.toHaveBeenCalled();
});

it("ignores remaining frames when a chunk callback stops the request", async () => {
  const response = liveStream(false);
  const controller = new AbortController();
  const chunk = vi.fn(() => controller.abort());
  const meta = vi.fn();
  const running = streamChat(
    { content: "first" },
    chunk,
    meta,
    vi.fn(),
    undefined,
    undefined,
    controller.signal
  );
  response.write('data: {"content":"first"}\n\ndata: {"content":"late","conversation_id":99}\n\n');
  response.close();
  await running;
  expect(chunk.mock.calls).toEqual([["first"]]);
  expect(meta).not.toHaveBeenCalled();
});

it("does not issue fetch for an already cancelled request", async () => {
  const controller = new AbortController();
  controller.abort();
  const fetch = vi.fn().mockResolvedValue(new Response(""));
  vi.stubGlobal("fetch", fetch);
  await streamChat({}, vi.fn(), vi.fn(), vi.fn(), undefined, undefined, controller.signal);
  expect(fetch).not.toHaveBeenCalled();
  expect(vi.getTimerCount()).toBe(0);
});

it("does not handle a late HTTP error after cancellation", async () => {
  let finish: (response: Response) => void;
  vi.stubGlobal(
    "fetch",
    vi.fn(
      () =>
        new Promise<Response>((resolve) => {
          finish = resolve;
        })
    )
  );
  const controller = new AbortController();
  const error = vi.fn();
  const running = streamChat({}, vi.fn(), vi.fn(), error, undefined, undefined, controller.signal);
  controller.abort();
  finish!(new Response('{"detail":"late error"}', { status: 403 }));
  await running;
  expect(error).not.toHaveBeenCalled();
});

it("keeps normal content/meta/steps/restart behavior with an optional signal", async () => {
  const response = liveStream();
  const controller = new AbortController();
  const chunk = vi.fn(),
    meta = vi.fn(),
    error = vi.fn(),
    steps = vi.fn(),
    restart = vi.fn();
  const running = streamChat(
    { content: "normal", conversationId: 7 },
    chunk,
    meta,
    error,
    steps,
    restart,
    controller.signal
  );
  response.write(
    'data: {"content":"answer"}\n\ndata: {"type":"step","steps":[]}\n\ndata: {"type":"restart"}\n\ndata: {"type":"final","conversation_id":7,"run_id":"run-test","coverage_status":"full"}\n\n'
  );
  response.close();
  await running;
  expect(chunk).toHaveBeenCalledWith("answer");
  expect(steps).toHaveBeenCalledWith([]);
  expect(restart).toHaveBeenCalledOnce();
  expect(meta).toHaveBeenCalledWith(
    expect.objectContaining({ conversation_id: 7, agent_event: "final" })
  );
  expect(error).not.toHaveBeenCalled();
  expect(controller.signal.aborted).toBe(false);
  expect(vi.getTimerCount()).toBe(0);
});

it("keeps the 180-second idle watchdog and reports timeout once", async () => {
  const request = pendingFetch();
  const error = vi.fn();
  const running = streamChat({}, vi.fn(), vi.fn(), error);
  await vi.advanceTimersByTimeAsync(180_000);
  await running;
  expect(request.signal().aborted).toBe(true);
  expect(error.mock.calls).toEqual([["连接超时，已中断"]]);
  expect(vi.getTimerCount()).toBe(0);
});

it("keeps processing alive with heartbeats beyond 180 seconds and still stops cleanly", async () => {
  const response = liveStream();
  const controller = new AbortController();
  const chunk = vi.fn(),
    meta = vi.fn(),
    error = vi.fn(),
    steps = vi.fn(),
    restart = vi.fn();
  let finished = false;
  const running = streamChat(
    { content: "pending agent" },
    chunk,
    meta,
    error,
    steps,
    restart,
    controller.signal
  ).then(() => {
    finished = true;
  });
  response.write('data: {"type":"agent_status","status":"processing"}\n\n');
  await vi.advanceTimersByTimeAsync(0);

  // Thirteen 15-second intervals outlast the watchdog's original 180-second deadline.
  for (let index = 0; index < 13; index++) {
    await vi.advanceTimersByTimeAsync(15_000);
    response.write(": heartbeat\n\n");
    await vi.advanceTimersByTimeAsync(0);
    expect(response.signal().aborted).toBe(false);
    expect(finished).toBe(false);
    expect(vi.getTimerCount()).toBe(1);
  }
  expect(chunk).not.toHaveBeenCalled();
  expect(meta).not.toHaveBeenCalled();
  expect(error).not.toHaveBeenCalled();
  expect(steps).not.toHaveBeenCalled();
  expect(restart).not.toHaveBeenCalled();

  controller.abort();
  expect(response.signal().aborted).toBe(true);
  await running;
  expect(finished).toBe(true);
  expect(vi.getTimerCount()).toBe(0);
  await vi.advanceTimersByTimeAsync(180_000);
  expect(error).not.toHaveBeenCalled();
  expect(chunk).not.toHaveBeenCalled();
  expect(meta).not.toHaveBeenCalled();
});

it("propagates real network errors and clears the watchdog", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network failed")));
  await expect(streamChat({}, vi.fn(), vi.fn(), vi.fn())).rejects.toThrow("network failed");
  expect(vi.getTimerCount()).toBe(0);
});

it("removes the caller's abort listener after normal completion", async () => {
  const controller = new AbortController();
  const add = vi.spyOn(controller.signal, "addEventListener");
  const remove = vi.spyOn(controller.signal, "removeEventListener");
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("")));
  await streamChat({}, vi.fn(), vi.fn(), vi.fn(), undefined, undefined, controller.signal);
  expect(add).toHaveBeenCalledWith("abort", expect.any(Function), { once: true });
  expect(remove).toHaveBeenCalledWith("abort", add.mock.calls[0][1]);
});
