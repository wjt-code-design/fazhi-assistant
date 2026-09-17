import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import SWRegister from "./SWRegister";

export const metadata = {
  title: "法智 · AI 法律咨询小助手",
  description: "基于公开法律条文的智能问答。仅供参考，不构成正式法律意见。",
  manifest: "/manifest.webmanifest", // PWA（2026-08-08）：添加到主屏幕 / 安装
  appleWebApp: { capable: true, title: "法智", statusBarStyle: "default" },
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#2a3b5c", // 跟 --ink（樱花海深墨蓝）
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <head>
        <link rel="manifest" href="/manifest.webmanifest" />
        <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
        <meta name="mobile-web-app-capable" content="yes" />
      </head>
      <body className="antialiased bg-parchment text-ink">
        <AuthProvider>{children}</AuthProvider>
        <SWRegister />
      </body>
    </html>
  );
}
