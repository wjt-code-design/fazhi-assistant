// SSE 帧解析（执行书 T0.3 最小抽函数）：从 streamChat 内联逻辑逐行等价抽出，行为零变更。
// 纯函数：不触碰网络/状态/DOM，供单测锁定以下语义——
//   1) 帧以空行（\n\n）分隔，残尾留在缓冲区等待下一 chunk；
//   2) 仅接受 "data: " 前缀帧；[DONE] 哨兵与其它非 data 行（event:/注释）忽略；
//   3) 返回帧体（已去 "data: " 前缀的 JSON 字符串数组），调用方负责 JSON.parse 与分发。

export interface SSEParsed {
  /** 完整帧的帧体（"data: " 之后的内容，原样保留） */
  frames: string[];
  /** 最后一个 \n\n 之后的残帧（含空串），需与后续 chunk 拼接后再喂 */
  rest: string;
}

export function parseSSEFrames(buffer: string): SSEParsed {
  const parts = buffer.split("\n\n");
  const rest = parts.pop() ?? "";
  const frames: string[] = [];
  for (const part of parts) {
    const line = part.trim();
    if (!line.startsWith("data: ") || line.includes("[DONE]")) continue;
    frames.push(line.slice(6));
  }
  return { frames, rest };
}
