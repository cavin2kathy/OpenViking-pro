# OpenViking-pro

本项目基于 [volcengine/OpenViking](https://github.com/volcengine/OpenViking) 修改。

官方 README: [https://github.com/volcengine/OpenViking/blob/main/README_CN.md](https://github.com/volcengine/OpenViking/blob/main/README_CN.md)

---

## 本项目优化内容

### 1. 部署优化

- 详细部署避坑指南，见 [OpenViking 部署与集成避坑指南](./examples/openclaw-memory-plugin/OPENVIKING_DEPLOY_GUIDE.md)
- 包含国内网络环境配置（Go GOPROXY、setuptools-scm 版本问题）
- 提供完整配置文件示例（volcengine backend）
- E2E 测试脚本验证部署

### 2. 多 Agent 记忆隔离支持

- 支持通过 `X-OpenViking-Agent` Header 实现基于 Agent ID 的记忆隔离
- 详细隔离验证脚本
- OpenClaw 插件集成配置

### 3. API 调用优化

针对 OpenViking API 调用浪费严重的问题（发现时浪费 92.2%），进行了以下优化：

#### 3.1 Embedding API 优化

- **统一接口 + 缓存层**
- 核心功能：
  - 缓存查找 - 避免重复 API 调用
  - 并发控制 - 相同内容只调用 1 次 API
  - 限流控制 - 最多 10 个并发 API 调用
  - 线程安全 - finally 块保证异常时清理资源

#### 3.2 统计监控

- 实时监控脚本
- API 查询

---

## 快速开始

### 安装

```bash
# 设置环境变量
export SETUPTOOLS_SCM_PRETEND_VERSION_FOR_OPENViking=0.1.12
export GOPROXY=https://goproxy.cn,direct

# 安装依赖
pip install ./third_party/agfs/agfs-sdk/python
pip install .
```

### 配置

创建 `~/.openviking/ov.conf`：

```json
{
  "server": {
    "host": "127.0.0.1",
    "port": 1933,
    "root_api_key": null
  },
  "storage": {
    "workspace": "/root/.openviking/data",
    "vectordb": {
      "name": "context",
      "backend": "local",
      "project": "default"
    },
    "agfs": {
      "port": 1833,
      "backend": "local"
    }
  },
  "embedding": {
    "dense": {
      "backend": "volcengine",
      "api_key": "YOUR_API_KEY",
      "model": "ep-xxxxx",
      "api_base": "https://ark.cn-beijing.volces.com/api/v3",
      "dimension": 2048
    }
  }
}
```

### 启动

```bash
openviking-server
```

服务默认监听 **1933** 端口。

---

## License

继承原项目 Apache License 2.0。
