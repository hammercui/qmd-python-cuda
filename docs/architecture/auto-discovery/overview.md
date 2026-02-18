# 自动服务发现机制

**状态**: 设计完成，待实现
**优先级**: P0（核心功能）
**最后更新**: 2026-02-18

---

## 概述

自动服务发现机制允许 OpenClaw 和其他 AI 工具**透明地使用 QMD Server**，无需用户手动启动或管理 Server 进程。

### 核心价值

| 维度 | 分离设计 | 自动服务发现 |
|------|----------|----------------|
| **用户操作** | 手动启动server | 零操作 |
| **进程管理** | 可能重复启动 | 自动检测避免重复 |
| **端口冲突** | 启动失败 | 自动递增 |
| **配置复杂度** | 需要知道端口 | 零配置 |

---

## 工作流程

```
┌─────────────────────────────────────────────────────┐
│                OpenClaw CLI 调用                    │
│            qmd.exe search "query"                   │
└───────────────────────────┬─────────────────────────┘
                            │
                            ▼
         ┌──────────────────────────────────────┐
         │   Client自动服务发现逻辑              │
         │   (qmd/server/client.py)             │
         └──────────────────────────────────────┘
                            │
         ┌──────────────────┼──────────────────┐
         │                  │                  │
         ▼                  ▼                  ▼
    尝试18765        读取端口文件        检查进程
    连接默认端口      ~/.qmd/...          psutil检测
         │                  │                  │
         │             ┌────┴────┐             │
         │             │         │             │
      成功✅          失败✅      失败✅       不存在✅
         │             │         │             │
         │             │         │         ┌───┴───┐
         │             │         │         │       │
         │             │      连接成功   启动Server
         │             │         │         │   等待启动
         │             │         │         │   连接成功
         │             └─────────┴─────────┴───────┘
         │
         ▼
    使用HTTP API
```

---

## 核心组件

### 1. Server端：端口管理器

**文件**: `qmd/server/port_manager.py`

**功能**：

| 函数 | 功能 | 返回值 |
|------|------|--------|
| `find_available_port(start_port, max_attempts)` | 检测可用端口，冲突时递增 | int |
| `save_server_port(port)` | 保存实际端口到文件 | None |
| `get_saved_port()` | 读取保存的端口 | int \| None |

### 2. 进程检测器

**文件**: `qmd/server/process.py`

**功能**：

| 函数 | 功能 | 返回值 |
|------|------|--------|
| `find_server_processes()` | 查找所有qmd server进程 | list[psutil.Process] |
| `get_server_port_from_process(proc)` | 从命令行提取端口号 | int \| None |
| `kill_server_processes()` | 调试停止所有server进程 | None |

### 3. 智能客户端

**文件**: `qmd/server/client.py`

**核心方法**: `_discover_server()`

**发现序列**：
1. 尝试连接默认端口（18765）
2. 尝试读取保存的端口（~/.qmd/server_port.txt）
3. 检查server进程是否存在
4. 进程不存在则自动启动server

---

## 使用场景

### 场景1：首次使用（无server）

```bash
# 用户执行搜索（无需手动启动server）
qmd search "how to use qmd"

# 内部流程：
# 1. 尝试连接18765 → 失败
# 2. 读取端口文件 → 不存在
# 3. 检查进程 → 不存在
# 4. 自动启动server
# 5. 等待启动（最多10秒）
# 6. 连接成功
# 7. 执行搜索

# 输出：
# [cyan]QMD server not running, auto-starting...[/cyan]
# [cyan]Starting QMD MCP Server[/cyan]
# [cyan]Host: 127.0.0.1, Port: 18765[/cyan]
# (搜索结果...)
```

### 场景2：Server已运行

```bash
# Terminal 1: 启动server
qmd server
# [cyan]Starting QMD MCP Server[/cyan]
# [cyan]Host: 127.0.0.1, Port: 18765[/cyan]

# Terminal 2: 执行搜索
qmd search "test query"

# 内部流程：
# 1. 尝试连接18765 → 成功
# 2. 直接使用现有连接
# 3. 执行搜索

# 输出：
# (无启动日志，直接搜索结果)
```

### 场景3：端口冲突

```bash
# Terminal 1: 占用18765
python -m http.server 18765

# Terminal 2: 执行搜索
qmd search "test query"

# 内部流程：
# 1. 尝试连接18765 → 失败（被占用）
# 2. 读取端口文件 → 不存在
# 3. 检查进程 → 不存在
# 4. 自动启动server
# 5. 端口检测：18765被占用
# 6. 尝试18766 → 成功
# 7. 保存18766到文件
# 8. 连接成功
# 9. 执行搜索

# 输出：
# [cyan]QMD server not running, auto-starting...[/cyan]
# [yellow]Port 18765 occupied, using 18766[/yellow]
# [cyan]Starting QMD MCP Server[/cyan]
# [cyan]Host: 127.0.0.1, Port: 18766[/cyan]
# (搜索结果...)
```

### 场景4：Server退出后重启

```bash
# Terminal 1: 启动server
qmd server
# (Ctrl+C 停止)
# [yellow]Shutting down server...[/yellow]

# Terminal 2: 执行搜索
qmd search "test query"

# 内部流程：
# 1. 尝试连接18765 → 失败
# 2. 读取端口文件：18765 → 失败（进程已退出）
# 3. 检查进程 → 不存在
# 4. 自动启动新server
# 5. 连接成功
# 6. 执行搜索

# 输出：
# [cyan]QMD server not running, auto-starting...[/cyan]
# [cyan]Starting QMD MCP Server[/cyan]
# (搜索结果...)
```

---

## 依赖需求

需要添加到 `pyproject.toml`:

```toml
dependencies = [
    # ... 现有依赖
    "psutil>=5.9.0",  # 进程检测
    "requests>=2.28.0",  # HTTP连接检测
]
```

---

## 实现优先级

| 任务 | 优先级 | 预估时间 |
|------|--------|----------|
| 端口检测和递增 | P0 | 1小时 |
| 端口存储机制 | P0 | 30分钟 |
| 进程检测 | P0 | 1小时 |
| 自动启动逻辑 | P0 | 1.5小时 |
| 测试和调试 | P0 | 1小时 |
| **总计** | - | **5小时** |

---

## 测试检查清单

### 单元测试

- [ ] `test_find_available_port()` - 端口检测和递增
- [ ] `test_save_server_port()` - 端口保存
- [ ] `test_get_saved_port()` - 端口读取
- [ ] `test_find_server_processes()` - 进程检测
- [ ] `test_get_server_port_from_process()` - 端口提取
- [ ] `test_try_connect()` - 连接检测
- [ ] `test_is_server_running()` - 进程状态
- [ ] `test_auto_start_server()` - 自动启动

### 集成测试

- [ ] 场景1：首次使用（无server）
- [ ] 场景2：Server已运行
- [ ] 场景3：端口冲突
- [ ] 场景4：Server退出后重启
- [ ] OpenClaw集成测试

### 边界测试

- [ ] 端口0-1024（系统保留端口）
- [ ] 端口被系统服务占用
- [ ] 无权限启动进程
- [ ] 启动超时（延迟高的系统）

---

## 相关文档

- [实现细节](./implementation.md) - 代码实现详情
- [架构总览](../core/overview.md) - 完整架构设计
- [Client-Server分离决策](../decisions/2026-02-15-client-server-separation.md) - 决策记录

---

**文档版本**: 1.0.0
**最后更新**: 2026-02-18
