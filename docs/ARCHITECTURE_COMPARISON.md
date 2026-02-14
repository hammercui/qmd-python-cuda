# QMD MCP Server 架构对比

## 问题回顾

**原始设计**：分离的 HTTP Server 和 MCP Server
```
qmd-python
├── qmd/server/        # HTTP Server
└── qmd-mcp-server/  # MCP Server (独立)
```

**问题**：
- ❌ 两个独立进程 = 8GB+ VRAM（同时运行时）
- ❌ 代码重复（两套模型加载逻辑）
- ❌ 维护困难（同步更新两个 Server）

---

## 统一架构（当前方案）

**核心思想**：单一 Server，多 Transport

```
qmd-python
├── qmd/server/              # 单一 Server（共享模型）
│   ├── core.py               # 核心搜索引擎
│   ├── app.py                # QmdServer 类（4GB VRAM）
│   ├── transports/            # Transport 层
│   │   ├── __init__.py
│   │   ├── http.py            # HTTP Transport
│   │   ├── mcp.py             # MCP Transport (新增）
│   │   └── stdio.py          # Stdio Transport (可选)
│   └── tools.py              # MCP Tools
└── qmd/
```

---

## 对比表

| 维度 | 分离设计 | 统一架构 |
|------|----------|----------|
| **进程数** | 2 个 | 1 个 |
| **显存占用** | 8GB（两例） | 4GB（单例） |
| **代码复用** | 低（重复逻辑） | 高（共享核心） |
| **维护成本** | 高（两套代码） | 低（单一代码库） |
| **用户体验** | 困惑（两个命令） | 简单（一个命令） |

---

## Transport 对比

### HTTP Transport

**用途**：为 CLI 命令提供 REST API

```python
# 端点：http://localhost:8000
POST /search
POST /vsearch
POST /query
GET /health
```

**谁用**：
- ✅ `qmd search` 命令（auto 模式检测）
- ✅ `qmd vsearch`
- ✅ `qmd query`
- ✅ `qmd server`（启动 Server）

---

### MCP Transport

**用途**：为 AI Agent 提供标准工具接口

```python
# 协议：MCP (JSON-RPC 2.0 over stdio)
# 工具：search, vsearch, query, get, multi_get, status
```

**谁用**：
- ✅ Claude Desktop / OpenClaw（通过配置）
- ✅ 其他 AI Agent（支持 MCP 协议）

---

## 配置示例

### 单一配置文件

```yaml
# ~/.config/qmd/server.yml
server:
  # Transport 模式
  transport: both  # http | mcp | both
  
  # HTTP 配置
  http:
    host: 127.0.0.1
    port: 8000
    log_level: info
  
  # MCP 配置
  mcp:
    enabled: true
  
  # 共享配置
  model:
    # 单例实例
    max_queue_size: 100
```

### CLI 使用示例

```bash
# 方式 1：只启动 HTTP（当前）
qmd server --transport http

# 方式 2：只启动 MCP（Claude 使用）
qmd server --transport mcp

# 方式 3：同时启动（推荐）
qmd server --transport both
```

---

## 迁移指南

如果已经实现了分离的 HTTP Server，迁移到统一架构：

### Phase 1: 重构核心（1-2 天）
```bash
# 1. 创建 Transport 基类
qmd/server/transports/base.py

# 2. 重构 HTTP Server
# 3. 实现 MCP Transport
qmd/server/transports/mcp.py

# 4. 更新 QmdServer 类
```

### Phase 2: 更新 CLI（0.5 天）
```bash
# 1. 添加 --transport 选项
# 2. 移除独立 server 命令
# 3. 更新文档
```

### Phase 3: 测试（1 天）
```bash
# 单元测试
# 集成测试
# 性能测试
```

---

## 总结

**推荐**：统一架构

**理由**：
- ✅ 节省 4GB VRAM
- ✅ 代码复用率高
- ✅ 维护简单
- ✅ 用户体验好

**何时选择分离**：
- 需要独立部署 HTTP Server（为外部工具提供 API）
- 需要 HIP 工作负载分离
- 团队协作，不同团队维护不同组件
