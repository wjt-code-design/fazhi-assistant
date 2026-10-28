import type { Config } from "tailwindcss";

// colors 全部映射到 CSS 变量（globals.css :root）——换主题只改变量表，全页面联动。
// 透明度类（bg-ink/50 等）：Tailwind 3.4 不支持"变量色直接 /alpha"（静默丢弃），
// 用函数形式 `rgb(var(--x-rgb) / <alpha-value>)`（:root 有对应 RGB 三元组）。
// Tailwind 3.4 Config 类型未收录函数色（只收 string/嵌套对象），运行时支持——加 any 断言。
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const varColor = (hex: string, rgb: string): any => ({ opacityValue }: { opacityValue?: string }) =>
  opacityValue === undefined ? `var(${hex})` : `rgb(var(${rgb}) / ${opacityValue})`;

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: varColor("--ink", "--ink-rgb"), // 深墨蓝 · 主文字 / 深色气泡 / 深色侧栏
        "ink-2": varColor("--ink-2", "--ink-2-rgb"), // 深色面板第二层次
        parchment: varColor("--parchment", "--parchment-rgb"), // 樱海浅底 · 页面底
        paper: varColor("--paper", "--paper-rgb"), // 卡片底
        slate: varColor("--slate", "--slate-rgb"), // 冷灰蓝 · 次要文字
        accent: varColor("--accent", "--accent-rgb"), // 樱花粉 · 单色强调（细节 / 可读文字）
        "accent-deep": varColor("--accent-deep", "--accent-deep-rgb"), // 樱花粉深（hover / 强调文字）
        jade: varColor("--jade", "--jade-rgb"), // 玉绿 · 成功 / 正向
        mist: varColor("--mist", "--mist-rgb"), // 淡蓝灰 · 分割线 / 浅灰底
        error: varColor("--error", "--error-rgb"), // 错误语义
        cool: varColor("--sea", "--sea-rgb"), // 海盐蓝 · 极细点缀 / 法条引用
        sea: varColor("--sea", "--sea-rgb"), // 海盐蓝 · 辅助
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
