"use client";

import { useEffect } from "react";

/** PWA service worker 注册（2026-08-08）：仅生产注册，开发不注册避免缓存干扰热更新。 */
export default function SWRegister() {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production") return;
    if (!("serviceWorker" in navigator)) return;
    navigator.serviceWorker.register("/sw.js").catch((e) => {
      console.warn("[sw] 注册失败:", e);
    });
  }, []);
  return null;
}
