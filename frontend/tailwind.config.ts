import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#15202e", // 深蓝黑，主文字/深色区域
        "ink-2": "#1e2c3f", // 深色面板第二层次
        parchment: "#f7f4ed", // 微暖纸色，页面底
        paper: "#fdfcf9", // 卡片底（近白微暖）
        slate: "#54627a", // 蓝调灰，次要文字/边框
        vermilion: "#c2402f", // 印章朱红，强调/CTA
        "vermilion-deep": "#a23223", // 朱红加深（hover）
        jade: "#2d6a4f", // 墨绿，成功/正向
        mist: "#e8e3d9", // 分割线/浅灰底
        error: "#b91c1c", // 错误语义
        gold: "#b08d57", // 点缀金，仅细节
      },
      fontFamily: {
        serif: ['"Songti SC"', '"STSong"', '"SimSun"', '"Noto Serif CJK SC"', "serif"],
        sans: ['"PingFang SC"', '"Microsoft YaHei"', '"Hiragino Sans GB"', '"Noto Sans CJK SC"', "sans-serif"],
      },
      borderRadius: {
        DEFAULT: "8px",
      },
      boxShadow: {
        card: "0 1px 2px rgba(21,32,46,.04), 0 2px 8px rgba(21,32,46,.05)",
        lift: "0 2px 6px rgba(21,32,46,.05), 0 10px 24px -8px rgba(21,32,46,.12)",
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
