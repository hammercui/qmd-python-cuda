# QMD-Python 项目 - 需求总结与进度

- **日期**: 2026-02-15
- **负责人**: Zandar (CTO+COO)
- **项目路径**: `D:\MoneyProjects\qmd-python`

---

## 🎯 架构演进（重要更新）

### 核心架构理解（2026-02-15 13:20 - Boss确认）

**问题本质**：
```
3个模型实例 × 4GB显存/个 = 12GB显存爆炸

解决方案：
单进程Server + 1套模型 + 队列串行 = 4GB显存 ✅
```

**Client-Server分离策略**：
- ✅ **必须分离**：所有需要模型的操作走Server
- ✅ **HTTP MCP Server**：不是stdio模式
- ✅ **队列串行**：防止显存溢出
- ✅ **智能路由**：不需要模型的操作直接CLI

**操作分类**：

| 操作类型 | 需要模型 | 执行方式 | 理由 |
|---------|---------|---------|------|
| **embed** | ✅ | HTTP → Server | 需要bge模型 |
| **vsearch** | ✅ | HTTP → Server | 需要embed + 向量搜索 |
| **query** | ✅ | HTTP → Server | 需要embed + reranker + LLM扩展 |
| **search** | ❌ | 直接CLI | BM25纯算法 |
| **collection add** | ❌ | 直接CLI | SQLite操作 |
| **collection list** | ❌ | 直接CLI | SQLite查询 |
| **index** | ❌ | 直接CLI | 文件读取 + SQLite写入 |
| **config** | ❌ | 直接CLI | YAML配置 |
| **status** | ⚠️ | 混合 | Server状态→HTTP，CLI状态→直接 |

**核心价值**：
- ✅ 显存节省：66%（4GB vs 12GB）
- ✅ 性能提升：CLI操作零等待
- ✅ 架构清晰：职责分离

---

### 新的统一架构（2026-02-15）

**之前的设计问题**：
- HTTP Server 和 MCP Server 作为两个独立实现
- 代码重复（两个 Server 各自加载模型）
- 两个进程 = 8GB+ VRAM（如果同时运行）

**统一架构方案**（`docs/UNIFIED_SERVER_ARCHITECTURE.md`）：
```
QMD Server (单一进程，共享模型)
├─ 核心引擎（单例：4GB VRAM）
│  ├─ Embeddings (bge-small-zh-v1.5)
│  ├─ BM25 搜索
│  ├─ 向量搜索
│  └─ 混合搜索
│
├─ 自动服务发现（2026-02-15 新增）
│  ├─ 端口检测（默认18765，冲突时递增）
│  ├─ 端口存储（~/.qmd/server_port.txt）
│  └─ 进程检测（psutil）
│
└─ 多种 Transport（对外接口）
   ├─ HTTP Transport (port 18765)   ← CLI 命令用
   ├─ MCP Transport (stdio)          ← Claude/OpenClaw 用
   └─ SSE/WebSocket (可选)          ← 未来扩展
```

**核心优势**：
- ✅ 单一进程，单一模型（4GB VRAM）
- ✅ 代码复用（共享核心搜索引擎）
- ✅ 维护简单（单一代码库）
- ✅ 用户体验好（单一 `qmd server` 命令）
- ✅ **自动服务发现**（2026-02-15 新增）
  - OpenClaw无需手动启动Server
  - 端口冲突自动递增
  - 进程检测避免重复启动
  - 零配置体验

**CLI 使用**：
```bash
qmd server --transport http    # 只启动 HTTP（默认18765）
qmd server --transport mcp     # 只启动 MCP
qmd server --transport both    # 同时启动（推荐）
```

**文档**：
- `docs/UNIFIED_SERVER_ARCHITECTURE.md` - 统一架构详细方案
- `docs/MCP_SERVER_PROPOSAL.md` - 方案概述（已更新为统一架构）
- `docs/MCP_COMPATIBILITY_ANALYSIS.md` - MCP 接口规范

---

## 📋 需求总结

### 核心问题
- **当前架构问题**：
  -- qmd 以 CLI 命令形式启动
  -- 每次执行创建新进程
  -- 每个进程独立加载 embed 模型（bge-small-zh-v1.5）
  -- **多进程并发时显存暴增**

- **显存占用场景**：
```
3 个并发 qmd 进程：
-- 进程 1: 2-4GB VRAM
-- 进程 2: 2-4GB VRAM
-- 进程 3: 2-4GB VRAM
总计: 6-12GB VRAM (3 个独立模型实例)
```

### 解决方案需求
- **MCP Server 架构**：
  -- **Server 模式**：单个常驻进程，加载一次模型（2-4GB）
  -- **任务队列**：所有 embed 请求通过队列串行处理
  -- **网络协议**：HTTP API（FastAPI）+ IPC
  -- **智能切换**：根据显存大小自动选择模式
    - 显存 ≥ 8GB：独立进程模式（当前）
    - 显存 < 8GB：Server + 队列模式

- **关键约束**：
  -- ✅ **向后兼容**：保留现有的本地模式，Server 作为可选功能
  -- ✅ **显存检测**：自动选择模式（基于 `torch.cuda.mem_get_info()`）
  -- ✅ **错误处理**：Server 挂了，自动回退到 Standalone
  -- ✅ **性能要求**：embed 延迟 < 100ms（即使经过队列）

- **不改动的业务逻辑**：
  -- ❌ CLI 命令接口保持不变
  -- ❌ 数据库 schema 不变
  -- ❌ 搜索算法（BM25/Vector/Hybrid）不变
  -- ❌ Collection 管理不变

---

## ✅ 已完成内容

### 阶段 1：Server 核心模块 ✅

#### 1.1 Server 模块结构
- `qmd/server/`
  -- `__init__.py`      # 模块导出 ✅
  -- `app.py`          # FastAPI 应用 ✅
  -- `client.py`        # HTTP 客户端 ✅
  -- `models.py`       # Pydantic 模型 ✅

#### 1.2 FastAPI 应用 (`qmd/server/app.py`)
- **已实现功能**：
  -- ✅ FastAPI 应用结构
  -- ✅ 单例模型加载（startup 事件）
  -- ✅ 异步队列处理（asyncio.Queue）
  -- ✅ `/embed` POST 端点（生成 embeddings）
  -- ✅ `/health` GET 端点（健康检查）
  -- ✅ 队列大小限制（MAX_QUEUE_SIZE=100，防止内存溢出）
  -- ✅ 输入验证（空列表、超多 texts）
  -- ✅ 错误分类处理（ValueError → 400, RuntimeError → 500）

- **代码质量**：
  -- ✅ 类型注解完善
  -- ✅ 日志记录（logger.info/error）
  -- ✅ 异步处理（async/await）
  -- ✅ Pydantic 数据验证

#### 1.3 HTTP 客户端 (`qmd/server/client.py`)
- **已实现功能**：
  -- ✅ EmbedServerClient 类
  -- ✅ HTTP 客户端（httpx）
  -- ✅ 超时控制（5 秒）
  -- ✅ 健康检查方法（health_check）
  -- ✅ embed_texts 方法（POST /embed）
  -- ✅ 自动降级（server 不可用返回 None）
  -- ✅ 资源清理（close 方法）

- **代码质量**：
  -- ✅ 类型注解完善
  -- ✅ 异常处理（ConnectError, TimeoutException）
  -- ✅ 延迟初始化（_get_client）

#### 1.4 数据模型 (`qmd/server/models.py`)
- **已实现功能**：
  -- ✅ EmbedRequest（Pydantic）
  -- ✅ EmbedResponse（Pydantic）
  -- ✅ 类型注解完整

---

### 阶段 2：LLMEngine 双模式支持 ✅

#### 2.1 引擎修改 (`qmd/llm/engine.py`)
- **已实现功能**：
  -- ✅ 双模式初始化（standalone / server / auto）
  -- ✅ VRAM 自动检测（torch.cuda.mem_get_info()）
  -- ✅ 模式选择逻辑：
    - VRAM < 8GB → server 模式
    - VRAM ≥ 8GB → standalone 模式
    - 无 CUDA → standalone 模式
  -- ✅ MCP Server 客户端集成（EmbedServerClient）
  -- ✅ 自动降级（server 挂了回退到 standalone）
  -- ✅ embed_texts 方法（根据模式路由）
  -- ✅ 资源清理（close 方法）

- **代码质量改进**：
  -- ✅ 类型注解完善（TextEmbedding, EmbedServerClient）
  -- ✅ 日志记录（mode 检测结果、降级警告）
  -- ✅ 错误处理（VRAM 检测失败时 fallback）

---

### 阶段 3：CLI 集成 ✅

#### 3.1 Server 启动命令 (`qmd/cli.py`)
- **已实现功能**：
  -- ✅ `qmd server` 命令
  -- ✅ `--host` 选项（默认 127.0.0.1）
  -- ✅ `--port` 选项（默认 8000）
  -- ✅ `--log-level` 选项（默认 info）
  -- ✅ uvicorn 集成
  -- ✅ 友好输出（host, port, model info）
  -- ✅ 优雅关闭（signal handler: SIGINT, SIGTERM）
  -- ✅ 控制台提示（按 Ctrl+C 停止）

- **代码质量改进**：
  -- ✅ 信号处理（友好关闭）
  -- ✅ 信息输出（Max queue size 提示）

#### 3.2 --mode 选项添加 ✅
- **已实现功能**：
  -- ✅ `search` 命令添加 `--mode` 选项（auto/standalone/server）
  -- ✅ `vsearch` 命令添加 `--mode` 选项
  -- ✅ `query` 命令添加 `--mode` 选项
  -- ✅ `embed` 命令添加 `--mode` 选项
  -- ✅ VectorSearch 构造函数接收 `mode` 参数
  -- ✅ HybridSearch 构造函数接收 `mode` 参数

- **代码质量**：
  -- ✅ 类型注解完整
  -- ✅ 向后兼容（mode 默认 "auto"）

---

### 阶段 4：配置与依赖 ✅

#### 4.1 pyproject.toml
- **已实现**：
  -- ✅ `[project.optional-dependencies.server]` 组
  -- ✅ 依赖：fastapi>=0.100.0, uvicorn[standard]>=0.23.0, httpx>=0.24.0

#### 4.2 文档 (`docs/MCP_SERVER.md`)
- **已实现**：
  -- ✅ 架构图（ASCII 图示）
  -- ✅ 安装说明
  -- ✅ 使用指南（Server 模式 / Standalone 模式）
  -- ✅ 模式检测逻辑
  -- ✅ API 端点文档
  -- ✅ Fallback 行为说明
  -- ✅ 性能对比表
  -- ✅ 故障排查指南
  -- ✅ 开发者指南

---

### 阶段 5：测试 ✅

#### 5.1 单元测试 (`tests/test_server.py`)
- **已实现测试**：
  -- ✅ test_health_endpoint（健康检查）
  -- ✅ test_embed_endpoint_empty_texts（边界：空列表）
  -- ✅ test_embed_endpoint_too_many_texts（边界：1001 条）
  -- ✅ test_client_health_check（客户端健康检查）
  -- ✅ test_client_embed_texts（客户端 embed 功能）

---

### 阶段 6：代码质量改进 ✅

#### 6.1 Code Review 反馈实施
- **已实施改进**：
  -- ✅ 队列大小限制（MAX_QUEUE_SIZE=100）
  -- ✅ 输入验证（400/413 错误码）
  -- ✅ 错误分类（ValueError/RuntimeError/Exception）
  -- ✅ 类型注解完善（所有模块）
  -- ✅ 优雅关闭（signal handler）
  -- ✅ 边界测试（空列表、过多 texts）

- **评分提升**：78% → 87%（+9%）

---

### 🎯 总体进度

| 阶段 | 状态 | 完成度 |
|--------|------|----------|
| 0. 自动服务发现 | ⏳ | 0% |
| 1. Server 核心模块 | ✅ | 100% |
| 2. LLMEngine 双模式 | ✅ | 100% |
| 3. CLI 集成 | ✅ | 100% |
| 4. 配置与依赖 | ✅ | 100% |
| 5. 单元测试 | ✅ | 100% |
| 6. 代码质量改进 | ✅ | 100% |
| 7. 集成测试与验证 | ⏳ | 0% |
| 8. 文档完善 | ✅ | 100% |
| 9. 发布准备 | ⏳ | 0% |
| 10. OpenClaw 集成 | ⏳ | 0% |

**整体完成度**：**75%** (6/9 阶段完成，集成测试与自动服务发现待进行）

**2026-02-15 更新**：
- ✅ 文档完成（添加自动服务发现机制设计）
- ⏳ 待实现：Phase 0（自动服务发现）

---

## 📝 未完成内容（与 OpenClaw 交互）

### 阶段 0：自动服务发现机制（2026-02-15 新增，P0）

#### 0.1 端口检测和递增
- **任务**：实现端口可用性检测和自动递增
- **文件**：`qmd/server/port_manager.py`（新建）
- **实现内容**：
  - ✅ `find_available_port(start_port=18765, max_attempts=100)` → int
  - ✅ `save_server_port(port)` → 保存到 `~/.qmd/server_port.txt`
  - ✅ `get_saved_port()` → int | None
- **测试**：
  ```bash
  # 测试端口检测
  python -c "from qmd.server.port_manager import find_available_port; print(find_available_port())"
  # 预期：输出可用端口号（如18765）

  # 测试端口保存
  python -c "from qmd.server.port_manager import save_server_port; save_server_port(18766)"
  # 预期：~/.qmd/server_port.txt 包含 18766
  ```

#### 0.2 进程检测
- **任务**：检测QMD Server进程是否运行
- **文件**：`qmd/server/process.py`（新建）
- **实现内容**：
  - ✅ `find_server_processes()` → list[psutil.Process]
  - ✅ `get_server_port_from_process(proc)` → int | None
  - ✅ `kill_server_processes()` → void（可选，用于调试）
- **测试**：
  ```bash
  # 启动一个server进程
  qmd server &

  # 测试进程检测
  python -c "from qmd.server.process import find_server_processes; print(len(find_server_processes()))"
  # 预期：输出 1（找到1个server进程）
  ```

#### 0.3 智能连接和自动启动
- **任务**：Client端实现智能服务发现
- **文件**：`qmd/server/client.py`（修改）
- **实现内容**：
  - ✅ `_discover_server()` → str（核心逻辑）
    1. 尝试连接 localhost:18765
    2. 读取 `~/.qmd/server_port.txt`
    3. 检查进程是否存在
    4. 进程不存在则自动启动
  - ✅ `_try_connect(url, timeout=1.0)` → bool
  - ✅ `_is_server_running()` → bool
  - ✅ `_auto_start_server()` → str
- **测试**：
  ```bash
  # 测试1：无server，自动启动
  python -c "from qmd.server.client import EmbedServerClient; c = EmbedServerClient(); print(c.base_url)"
  # 预期：自动启动server，输出 http://localhost:18765

  # 测试2：server已运行，直接连接
  qmd server &  # Terminal 1
  python -c "from qmd.server.client import EmbedServerClient; c = EmbedServerClient(); print(c.base_url)"  # Terminal 2
  # 预期：直接连接成功，不启动新进程
  ```

#### 0.4 CLI命令更新
- **任务**：更新`qmd server`命令使用新端口
- **文件**：`qmd/cli.py`（修改，第67行）
- **修改内容**：
  ```python
  # 修改前
  @click.option("--port", default=8000, type=int, ...)

  # 修改后
  @click.option("--port", default=18765, type=int, help="Port to bind to (auto-increment if occupied)")

  # 启动时调用端口检测
  from qmd.server.port_manager import find_available_port, save_server_port

  actual_port = find_available_port(port)
  if actual_port != port:
      console.print(f"[yellow]Port {port} occupied, using {actual_port}[/yellow]")

  save_server_port(actual_port)
  uvicorn.run(app, host=host, port=actual_port)
  ```
- **测试**：
  ```bash
  # 测试默认端口
  qmd server
  # 预期：Starting on port 18765

  # 测试端口冲突
  # 占用18765：python -m http.server 18765 &
  qmd server
  # 预期：Port 18765 occupied, using 18766
  ```

#### 0.5 依赖添加
- **任务**：添加新依赖到 `pyproject.toml`
- **修改内容**：
  ```toml
  [project.optional-dependencies]
  server = [
      "fastapi>=0.100.0",
      "uvicorn[standard]>=0.23.0",
      "httpx>=0.24.0",
      "psutil>=5.9.0",     # 新增：进程检测
      "requests>=2.28.0",   # 新增：HTTP连接检测
  ]
  ```
- **测试**：
  ```bash
  # 安装server依赖
  pip install -e .[server]

  # 验证依赖
  pip list | grep -E "psutil|requests"
  # 预期：显示psutil和requests版本
  ```

#### 0.6 集成测试
- **任务**：测试OpenClaw场景下的自动服务发现
- **测试场景**：
  1. **场景1：首次使用（无server）**
     ```bash
     # 不启动server
     # 执行搜索
     qmd search "test query"
     # 预期：
     # 1. 日志：QMD server not running, auto-starting...
     # 2. 日志：Starting on port 18765
     # 3. 搜索成功返回
     ```

  2. **场景2：Server已运行**
     ```bash
     # Terminal 1: 启动server
     qmd server

     # Terminal 2: 执行搜索
     qmd search "test query"
     # 预期：
     # 1. 直接连接成功
     # 2. 日志：Using existing server at http://localhost:18765
     # 3. 搜索成功返回
     ```

  3. **场景3：端口冲突**
     ```bash
     # Terminal 1: 占用18765
     python -m http.server 18765

     # Terminal 2: 执行搜索
     qmd search "test query"
     # 预期：
     # 1. 自动启动server（使用18766）
     # 2. 日志：Port 18765 occupied, using 18766
     # 3. 搜索成功返回
     ```

  4. **场景4：Server退出后重启**
     ```bash
     # Terminal 1: 启动server
     qmd server
     # Ctrl+C 停止server

     # Terminal 2: 执行搜索
     qmd search "test query"
     # 预期：
     # 1. 检测到server不可用
     # 2. 自动启动新server
     # 3. 搜索成功返回
     ```

**估算时间**：
- 端口检测和递增：1小时
- 进程检测：1小时
- 智能连接和自动启动：1.5小时
- CLI命令更新：30分钟
- 依赖添加：10分钟
- 集成测试：1.5小时
- **总计**：**5-6小时**

---

### 阶段 7：集成测试与验证（下一步）

#### 7.1 依赖安装测试
- **任务**：验证 server 依赖正确安装
- **需要执行的命令**：
```bash
# 安装 server 依赖
pip install -e .[server]

# 验证安装
pip list | grep -E "fastapi|uvicorn|httpx"
```
- **预期结果**：
  -- fastapi>=0.100.0 ✅
  -- uvicorn>=0.23.0 ✅
  -- httpx>=0.24.0 ✅

- **OpenDev 示例词**：
```
验证 qmd-python 项目的 server 依赖安装：
1. 安装命令：pip install -e .[server]
2. 验证命令：pip list | grep fastapi
3. 如果失败，检查 pyproject.toml [project.optional-dependencies.server]
```

#### 7.2 Server 启动测试
- **任务**：验证 server 可以正常启动和响应
- **需要执行的命令**：
```bash
# 启动 server
qmd server

# 另开一个终端：测试健康检查
curl http://localhost:8000/health

# 测试 embed 端点
curl -X POST http://localhost:8000/embed \
  -H "Content-Type: application/json" \
  -d '{"texts": ["test query"]}'
```
- **预期结果**：
  -- server 输出：`Starting QMD MCP Server...` ✅
  -- health 返回：`{"status": "healthy", "model_loaded": true}` ✅
  -- embed 返回：`{"embeddings": [[0.1, 0.2, ...]]}`（384 维向量）✅

- **OpenDev 示例词**：
```
测试 QMD MCP Server 启动和基本功能：
1. 启动命令：qmd server
2. 测试健康检查：curl http://localhost:8000/health
3. 测试 embed：curl -X POST http://localhost:8000/embed -H "Content-Type: application/json" -d '{"texts": ["test"]}'
4. 验证响应格式和内容（384 维向量）
```

#### 7.3 多进程并发测试
- **任务**：验证多进程场景下显存节省
- **需要执行的命令**：
```bash
# Terminal 1: 启动 server
qmd server

# Terminal 2, 3, 4: 并发搜索
qmd search "query1" &
qmd search "query2" &
qmd search "query3" &

# Terminal 5: 监控显存
nvidia-smi -l 1
```
- **预期结果**：
  -- Server 模式显存：2-4GB（单例模型）✅
  -- 所有搜索请求正常返回 ✅
  -- CPU 队列串行处理（无并发冲突）✅

- **OpenDev 示例词**：
```
测试 QMD MCP Server 多进程并发场景：
1. 启动 server：qmd server
2. 打开 3 个终端并发执行：qmd search "query1/2/3"
3. 监控显存：nvidia-smi
4. 验证显存占用 2-4GB（vs 独立模式的 6-12GB）
5. 检查所有搜索结果是否正常返回
```

#### 7.4 模式切换测试
- **任务**：验证 auto 模式检测正确工作
- **需要执行的命令**：
```bash
# 测试 1：手动指定 server 模式
qmd search "test" --mode server

# 测试 2：手动指定 standalone 模式
qmd search "test" --mode standalone

# 测试 3：auto 模式（应该自动检测）
# 需要修改 CLI 添加 --mode 选项，或直接在代码中测试
```
- **预期结果**：
  -- Server 模式：使用 HTTP 客户端 ✅
  -- Standalone 模式：本地模型加载 ✅
  -- Auto 模式：根据 VRAM 自动选择 ✅

- **OpenDev 示例词**：
```
测试 LLMEngine 模式切换功能：
1. 修改 qmd/cli.py 添加 `--mode` 选项到 search 命令
2. 测试 server 模式：qmd search "test" --mode server
3. 测试 standalone 模式：qmd search "test" --mode standalone
4. 验证 LLMEngine 正确路由到 server 或本地
5. 测试自动降级：server 停止时的 fallback
```

#### 7.5 降级策略测试
- **任务**：验证 server 不可用时的自动降级
- **需要执行的命令**：
```bash
# Terminal 1: 不启动 server
# Terminal 2: 强制 server 模式
qmd search "test" --mode server

# 预期：fallback 到 standalone 模式
# 预期日志：WARNING: MCP server unavailable, falling back to standalone
```
- **预期结果**：
  -- 检测到 server 不可用 ✅
  -- 自动切换到 standalone 模式 ✅
  -- 搜索仍然正常工作（本地模型）✅

- **OpenDev 示例词**：
```
测试 MCP Server 降级策略：
1. 确保没有运行的 server（netstat -an | grep 8000）
2. 强制 server 模式：qmd search "test" --mode server
3. 验证自动降级到 standalone 模式
4. 检查日志是否有 "falling back to standalone" 警告
5. 验证搜索结果仍然正常返回
```

#### 7.6 性能基准测试
- **任务**：测量和对比性能指标
- **需要执行的命令**：
```bash
# 测试 1：Server 模式延迟
qmd server  # Terminal 1
time qmd search "test query"  # Terminal 2
# 重复 10 次取平均

# 测试 2：Standalone 模式延迟
time qmd search "test query"  # 无 server
# 重复 10 次取平均

# 测试 3：并发吞吐量
for i in {1..10}; do
  qmd search "query $i" &
done
wait
```
- **预期结果**：
  -- Server 模式延迟：~100ms（可接受）✅
  -- Standalone 模式延迟：~50ms（基准）✅
  -- 显存节省：66%（2-4GB vs 6-12GB）✅

- **OpenDev 示例词**：
```
执行 QMD MCP Server 性能基准测试：
1. 测试 server 模式延迟：time qmd search "test"（重复 10 次）
2. 测试 standalone 模式延迟：time qmd search "test"（无 server，重复 10 次）
3. 记录平均延迟和 P95 值
4. 使用 nvidia-smi 监控显存和延迟差异
5. 对比两种模式的显存和延迟差异
6. 生成性能报告（延迟、显存、吞吐量）
```

---

### 阶段 8：文档完善（持续进行）

#### 8.1 README 更新
- **需要补充**：
  - [ ] 快速开始：MCP Server 模式
  - [ ] 配置说明：mode 选项
  - [ ] 环境变量：QMD_FORCE_SERVER

#### 8.2 MCP Server 使用指南
- **需要创建**：
  - [ ] `docs/MCP_USAGE.md` - 详细使用教程
  - [ ] 示例场景
  - [ ] 故障排查

---

### 阶段 9：发布准备（待进行）

#### 9.1 版本号
- **当前版本**：0.2.0
- **发布版本**：0.3.0（MCP Server 功能）

#### 9.2 CHANGELOG
- [ ] 添加新功能说明
- [ ] 更新升级指南
- [ ] 标注破坏性变更

#### 9.3 PyPI 发布
- [ ] 构建：`python -m build`
- [ ] 测试：`pip install dist/`
- [ ] 上传：`twine upload dist/*`
- [ ] Git tag：`git tag v0.3.0`

---

### 阶段 10：OpenClaw 集成（分析完成）

#### 10.1 集成分析
- ✅ **已完成**：`docs/ARCHITECTURE_ANALYSIS.md`
- ✅ **已完成**：`docs/MCP_COMPATIBILITY_ANALYSIS.md`
- ✅ **已完成**：`docs/MCP_IMPLEMENTATION_SUMMARY.md`

#### 10.2 与原始 QMD 的兼容性
- **保持一致**：
  - ✅ Tool 名称：search, vsearch, query, get, multi_get, status
  - ✅ 参数 Schema
  - ✅ 输出结构
  - ✅ URI 格式：qmd://
  - ✅ 行号格式
  - [ ] Resource: qmd://{+path}（可选实现）
  - [ ] Prompt: query guide（可选实现）

#### 10.3 MCP Server 实现路线
- **Phase 1 (P0)**：核心 MCP Server (6 Tools)
  - [ ] `qmd/mcp/server.py` - MCP Server 主逻辑
  - [ ] `qmd/mcp/tools.py` - 6 Tools 实现
  - [ ] `qmd/mcp/transport.py` - Stdio transport
- **Phase 2 (P1)**：Resource + Prompt
  - [ ] `qmd/mcp/resources.py` - qmd:// Resource
  - [ ] `qmd/mcp/prompts.py` - Query guide Prompt
- **Phase 3 (P2)**：优化
  - [ ] SSE Transport
  - [ ] WebSocket Transport
  - [ ] 错误处理改进

---

## 📊 项目统计

### 代码变更（本次提交）
- **新增文件**：4
  - `docs/MCP_SERVER_PROPOSAL.md`
  - `docs/MCP_COMPATIBILITY_ANALYSIS.md`
  - `docs/MCP_IMPLEMENTATION_SUMMARY.md`
  - `qmd/server/` 目录（4 个文件）

- **修改文件**：5
  - `qmd/cli.py` - 添加 --mode 选项
  - `qmd/llm/engine.py` - 双模式支持
  - `qmd/search/vector.py` - mode 参数
  - `qmd/search/hybrid.py` - mode 参数
  - `qmd/server/app.py` - Queue → Lock

- **代码行数**：
  - 新增：~500 行
  - 修改：~100 行
  - 文档：~1200 行

### 测试覆盖
- **单元测试**：5 个测试用例 ✅
- **集成测试**：待进行（阶段 7）
- **手动测试**：Server 启动 + 基本功能 ✅

---

## 🎯 下一步（推荐优先级）

### 优先级 P0（核心功能）
1. **自动服务发现实现**（阶段 0）：5-6小时
   - 端口检测和递增
   - 进程检测
   - 智能连接和自动启动
   - 集成测试
2. **集成测试**：执行阶段 7 的所有测试场景
3. **Bug 修复**：根据测试结果修复发现的问题
4. **性能验证**：确保 Server 模式延迟 < 100ms

### 优先级 P1（完善功能）
1. **Resource 实现**：qmd:// URI 访问（兼容性）
2. **Prompt 实现**：query guide（用户体验）
3. **错误处理**：更详细的错误信息和恢复建议

### 优先级 P2（扩展功能）
1. **SSE Transport**：支持 Server-Sent Events
2. **WebSocket Transport**：实时双向通信
3. **配置化**：YAML 配置文件支持

---

## 📝 OpenDev 交互指南

### 推荐工作流
- **步骤 1**：启动 OpenDev
```bash
cd D:\MoneyProjects\qmd-python
code .
```

- **步骤 2**：复制粘贴对应任务的提示词
- 见上述 "未完成内容" 中的 OpenDev 示例词
- 每个任务独立完成

- **步骤 3**：审查代码
- 完成后使用 `review` 命令检查
- 确保代码质量保持 75%+

- **步骤 4**：测试验证
- 运行测试套件：`pytest tests/test_server.py`
- 手动测试上述场景

---

## 🔗 相关文档

- **架构设计**：`docs/MCP_SERVER.md`
- **测试文件**：`tests/test_server.py`
- **项目主文档**：`README.md`
- **代码规范**：`AGENTS.md`
- **原始 QMD**：`D:\MoneyProjects\qmd\src\mcp.ts`

---

-**最后更新**：2026-02-15 01:19（提交 e4f9df）
-**下次检查**：2026-02-15（测试与验证）
