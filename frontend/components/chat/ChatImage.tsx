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
    // eslint-disable-next-line @next/next/no-img-element -- src 为 data:/blob: URL（本地预览或经 loadMediaSrc 带鉴权取的 blob），next/image 不支持且其服务端优化器不带令牌会 401。详见 T12-D 报告。
    <img
      src={src}
      alt="附图"
      className="mt-1 max-h-56 rounded-lg border border-mist object-contain"
    />
  );
}
