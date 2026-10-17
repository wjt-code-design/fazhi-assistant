// 票 W7-FIX B5/B7（2026-10-17）：前端「识图失败」只认**结构化信号**，不认状态码印象。
//
// 为什么这几条必须在浏览器侧独立成判据（后端 TestClient 那条钉的是"信号发得出"，钉不到"消费端认什么"）：
// 改前 `lib/api.ts` 只看「502 ＋ 本轮带图」，而 502 可能是**反代合成的**（请求根本没到 FastAPI），
// 于是基建故障被标成"图片识别失败"，用户按提示重试永远好不了。
// 正例两条（头 / detail 各一条——detail 那条是代理剥掉自定义响应头时的退路），
// 反例两条（裸 502、以及带**别的** detail 的 502）：反例必须**不**被标成图片失败。
import { afterEach, expect, it, vi } from "vitest";
import { streamChat } from "@/lib/api";
import {
  IMAGE_DESCRIBE_FAILED_DETAIL,
  IMAGE_DESCRIBE_FAILED_MESSAGE,
  IMAGE_FAILURE_HEADER,
  IMAGE_FAILURE_HEADER_VALUE,
} from "@/lib/constants";

const IMAGE = "data:image/png;base64,iVBORw0KGgo=";

afterEach(() => vi.unstubAllGlobals());

function stubResponse(status: number, body: string, headers: Record<string, string> = {}) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(body, { status, headers }))
  );
}

it("labels a 502 carrying the image-failure response header as an image failure", async () => {
  stubResponse(502, '{"detail":"anything"}', {
    "Content-Type": "application/json",
    [IMAGE_FAILURE_HEADER]: IMAGE_FAILURE_HEADER_VALUE,
  });
  const error = vi.fn();
  await streamChat({ content: "这合同有效吗", image: IMAGE }, vi.fn(), vi.fn(), error);
  expect(error).toHaveBeenCalledWith(IMAGE_DESCRIBE_FAILED_MESSAGE, { turnNotCommitted: true });
});

it("still labels it when a proxy strips the header but the detail matches exactly", async () => {
  stubResponse(502, JSON.stringify({ detail: IMAGE_DESCRIBE_FAILED_DETAIL }), {
    "Content-Type": "application/json",
  });
  const error = vi.fn();
  await streamChat({ content: "这合同有效吗", image: IMAGE }, vi.fn(), vi.fn(), error);
  expect(error.mock.calls[0][0]).toBe(IMAGE_DESCRIBE_FAILED_MESSAGE);
});

it("does NOT label a proxy-synthesized bare 502 as an image failure", async () => {
  // nginx/Caddy 在 upstream 挂掉时自己造的 502：没有后端那条头，body 也不是 FastAPI 的 JSON。
  stubResponse(502, "<html>502 Bad Gateway</html>", { "Content-Type": "text/html" });
  const error = vi.fn();
  await streamChat({ content: "这合同有效吗", image: IMAGE }, vi.fn(), vi.fn(), error);
  expect(error.mock.calls[0][0]).not.toBe(IMAGE_DESCRIBE_FAILED_MESSAGE);
  expect(error.mock.calls[0][1]).toBeUndefined(); // 不是"未提交"那一类 ⇒ 用户气泡留在原地
  expect(error.mock.calls[0][0]).toContain("502");
});

it("does NOT label a 502 with a different detail as an image failure", async () => {
  // 同码不同语义：语音那条路由的 502 文案（本轮带图也不该被认成识图失败）。
  stubResponse(502, JSON.stringify({ detail: "语音识别服务暂时不可用，请稍后重试" }), {
    "Content-Type": "application/json",
  });
  const error = vi.fn();
  await streamChat({ content: "这合同有效吗", image: IMAGE }, vi.fn(), vi.fn(), error);
  expect(error.mock.calls[0][0]).toBe("语音识别服务暂时不可用，请稍后重试");
  expect(error.mock.calls[0][0]).not.toBe(IMAGE_DESCRIBE_FAILED_MESSAGE);
});

it("does NOT label a signalled 502 as image failure when this turn carried no image", async () => {
  stubResponse(502, "{}", {
    "Content-Type": "application/json",
    [IMAGE_FAILURE_HEADER]: IMAGE_FAILURE_HEADER_VALUE,
  });
  const error = vi.fn();
  await streamChat({ content: "纯文本提问" }, vi.fn(), vi.fn(), error);
  expect(error.mock.calls[0][0]).not.toBe(IMAGE_DESCRIBE_FAILED_MESSAGE);
});
