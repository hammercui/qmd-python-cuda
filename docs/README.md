# QMD-Python 文档中心

> **最后更新**: 2026-02-18
> **项目路径**: D:\MoneyProjects\qmd-python

---

## 📁 文档结构

```
docs/
├── README.md                   # 本文档 - 文档索引
├── architecture/               # 架构设计文档
│   ├── README.md               # 架构文档索引
│   ├── decisions/              # 决策记录
│   ├── core/                   # 核心架构
│   └── auto-discovery/         # 自动服务发现
├── api/                        # API 接口规范
│   ├── README.md               # API文档索引
│   ├── mcp-tools.md            # MCP Tools规范
│   ├── http-endpoints.md       # HTTP端点规范
│   ├── compatibility.md        # 兼容性分析
│   └── implementation-guide.md # 实现指南
├── guide/                      # 使用指南
│   └── FINAL_CONFIG.md         # 模型配置和使用
├── analysis/                   # 技术分析
│   └── SEARCH_VSEARCH_COMPARISON.md
├── requirement/                # 需求文档
│   ├── 01-root-cause-analysis.md
│   ├── 02-design-document.md
│   ├── 03-requirements.md
│   ├── 04-testing.md
│   ├── 05-metrics.md
│   └── 06-models.md
└── archived/                   # 归档文档
```

---

## 🏗️ 架构文档 (architecture/)

详见 [architecture/README.md](architecture/README.md) - 架构文档索引

### 核心文档

#### [架构总览](architecture/core/overview.md)
**版本**: 1.0.0 | **状态**: 设计完成

完整架构概述，包括：
- Client-Server分离架构
- CLI智能路由
- Server核心组件
- 工作流程和性能指标

#### [Client-Server分离决策](architecture/decisions/2026-02-15-client-server-separation.md)
**日期**: 2026-02-15 | **状态**: ✅ 已确认

核心架构决策记录：
- Client-Server分离设计
- HTTP MCP Server方案
- 操作分类与智能路由
- 队列串行机制

#### [Transport层设计](architecture/core/transport-design.md)
**版本**: 1.0.0 | **状态**: 设计完成

多种Transport设计：
- QmdServer核心类
- HTTP Transport（CLI命令）
- MCP Transport（AI Agent）
- 文件结构和使用示例

#### [自动服务发现](architecture/auto-discovery/overview.md)
**优先级**: P0 | **状态**: 设计完成

零配置服务发现机制：
- 端口自动检测和递增
- 进程检测避免重复启动
- 自动启动Server
- 使用场景和测试计划

#### [实现细节](architecture/auto-discovery/implementation.md)
**状态**: 设计完成，待实现

代码实现详情：
- 端口管理器（port_manager.py）
- 进程检测器（process.py）
- 智能客户端（client.py）
- CLI集成和依赖管理

---

## 🔌 API 文档 (api/)

详见 [api/README.md](api/README.md) - API 文档索引

### 核心文档

#### [MCP Tools 规范](api/mcp-tools.md)
**版本**: 1.0.0 | **协议**: MCP 2025-06-18

- **6 个 Tools**: search, vsearch, query, get, multi_get, status
- **1 个 Resource**: qmd://{+path}
- **1 个 Prompt**: query 使用指南

#### [HTTP 端点规范](api/http-endpoints.md)
**版本**: 1.0.0 | **协议**: HTTP/1.1

- 5 个核心端点：embed, vsearch, query, search, health
- REST API 接口
- 默认端口：18765

#### [兼容性分析](api/compatibility.md)
**用途**: 与原版 QMD (TypeScript) 的兼容性分析

#### [实现指南](api/implementation-guide.md)
**用途**: Server 实现者参考

- 辅助函数定义
- 数据结构说明
- 测试用例

---

## 📖 使用指南 (guide/)

### [最终配置文档](guide/FINAL_CONFIG.md)
**配置日期**: 2026-02-17 | **版本**: v1.0

项目最终配置方案（PyTorch + fastembed 混合）：
- 模型配置（Embedding + Reranker + Query Expansion）
- 安装指南
- 使用方法
- 性能数据
- 验证测试

---

## 🔬 技术分析 (analysis/)

### [Search vs VSearch 对比](analysis/SEARCH_VSEARCH_COMPARISON.md)

两种搜索方式的架构对比：
- Search (FTS 全文搜索) - SQLite FTS5 + BM25
- VSearch (向量语义搜索) - ChromaDB + fastembed-gpu
- 架构差异（TypeScript vs Python）
- 性能对比数据
- 使用场景建议

---

## 📋 需求文档 (requirement/)

| 文件 | 说明 |
|------|------|
| [01-root-cause-analysis.md](requirement/01-root-cause-analysis.md) | 根因分析 |
| [02-design-document.md](requirement/02-design-document.md) | 设计文档 |
| [03-requirements.md](requirement/03-requirements.md) | 需求规格 |
| [04-testing.md](requirement/04-testing.md) | 测试计划 |
| [05-metrics.md](requirement/05-metrics.md) | 指标定义 |
| [06-models.md](requirement/06-models.md) | 模型配置 |

---

## 🎯 推荐阅读顺序

### 快速了解项目
1. [README.md](../README.md) - 项目概述
2. [最终配置文档](guide/FINAL_CONFIG.md) - 模型配置和使用
3. [架构总览](architecture/core/overview.md) - 系统架构

### 深入技术细节
4. [Client-Server分离决策](architecture/decisions/2026-02-15-client-server-separation.md) - 核心决策
5. [Transport层设计](architecture/core/transport-design.md) - HTTP + MCP Transport
6. [自动服务发现](architecture/auto-discovery/overview.md) - 零配置机制
7. [MCP Tools规范](api/mcp-tools.md) - API规范

### 了解问题背景
8. [根因分析](requirement/01-root-cause-analysis.md) - 问题背景
9. [Search vs VSearch](analysis/SEARCH_VSEARCH_COMPARISON.md) - 搜索技术对比

---

## 📝 维护说明

### 文档更新规范
- 每次重大更新后更新本文档索引
- 保持文档格式一致（Markdown + frontmatter）
- 使用语义化的文件名
- 添加明确的更新时间和状态

### 文档状态标记
- **设计完成**: 方案已确定，待实现
- **已确认**: 决策已确认，正在实施
- **生产就绪**: 功能已实现并测试
- **已归档**: 历史文档，仅供参考

---

**最后更新**: 2026-02-17
