"use client";
import { useEffect, useState } from "react";

// 交互判定（MAC/触控适配）：桌面纯鼠标 → hover 优先；触屏 / Mac 触控板（maxTouchPoints>0）→ click inline。
// 惰性初始化：移动端首帧就按真实设备能力判定，避免 useState(true) 让移动端首帧误走 hover 路径。
export function useHoverCapable(): boolean {
  const [capable, setCapable] = useState(() =>
    typeof window !== "undefined"
      ? window.matchMedia("(hover: hover)").matches && navigator.maxTouchPoints <= 0
      : true
  );
  useEffect(() => {
    if (typeof window === "undefined") return;
    setCapable(window.matchMedia("(hover: hover)").matches && navigator.maxTouchPoints <= 0);
  }, []);
  return capable;
}
