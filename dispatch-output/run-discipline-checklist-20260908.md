# 运行纪律与收尾清单（run-6 期间整理，2026-09-08）

> 目的：把"运行前快照"制度化（P1-1 行动项）、列出 run-6 完成后的提交/核实清单，避免遗漏。
> 前提约束：run-6 结束前不改服务端运行代码、不重启服务、不新调 LLM。

## 1. 每次正式运行前的快照纪律（制度化，写入后续 runbook）

正式运行（Gate2/3/4/5 采集）启动前，必须先记录并留存：
1. `git rev-parse HEAD`（提交基线）
2. `git status --short`（工作区污染如实记录）
3. 服务进程启动时间与 PID（`Get-CimInstance Win32_Process | where CommandLine -match uvicorn`）
4. 采集 runner 版本 sha（`git hash-object backend/scripts/gate2_runner.py`）
5. 可选增强：复用 `gate1-freeze-manifest-v2.json`（HEAD+22 文件 hash 已锁定）做基线比对

## 2. run-6 结束后待办清单

### 2.1 判定与文档
- [x] 解析 `gate2-run-gate5-dev-run-6-sessions.json`，逐题判定（error_codes/final_chars/over2/命中）—— **1/10 机械通过（C05 首次完整六段式）**
- [x] 与 run-4（LongCat 无回喂）、run-5（qwen+回喂）横向对比，验证"错误回喂对 LongCat 同样成立"—— **成立：PLANNER_PARSE_ERROR 7→3/10**
- [x] 结果写入 `docs/gate5-formal-dev-20260908.md` 附 E

### 2.2 待提交清单（建议批次，运行代码不受影响）
- [x] 批次 A：`backend/scripts/gate2_runner.py` → commit `19becb0`
- [x] 批次 B：manifest-v2 / red-evidence / 附E / 结算文档 / task2-4 产物 → commit `d1215ac`（16 文件）
- [ ] （可选）后续批次：隐藏集验收结论发布时随 Owner 文档一起提交（task1 产物含隐藏题，**不入库**）

### 2.3 待核实项
- [x] **app.db 落库缺口 —— 已澄清为查询时区假象，非缺口**：conversations/agent_runs/messages 的 created_at 存 UTC（datetime.utcnow）；run-6 会话全部在库（C01 conv=2256，UTC 09:48=本地 17:48 与 runner 启动吻合）。教训：查询 DB 时间列须用 UTC；"缺口"判断链条（UUID 排序错误 → 'T' 格式错误 → 时区比较错误）三连误，最终以 conv_id 直查 conversations 表闭环定案。**关闭**
- [x] 双 runner：sessions 文件唯一（31KB/19:10 写入）无覆盖（台账#4，P3）
- [ ] 双 uvicorn（台账#5）：清理尝试证实 **kill venv 败者会连坐 job 进程树、误杀真实服务**（16:23 起服务被连带终止）；已重启（19:49，监听 PID 36812，health 200）。处置策略改为：**保持现状不 kill**，或未来以独立进程原生启动服务后统一替换。**服务重启记录**：对已固化 sessions/判定无影响；后续新 run 需按 §1 快照纪律重录服务启动时间

## 3. 已闭合（本轮并行）
- [x] task4 P2-1 red→green 梯度证据（docs/red-evidence-20260908.md）
- [x] A1 处置决策材料（dispatch-output/decision-a1-hidden-f1f5-20260908.md，待 Owner 拍板）
- [x] task4 全项（P1-1/1-2/2-1/2-2/2-3）响应文档

## 4. 运行窗口观察（run-6 期间）
- 17:48 启动，双 runner 进程存活；8000 端口持续存在 Established SSE 连接（当前题流式处理中）
- sessions 文件末尾统一写盘 → 完成前无逐题可见进度（采集脚本 print 为块缓冲）