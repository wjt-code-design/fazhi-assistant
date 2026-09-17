"use client";
// T2.2 自 chat/page.tsx 原样搬移，零行为变更。
import { useEffect, useState } from "react";
import { loadMediaSrc } from "@/lib/api";

export function ChatImage({
  dataURL,
  imgRef,
  thumbRef,
}: {
  dataURL?: string;
  imgRef?: string;
  thumbRef?: string;
}) {
  const [src, setSrc] = useState<string | undefined>(dataURL);
  useEffect(() => {
    if (dataURL) {
      setSrc(dataURL);
      return;
    }
    const ref = thumbRef || imgRef;
    if (!ref) return;
    let alive = true;
    loadMediaSrc(ref).then((u) => {
      if (alive && u) setSrc(u);
    });
    return () => {
      alive = false;
    };
  }, [dataURL, imgRef, thumbRef]);
  if (!src) return null;
  return (
    <img
      src={src}
      alt="附图"
      className="mt-1 max-h-56 rounded-lg border border-mist object-contain"
    />
  );
}
