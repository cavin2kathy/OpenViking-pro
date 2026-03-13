# OpenViking 插件接口说明文档

> 本文档描述 OpenViking 插件提供的所有 HTTP API 接口
> 版本：1.0 | 更新日期：2026-03-11

---

## 目录

1. [概述](#概述)
2. [认证方式](#认证方式)
3. [系统接口](#系统接口)
4. [会话管理接口](#会话管理接口)
5. [资源管理接口](#资源管理接口)
6. [搜索接口](#搜索接口)
7. [Bot 接口](#bot-接口)
8. [管理接口](#管理接口)

---

## 概述

OpenViking 是一个 AI Agent 长期记忆管理系统，提供 HTTP API 接口供外部调用。所有接口采用 RESTful 风格，默认端口 `8000`。

**基础 URL**: `http://localhost:8000`

**本地插件目录**: `/root/OpenViking-main/openviking/server/routers/`

---

## 认证方式

接口支持两种认证方式：

| 认证头 | 说明 |
|--------|------|
| `X-API-Key` | API Key 认证 |
| `Authorization: Bearer <token>` | Bearer Token 认证 |

> 大部分接口需要有效认证，除了 `/health` 和 `/ready` 健康检查接口。

---

## 系统接口

### 1. 健康检查

```http
GET /health
```

检查服务是否运行正常。

**响应示例**:
```json
{"status": "ok"}
```

---

### 2. 就绪检查

```http
GET /ready
```

检查系统各子系统状态（AGFS、VectorDB、APIKeyManager）。

**响应示例**:
```json
{
  "status": "ready",
  "checks": {
    "agfs": "ok",
    "vectordb": "ok",
    "api_key_manager": "ok"
  }
}
```

---

### 3. 系统状态

```http
GET /api/v1/system/status
```

获取系统初始化状态。

**需要认证**: ✅

---

### 4. 等待处理完成

```http
POST /api/v1/system/wait
```

等待所有资源处理完成。

**请求体**:
```json
{
  "timeout": 60.0
}
```

---

## 会话管理接口

### 5. 创建会话

```http
POST /api/v1/sessions
```

创建一个新的会话。

**需要认证**: ✅

**响应示例**:
```json
{
  "status": "ok",
  "result": {
    "session_id": "sess_xxx",
    "user": {...}
  }
}
```

---

### 6. 列出会话

```http
GET /api/v1/sessions
```

列出所有会话。

**需要认证**: ✅

---

### 7. 获取会话详情

```http
GET /api/v1/sessions/{session_id}
```

获取指定会话的详细信息。

**路径参数**:
- `session_id`: 会话 ID

**需要认证**: ✅

---

### 8. 删除会话

```http
DELETE /api/v1/sessions/{session_id}
```

删除指定会话。

**路径参数**:
- `session_id`: 会话 ID

**需要认证**: ✅

---

### 9. 提交会话

```http
POST /api/v1/sessions/{session_id}/commit
```

提交会话（归档并提取记忆）。

**路径参数**:
- `session_id`: 会话 ID

**需要认证**: ✅

---

### 10. 提取记忆

```http
POST /api/v1/sessions/{session_id}/extract
```

从会话中提取记忆。

**路径参数**:
- `session_id`: 会话 ID

**需要认证**: ✅

---

### 11. 添加消息

```http
POST /api/v1/sessions/{session_id}/messages
```

向会话添加消息。支持两种模式：

**简单模式**:
```json
{
  "role": "user",
  "content": "Hello"
}
```

**Parts 模式**:
```json
{
  "role": "assistant",
  "parts": [
    {"type": "text", "text": "Here's the answer"},
    {"type": "context", "uri": "viking://resources/doc.md", "abstract": "..."}
  ]
}
```

**需要认证**: ✅

---

## 资源管理接口

### 12. 临时文件上传

```http
POST /api/v1/resources/temp_upload
```

上传临时文件用于后续的资源添加。

**需要认证**: ✅

**表单参数**:
- `file`: 文件对象

---

### 13. 添加资源

```http
POST /api/v1/resources
```

向 OpenViking 添加资源（文档、文件等）。

**请求体**:
```json
{
  "path": "/path/to/resource",
  "temp_path": "/tmp/uploaded_file",
  "target": "viking://memory/...",
  "reason": "添加记忆",
  "instruction": "分析这段内容",
  "wait": true,
  "timeout": 300.0,
  "strict": true
}
```

**需要认证**: ✅

---

### 14. 添加 Skill

```http
POST /api/v1/skills
```

添加 Skill 到 OpenViking。

**请求体**:
```json
{
  "data": {...},
  "temp_path": "/tmp/skill_file",
  "wait": true,
  "timeout": 300.0
}
```

**需要认证**: ✅

---

## 搜索接口

### 15. 语义搜索（无会话）

```http
POST /api/v1/search/find
```

进行语义搜索，不需要会话上下文。

**请求体**:
```json
{
  "query": "查找关于项目的记忆",
  "target_uri": "viking://memory/...",
  "limit": 10,
  "score_threshold": 0.7
}
```

**需要认证**: ✅

---

### 16. 语义搜索（带会话）

```http
POST /api/v1/search/search
```

进行语义搜索，可选会话上下文。

**请求体**:
```json
{
  "query": "查找相关文档",
  "target_uri": "viking://memory/...",
  "session_id": "sess_xxx",
  "limit": 10
}
```

**需要认证**: ✅

---

### 17. 内容搜索

```http
POST /api/v1/search/grep
```

按内容模式搜索。

**请求体**:
```json
{
  "uri": "viking://resources/...",
  "pattern": "*.py",
  "case_insensitive": false
}
```

**需要认证**: ✅

---

### 18. 文件匹配

```http
POST /api/v1/search/glob
```

按文件模式匹配。

**请求体**:
```json
{
  "pattern": "**/*.md",
  "uri": "viking://"
}
```

**需要认证**: ✅

---

## Bot 接口

> Bot 接口需要在启动服务时添加 `--with-bot` 参数启用。

### 19. Bot 健康检查

```http
GET /bot/health
```

检查 Bot 服务健康状态。

**需要认证**: ❌（代理到 Bot 服务）

---

### 20. 聊天

```http
POST /bot/chat
```

发送消息给 Bot 并获取响应。

**需要认证**: ✅

---

### 21. 流式聊天

```http
POST /bot/chat/stream
```

发送消息给 Bot 并获取流式响应（SSE）。

**需要认证**: ✅

---

## 管理接口

> 管理接口需要 ROOT 角色权限。

### 22. 创建账户

```http
POST /api/v1/admin/accounts
```

创建新的账户（工作区）。

**需要认证**: ✅（ROOT）

**请求体**:
```json
{
  "account_id": "new_account",
  "admin_user_id": "admin"
}
```

---

### 23. 列出账户

```http
GET /api/v1/admin/accounts
```

列出所有账户。

**需要认证**: ✅（ROOT）

---

### 24. 删除账户

```http
DELETE /api/v1/admin/accounts/{account_id}
```

删除指定账户及其存储。

**需要认证**: ✅（ROOT）

---

### 25. 注册用户

```http
POST /api/v1/admin/users
```

在账户下注册新用户。

**需要认证**: ✅（ADMIN）

---

## 接口响应格式

所有接口统一响应格式：

```json
{
  "status": "ok",
  "result": {...}
}
```

错误响应：

```json
{
  "status": "error",
  "error": {
    "code": "ERROR_CODE",
    "message": "错误描述"
  }
}
```

---

## 常用 URI 前缀

| 前缀 | 用途 |
|------|------|
| `viking://memory/` | 记忆存储 |
| `viking://resources/` | 资源文件 |
| `viking://skills/` | Skill 定义 |
| `viking://sessions/` | 会话数据 |

---

## 快速开始

```bash
# 启动服务
cd /root/OpenViking-main
python -m openviking.server.app

# 测试健康检查
curl http://localhost:8000/health

# 测试认证的接口
curl -H "X-API-Key: your_api_key" http://localhost:8000/api/v1/sessions
```

---

*文档生成时间: 2026-03-11*
