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
OpenViking 默认查找 `~/.openviking/ov.conf`。你可以手动创建：

```bash
mkdir -p ~/.openviking
nano ~/.openviking/ov.conf
```

**推荐配置 (Volcengine Backend)**:
此配置已验证支持 **2048 维度** 多模态向量模型。
> **注意**: `api_base` 请填写 Base URL (如 `.../api/v3`)，不要包含 `/embeddings/multimodal` 后缀，SDK 会自动拼接。

**安全警告**: 如果 `server.host` 配置为 `0.0.0.0` (允许外部访问)，必须配置 `server.root_api_key`，否则服务将因安全检查而无法启动。开发环境建议绑定 `127.0.0.1`。

```json
{
  "server": {
    "host": "127.0.0.1",
    "port": 1933,
    "root_api_key": null,
    "cors_origins": [
      "*"
    ]
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
      "log_level": "warn",
      "backend": "local",
      "timeout": 10,
      "retry_times": 3
    }
  },
  "embedding": {
    "dense": {
      "backend": "volcengine",
      "api_key": "YOUR_API_KEY",
      "model": "ep-20260305232106-cwjgr",
      "api_base": "https://ark.cn-beijing.volces.com/api/v3",
      "dimension": 2048,
      "input": "multimodal"
    }
  },
  "vlm": {
    "backend": "volcengine",
    "api_key": "YOUR_API_KEY",
    "model": "ep-20260306002208-58nxn",
    "api_base": "https://ark.cn-beijing.volces.com/api/v3",
    "temperature": 0.1,
    "max_retries": 3
  }
}
```
*注意：如果不配置 embedding/vlm，部分语义检索功能可能无法工作。*

### 启动服务
```bash
openviking-server
```
服务默认监听 **1933** 端口。

## 5. 端到端测试脚本 (E2E Verification)

部署完成后，不要只看进程是否在跑，务必跑通以下业务流程：`Session创建 -> 消息写入 -> 记忆抽取 -> 语义检索 -> 清理`。

保存为 `test_ov.py` 并运行：

```python
import requests
import json
import time
import uuid

BASE_URL = "http://127.0.0.1:1933"
# 生成随机Marker以避免缓存干扰
MARKER = f"TEST_KEY_{uuid.uuid4().hex[:8]}"

def run_test():
    print(f"Starting OpenViking Test with Marker: {MARKER}")
    
    # 1. 健康检查
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"[Health] Status: {resp.status_code}")
        if resp.status_code != 200:
            print("服务未就绪")
            return
    except Exception as e:
        print(f"连接失败: {e}")
        return

    # 2. 创建会话 (Session)
    print("\n[1/4] Creating Session...")
    resp = requests.post(f"{BASE_URL}/api/v1/sessions", json={})
    if resp.status_code != 200:
        print(f"Create session failed: {resp.text}")
        return
    
    # 解析嵌套的响应结构
    try:
        data = resp.json()
        if 'result' in data and 'session_id' in data['result']:
            session_id = data['result']['session_id']
        elif 'session_id' in data:
            session_id = data['session_id']
        else:
            print(f"Could not find ID in response: {data}")
            return
    except Exception:
        print(f"Failed to parse JSON: {resp.text}")
        return

    print(f"Session ID: {session_id}")

    # 3. 写入消息 (Add Message)
    msg_content = f"Please remember this important secret key: {MARKER}. It is crucial for the system configuration."
    print(f"\n[2/4] Adding message: {msg_content}")
    resp = requests.post(f"{BASE_URL}/api/v1/sessions/{session_id}/messages", 
                         json={"role": "user", "content": msg_content})
    if resp.status_code != 200:
        print(f"Add message failed: {resp.text}")
        return
    print("Message added successfully.")

    # 4. 触发记忆抽取 (Extract)
    print("\n[3/4] Triggering extraction...")
    resp = requests.post(f"{BASE_URL}/api/v1/sessions/{session_id}/extract", json={})
    if resp.status_code != 200:
        print(f"Extraction failed: {resp.text}")
        return
    
    extraction_resp = resp.json()
    # 检查是否有记忆生成 (注意：可能是异步的，这里仅检查请求成功)
    print("Extraction triggered successfully.")

    # 5. 等待索引 (Indexing Wait)
    print("Waiting 10 seconds for VLM processing and vector indexing...")
    time.sleep(10)

    # 6. 语义检索 (Search)
    query = f"What is the secret key? {MARKER}"
    print(f"\n[4/4] Searching for: {query}")
    resp = requests.post(f"{BASE_URL}/api/v1/search/find", 
                         json={"query": query, "limit": 5})
    
    if resp.status_code == 200:
        search_resp = resp.json()
        print(f"Search Raw Response: {json.dumps(search_resp, indent=2, ensure_ascii=False)}")
        
        # 简单字符串匹配验证
        if MARKER in str(search_resp):
            print("\n[SUCCESS] ✅ Marker found in search results! Test Passed.")
        else:
            print("\n[FAILURE] ❌ Marker NOT found in search results. Check embedding/VLM logs.")
    else:
        print(f"Search failed: {resp.text}")

if __name__ == "__main__":
    run_test()
```

## 6. 多 Agent 记忆隔离支持 (Multi-Agent Isolation)

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

### 隔离验证脚本
使用 `verify_isolation.py` 验证不同 Agent ID 是否能访问彼此的记忆。

```python
import requests
import json
import time
import uuid

BASE_URL = "http://127.0.0.1:1933"

def create_session(agent_id):
    headers = {"X-OpenViking-Agent": agent_id}
    resp = requests.post(f"{BASE_URL}/api/v1/sessions", json={}, headers=headers)
    if resp.status_code == 200:
        return resp.json()['result']['session_id']
    return None

def add_message(session_id, agent_id, content):
    headers = {"X-OpenViking-Agent": agent_id}
    requests.post(f"{BASE_URL}/api/v1/sessions/{session_id}/messages", 
                  json={"role": "user", "content": content}, headers=headers)

def extract(session_id, agent_id):
    headers = {"X-OpenViking-Agent": agent_id}
    requests.post(f"{BASE_URL}/api/v1/sessions/{session_id}/extract", json={}, headers=headers)

def search(query, agent_id):
    headers = {"X-OpenViking-Agent": agent_id}
    resp = requests.post(f"{BASE_URL}/api/v1/search/find", 
                         json={"query": query, "limit": 5}, headers=headers)
    return str(resp.json()) if resp.status_code == 200 else ""

def run_test():
    marker = f"SECRET_{uuid.uuid4().hex[:8]}"
    agent_a, agent_b = "agent_a", "agent_b"
    
    print(f"Testing Isolation with Marker: {marker}")
    
    # 1. Agent A 写入记忆
    sid_a = create_session(agent_a)
    add_message(sid_a, agent_a, f"My secret is {marker}")
    extract(sid_a, agent_a)
    print("Waiting 10s for indexing...")
    time.sleep(10)
    
    # 2. Agent A 应该能搜到
    res_a = search(marker, agent_a)
    if marker in res_a:
        print(f"✅ Agent A found memory (Expected)")
    else:
        print(f"❌ Agent A failed to find memory")

    # 3. Agent B 不应该搜到
    res_b = search(marker, agent_b)
    if marker not in res_b:
        print(f"✅ Agent B did NOT find memory (Isolation Success)")
    else:
        print(f"❌ Agent B found Agent A's memory! (Isolation Failed)")

if __name__ == "__main__":
    run_test()
```

## 7. OpenClaw 集成排查

如果你是作为 OpenClaw 的插件运行，还需要注意：
1.  **插件加载**: 确保 `~/.openclaw/openclaw.json` 中的 `plugins.load.paths` 指向正确的源码路径。
2.  **端口冲突**: 如果 OpenClaw 自身也占用了某些端口，确保 `ov.conf` 中的端口 (1933/1833) 不冲突。
3.  **日志查看**: OpenClaw 的日志通常在 `/tmp/openclaw/` 或 `~/.openclaw/logs/`，排查 `connection refused` 错误最为关键。

## 8. OpenClaw 插件多 Agent 隔离配置 (isolationMode)

本节介绍如何在 OpenClaw 中启用基于 Agent ID 的记忆隔离。

### 8.1 插件加载机制

OpenClaw 从 `plugins.load.paths` 指定的源码路径加载插件，而非从 `extensions/` 目录。配置示例：

```json
{
  "plugins": {
    "load": {
      "paths": ["/root/OpenViking-main/examples/openclaw-memory-plugin"]
    }
  }
}
```

### 8.2 启用隔离模式

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

### 8.3 必要修改

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

### 8.4 Agent ID 获取逻辑

插件代码已实现从多个来源自动获取 Agent ID（按优先级）：

1. `ctx.agentId` - OpenClaw 事件上下文
2. `event.agentId` - 事件对象
3. `process.env.OPENCLAW_AGENT_ID` - 环境变量
4. `workspace` 路径（如 `~/.openclaw/workspace-coding` -> `coding`）
5. 默认值 `"default"`

### 8.5 验证隔离效果

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

### 8.6 OpenClaw 升级影响与插件管理

**重要**: 如果 OpenClaw 重新安装或更新插件源码，可能会覆盖以下文件：
- `{插件源码路径}/openclaw.plugin.json` - 配置定义
- `{插件源码路径}/index.ts` - 插件代码

**推荐方案: 使用 extensions 目录管理自定义插件**

为避免升级 OpenClaw 时丢失修改，建议将插件复制到 extensions 目录管理：

```bash
# 1. 复制插件到 extensions 目录
mkdir -p ~/.openclaw/extensions/memory-openviking
cp -r /root/OpenViking-main/examples/openclaw-memory-plugin/* ~/.openclaw/extensions/memory-openviking/

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

### 8.7 目录结构说明

OpenViking 按 agentId 创建独立目录：
```
/root/.openviking/data/viking/default/agent/
├── coding/      # coding agent 的记忆
├── writing/     # writing agent 的记忆
├── business/    # business agent 的记忆
├── main/        # main agent 的记忆
└── default/     # 默认记忆
```

每个 agent 目录内包含：
- `memories/` - 提取的记忆
- `instructions/` - 指令
- `skills/` - 技能
- `workspaces/` - 工作空间
