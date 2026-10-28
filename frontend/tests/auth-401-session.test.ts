import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { api, getToken, setToken, streamChat } from "@/lib/api";

/**
 * B05：旧账号请求迟到 401 不能清掉新账号的 token/导航；
 * 当前账号自己的 401 仍必须失效。普通请求与流式请求同口径。
 */

const store = new Map<string, string>();

beforeEach(() => {
  store.clear();
  vi.stubGlobal("localStorage", {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => store.set(key, value),
    removeItem: (key: string) => store.delete(key),
  });
  vi.stubGlobal("window", { location: { pathname: "/chat", href: "" } });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function deferredFetch() {
  let resolve!: (response: Response) => void;
  vi.stubGlobal(
    "fetch",
    vi.fn(
      () =>
        new Promise<Response>((done) => {
          resolve = done;
        })
    )
  );
  return (response: Response) => resolve(response);
}

it("late 401 from the old token does not clear the new session", async () => {
  setToken("token-A");
  const finish = deferredFetch();
  const pending = api.get("/api/conversations");
  setToken("token-B");
  finish(new Response(null, { status: 401 }));

  await expect(pending).rejects.toMatchObject({ status: 401 });
  expect(getToken()).toBe("token-B");
  expect((window as unknown as { location: { href: string } }).location.href).toBe("");
});

it("401 for the current token still clears and redirects", async () => {
  setToken("token-A");
  const finish = deferredFetch();
  const pending = api.get("/api/conversations");
  finish(new Response(null, { status: 401 }));

  await expect(pending).rejects.toMatchObject({ status: 401 });
  expect(getToken()).toBe(null);
  expect((window as unknown as { location: { href: string } }).location.href).toBe("/login");
});

it("late 401 on a stream does not notify or clear the new session", async () => {
  setToken("token-A");
  const finish = deferredFetch();
  const onError = vi.fn();
  const pending = streamChat(
    { content: "hi" },
    () => {},
    () => {},
    onError
  );
  setToken("token-B");
  finish(new Response(null, { status: 401 }));

  await pending;
  expect(getToken()).toBe("token-B");
  expect(onError).not.toHaveBeenCalled();
});

it("401 on the current stream token clears and reports", async () => {
  setToken("token-A");
  const finish = deferredFetch();
  const onError = vi.fn();
  const pending = streamChat(
    { content: "hi" },
    () => {},
    () => {},
    onError
  );
  finish(new Response(null, { status: 401 }));

  await pending;
  expect(getToken()).toBe(null);
  expect((window as unknown as { location: { href: string } }).location.href).toBe("/login");
  expect(onError).toHaveBeenCalledWith("登录已过期，请重新登录");
});
