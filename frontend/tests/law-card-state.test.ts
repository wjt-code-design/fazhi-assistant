// 无 DOM harness：只验证 hook 请求/缓存与失效行为，不声称浏览器渲染验收。
import { beforeEach, describe, expect, it, vi } from "vitest";
const mocks = vi.hoisted(() => ({ detail: vi.fn(), setState: vi.fn() }));
vi.mock("react", () => ({
  useRef: (value: unknown) => ({ current: value }),
  useState: () => [null, mocks.setState],
}));
vi.mock("@/lib/api", () => ({ lawApi: { detail: mocks.detail } }));
import { useLawCards } from "@/lib/hooks/useLawCards";

const ref = {
  getAttribute: () => "民法典",
  textContent: "第675条",
  closest: () => null,
} as unknown as Element;

describe("snapshot cache isolation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });
  it("deduplicates within run but never shares another run's snapshot", async () => {
    mocks.detail.mockResolvedValue({ content: "snapshot", is_snapshot: true });
    const cards = useLawCards();
    await cards.toggleInlineLaw(ref, 0, "run-old");
    await cards.toggleInlineLaw(ref, 0, "run-old");
    await cards.toggleInlineLaw(ref, 1, "run-new");
    expect(mocks.detail.mock.calls).toEqual([
      ["民法典", "第675条", "run-old"],
      ["民法典", "第675条", "run-new"],
    ]);
  });
  it("does not display an obsolete request after clearing the conversation", async () => {
    let resolve!: (value: unknown) => void;
    mocks.detail.mockReturnValue(
      new Promise((done) => {
        resolve = done;
      })
    );
    const cards = useLawCards();
    const pending = cards.toggleInlineLaw(ref, 0, "run-old");
    cards.clearExpandedLaw();
    mocks.setState.mockClear();
    resolve({ content: "old" });
    await pending;
    expect(mocks.setState).not.toHaveBeenCalled();
  });
  it("preserves both toggles when the same reference is clicked twice before the request resolves", async () => {
    let resolve!: (value: unknown) => void;
    mocks.detail.mockReturnValue(
      new Promise((done) => {
        resolve = done;
      })
    );
    const cards = useLawCards();
    const first = cards.toggleInlineLaw(ref, 0, "run-old");
    const second = cards.toggleInlineLaw(ref, 0, "run-old");
    resolve({ content: "snapshot" });
    await Promise.all([first, second]);
    expect(mocks.detail).toHaveBeenCalledTimes(1);
    expect(mocks.setState).toHaveBeenCalledTimes(2);
  });
  it("retries failure with the same run, never falls back to current law", async () => {
    mocks.detail
      .mockRejectedValueOnce(new Error("404"))
      .mockResolvedValueOnce({ content: "snapshot" });
    const cards = useLawCards();
    await cards.toggleInlineLaw(ref, 0, "run-old");
    await cards.toggleInlineLaw(ref, 0, "run-old");
    expect(mocks.detail).toHaveBeenCalledTimes(2);
    expect(mocks.detail).toHaveBeenLastCalledWith("民法典", "第675条", "run-old");
  });
});
