# OpenViking 部署与集成避坑指南

本文档总结了在 OpenClaw 环境下部署 OpenViking 记忆服务（Memory Service）的完整流程，特别是针对国内网络环境和源码安装常见问题的解决方案。

## 1. 前置要求 (Prerequisites)

在开始部署之前，请确保目标机器满足以下条件：

- **操作系统**: Linux (推荐 Ubuntu 22.04+) 或 Windows WSL2。
- **Python**: 版本 **3.10+** (推荐 3.11，实测兼容性最好)。
- **Go**: 版本 **1.20+** (用于编译 AGFS 存储层)。
- **Node.js**: (可选) 如果需要运行 OpenClaw 插件部分的构建脚本。

## 2. 核心坑点与解决方案 (Critical Issues)

在安装过程中，你可能会遇到以下三个主要问题，**请务必提前配置环境变量**：

### 坑点 1: `setuptools-scm` 版本检测失败
源码安装时，`setuptools-scm` 可能无法正确从 git 历史获取版本号，导致安装中断。
**解决**: 强制指定版本号。
```bash
export SETUPTOOLS_SCM_PRETEND_VERSION_FOR_OPENVIKING=0.1.12
```

### 坑点 2: Go 依赖下载超时
AGFS 组件在编译时需要下载 Go 依赖，国内环境通常连接 `proxy.golang.org` 失败。
**解决**: 配置国内 GOPROXY。
```bash
export GOPROXY=https://goproxy.cn,direct
```

### 坑点 3: `pyagfs` 导入错误
OpenViking 依赖 `pyagfs`，但 PyPI 上可能没有最新版本或安装脚本未自动处理本地路径。
**解决**: 手动安装源码中的 SDK。
```bash
# 假设你在 OpenViking 源码根目录
pip install ./third_party/agfs/agfs-sdk/python
```

## 3. 标准部署流程 (Step-by-Step)

### 步骤 1: 获取源码
```bash
git clone https://github.com/openviking/OpenViking.git
cd OpenViking
```

### 步骤 2: 设置环境变量 (一次性执行)
建议将这些写入 `~/.bashrc` 或启动脚本。
```bash
export SETUPTOOLS_SCM_PRETEND_VERSION_FOR_OPENVIKING=0.1.12
export GOPROXY=https://goproxy.cn,direct
```

### 步骤 3: 安装依赖与主程序
```bash
# 1. 安装 AGFS Python SDK (必须先装这个)
pip install ./third_party/agfs/agfs-sdk/python

# 2. 安装 OpenViking 主程序
# 注意：使用 -e (editable) 模式方便调试，或者直接 install .
pip install .
```

### 步骤 4: 验证安装
检查是否安装成功：
```bash
openviking-server --help
```
如果能看到帮助信息，说明安装成功。

## 4. 配置与启动

### 配置文件 `ov.conf`
OpenViking 默认查找 `~/.openviking/ov.conf`。

**安全警告**: 如果 `server.host` 配置为 `0.0.0.0` (允许外部访问)，必须配置 `server.root_api_key`，否则服务将因安全检查而无法启动。开发环境建议绑定 `127.0.0.1`。

配置项说明：
- `server`: 服务配置（端口、认证等）
- `storage`: 存储配置（工作目录、向量数据库、AGFS）
- `embedding`: 向量嵌入模型配置
- `vlm`: 视觉语言模型配置

### 启动服务
```bash
openviking-server
```
服务默认监听 **1933** 端口。

## 5. 多 Agent 记忆隔离支持 (Multi-Agent Isolation)

OpenViking 支持通过 Header 实现基于 Agent ID 的记忆隔离。

### 启用方式
在客户端请求中增加 `X-OpenViking-Agent` Header：
```bash
X-OpenViking-Agent: <custom_agent_id>
```

### 关键代码修改 (强制全量隔离)
默认情况下，部分记忆类型（如偏好、实体）存储在 User 层级。为实现完全的 Agent 隔离，需修改 `openviking/session/memory_extractor.py`：

```python
# 修改前：根据类别区分存储路径
# if candidate.category in [MemoryCategory.PREFERENCES, ...]:
#     parent_uri = f"viking://user/{ctx.user.user_space_name()}/{cat_dir}"

# 修改后：强制所有类别使用 Agent 空间
parent_uri = f"viking://agent/{ctx.user.agent_space_name()}/{cat_dir}"
```

## 6. OpenClaw 集成排查

如果你是作为 OpenClaw 的插件运行，还需要注意：
1.  **插件加载**: 确保 `~/.openclaw/openclaw.json` 中的 `plugins.load.paths` 指向正确的源码路径。
2.  **端口冲突**: 如果 OpenClaw 自身也占用了某些端口，确保 `ov.conf` 中的端口 (1933/1833) 不冲突。
3.  **日志查看**: OpenClaw 的日志通常在 `/tmp/openclaw/` 或 `~/.openclaw/logs/`，排查 `connection refused` 错误最为关键。

## 7. OpenClaw 插件多 Agent 隔离配置 (isolationMode)

本节介绍如何在 OpenClaw 中启用基于 Agent ID 的记忆隔离。

### 7.1 插件加载机制

OpenClaw 从 `plugins.load.paths` 指定的源码路径加载插件，而非从 `extensions/` 目录。配置示例：

```json
{
  "plugins": {
    "load": {
      "paths": ["/path/to/openclaw-memory-plugin"]
    }
  }
}
```

### 7.2 启用隔离模式

在插件配置中添加 `isolationMode: "isolated"`：

```json
{
  "plugins": {
    "entries": {
      "memory-openviking": {
        "enabled": true,
        "config": {
          "mode": "local",
          "configPath": "/root/.openviking/ov.conf",
          "port": 1933,
          "targetUri": "viking://user/memories",
          "autoRecall": true,
          "autoCapture": true,
          "isolationMode": "isolated"
        }
      }
    }
  }
}
```

### 7.3 必要修改

由于 OpenClaw 插件配置验证严格，需修改插件的 `openclaw.plugin.json` 添加 `isolationMode` 配置项：

**修改文件**: `{插件源码路径}/openclaw.plugin.json`

1. 在 `uiHints` 中添加配置说明：
```json
"isolationMode": {
  "label": "Memory Isolation Mode",
  "placeholder": "shared",
  "help": "\"shared\" = all agents share memory; \"isolated\" = each agent has isolated memory space"
}
```

2. 在 `configSchema.properties` 中添加验证：
```json
"isolationMode": {
  "type": "string",
  "enum": ["shared", "isolated"]
}
```

### 7.4 Agent ID 获取逻辑

插件代码已实现从多个来源自动获取 Agent ID（按优先级）：

1. `ctx.agentId` - OpenClaw 事件上下文
2. `event.agentId` - 事件对象
3. `process.env.OPENCLAW_AGENT_ID` - 环境变量
4. `workspace` 路径（如 `~/.openclaw/workspace-coding` -> `coding`）
5. 默认值 `"default"`

### 7.5 验证隔离效果

重启 OpenClaw 后，触发 Agent 活动，检查日志：
```bash
tail -f /tmp/openclaw/openclaw-2026-03-06.log | grep -i "isolation"
```

应看到类似输出：
```
memory-openviking: isolation enabled, agentId=coding
```

检查数据目录确认按 Agent ID 分隔：
```bash
ls -la /root/.openviking/data/viking/default/agent/
# 应看到 coding, writing, business 等子目录
```

### 7.6 OpenClaw 升级影响与插件管理

**重要**: 如果 OpenClaw 重新安装或更新插件源码，可能会覆盖以下文件：
- `{插件源码路径}/openclaw.plugin.json` - 配置定义
- `{插件源码路径}/index.ts` - 插件代码

**推荐方案: 使用 extensions 目录管理自定义插件**

为避免升级 OpenClaw 时丢失修改，建议将插件复制到 extensions 目录管理：

```bash
# 1. 复制插件到 extensions 目录
mkdir -p ~/.openclaw/extensions/memory-openviking
cp -r /path/to/openclaw-memory-plugin/* ~/.openclaw/extensions/memory-openviking/

# 2. 修改 openclaw.json，移除源码路径，改用 extensions
```

**修改 openclaw.json**:
```json
{
  "plugins": {
    "load": {
      "paths": []  // 清空源码路径
    }
  }
}
```

OpenClaw 会自动加载 `~/.openclaw/extensions/` 下的插件。

**验证加载**:
```bash
openclaw doctor 2>&1 | grep -i openclaw-memory-openviking
```
