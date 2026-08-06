// 浏览器录音 → WAV（16kHz / 单声道 / 16bit PCM）。
// 后端 /api/chat/transcribe 只接受 wav/mp3/m4a/flac/ogg，拒绝 webm/opus（浏览器
// MediaRecorder 默认产物），因此这里自行抓取 PCM 并编码为 WAV。
//
// 注意：ScriptProcessor 已被废弃（deprecated），但浏览器仍普遍可用；本项目用它换取
// 零依赖。需要时后续可迁移到 AudioWorklet。

const TARGET_RATE = 16000;
const BUFFER_SIZE = 4096;

export interface WavRecorder {
  /** 停止录音并返回完整的 WAV 音频 Blob。 */
  stop(): Promise<Blob>;
}

/** 线性插值重采样。sourceRate 与 targetRate 相等时原样返回。 */
function resample(chunks: Float32Array[], sourceRate: number, targetRate: number): Float32Array {
  const total = chunks.reduce((n, c) => n + c.length, 0);
  const input = new Float32Array(total);
  let offset = 0;
  for (const c of chunks) {
    input.set(c, offset);
    offset += c.length;
  }
  if (sourceRate === targetRate || input.length === 0) return input;

  const outputLength = Math.max(1, Math.round((input.length * targetRate) / sourceRate));
  const output = new Float32Array(outputLength);
  const ratio = input.length / outputLength;
  for (let i = 0; i < outputLength; i++) {
    const pos = i * ratio;
    const i0 = Math.floor(pos);
    const i1 = Math.min(i0 + 1, input.length - 1);
    const frac = pos - i0;
    output[i] = input[i0] * (1 - frac) + input[i1] * frac;
  }
  return output;
}

/** 将 Float32 样本（-1..1）编码为标准 WAV：44 字节头 + Int16LE 样本。 */
function encodeWav(samples: Float32Array, sampleRate: number): Blob {
  const dataLength = samples.length * 2;
  const buffer = new ArrayBuffer(44 + dataLength);
  const view = new DataView(buffer);

  const writeString = (offset: number, s: string) => {
    for (let i = 0; i < s.length; i++) view.setUint8(offset + i, s.charCodeAt(i));
  };

  writeString(0, "RIFF");
  view.setUint32(4, 36 + dataLength, true);
  writeString(8, "WAVE");
  writeString(12, "fmt ");
  view.setUint32(16, 16, true); // fmt 块大小
  view.setUint16(20, 1, true); // PCM 编码
  view.setUint16(22, 1, true); // 单声道
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // 字节率 = 采样率 × 块对齐
  view.setUint16(32, 2, true); // 块对齐 = 声道数 × 位深/8
  view.setUint16(34, 16, true); // 位深
  writeString(36, "data");
  view.setUint32(40, dataLength, true);

  for (let i = 0; i < samples.length; i++) {
    // clamp 到 Int16 范围（-32768..32767），避免溢出回绕。
    let s = Math.round(samples[i] * 32767);
    if (s > 32767) s = 32767;
    else if (s < -32768) s = -32768;
    view.setInt16(44 + i * 2, s, true);
  }

  return new Blob([buffer], { type: "audio/wav" });
}

/**
 * 开始录音。请求单声道麦克风，AudioContext 请求 16kHz；若浏览器不支持 16kHz 会
 * 落到设备采样率，stop() 时统一线性重采样到 16kHz。
 */
export async function startWavRecorder(): Promise<WavRecorder> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1 },
  });

  const ctx = new AudioContext({ sampleRate: TARGET_RATE });
  const source = ctx.createMediaStreamSource(stream);
  // 仅取第 0 声道（请求了单声道，实际即全部数据）。
  const processor = ctx.createScriptProcessor(BUFFER_SIZE, 1, 1);
  const chunks: Float32Array[] = [];
  let recording = true;

  processor.onaudioprocess = (e) => {
    if (!recording) return;
    const data = e.inputBuffer.getChannelData(0);
    chunks.push(new Float32Array(data));
  };

  // 必须连到 destination 才能触发 onaudioprocess；经零增益节点输出，避免录音时
  // 麦克风声音被扬声器放大（回声/啸叫）。
  const silent = ctx.createGain();
  silent.gain.value = 0;
  source.connect(processor);
  processor.connect(silent);
  silent.connect(ctx.destination);

  return {
    async stop(): Promise<Blob> {
      if (!recording) throw new Error("recorder already stopped");
      recording = false;
      processor.onaudioprocess = null;

      const sourceRate = ctx.sampleRate;
      try {
        source.disconnect();
        processor.disconnect();
        silent.disconnect();
      } catch {
        /* ignore */
      }
      stream.getTracks().forEach((t) => t.stop());
      await ctx.close();

      const samples = resample(chunks, sourceRate, TARGET_RATE);
      return encodeWav(samples, TARGET_RATE);
    },
  };
}
