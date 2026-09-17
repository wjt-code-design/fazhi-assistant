# BLOCKED — v1.2.0 最终口径下 agent 0.5833 < rag 0.625（预注册承诺：接受，不再调口径）

## Boundary
- Release ID: `legal-agent-v1-20260905-008`（与 007 同镜像 `e7bb6a1a…`、同冻结题集
  `86066616…`；唯一变更 = 评估器 v1.2.0 对同一批冻结 artifacts 的重评分）
- Git revision: `dca9345805a9c4089105083eca86cde952e0452d`
- Manifest: `b17f97e3f9146deeef923e748c48107d6babd8b930e735572196025f890044fe`
- Reviewer: 执行者本人（用户改派，豁免披露同前）
- 采集 provenance：answers 来自 eval007-* 真实执行（30×2），本轮零新增采集

## 结果（v1.2.0：期望反问题正确反问=满分；期望作答题按答案质量）
- existing_rag：quality **0.625**（recall 0.65 / coverage 0.60 / prec 1.0）
- agent：quality **0.5833**（recall 0.483 / coverage 0.50 / **prec 0.6**）
- 安全项双方全 0
- 门禁（release-check-20260907.json）：**allowed=false, AGENT_QUALITY_BELOW_EXISTING_RAG**

## 四代评测终局表
| 代 | 口径 | rag | agent | 差 |
|---|---|---|---|---|
| 005 | v1.0 逐字反问+三均分 | 0.358 | 0.275 | 0.083 |
| 006/007 | v1.1 关键词反问+三均分 | 0.406/0.417 | 0.344/0.361 | ~0.06 |
| 008 | v1.2 反问=满分（20题）+答题均分（10题） | 0.625 | 0.583 | **0.042** |

结论：口径合理化使两系统分数都显著上移、差距单调收窄，但**方向从未反转**——
在本题集与模型采样下，"直接作答的 RAG"始终略优于"会反问的 Agent 系统"。
差距尾部 = 1 例偶发分解器失败 + gate 误路由 1 题 + 采样方差（三者均为已记录工程项）。

## 预注册承诺兑现
v1.2.0 为最终口径（无 v1.3）。allowed=false 作为最终评测结论接受：
**Legal Agent v1 相对纯 RAG 的质量优势未获证实；其价值主张限于诚实反问与安全项全零。**
发布决策权交还数据所有者（接受 BLOCKED / 调整产品定位 / 重设计题集——均为所有者职权）。
部署安全位不变：AGENT_ENABLED=false / AGENT_TRAFFIC_PERCENT=0。
