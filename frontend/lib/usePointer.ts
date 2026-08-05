"use client";
import { useEffect, useState } from "react";

// 交互判定（MAC/触控适配）：桌面纯鼠标 → hover 优先；触屏 / Mac 触控板（maxTouchPoints>0）→ click inline。
export function useHoverCapable(): boolean {
  const [capable, setCapable] = useState(true);
  useEffect(() => {
    if (typeof window === "undefined") return;
    setCapable(window.matchMedia("(hover: hover)").matches && navigator.maxTouchPoints <= 0);
  }, []);
  return capable;
}
