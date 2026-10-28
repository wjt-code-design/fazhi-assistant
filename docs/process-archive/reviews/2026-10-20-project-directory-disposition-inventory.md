# 法智相关目录处置清单

日期：2026-10-20。执行范围：只读盘点，新增本报告与隔离采集产物；没有移动、删除、归档、切换分支或修改Git引用。

桌面相关命名目录 **44 个**，加上另外的已登记工作树，共检查 **48 个目录**。Git登记 **11 个工作树（含主目录）**，分布在桌面、项目内部、Codex与WorkBuddy路径。

这些目录包含代码副本、数据备份、历史包及评测/审查资料，不能统称为44份项目版本。

## 1. 建议汇总

| 建议 | 数量 |
|---|---:|
| 归档代码候选 | 8 |
| 保留工作副本 | 4 |
| 保留历史包 | 7 |
| 归档证据资料 | 27 |
| 保留数据备份 | 2 |

**本轮没有认定任何整个目录可立即删除。** Git干净不涵盖被忽略的配置、数据库、上传文件；选定源码相同也不代表整个目录重复。

建议最终桌面保留一个法智入口。唯一主用版本等修复助手交付并验收后确定，本次没有根据目录名、master分支名或提交日期替用户决定最终版本。

## 2. Git工作副本

| 完整路径 | HEAD | 分支 | 修改／未跟踪条目 | 与修复候选关系 | 建议 |
|---|---|---|---|---|---|
| [C:\Users\33393\.codex\worktrees\local-candidate-closeout\ai-legal-helper](C:/Users/33393/.codex/worktrees/local-candidate-closeout/ai-legal-helper) | fbc29e87c14e | codex/local-candidate-closeout | 0／0 | 提交不在候选历史中 | 归档代码候选 |
| [C:\Users\33393\Desktop\ai-legal-helper](C:/Users/33393/Desktop/ai-legal-helper) | 0b543960c717 | master | 21／577 | 提交在候选历史中 | 保留工作副本 |
| [C:\Users\33393\Desktop\ai-legal-helper-005](C:/Users/33393/Desktop/ai-legal-helper-005) | 3ba4aafb2ada | (detached) | 0／0 | 提交不在候选历史中 | 归档代码候选 |
| [C:\Users\33393\Desktop\ai-legal-helper-006](C:/Users/33393/Desktop/ai-legal-helper-006) | b0c229d33c37 | (detached) | 0／0 | 提交不在候选历史中 | 归档代码候选 |
| [C:\Users\33393\Desktop\ai-legal-helper-007](C:/Users/33393/Desktop/ai-legal-helper-007) | ba8a5691fb3b | (detached) | 0／0 | 提交不在候选历史中 | 归档代码候选 |
| [C:\Users\33393\Desktop\ai-legal-helper-008](C:/Users/33393/Desktop/ai-legal-helper-008) | dca9345805a9 | (detached) | 0／0 | 提交不在候选历史中 | 归档代码候选 |
| [C:\Users\33393\Desktop\ai-legal-helper-009](C:/Users/33393/Desktop/ai-legal-helper-009) | 30a865f76b37 | (detached) | 0／0 | 提交不在候选历史中 | 归档代码候选 |
| [C:\Users\33393\Desktop\ai-legal-helper-e9b0e17](C:/Users/33393/Desktop/ai-legal-helper-e9b0e17) | e9b0e17d98bc | (detached) | 0／0 | 提交不在候选历史中 | 归档代码候选 |
| [C:\Users\33393\Desktop\ai-legal-helper\.worktrees\legal-agent-v1](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/legal-agent-v1) | 8aecf3e01dfb | codex/legal-agent-v1 | 0／1 | 提交不在候选历史中 | 保留工作副本 |
| [C:\Users\33393\Desktop\ai-legal-helper\.worktrees\nondeploy-closeout-20261010](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010) | 4ba4237965a1 | codex/nondeploy-closeout-20261010 | 0／0 | 提交在候选历史中 | 保留工作副本 |
| [C:\Users\33393\WorkBuddy\Worktrees\ai-legal-helper\master-e8826c5b](C:/Users/33393/WorkBuddy/Worktrees/ai-legal-helper/master-e8826c5b) | f3690940a94f | master-e8826c5b | 0／6 | 提交不在候选历史中 | 保留工作副本 |

提交图比较参考候选：adf65d7a938030555cf5310a9859fbe38eef00fa。祖先关系不包含未提交修改，也不代表候选已经通过验收。助手可能继续修改，各目录不是同一瞬间的原子快照。

未跟踪目录可能只算一个条目，条目数不等于文件数。Git只读命令设置GIT_OPTIONAL_LOCKS=0。

## 3. 逐目录清单

体积是扫描文件的逻辑大小，排除了Git对象、依赖/虚拟环境、构建/缓存与重解析点；不是实际磁盘占用或可释放容量。数据库及潜在凭据只统计元数据。配置类计数包含.env模板，不代表一定存在真实凭据。选定源码为0不代表没有代码：嵌套在评测环境或证据子目录里的源码不参与指纹比较。

| 目录 | 建议 | 依据 | 选定源码文件 | 数据库类文件 | 配置/密钥类文件含模板 | 扫描体积 |
|---|---|---|---:|---:|---:|---:|
| [ai-legal-helper（Codex）](C:/Users/33393/.codex/worktrees/local-candidate-closeout/ai-legal-helper) | 归档代码候选 | Git当前干净；保住提交及独有资料后可撤掉完整副本；数据库类文件另行保留 | 325 | 1 | 3 | 338.5 MiB |
| [ai-legal-helper](C:/Users/33393/Desktop/ai-legal-helper) | 保留工作副本 | 有未提交修改或未跟踪条目；数据库类文件另行保留 | 338 | 10861 | 51 | 8.60 GiB |
| [ai-legal-helper-005](C:/Users/33393/Desktop/ai-legal-helper-005) | 归档代码候选 | Git当前干净；保住提交及独有资料后可撤掉完整副本 | 200 | 0 | 3 | 152.2 MiB |
| [ai-legal-helper-006](C:/Users/33393/Desktop/ai-legal-helper-006) | 归档代码候选 | Git当前干净；保住提交及独有资料后可撤掉完整副本 | 200 | 0 | 3 | 301.5 MiB |
| [ai-legal-helper-007](C:/Users/33393/Desktop/ai-legal-helper-007) | 归档代码候选 | Git当前干净；保住提交及独有资料后可撤掉完整副本 | 200 | 0 | 3 | 302.9 MiB |
| [ai-legal-helper-008](C:/Users/33393/Desktop/ai-legal-helper-008) | 归档代码候选 | Git当前干净；保住提交及独有资料后可撤掉完整副本 | 201 | 0 | 3 | 304.3 MiB |
| [ai-legal-helper-009](C:/Users/33393/Desktop/ai-legal-helper-009) | 归档代码候选 | Git当前干净；保住提交及独有资料后可撤掉完整副本 | 201 | 0 | 3 | 304.4 MiB |
| [ai-legal-helper-bundles](C:/Users/33393/Desktop/ai-legal-helper-bundles) | 保留历史包 | 含Git bundle，集中保存并验证恢复 | 0 | 0 | 0 | 0.0 MiB |
| [ai-legal-helper-e9b0e17](C:/Users/33393/Desktop/ai-legal-helper-e9b0e17) | 归档代码候选 | Git当前干净；保住提交及独有资料后可撤掉完整副本 | 197 | 0 | 3 | 2.3 MiB |
| [legal-agent-v1](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/legal-agent-v1) | 保留工作副本 | 有未提交修改或未跟踪条目；数据库类文件另行保留 | 1252 | 3 | 5 | 526.2 MiB |
| [nondeploy-closeout-20261010](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010) | 保留工作副本 | 当前修复候选，等待交付与验收；数据库类文件另行保留 | 395 | 3 | 4 | 354.4 MiB |
| [answer-quality-eval-20261013](C:/Users/33393/Desktop/answer-quality-eval-20261013) | 归档证据资料 | 评测/审查/运行资料（可能含嵌套源码），建议集中保存；数据库类文件另行保留 | 0 | 1 | 0 | 364.0 MiB |
| [fazhi-cancel-backend-20261005-3d68d1547a1c47839266df465a7b6629](C:/Users/33393/Desktop/fazhi-cancel-backend-20261005-3d68d1547a1c47839266df465a7b6629) | 归档证据资料 | 评测/审查/运行资料（可能含嵌套源码），建议集中保存；数据库类文件另行保留 | 0 | 7 | 2 | 445.2 MiB |
| [fazhi-cancel-repair-20261005-13137719e0d043d5ba17a9efc33d30ce](C:/Users/33393/Desktop/fazhi-cancel-repair-20261005-13137719e0d043d5ba17a9efc33d30ce) | 归档证据资料 | 评测/审查/运行资料（可能含嵌套源码），建议集中保存；数据库类文件另行保留 | 0 | 24 | 2 | 580.9 MiB |
| [fazhi-chat-cancel-20261005-eb0f87ebddb44cd6a133684cd65a27b8](C:/Users/33393/Desktop/fazhi-chat-cancel-20261005-eb0f87ebddb44cd6a133684cd65a27b8) | 归档证据资料 | 评测/审查/运行资料（可能含嵌套源码），建议集中保存 | 0 | 0 | 1 | 2.4 MiB |
| [fazhi-closeout-auditfix-20261007](C:/Users/33393/Desktop/fazhi-closeout-auditfix-20261007) | 归档证据资料 | 评测/审查/运行资料（可能含嵌套源码），建议集中保存；数据库类文件另行保留 | 0 | 22 | 4 | 492.7 MiB |
| [fazhi-closeout-reviewfix-20261006](C:/Users/33393/Desktop/fazhi-closeout-reviewfix-20261006) | 归档证据资料 | 评测/审查/运行资料（可能含嵌套源码），建议集中保存；数据库类文件另行保留 | 0 | 57 | 7 | 705.5 MiB |
| [fazhi-closeout-scan-runlogs](C:/Users/33393/Desktop/fazhi-closeout-scan-runlogs) | 归档证据资料 | 评测/审查/运行资料（可能含嵌套源码），建议集中保存 | 0 | 0 | 0 | 0.0 MiB |
| [fazhi-closeout-trim-c80d47a-20260930](C:/Users/33393/Desktop/fazhi-closeout-trim-c80d47a-20260930) | 归档证据资料 | 评测/审查/运行资料（可能含嵌套源码），建议集中保存 | 0 | 0 | 0 | 13.4 MiB |
| [fazhi-closeout-ui-profiles-20261007](C:/Users/33393/Desktop/fazhi-closeout-ui-profiles-20261007) | 归档证据资料 | 评测/审查/运行资料（可能含嵌套源码），建议集中保存；数据库类文件另行保留 | 0 | 75 | 0 | 380.3 MiB |
| [fazhi-data-backup-20260919](C:/Users/33393/Desktop/fazhi-data-backup-20260919) | 保留数据备份 | 尚未验证与其他备份相同或可恢复 | 0 | 2 | 0 | 366.2 MiB |
| [fazhi-data-backup-20260919-b](C:/Users/33393/Desktop/fazhi-data-backup-20260919-b) | 保留数据备份 | 尚未验证与其他备份相同或可恢复 | 0 | 6 | 0 | 388.4 MiB |
| [fazhi-dependency-preflight-20261004-7264fb73e5e34d89b790cd77b10e6d73](C:/Users/33393/Desktop/fazhi-dependency-preflight-20261004-7264fb73e5e34d89b790cd77b10e6d73) | 归档证据资料 | 评测/审查/运行资料（可能含嵌套源码），建议集中保存 | 0 | 0 | 0 | 0.2 MiB |
| [fazhi-joint-candidate-20261003-ac701f4a880441b5a453b1b7cbb06f01](C:/Users/33393/Desktop/fazhi-joint-candidate-20261003-ac701f4a880441b5a453b1b7cbb06f01) | 归档证据资料 | 评测/审查/运行资料（可能含嵌套源码），建议集中保存；数据库类文件另行保留 | 0 | 163 | 3 | 541.8 MiB |
| [fazhi-local-candidate-20261002-67944caf51ff48ce9432831cdd62f72b](C:/Users/33393/Desktop/fazhi-local-candidate-20261002-67944caf51ff48ce9432831cdd62f72b) | 归档证据资料 | 评测/审查/运行资料（可能含嵌套源码），建议集中保存；数据库类文件另行保留 | 0 | 36 | 15 | 2.23 GiB |
| [fazhi-local-closeout-20261006](C:/Users/33393/Desktop/fazhi-local-closeout-20261006) | 归档证据资料 | 评测/审查/运行资料（可能含嵌套源码），建议集中保存；数据库类文件另行保留 | 0 | 22 | 4 | 515.8 MiB |
| [fazhi-main-integration-20261007](C:/Users/33393/Desktop/fazhi-main-integration-20261007) | 归档证据资料 | 评测/审查/运行资料（可能含嵌套源码），建议集中保存；数据库类文件另行保留 | 0 | 1100 | 15 | 1.26 GiB |
| [fazhi-next-acceptance-review-20261004-a43ad25a98f04fb597e5b1aabe270b9a](C:/Users/33393/Desktop/fazhi-next-acceptance-review-20261004-a43ad25a98f04fb597e5b1aabe270b9a) | 归档证据资料 | 评测/审查/运行资料（可能含嵌套源码），建议集中保存 | 0 | 0 | 0 | 0.4 MiB |
| [fazhi-next-local-20261004-356fb810b3144d158e5dd18b9e276499](C:/Users/33393/Desktop/fazhi-next-local-20261004-356fb810b3144d158e5dd18b9e276499) | 归档证据资料 | 评测/审查/运行资料（可能含嵌套源码），建议集中保存；数据库类文件另行保留 | 0 | 630 | 6 | 2.60 GiB |
| [fazhi-next-local-repair-20261004-a6b8b40ac2f74c94b331eeda8a30072c](C:/Users/33393/Desktop/fazhi-next-local-repair-20261004-a6b8b40ac2f74c94b331eeda8a30072c) | 归档证据资料 | 评测/审查/运行资料（可能含嵌套源码），建议集中保存；数据库类文件另行保留 | 0 | 36 | 3 | 663.6 MiB |
| [fazhi-next-plan-review-20261004-3aef135fe0994c77be4c14c44701282a](C:/Users/33393/Desktop/fazhi-next-plan-review-20261004-3aef135fe0994c77be4c14c44701282a) | 归档证据资料 | 评测/审查/运行资料（可能含嵌套源码），建议集中保存 | 0 | 0 | 0 | 0.0 MiB |
| [fazhi-nondeploy-closeout-20261010-b4e7a2](C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2) | 归档证据资料 | 评测/审查/运行资料（可能含嵌套源码），建议集中保存；数据库类文件另行保留 | 0 | 1261 | 47 | 7.24 GiB |
| [fazhi-plan-handoff-review-20261004-c880b3c6b66342eeac71d59c72452f38](C:/Users/33393/Desktop/fazhi-plan-handoff-review-20261004-c880b3c6b66342eeac71d59c72452f38) | 归档证据资料 | 评测/审查/运行资料（可能含嵌套源码），建议集中保存 | 0 | 0 | 0 | 0.0 MiB |
| [fazhi-project-closeout-20261008-7e20048efb4e46068a9ecf1a54c6b527](C:/Users/33393/Desktop/fazhi-project-closeout-20261008-7e20048efb4e46068a9ecf1a54c6b527) | 归档代码候选 | 普通目录含源码，尚未确认原始提交与独有资料 | 62 | 0 | 0 | 2.1 MiB |
| [fazhi-release-preflight-20261008-02b95968ef4541858da309bc26aaf703](C:/Users/33393/Desktop/fazhi-release-preflight-20261008-02b95968ef4541858da309bc26aaf703) | 归档证据资料 | 评测/审查/运行资料（可能含嵌套源码），建议集中保存 | 0 | 0 | 0 | 2.1 MiB |
| [fazhi-rescue-4465080-20260919](C:/Users/33393/Desktop/fazhi-rescue-4465080-20260919) | 保留历史包 | 含Git bundle，集中保存并验证恢复 | 0 | 0 | 0 | 258.5 MiB |
| [fazhi-rescue-88bd167-20260919](C:/Users/33393/Desktop/fazhi-rescue-88bd167-20260919) | 保留历史包 | 含Git bundle，集中保存并验证恢复 | 0 | 0 | 3 | 589.7 MiB |
| [fazhi-rescue-b820295-20260919](C:/Users/33393/Desktop/fazhi-rescue-b820295-20260919) | 保留历史包 | 含Git bundle，集中保存并验证恢复 | 0 | 0 | 0 | 258.7 MiB |
| [fazhi-rescue-c362c91-20260919](C:/Users/33393/Desktop/fazhi-rescue-c362c91-20260919) | 保留历史包 | 含Git bundle，集中保存并验证恢复 | 0 | 0 | 0 | 258.6 MiB |
| [fazhi-rescue-d6077d0-20260919](C:/Users/33393/Desktop/fazhi-rescue-d6077d0-20260919) | 保留历史包 | 含Git bundle，集中保存并验证恢复 | 0 | 0 | 0 | 259.1 MiB |
| [fazhi-rescue-dbc0f9b-20260919](C:/Users/33393/Desktop/fazhi-rescue-dbc0f9b-20260919) | 保留历史包 | 含Git bundle，集中保存并验证恢复 | 0 | 0 | 0 | 259.1 MiB |
| [fazhi-risk-followup-75542ea22e9b4627a4e090cbc5c7f9aa](C:/Users/33393/Desktop/fazhi-risk-followup-75542ea22e9b4627a4e090cbc5c7f9aa) | 归档证据资料 | 评测/审查/运行资料（可能含嵌套源码），建议集中保存；数据库类文件另行保留 | 0 | 437 | 6 | 921.7 MiB |
| [fazhi-risk-review-20261003-e30b720af8364e4c83ded98210868f7b](C:/Users/33393/Desktop/fazhi-risk-review-20261003-e30b720af8364e4c83ded98210868f7b) | 归档证据资料 | 评测/审查/运行资料（可能含嵌套源码），建议集中保存；数据库类文件另行保留 | 0 | 320 | 6 | 1.05 GiB |
| [fazhi-tmppack-probe-20260919](C:/Users/33393/Desktop/fazhi-tmppack-probe-20260919) | 归档证据资料 | 评测/审查/运行资料（可能含嵌套源码），建议集中保存 | 0 | 0 | 0 | 60.7 MiB |
| [legal-rerank-acceptance-20261002-c9c0d7684b274afb9427f27a32638af8](C:/Users/33393/Desktop/legal-rerank-acceptance-20261002-c9c0d7684b274afb9427f27a32638af8) | 归档证据资料 | 评测/审查/运行资料（可能含嵌套源码），建议集中保存；数据库类文件另行保留 | 0 | 2 | 3 | 1.04 GiB |
| [legal-rerank-round2-20261002-abc6d089a8a84bba90d7a87673936fae](C:/Users/33393/Desktop/legal-rerank-round2-20261002-abc6d089a8a84bba90d7a87673936fae) | 归档证据资料 | 评测/审查/运行资料（可能含嵌套源码），建议集中保存；数据库类文件另行保留 | 0 | 1 | 3 | 718.4 MiB |
| [legal-rerank-round3-20261002-cebf70a641c549f9ad44c27cf27261a9](C:/Users/33393/Desktop/legal-rerank-round3-20261002-cebf70a641c549f9ad44c27cf27261a9) | 归档证据资料 | 评测/审查/运行资料（可能含嵌套源码），建议集中保存；数据库类文件另行保留 | 0 | 1 | 3 | 718.4 MiB |
| [master-e8826c5b（WorkBuddy）](C:/Users/33393/WorkBuddy/Worktrees/ai-legal-helper/master-e8826c5b) | 保留工作副本 | 有未提交修改或未跟踪条目；数据库类文件另行保留 | 325 | 1 | 3 | 337.5 MiB |

## 4. 选定源码重复检查

仅比较目录根部backend/frontend下的Python、TypeScript、JavaScript、CSS、HTML等选定源码，排除数据/模型目录。指纹包括相对路径和SHA-256；不比较全部JSON/YAML配置、数据库、上传文件或依赖，不能作为整目录安全删除证明。

没有发现选定源码集合完全相同的两个目录；这不代表每个目录都值得长期保留，也不排除部分文件重复。

## 5. 推荐执行顺序

1. 修复助手交付后确定唯一主用版本，为修复前、验收通过等重要节点固定Git引用。
2. 对保留的工作副本逐一保存未提交修改、未跟踪文件及被忽略的独有数据；保留正在使用的目录。
3. 将数据库/向量库备份、Git bundle、评测与审查证据分别集中归档，并验证其恢复/读取能力。
4. 对归档代码候选，确认提交历史、独有资料已经保存且没有任务/进程占用后，通过Git或Codex/WorkBuddy管理入口撤下工作树。Git工作树不要直接当普通文件夹移动。
5. 普通证据目录归档核对后可以从桌面撤走；停用副本的可重建依赖与缓存可另列清理项。本次没有测量这部分体积。

本报告是具体处置建议清单。当前执行的是盘点；真正移动/删除前，仍须针对所选目录完成保存、恢复验证与占用核对。

## 6. 证据与限制

- [盘点JSON](C:/Users/33393/.codex/visualizations/2026/10/18/01a14fe1-dd41-7e83-a8f6-c4c2d27b6be7/fazhi-directory-inventory-20261020/inventory.json)：完整路径、版本、改动计数、源码指纹、排除项及建议。
- [采集脚本](C:/Users/33393/.codex/visualizations/2026/10/18/01a14fe1-dd41-7e83-a8f6-c4c2d27b6be7/fazhi-directory-inventory-20261020/inventory.py)；[状态刷新和报告脚本](C:/Users/33393/.codex/visualizations/2026/10/18/01a14fe1-dd41-7e83-a8f6-c4c2d27b6be7/fazhi-directory-inventory-20261020/report.py)。
- [工作区外Git状态只读补采](C:/Users/33393/.codex/visualizations/2026/10/18/01a14fe1-dd41-7e83-a8f6-c4c2d27b6be7/fazhi-directory-inventory-20261020/git-metadata-supplement.json)：8个目录首次受权限限制，补采后均成功；未通过修改Git安全配置或仓库内容绕过。
- 采集记录时间：2026-10-20T10:39:21.187508+00:00，Git状态随后逐目录刷新。
- 没有读取.env/私钥或数据库内容，没有运行产品、测试、构建、模型、迁移或恢复。
- 未验证备份恢复、Git对象完整性、目录进程占用或任务归属；不把没有查到占用当作没有占用。
- 依赖、Git对象、构建缓存与重解析点被跳过，扫描错误保守保留。源码指纹只代表选定范围。

异常与变化记录：

未记录到上述扫描异常；不替代恢复或占用验证。
