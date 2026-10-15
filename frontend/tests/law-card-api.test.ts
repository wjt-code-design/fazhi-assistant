import { afterEach, expect, it, vi } from "vitest";
import { lawApi, streamChat } from "@/lib/api";

afterEach(() => vi.unstubAllGlobals());

it("forwards final run id from the real SSE parser", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
    'data: {"type":"final","run_id":"run-old","coverage_status":"full"}\n\n',
    { headers: { "Content-Type": "text/event-stream" } },
  )));
  const meta = vi.fn();
  const error = vi.fn();
  await streamChat({ content: "test" }, vi.fn(), meta, error);
  expect(error).not.toHaveBeenCalled();
  expect(meta).toHaveBeenCalledWith(expect.objectContaining({ agent_run_id: "run-old", agent_event: "final" }));
});

it("includes the run in the authenticated lookup URL", async () => {
  const fetch = vi.fn().mockResolvedValue(new Response('{}', { headers: { "Content-Type": "application/json" } }));
  vi.stubGlobal("fetch", fetch);
  await lawApi.detail("民法典", "第675条", "run-old");
  expect(fetch.mock.calls[0][0]).toContain("&run_id=run-old");
});
