import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      // colors 全部映射到 CSS 变量（globals.css :root）——换主题只改变量表，全页面联动。
      // 透明度类（bg-ink/50 等）走 Tailwind 3.4 color-mix(in oklab, var(--x), transparent)。
      colors: {
        ink: "var(--ink)", // 深墨蓝 · 主文字 / 深色气泡 / 深色侧栏
        "ink-2": "var(--ink-2)", // 深色面板第二层次
        parchment: "var(--parchment)", // 樱海浅底 · 页面底
        paper: "var(--paper)", // 卡片底
        slate: "var(--slate)", // 冷灰蓝 · 次要文字
        accent: "var(--accent)", // 樱花粉 · 单色强调（细节 / 可读文字）
        "accent-deep": "var(--accent-deep)", // 樱花粉深（hover / 强调文字）
        jade: "var(--jade)", // 玉绿 · 成功 / 正向
        mist: "var(--mist)", // 淡蓝灰 · 分割线 / 浅灰底
        error: "var(--error)", // 错误语义
        cool: "var(--sea)", // 海盐蓝 · 极细点缀 / 法条引用
        sea: "var(--sea)", // 海盐蓝 · 辅助
      },
      fontFamily: {
        serif: ['"Songti SC"', '"STSong"', '"SimSun"', '"Noto Serif CJK SC"', "serif"],
        sans: ['"PingFang SC"', '"Microsoft YaHei"', '"Hiragino Sans GB"', '"Noto Sans CJK SC"', "sans-serif"],
      },
      borderRadius: {
        DEFAULT: "6px",
      },
      boxShadow: {
        card: "0 1px 2px rgba(42,59,92,.04), 0 2px 8px rgba(42,59,92,.05)",
        lift: "0 2px 6px rgba(42,59,92,.05), 0 10px 24px -8px rgba(42,59,92,.12)",
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
