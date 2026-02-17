# QMD-Python 文档中心

> **最后更新**: 2026-02-17
> **项目路径**: D:\MoneyProjects\qmd-python

---

## 📁 文档结构

```
docs/
├── README.md                   # 本文档 - 文档索引
├── architecture/               # 架构设计文档
│   ├── ARCHITECTURE_DECISION_2026-02-15.md
│   ├── UNIFIED_SERVER_ARCHITECTURE.md
│   └── AUTO_SERVER_DISCOVERY.md
├── api/                        # API 接口规范
│   ├── MCP_INTERFACE_SPEC.md
│   └── MCP_COMPATIBILITY_ANALYSIS.md
├── guide/                      # 使用指南
│   └── FINAL_CONFIG.md
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

### [架构决策记录](architecture/ARCHITECTURE_DECISION_2026-02-15.md)
**日期**: 2026-02-15 | **状态**: 已确认

核心架构决策，包括：
- Client-Server 分离设计
- HTTP MCP Server 方案
- 操作分类与智能路由
- 队列串行机制

### [统一服务器架构](architecture/UNIFIED_SERVER_ARCHITECTURE.md)
**版本**: 1.0.0 | **状态**: 设计完成

单一 Server 进程 + 多 Transport 架构：
- 核心：单例模型（4GB VRAM）
- HTTP Transport（端口 18765）
- MCP Transport（stdio）
- 自动服务发现机制

### [自动服务发现](architecture/AUTO_SERVER_DISCOVERY.md)
**优先级**: P0 | **状态**: 设计完成

零配置服务发现机制：
- 端口自动检测和递增（18765→18766→...）
- 端口信息持久化（`~/.qmd/server_port.txt`）
- 进程检测避免重复启动
- 自动启动 Server

---

## 🔌 API 文档 (api/)

### [MCP 接口规范](api/MCP_INTERFACE_SPEC.md)
**版本**: 1.0.0 | **协议**: MCP 2025-06-18

完整的 MCP Server 接口规范：
- **6 个 Tools**: search, vsearch, query, get, multi_get, status
- **1 个 Resource**: qmd://{+path}
- **1 个 Prompt**: query 使用指南
- HTTP Transport 端点规范

### [MCP 兼容性分析](api/MCP_COMPATIBILITY_ANALYSIS.md)
**用途**: 与原版 QMD (TypeScript) 的兼容性分析

包含：
- 原始 QMD MCP Server 分析
- 接口规范对比
- 兼容性检查清单
- 实现注意事项

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
3. [统一服务器架构](architecture/UNIFIED_SERVER_ARCHITECTURE.md) - 系统架构

### 深入技术细节
4. [架构决策记录](architecture/ARCHITECTURE_DECISION_2026-02-15.md) - 核心决策
5. [MCP 接口规范](api/MCP_INTERFACE_SPEC.md) - API 规范
6. [自动服务发现](architecture/AUTO_SERVER_DISCOVERY.md) - 服务发现机制

### 了解问题背景
7. [根因分析](requirement/01-root-cause-analysis.md) - 问题背景
8. [Search vs VSearch](analysis/SEARCH_VSEARCH_COMPARISON.md) - 搜索技术对比

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
