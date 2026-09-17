"use client";
// T2.3 状态收敛：语音输入（M2）。toggleVoice/transcribeAndFill/legacyWebSpeech 及卸载清理
// 为 chat 页原实现逐行搬移，零行为变更；转写结果回填经 opts.setInput 注入。
import { useEffect, useRef, useState, type Dispatch, type SetStateAction } from "react";
import { transcribeApi } from "@/lib/api";
import { startWavRecorder } from "@/lib/recorder";

export function useVoice(opts: { setInput: Dispatch<SetStateAction<string>> }) {
  const [listening, setListening] = useState(false); // 语音输入（Web Speech API）录音中
  const recRef = useRef<{ stop: () => void } | null>(null);
  const [transcribing, setTranscribing] = useState(false);
  const wavRecRef = useRef<{ stop: () => Promise<Blob> } | null>(null);
  const voiceTimeoutRef = useRef<number | null>(null);

  // 卸载清理：语音超时 + 停止正在录音的麦克风（对抗审计 v2 #11：离开页面不 stop，
  // 麦克风权限/轨道持续占用；静默丢弃录音，只释放轨道）
  useEffect(() => {
    return () => {
      if (voiceTimeoutRef.current) clearTimeout(voiceTimeoutRef.current);
      if (wavRecRef.current) {
        const w = wavRecRef.current;
        wavRecRef.current = null;
        void w.stop().catch(() => {});
      }
    };
  }, []);

  async function toggleVoice() {
    // 语音转文字（M2）：优先后端 Qwen livetranslate 语音模型转写（麦克风录音→WAV→上传，
    // 识别质量优于浏览器 Web Speech）；失败/无麦克风权限 → 回退浏览器 Web Speech。
    if (listening) {
      const w = wavRecRef.current;
      wavRecRef.current = null;
      if (voiceTimeoutRef.current) clearTimeout(voiceTimeoutRef.current);
      setListening(false);
      if (w) {
        const blob = await w.stop();
        void transcribeAndFill(blob);
      }
      return;
    }
    if (window.AudioContext) {
      try {
        // getUserMedia 缺失会在此抛错，被 catch 兜底回退 Web Speech
        wavRecRef.current = await startWavRecorder();
        // 60s 自动停止并转写
        voiceTimeoutRef.current = window.setTimeout(() => {
          const w = wavRecRef.current;
          if (w) {
            wavRecRef.current = null;
            setListening(false);
            void w
              .stop()
              .then(transcribeAndFill)
              .catch(() => {});
          }
        }, 60000);
        setListening(true);
        return;
      } catch {
        // 麦克风权限拒绝等 → 回退 Web Speech
      }
    }
    legacyWebSpeech();
  }

  async function transcribeAndFill(blob: Blob) {
    setTranscribing(true);
    try {
      const r = await transcribeApi.post(blob);
      opts.setInput((prev) => (prev ? prev + r.text : r.text));
    } catch (err) {
      alert(`语音转写失败（${err instanceof Error ? err.message : err}），已回退浏览器识别`);
      legacyWebSpeech();
    } finally {
      setTranscribing(false);
    }
  }

  function legacyWebSpeech() {
    // 兜底：浏览器 Web Speech API（zh-CN 连续识别）
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) {
      alert("当前浏览器不支持语音输入，请用 Chrome 或 Edge");
      return;
    }
    if (listening) {
      recRef.current?.stop();
      setListening(false);
      return;
    }
    const rec = new SR();
    rec.lang = "zh-CN";
    rec.continuous = true;
    rec.interimResults = true;
    recRef.current = rec;
    rec.onresult = (e: any) => {
      let text = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        text += e.results[i][0].transcript;
      }
      opts.setInput((prev) => (prev ? prev + text : text));
    };
    rec.onend = () => setListening(false);
    rec.onerror = () => {
      setListening(false);
      alert("语音识别失败，请检查麦克风权限后重试");
    };
    rec.start();
    setListening(true);
  }

  return { listening, transcribing, toggleVoice };
}
