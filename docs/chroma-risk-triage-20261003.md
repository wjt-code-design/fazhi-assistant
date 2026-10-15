# Chroma剩余风险的只读适用面核对（2026-10-03）

## 结论

仍保留两条通报，不升级、不加pip-audit忽略ID。冻结候选使用嵌入式持久库、固定collection和本地模型，并未配置Chroma HTTP服务或多租户隔离。这可作为受限Windows实验的风险背景，**不能认定依赖已修复、所有入口不受影响或生产安全**。

## 官方／原始通报与本项目路径

| 通报 | 一手依据 | 当前静态事实与限制 |
|---|---|---|
| CVE-2026-45833／GHSA-36p7-vc44-83pf | [研究者原始公告](https://www.hiddenlayer.com/sai-security-advisory/2026-06-chromadb-5)：经认证的collection更新，将恶意模型和trust_remote_code配置送入服务端模型构造。[GitHub数据库](https://github.com/advisories/GHSA-36p7-vc44-83pf)当前列影响范围0.4.17–1.5.9，未列修复版本 | `rag_chain.py`固定BGE名称、CPU参数；`Chroma(persist_directory=..., embedding_function=...)`；`knowledge_service.py`沿用同一嵌入对象。backend Dockerfile启动main:app而非Chroma server，compose无单独Chroma服务。实装0.4.24服务器文件未找到公告所述new_configuration／build_from_config／api-v2路径；这只是版本／入口差异，不能仅凭零匹配裁定CVE不适用 |
| CVE-2026-45830／GHSA-2wm9-hf6c-p5cr | [研究者原始公告](https://www.hiddenlayer.com/sai-security-advisory/2026-06-chromadb)：collection UUID查找缺少tenant过滤，引出跨租户读写。[GitHub数据库](https://github.com/advisories/GHSA-2wm9-hf6c-p5cr)当前同样未列修复版本 | 业务使用固定collection，没有发现项目层通过Chroma tenant隔离用户或启动Chroma HTTP服务器的配置；不证明依赖内部没有该缺陷。未来多租户／外部客户端／共享库用途必须重评 |

本项目证据来自联合实验冻结source的 `backend/rag_chain.py:38`、`:122`、`backend/knowledge_service.py:41`、backend/Dockerfile末尾与docker-compose.yml；没有调用管理接口、运行漏洞利用、启动／停止服务或访问真实数据库内容。

上游[问题7588](https://github.com/chroma-core/chroma/issues/7588)与[修复PR7602](https://github.com/chroma-core/chroma/pull/7602)提供授权边界修复讨论，但讨论或PR不等于已发布、已兼容的修复版；本轮没有把未发布分支当可安装版本。不要仅按“空fix列表”认定永久无修复，也不要盲升最新版本后声称两条风险关闭。

## 最小后续处置

1. 受限本地实验保持现有嵌入式、公开语料、受控代码／路径，不开放Chroma HTTP服务，不接受用户自定义embedding模型／trust_remote_code配置；这是候选用途约束，不是本轮新增防护代码。
2. 发布或改变用途前，核对上游正式修复版本及两条公告；如新增HttpClient、Chroma server、多tenant或动态embedding配置，立即重新审查，旧受限用途结论不沿用。
3. 升级仍需单独兼容分案：活跃langchain-chroma上界、持久格式、公开副本恢复／查询验收；先准备回退，不写原库。既有全量测试通过不能替代这一步。
4. D2是否接受这些受限条件仍由Owner决定，本文件不代签，也不豁免上线审计。
