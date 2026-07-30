import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#1a2332", // 深蓝黑，主文字/深色区域
        parchment: "#f5f2eb", // 微暖旧纸色（偏灰不偏黄），页面底
        slate: "#4a5568", // 蓝调灰，次要文字/边框
        vermilion: "#c53d2d", // 印章朱红，强调/CTA
        "vermilion-deep": "#a8331f", // 朱红加深（hover）
        jade: "#2d6a4f", // 墨绿，成功/正向
        mist: "#e8e4dd", // 卡片底/分割线/浅灰
        error: "#b91c1c", // 错误语义
      },
      fontFamily: {
        serif: ['"Songti SC"', '"STSong"', '"SimSun"', '"Noto Serif CJK SC"', "serif"],
        sans: ['"PingFang SC"', '"Microsoft YaHei"', '"Hiragino Sans GB"', '"Noto Sans CJK SC"', "sans-serif"],
      },
      borderRadius: {
        DEFAULT: "6px", // 统一克制小圆角，法律文书的正式感
      },
    },
  },
  plugins: [],
};
export default config;
