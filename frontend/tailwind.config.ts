import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#1a2332", // 冷深蓝黑 · 主文字 / 深色区域
        "ink-2": "#243044", // 深色面板第二层次
        parchment: "#f4f6f9", // 冷云灰 · 页面底
        paper: "#ffffff", // 卡片底
        slate: "#64748b", // 冷灰蓝 · 次要文字 / 边框
        accent: "#0284c7", // 青蓝 · 单色强调（细节）
        "accent-deep": "#0369a1", // 青蓝加深（hover）
        jade: "#2d6a4f", // 墨绿 · 成功 / 正向
        mist: "#e2e8f0", // 冷灰 · 分割线 / 浅灰底
        error: "#dc2626", // 错误语义
        cool: "#38bdf8", // 冷青 · 极细点缀（替代旧 gold）
      },
      fontFamily: {
        serif: ['"Songti SC"', '"STSong"', '"SimSun"', '"Noto Serif CJK SC"', "serif"],
        sans: ['"PingFang SC"', '"Microsoft YaHei"', '"Hiragino Sans GB"', '"Noto Sans CJK SC"', "sans-serif"],
      },
      borderRadius: {
        DEFAULT: "6px",
      },
      boxShadow: {
        card: "0 1px 2px rgba(15,23,42,.04), 0 2px 8px rgba(15,23,42,.05)",
        lift: "0 2px 6px rgba(15,23,42,.05), 0 10px 24px -8px rgba(15,23,42,.12)",
      },
      transitionTimingFunction: {
        "ease-out-expo": "cubic-bezier(0.22, 1, 0.36, 1)",
        spring: "cubic-bezier(0.34, 1.4, 0.64, 1)",
      },
    },
  },
  plugins: [],
};
export default config;
