# QMD-Python API 文档中心

> **最后更新**: 2026-02-17
> **协议版本**: MCP 2025-06-18, HTTP/1.1

---

## 📁 文档结构

```
docs/api/
├── README.md                    # 本文档 - API 文档索引
├── mcp-tools.md                 # MCP 协议规范（Tools、Resources、Prompts）
├── http-endpoints.md            # HTTP Transport 端点规范
├── compatibility.md             # 与原版 QMD 的兼容性分析
└── implementation-guide.md      # 实现指南和测试用例
```

---

## 🎯 快速导航

### 按角色查找

| 角色 | 推荐文档 | 说明 |
|------|---------|------|
| **MCP Client 开发者** | [mcp-tools.md](mcp-tools.md) | 6个 Tools + 1个 Resource + 1个 Prompt |
| **HTTP API 用户** | [http-endpoints.md](http-endpoints.md) | REST API 端点规范 |
| **集成开发者** | [compatibility.md](compatibility.md) | 与原版 QMD (TypeScript) 的兼容性 |
| **Server 实现者** | [implementation-guide.md](implementation-guide.md) | 实现细节、测试用例、注意事项 |

### 按协议类型查找

#### MCP 协议 (Model Context Protocol)

**文档**: [mcp-tools.md](mcp-tools.md)

**组成**:
- **6个 Tools**: search, vsearch, query, get, multi_get, status
- **1个 Resource**: qmd://{+path} (文档访问)
- **1个 Prompt**: query (使用指南)

**Transport**: Stdio (stdio://)
**SDK**: mcp (Python) 或 @modelcontextprotocol/sdk (TypeScript)

---

#### HTTP Transport (REST API)

**文档**: [http-endpoints.md](http-endpoints.md)

**端点**: 8个主要端点
- `POST /embed` - 生成嵌入
- `POST /vsearch` - 向量搜索
- `POST /query` - 混合搜索
- `POST /search` - BM25搜索
- `POST /get` - 获取文档
- `POST /multi_get` - 批量获取
- `GET /status` - 索引状态
- `GET /health` - 健康检查

**默认端口**: 18765
**认证**: 无（localhost only）

---

#### 兼容性分析

**文档**: [compatibility.md](compatibility.md)

**内容**:
- 原版 QMD (TypeScript) 分析
- 接口差异对比
- 兼容性检查清单
- 迁移建议

---

#### 实现指南

**文档**: [implementation-guide.md](implementation-guide.md)

**内容**:
- 辅助函数定义
- 数据结构说明
- 特殊行为说明
- 测试用例
- 实现注意事项

---

## 📊 API 对比

### MCP vs HTTP Transport

| 特性 | MCP 协议 | HTTP Transport |
|------|----------|---------------|
| **传输协议** | Stdio | HTTP/1.1 |
| **目标用户** | AI Agent (Claude Desktop, OpenCode) | CLI命令、OpenClaw |
| **接口类型** | Tools、Resources、Prompts | REST 端点 |
| **数据格式** | JSON-RPC 2.0 | JSON |
| **认证** | 由 MCP Client 管理 | 无（localhost） |
| **主要用途** | AI Agent 集成 | 程序化访问 |

### 功能映射

| 功能 | MCP Tool | HTTP 端点 |
|------|----------|-----------|
| BM25 搜索 | `search` | `POST /search` |
| 向量搜索 | `vsearch` | `POST /vsearch` |
| 混合搜索 | `query` | `POST /query` |
| 获取文档 | `get` | `POST /get` |
| 批量获取 | `multi_get` | `POST /multi_get` |
| 索引状态 | `status` | `GET /status` |
| 生成嵌入 | - | `POST /embed` |
| 健康检查 | - | `GET /health` |

---

## 🔗 相关文档

### 架构相关
- [统一服务器架构](../architecture/UNIFIED_SERVER_ARCHITECTURE.md) - Server 设计
- [自动服务发现](../architecture/AUTO_SERVER_DISCOVERY.md) - 零配置机制

### 使用指南
- [最终配置文档](../guide/FINAL_CONFIG.md) - 模型配置和使用

### 技术分析
- [Search vs VSearch](../analysis/SEARCH_VSEARCH_COMPARISON.md) - 搜索技术对比

---

## 📖 推荐阅读顺序

### 理解系统架构
1. [统一服务器架构](../architecture/UNIFIED_SERVER_ARCHITECTURE.md) - 了解整体设计
2. [自动服务发现](../architecture/AUTO_SERVER_DISCOVERY.md) - 理解服务发现机制

### 集成 QMD API

**场景 1: AI Agent 集成**
1. [mcp-tools.md](mcp-tools.md) - MCP 协议规范
2. [compatibility.md](compatibility.md) - 兼容性分析

**场景 2: HTTP API 调用**
1. [http-endpoints.md](http-endpoints.md) - HTTP 端点规范
2. [implementation-guide.md](implementation-guide.md) - 实现细节

**场景 3: Server 实现**
1. [http-endpoints.md](http-endpoints.md) - HTTP 端点
2. [mcp-tools.md](mcp-tools.md) - MCP 协议
3. [implementation-guide.md](implementation-guide.md) - 完整实现指南
4. [compatibility.md](compatibility.md) - 兼容性要求

---

## 📝 维护说明

### 文档更新规范

- **MCP 协议变更**: 更新 `mcp-tools.md` 和 `compatibility.md`
- **HTTP 端点变更**: 更新 `http-endpoints.md` 和 `implementation-guide.md`
- **实现细节更新**: 更新 `implementation-guide.md`

### 版本标记

所有 API 文档使用语义化版本：
- **MCP 协议**: 遵循 MCP spec 版本（当前 2025-06-18）
- **HTTP API**: 独立版本号（当前 1.0.0）

### 兼容性承诺

- ✅ **向后兼容**: 不破坏现有 API
- ⚠️ **弃用通知**: 提前标记废弃功能
- ✅ **迁移指南**: 提供升级路径

---

## 🤝 贡献指南

### 提交 Bug 或建议

1. 确认问题所属文档（MCP/HTTP/实现）
2. 提供复现步骤或详细描述
3. 附上相关日志或错误信息

### 文档改进

- 保持格式一致（Markdown + 标题层级）
- 添加代码示例和使用场景
- 更新日期和版本信息

---

**最后更新**: 2026-02-17
**维护者**: QMD-Python Team
