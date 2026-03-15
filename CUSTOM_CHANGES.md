# OpenViking-pro 自定义改动说明

## 基线与自定义提交

- 官网基线分支：`upstream/main`
- 当前本地主分支：`master`（跟踪 `origin/master`）
- 相对官网的自定义提交：`8f21b2c`
- 关系：当前 `master = upstream/main + 1 个自定义提交`

## 自定义改动清单（相对官网）

### 1) 新增扩展模块（集中放在 extention）

- `openviking/extention/vector_cache.py`
  - 文本向量缓存（含并发去重、持久化、启动加载、淘汰、统计打点）
  - 统一缓存入口：`get_embedding(text, embedder)`
  - 固定缓存目录：`/root/.openviking/cache`
- `openviking/extention/stats_collector.py`
  - 线程安全统计单例
  - 统计项包括 embedding 调用、VLM 调用、cache 命中/未命中等
- `openviking/extention/__init__.py`
  - 对扩展能力做统一导出

### 2) 接入点改造（确保真正向量调用走缓存）

- `openviking_cli/utils/config/embedding_config.py`
  - 增加 `CachedEmbedderProxy`
  - 在 `get_embedder()` 返回 embedder 时统一包一层代理
  - 代理将 `embed()` 调用路由到 `extention.vector_cache.get_embedding`

### 3) 服务启动与管理接口改动

- `openviking/server/bootstrap.py`
  - 启动时初始化向量缓存并打印加载数量
- `openviking/server/routers/admin.py`
  - 保留 `/stats` 统计接口
  - 已去掉 `/stats/reset`
- `openviking_cli/session/user_id.py`
  - `agent_space_name()` 从 `md5(user_id + agent_id)[:12]` 改为 `user_id + "_" + agent_id`
  - Agent 空间目录名不再使用哈希，改为可读拼接值

### 4) VLM 统计接入

- `openviking/models/vlm/backends/openai_vlm.py`
  - 异步完成接口中记录 `vlm_api_calls`
- `openviking/models/vlm/backends/volcengine_vlm.py`
  - 异步完成接口中记录 `vlm_api_calls`

## 以后与官网同步时的建议

1. 先更新官网代码：`git fetch upstream`
2. 在 `master` 上对齐到最新官网后再重放你的自定义提交
3. 重点检查冲突文件：
   - `embedding_config.py`
   - `bootstrap.py`
   - `admin.py`
   - `openai_vlm.py`
   - `volcengine_vlm.py`
4. 同步完成后做基础校验（至少 `py_compile`）

## 快速核对命令

```bash
git rev-list --left-right --count master...upstream/main
git log --oneline upstream/main..master
git diff --name-status upstream/main...master
```
