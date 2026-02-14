# QMD-Python 文档索引

**最后更新**: 2026-02-15

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
| **[MCP_COMPATIBILITY_ANALYSIS.md](./MCP_COMPATIBILITY_ANALYSIS.md)** | MCP接口规范和兼容性分析 | 开发参考 |

---

## 📂 归档文档

### 技术报告（`report/`）

| 文档 | 说明 |
|------|------|
| [TECH_STACK_ANALYSIS.md](./report/TECH_STACK_ANALYSIS.md) | 技术栈分析（GGUF vs PyTorch） |
| [COMPATIBILITY_ANALYSIS.md](./report/COMPATIBILITY_ANALYSIS.md) | 兼容性分析 |
| [MODEL_INVENTORY.md](./report/MODEL_INVENTORY.md) | 模型清单 |
| [AUDIT_REPORT.md](./report/AUDIT_REPORT.md) | 审计报告 |
| [MEMORY_ANALYSIS.md](./report/MEMORY_ANALYSIS.md) | 内存分析 |
| [FIX_SUMMARY.md](./report/FIX_SUMMARY.md) | 修复总结 |
| [TECH_STACK_VARIANCE.md](./report/TECH_STACK_VARIANCE.md) | 技术栈差异 |

### 需求文档（`requirement/`）

| 文档 | 说明 |
|------|------|
| [01-root-cause-analysis.md](./requirement/01-root-cause-analysis.md) | 根因分析 |
| [02-design-document.md](./requirement/02-design-document.md) | 设计文档 |
| [03-requirements.md](./requirement/03-requirements.md) | 需求说明 |
| [04-testing.md](./requirement/04-testing.md) | 测试计划 |
| [05-metrics.md](./requirement/05-metrics.md) | 性能指标 |
| [06-models.md](./requirement/06-models.md) | 模型说明 |

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

参考 `report/` 目录下的技术报告

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
**最后更新**: 2026-02-15
