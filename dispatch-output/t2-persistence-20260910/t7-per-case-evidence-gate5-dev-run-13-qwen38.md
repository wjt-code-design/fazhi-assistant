# T7 逐题留证 — run `gate5-dev-run-13-qwen38`

### C01
- runner: rounds=3 final_chars=404 completed=True errors=[]
- 引擎侧：run=8df747e6 conv=2327 status=completed v=9 | issues=1/4 覆盖=1 backfill=- clar=2 tools=1 steps=9
- 结束于：`finalize` / `VERIFIED_FINAL_STORED`（共 9 步）
- 决策序列：bootstrap › tool_call › tool_result › clarification › user_fact › clarification › user_fact › conditional_analysis › finalize
- judge: [C01] mechanical_completed=True R2=True R3=True R5=True R6=True R8hint=False full_passed=False missing=['劳动合同法:40', '劳动合同法:43', '劳动合同法:47', '劳动合同法:87'] unbound=1 redline=NOT_PROVEN

### C02
- runner: rounds=3 final_chars=0 completed=False errors=['EVIDENCE_COVERAGE_DEFICIENT']
- 引擎侧：run=f267220d conv=2328 status=failed v=17 | issues=4/4 覆盖=4 backfill=Y clar=2 tools=4 steps=16
- 结束于：`failure` / `EVIDENCE_COVERAGE_DEFICIENT`（共 17 步）
- 决策序列：bootstrap › tool_call › tool_result › clarification › user_fact › tool_call › tool_result › clarification › user_fact › tool_call › tool_result › backfill_retrieval › tool_call › tool_result › conditional_analysis › coverage_rewrite_attempt › failure
- judge: [C02] mechanical_completed=False R2=True R3=True R5=True R6=False R8hint=False full_passed=False missing=['劳动法:36', '劳动法:44', '劳动争议调解仲裁法:27'] unbound=0 redline=NOT_PROVEN

### C03
- runner: rounds=3 final_chars=790 completed=True errors=[]
- 引擎侧：run=4e58c81d conv=2329 status=completed v=13 | issues=3/5 覆盖=3 backfill=- clar=2 tools=3 steps=13
- 结束于：`finalize` / `VERIFIED_FINAL_STORED`（共 13 步）
- 决策序列：bootstrap › tool_call › tool_result › clarification › user_fact › tool_call › tool_result › clarification › user_fact › tool_call › tool_result › conditional_analysis › finalize
- judge: [C03] mechanical_completed=True R2=True R3=True R5=True R6=True R8hint=False full_passed=False missing=['劳动合同法:10'] unbound=1 redline=NOT_PROVEN

### C04
- runner: rounds=3 final_chars=0 completed=False errors=['UNSUPPORTED_NUMERIC_TOKEN']
- 引擎侧：run=f0407677 conv=2330 status=failed v=9 | issues=1/5 覆盖=1 backfill=- clar=2 tools=1 steps=9
- 结束于：`failure` / `UNSUPPORTED_NUMERIC_TOKEN`（共 9 步）
- 决策序列：bootstrap › tool_call › tool_result › clarification › user_fact › clarification › user_fact › conditional_analysis › failure
- judge: [C04] mechanical_completed=False R2=True R3=True R5=True R6=False R8hint=False full_passed=False missing=['民法典:586', '民法典:587', '民法典:588'] unbound=0 redline=NOT_PROVEN

### C05
- runner: rounds=3 final_chars=331 completed=True errors=[]
- 引擎侧：run=e76aa97b conv=2331 status=completed v=11 | issues=1/5 覆盖=1 backfill=- clar=2 tools=2 steps=11
- 结束于：`finalize` / `VERIFIED_FINAL_STORED`（共 11 步）
- 决策序列：bootstrap › tool_call › tool_result › clarification › user_fact › tool_call › tool_result › clarification › user_fact › conditional_analysis › finalize
- judge: [C05] mechanical_completed=True R2=True R3=True R5=True R6=True R8hint=False full_passed=False missing=['民法典:577'] unbound=1 redline=NOT_PROVEN

### C06
- runner: rounds=3 final_chars=667 completed=True errors=[]
- 引擎侧：run=700b3489 conv=2332 status=completed v=13 | issues=3/5 覆盖=3 backfill=- clar=2 tools=3 steps=13
- 结束于：`finalize` / `VERIFIED_FINAL_STORED`（共 13 步）
- 决策序列：bootstrap › tool_call › tool_result › clarification › user_fact › tool_call › tool_result › clarification › user_fact › tool_call › tool_result › conditional_analysis › finalize
- judge: [C06] mechanical_completed=True R2=True R3=True R5=True R6=True R8hint=False full_passed=False missing=['民法典:509', '民法典:543', '民法典:577'] unbound=1 redline=NOT_PROVEN

### C07
- runner: rounds=3 final_chars=556 completed=True errors=[]
- 引擎侧：run=340dd7b5 conv=2333 status=completed v=11 | issues=1/5 覆盖=1 backfill=- clar=2 tools=2 steps=11
- 结束于：`finalize` / `VERIFIED_FINAL_STORED`（共 11 步）
- 决策序列：bootstrap › tool_call › tool_result › clarification › user_fact › tool_call › tool_result › clarification › user_fact › conditional_analysis › finalize
- judge: [C07] mechanical_completed=True R2=True R3=True R5=True R6=True R8hint=True full_passed=False missing=['民法典:675'] unbound=1 redline=NOT_PROVEN

### C08
- runner: rounds=3 final_chars=0 completed=False errors=['UNSUPPORTED_NUMERIC_TOKEN']
- 引擎侧：run=4e23623d conv=2334 status=failed v=9 | issues=1/5 覆盖=1 backfill=- clar=2 tools=1 steps=9
- 结束于：`failure` / `UNSUPPORTED_NUMERIC_TOKEN`（共 9 步）
- 决策序列：bootstrap › tool_call › tool_result › clarification › user_fact › clarification › user_fact › conditional_analysis › failure
- judge: [C08] mechanical_completed=False R2=True R3=True R5=True R6=False R8hint=False full_passed=False missing=['民法典:686', '民法典:692', '民法典:693', '民法典:695'] unbound=0 redline=NOT_PROVEN

### C09
- runner: rounds=3 final_chars=529 completed=True errors=[]
- 引擎侧：run=b36fd443 conv=2335 status=completed v=11 | issues=2/5 覆盖=2 backfill=- clar=2 tools=2 steps=11
- 结束于：`finalize` / `VERIFIED_FINAL_STORED`（共 11 步）
- 决策序列：bootstrap › tool_call › tool_result › clarification › user_fact › tool_call › tool_result › clarification › user_fact › conditional_analysis › finalize
- judge: [C09] mechanical_completed=True R2=True R3=True R5=True R6=True R8hint=False full_passed=False missing=['消费者权益保护法:26', '民法典:496', '民法典:497', '民法典:577'] unbound=1 redline=NOT_PROVEN

### C10
- runner: rounds=3 final_chars=293 completed=True errors=[]
- 引擎侧：run=270431a0 conv=2336 status=completed v=9 | issues=1/4 覆盖=1 backfill=- clar=2 tools=1 steps=9
- 结束于：`finalize` / `VERIFIED_FINAL_STORED`（共 9 步）
- 决策序列：bootstrap › tool_call › tool_result › clarification › user_fact › clarification › user_fact › conditional_analysis › finalize
- judge: [C10] mechanical_completed=True R2=True R3=True R5=True R6=True R8hint=False full_passed=False missing=['民法典:577', '刑法:266'] unbound=1 redline=NOT_PROVEN

## judge 汇总

`mechanical_pass_count=7 full_closure_pass_count=0 full_closure_denominator=10 formal_gate_passed=False`
