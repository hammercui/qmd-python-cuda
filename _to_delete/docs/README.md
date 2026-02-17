# QMD-Python 文档索引

**最后更新**: 2026-02-16

---

## 📑 完整文档目录

> **[DOCS_INDEX.md](./DOCS_INDEX.md)** - 完整的项目文档索引（包含所有文档的大小、更新时间、统计信息）

---

## 📚 核心文档

### 架构设计

| 文档 | 说明 | 优先级 |
|------|------|--------|
| **[UNIFIED_SERVER_ARCHITECTURE.md](./UNIFIED_SERVER_ARCHITECTURE.md)** | 统一服务器架构设计（单一进程，多Transport） | ⭐⭐⭐ |
| **[AUTO_SERVER_DISCOVERY.md](./AUTO_SERVER_DISCOVERY.md)** | 自动服务发现机制（端口检测，进程管理） | ⭐⭐⭐ |

### 用户文档

| 文档 | 说明 | 用途 |
|------|------|------|
| **[CONFIG_GUIDE.md](./CONFIG_GUIDE.md)** | 配置文件使用指南 | 用户配置 |

### 技术规范

| 文档 | 说明 | 用途 |
|------|------|------|
| **[MCP_INTERFACE_SPEC.md](./MCP_INTERFACE_SPEC.md)** | MCP接口详细规范（6 Tools + 1 Resource + 1 Prompt） | 开发实现参考 |
| **[MCP_COMPATIBILITY_ANALYSIS.md](./MCP_COMPATIBILITY_ANALYSIS.md)** | MCP兼容性分析（为什么需要兼容） | 理解背景 |

---

## 📂 归档文档

以下文档已移动到 `_to_delete/` 目录供参考：

- **技术报告** (`_to_delete/report/`) - 8 个审计和分析报告（2026-02-14）
- **需求文档** (`_to_delete/requirement/`) - 6 个需求规格文档（2026-02-14）

详见：[DOC_CLEANUP_REPORT.md](./DOC_CLEANUP_REPORT.md)

---

## 📖 文档阅读指南

### 新手入门

1. 先读 **[CONFIG_GUIDE.md](./CONFIG_GUIDE.md)** - 了解如何配置QMD
2. 再读 **[UNIFIED_SERVER_ARCHITECTURE.md](./UNIFIED_SERVER_ARCHITECTURE.md)** - 了解架构设计

### 开发者

1. **[UNIFIED_SERVER_ARCHITECTURE.md](./UNIFIED_SERVER_ARCHITECTURE.md)** - 核心架构
2. **[AUTO_SERVER_DISCOVERY.md](./AUTO_SERVER_DISCOVERY.md)** - 自动服务发现
3. **[MCP_COMPATIBILITY_ANALYSIS.md](./MCP_COMPATIBILITY_ANALYSIS.md)** - MCP接口规范

### 性能优化

参考 **[ARCHITECTURE_DECISION_2026-02-15.md](./ARCHITECTURE_DECISION_2026-02-15.md)** - 性能优化决策和效果分析

### 历史报告

如需查看初期的审计和分析报告，请参阅 `_to_delete/` 目录。

---

## 🗂️ 文档历史

### 已删除的文档（2026-02-15清理）

以下文档已被删除或合并到核心文档中：

| 文档 | 删除原因 | 替代文档 |
|------|----------|----------|
| `MCP_SERVER_PROPOSAL.md` | 原始提案，已被统一架构替代 | UNIFIED_SERVER_ARCHITECTURE.md |
| `MCP_IMPLEMENTATION_SUMMARY.md` | 实施步骤，已被统一架构替代 | UNIFIED_SERVER_ARCHITECTURE.md |
| `ARCHITECTURE_COMPARISON.md` | 架构对比，统一架构已确定 | UNIFIED_SERVER_ARCHITECTURE.md |
| `ARCHITECTURE_ANALYSIS.md` | 从其他项目复制，不完全相关 | - |
| `MCP_SERVER.md` | 使用8000端口的旧版 | UNIFIED_SERVER_ARCHITECTURE.md |
| `docs/PROJECT_STATUS.md` | 与根目录重复 | PROJECT_STATUS.md（根目录） |

---

## 🔗 相关链接

- **项目状态**: [PROJECT_STATUS.md](../PROJECT_STATUS.md)
- **代码规范**: [AGENTS.md](../AGENTS.md)
- **主README**: [README.md](../README.md)

---

**维护者**: QMD-Python Team
**最后更新**: 2026-02-16
