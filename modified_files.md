# OpenViking 对比报告

对比目录:
- 备份: `/opt/openviking-back`
- 修改: `/root/OpenViking-main`

---

## 新增文件

| 文件路径 | 类型 |
|---------|------|
| examples/openclaw-memory-plugin/OPENVIKING_DEPLOY_GUIDE.md | 新增 |
| openviking/bin | 新增目录 |
| openviking/lib | 新增目录 |
| openviking/storage/vectordb/engine.so | 新增 |
| openviking/utils/stats_collector.py | 新增 |
| openviking/utils/vector_cache.py | 新增 |
| openviking/_version.py | 新增 |
| pyrightconfig.json | 新增 |

---

## 修改文件

| 文件路径 |
|---------|
| examples/openclaw-memory-plugin/config.ts |
| examples/openclaw-memory-plugin/index.ts |
| examples/openclaw-memory-plugin/openclaw.plugin.json |
| openviking/core/context.py |
| openviking/models/vlm/backends/openai_vlm.py |
| openviking/models/vlm/backends/volcengine_vlm.py |
| openviking/retrieve/hierarchical_retriever.py |
| openviking/server/auth.py |
| openviking/server/bootstrap.py |
| openviking/server/routers/admin.py |
| openviking/server/routers/sessions.py |
| openviking/session/memory_deduplicator.py |
| openviking/session/memory_extractor.py |
| openviking/storage/collection_schemas.py |
| openviking/storage/queuefs/embedding_msg_converter.py |
| openviking_cli/server_bootstrap.py |
| openviking_cli/session/user_id.py |
| openviking_cli/utils/config/embedding_config.py |
| openviking_cli/utils/config/open_viking_config.py |

---

## 删除文件

无

---

## 统计

- 新增文件: 8
- 修改文件: 20
- 删除文件: 0
- 总计: 28
