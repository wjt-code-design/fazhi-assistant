# D｜导入脚本类型检查与安全替换测试

你是 D 助手。**只执行本文件**，完成后向交办人回报；不要接手 A/B/C/E。仓库绝对路径：`C:\Users\33393\Desktop\ai-legal-helper`。文件内已有 T1/T2 未提交修改，其他助手可能并行写不同文件；保留现状，不还原、不清理、不提交、不推送。

## 目标与文件归属

T5：`backend/scripts/import_laws.py` 被全仓 `mypy .` 排除，直接检查存在已知的空列表类型推断问题。验证复核还指出：安全删除旧块的端到端用例只有 slow 测试；脚本 seed 冲突跳过路径缺测试。你独占写入 `backend/scripts/import_laws.py` 与 `backend/tests/test_import_laws_preflight.py`。不改 `backend/pyproject.toml`、真实语料、真实 Chroma、其他助手文件。

## 执行

1. 在 `backend/` 先运行 `venv\Scripts\python.exe -m mypy --follow-imports=skip scripts/import_laws.py`，记录错误；只为真实错误作最小修正（优先检查 `validate_entry` 中 `errors=[]` 的类型），再跑同一命令。若还有其他错误，定位后报告，不靠整体忽略或放宽配置过关。
2. 复用现有 `test_import_laws_preflight.py` 的隔离 `tmp_collection` 夹具，加一条非 slow 同版本、有生效日的重传用例：新块存在，旧块确实被安全替换；设计一次受控断开删旧接线的验证，证明测试会失败。再加 seed 冲突的 dry-run 用例：点名跳过、没有写入。不要用真实库运行。
3. 在 `backend/` 运行 `venv\Scripts\python.exe -B -m pytest tests/test_import_laws_preflight.py -q -m "not slow"`、直接 mypy，以及两归属文件的 Ruff lint/format。`mypy .` 的绿灯不能替代脚本直接检查。

## 交付判据

T5 定向类型检查通过；安全删旧与 seed 跳过在普通 CI 形状下可见。回报 `D / 修改文件 / 红绿证据 / 命令与退出码 / 未解决项`。
