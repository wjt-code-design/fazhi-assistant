# T7 逐题留证 — run `gate5-dev-modelarm-longcat`

> ⚠️ 无 `-sessions.json`（该 arm 被中途中止）→ runner 侧数据取自 checkpoint，**本文件为 PARTIAL**，不得当作整轮。

### C01
- runner: rounds=3 final_chars=0 completed=False errors=['EVIDENCE_COVERAGE_DEFICIENT']
- 引擎侧：run=cc0555fd conv=2347 status=failed v=14 | issues=3/4 覆盖=3 backfill=- clar=2 tools=3 steps=13
- 结束于：`failure` / `EVIDENCE_COVERAGE_DEFICIENT`（共 14 步）
- 决策序列：bootstrap › tool_call › tool_result › clarification › user_fact › tool_call › tool_result › clarification › user_fact › tool_call › tool_result › conditional_analysis › coverage_rewrite_attempt › failure
- judge: (无)

### C02
- runner: rounds=3 final_chars=804 completed=False errors=['AGENT_BUDGET_EXCEEDED']
- 引擎侧：run=499805e5 conv=2348 status=stopped v=16 | issues=8/4 覆盖=4 backfill=Y clar=2 tools=5 steps=15
- 结束于：`stop` / `AGENT_BUDGET_EXCEEDED`（共 16 步）
- 决策序列：bootstrap › tool_call › tool_result › clarification › user_fact › tool_call › tool_result › clarification › user_fact › tool_call › tool_result › backfill_retrieval › tool_call › tool_result › backfill_retrieval › stop
- judge: (无)

### C03
- runner: rounds=3 final_chars=726 completed=True errors=[]
- 引擎侧：run=49a8bd4e conv=2349 status=completed v=14 | issues=3/5 覆盖=3 backfill=- clar=2 tools=3 steps=13
- 结束于：`finalize` / `VERIFIED_FINAL_STORED`（共 14 步）
- 决策序列：bootstrap › tool_call › tool_result › clarification › user_fact › tool_call › tool_result › clarification › user_fact › tool_call › tool_result › conditional_analysis › coverage_rewrite_attempt › finalize
- judge: (无)

### C04
- runner: rounds=3 final_chars=765 completed=True errors=[]
- 引擎侧：run=80d20350 conv=2350 status=completed v=14 | issues=3/5 覆盖=3 backfill=- clar=2 tools=3 steps=13
- 结束于：`finalize` / `VERIFIED_FINAL_STORED`（共 14 步）
- 决策序列：bootstrap › tool_call › tool_result › clarification › user_fact › tool_call › tool_result › clarification › user_fact › tool_call › tool_result › conditional_analysis › coverage_rewrite_attempt › finalize
- judge: (无)

### C05
- runner: rounds=0 final_chars=None completed=None errors=[]
- 引擎侧：run=9d5fb4bf conv=2351 status=drafting v=12 | issues=3/5 覆盖=3 backfill=- clar=2 tools=3 steps=12
- 结束于：`conditional_analysis` / `CLARIFY_BUDGET_EXHAUSTED`（共 12 步）
- 决策序列：bootstrap › tool_call › tool_result › clarification › user_fact › tool_call › tool_result › clarification › user_fact › tool_call › tool_result › conditional_analysis
- judge: (无)

### C06
- runner: rounds=0 final_chars=None completed=None errors=[]
- 引擎侧：**无 agent_run 记录**（预运行失败，未 create_run）
- judge: (无)

### C07
- runner: rounds=0 final_chars=None completed=None errors=[]
- 引擎侧：**无 agent_run 记录**（预运行失败，未 create_run）
- judge: (无)

### C08
- runner: rounds=0 final_chars=None completed=None errors=[]
- 引擎侧：**无 agent_run 记录**（预运行失败，未 create_run）
- judge: (无)

### C09
- runner: rounds=0 final_chars=None completed=None errors=[]
- 引擎侧：**无 agent_run 记录**（预运行失败，未 create_run）
- judge: (无)

### C10
- runner: rounds=0 final_chars=None completed=None errors=[]
- 引擎侧：**无 agent_run 记录**（预运行失败，未 create_run）
- judge: (无)

## judge 汇总

(未跑 judge：无 sessions.json)
