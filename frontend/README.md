# 法智前端（frontend）

Next.js 14 App Router + React 18 + Tailwind 3.4 + TypeScript。

## 质量工具链（2026-09-15 批次 0 引入）

| 命令 | 作用 |
|---|---|
| `npm run lint` | ESLint（next/core-web-vitals），要求 0 error |
| `npm run format:check` | Prettier 检查（不自动改写） |
| `npm run test` | Vitest 纯函数测试（annotate / scope / SSE 帧解析） |
| `npm run check` | lint + tsc + test 全量门禁 |
| `npm run build` | 生产构建 |

### Prettier 渐进策略说明

执行书红线：**不**对既有文件运行 `prettier --write`（会产生海量无关 diff）。
引入时既有 9 个文件不符合当前 `.prettierrc`，已冻结进 `.prettierignore`（文件内有清单与原因）。
规则：

1. 冻结清单内的文件保持原状，直到它被结构性重写（如批次 2 拆分产出的新文件）；
2. **新增文件必须通过 `format:check`**，不允许加入 `.prettierignore`；
3. 批次 2 搬移时随文件迁移处理：老代码拆到新文件时顺手符合格式（改动被包裹在"纯搬移" commit 内可接受）。

### 已知仓库问题（与前端代码无关）

本仓库 master 中段历史存在丢失对象（`git fsck` 可见，远端无备份）。
影响：`git rev-list` 全量遍历与自动 gc 会报错；路径限定的 `diff/show` 正常。
处置：不要对该仓库做历史重写/浅克隆依赖；验收命令请使用 `git diff <base>..HEAD -- <path>` 形式。
