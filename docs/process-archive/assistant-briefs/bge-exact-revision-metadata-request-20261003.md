# 默认BGE模型精确revision元数据补证（只读）

交给能访问官方Hugging Face的助手或设备即可。目标是补元数据，不是下载模型或运行项目。

官方模型：`BAAI/bge-base-zh-v1.5`；固定revision：`f03589ceff5aac7111bd60cfc7d497ca17ecac65`。

请求地址：[官方精确revision tree API](https://huggingface.co/api/models/BAAI/bge-base-zh-v1.5/tree/f03589ceff5aac7111bd60cfc7d497ca17ecac65?recursive=true)。这是公开文件树，无需API key。禁止改成main、镜像、resolve权重地址，禁止下载409MB权重、改本机refs、运行embedding／rerank或重建索引。

在该设备新建独立输出目录，执行一次请求，连接／读取超时20秒。HTTP非200或失败时保留错误类型／状态码并停止，不连续重试。响应如有Link分页，仅跟随同一官方主机、同一精确revision API路径的下一页；每页保留未经编辑的响应JSON与Link字段。页面体超过1MiB则停止核查，不能把数据文件误当元数据下载。不得带Authorization、导出环境变量或交付.env。

需要保留：官方请求URL、实际取得时间（注明时区）、HTTP状态、原始分页JSON、下一页是否耗尽、每页字节数与SHA-256。不要将原JSON改成手工表，不只提供截图／文件名／大小。

核对默认11文件：

- `1_Pooling/config.json`
- `config.json`
- `config_sentence_transformers.json`
- `modules.json`
- `pytorch_model.bin`
- `README.md`
- `sentence_bert_config.json`
- `special_tokens_map.json`
- `tokenizer.json`
- `tokenizer_config.json`
- `vocab.txt`

交付整个小型元数据目录与一份简短结果说明即可。执行者不接触本项目模型缓存；收到材料后，由本项目助手核对10个小文件的Git blob SHA-1（`SHA1(b'blob '+str(len(content)).encode('ascii')+b'\0'+content)`），以及BIN的精确revision LFS SHA-256／大小。目录可能还有其他上游文件，不因此自动加载或下载。

缺少OID／LFS字段、分页不完整或无法确认官方精确revision时，结论仍为PARTIAL，写清缺项，不用main指针或“Safe”标记替代。来源通过也不关闭Torch／ST／Transformers依赖漏洞，不签署D2。原本机失败记录保留，不是要求再在同一失败网络环境反复运行。
