# MCP 文档拆分和重构方案

**日期**: 2026-02-17
**目标**: 消除重复，简化维护，提高可读性

---

## 📊 当前问题分析

### 文档大小对比

| 文档 | 行数 | 大小 | 问题 |
|------|------|------|------|
| MCP_INTERFACE_SPEC.md | 1593行 | 52KB | 过大，包含HTTP和MCP两部分 |
| MCP_COMPATIBILITY_ANALYSIS.md | 424行 | 13KB | 与前文档存在重复 |

### 重复内容统计

| 重复章节 | MCP_INTERFACE_SPEC | MCP_COMPATIBILITY | 重复度 |
|---------|-------------------|-------------------|--------|
| MCP Tools (6个) | 行1018-1448 | 行73-371 | ~80% |
| MCP Resources | 行1449-1467 | 行371-424 | ~90% |
| MCP Prompts | 行1468-1538 | - | 0% |
| HTTP Transport | 行43-954 | - | 0% |

**总重复行数**: 约350行（占 COMPATIBILITY 文档的 82%）

---

## 🎯 拆分方案

### 方案一：按协议类型拆分（推荐）

```
docs/api/
├── README.md                     # API 文档索引（新建）
├── mcp-tools.md                  # MCP 工具规范（新建，从 INTERFACE_SPEC 拆分）
├── http-endpoints.md             # HTTP 端点规范（新建，从 INTERFACE_SPEC 拆分）
├── compatibility.md              # 兼容性分析（重构，保留独特内容）
└── implementation-guide.md       # 实现指南（新建，合并检查清单和注意事项）
```

#### 文档职责划分

**README.md** (索引文件)
- API 文档导航
- 快速查找指南
- 推荐阅读顺序

**mcp-tools.md** (MCP 工具规范)
- 6个 MCP Tools 完整定义
- MCP Resources 规范
- MCP Prompts 规范
- 数据结构和类型定义
- 约 600 行

**http-endpoints.md** (HTTP 端点规范)
- HTTP Transport 概述
- 8个 HTTP 端点详细规范
- 错误处理
- CLI 直接操作说明
- 约 500 行

**compatibility.md** (兼容性分析 - 重构)
- 原始 QMD MCP Server 分析
- 与原版的关键差异对比（表格形式）
- 兼容性检查清单（精简版）
- 测试策略
- 约 300 行（删除重复的接口定义）

**implementation-guide.md** (实现指南)
- 实现注意事项
- 辅助函数定义
- 数据结构详细说明
- 特殊行为说明
- 测试用例
- 约 400 行

### 方案二：按使用场景拆分

```
docs/api/
├── README.md                     # 索引
├── server-implementation.md      # Server 开发者指南
├── client-usage.md               # Client 使用指南
└── compatibility.md              # 兼容性分析
```

---

## 📝 实施步骤（方案一）

### Phase 1: 创建新文档结构

```bash
cd docs/api
# 创建新文件
touch README.md
touch mcp-tools.md
touch http-endpoints.md
touch implementation-guide.md

# 重命名和重构
# MCP_COMPATIBILITY_ANALYSIS.md → compatibility.md
# MCP_INTERFACE_SPEC.md → 删除（内容已拆分）
```

### Phase 2: 内容迁移

**mcp-tools.md** 从 MCP_INTERFACE_SPEC.md 提取：
- 行 10-42: 概述
- 行 957-1593: MCP Tools + Resources + Prompts
- 添加快速索引表格

**http-endpoints.md** 从 MCP_INTERFACE_SPEC.md 提取：
- 行 1-42: 概述（调整）
- 行 43-954: HTTP Transport
- 行 955-1017: CLI 直接操作

**compatibility.md** 从 MCP_COMPATIBILITY_ANALYSIS.md 重构：
- 保留：行 1-27（概述和原始分析）
- 删除：行 73-424（重复的接口定义）
- 添加：差异对比表格（精简版）

**implementation-guide.md** 从 MCP_INTERFACE_SPEC.md 提取：
- 行 1539-1593: 实现细节和测试用例
- 从 compatibility.md 提取：实现注意事项

### Phase 3: 更新引用

更新以下文件中的文档链接：
- `docs/README.md`
- `README.md` (根目录)
- `docs/architecture/UNIFIED_SERVER_ARCHITECTURE.md`

---

## ✅ 预期效果

### 文档数量

| 项目 | 当前 | 重构后 | 变化 |
|------|------|--------|------|
| 文档数量 | 2个 | 5个 | +3 |
| 总行数 | 2017行 | ~1800行 | -10% |
| 重复内容 | 350行 | 0行 | -100% |

### 可维护性提升

- ✅ **职责单一**: 每个文档专注一个主题
- ✅ **易于查找**: 清晰的分类和索引
- ✅ **减少重复**: 消除 82% 的重复内容
- ✅ **便于更新**: 修改 HTTP 端点不影响 MCP Tools

### 查阅体验改善

| 角色 | 推荐文档 | 行数 | 提升 |
|------|---------|------|------|
| **MCP Client 开发者** | mcp-tools.md | 600行 | 只看需要的 40% |
| **HTTP API 用户** | http-endpoints.md | 500行 | 只看需要的 33% |
| **集成开发者** | compatibility.md | 300行 | 减少 30% |

---

## 🔄 迁移检查清单

### 创建新文档
- [ ] `docs/api/README.md` - 索引文件
- [ ] `docs/api/mcp-tools.md` - MCP 规范
- [ ] `docs/api/http-endpoints.md` - HTTP 规范
- [ ] `docs/api/implementation-guide.md` - 实现指南

### 重构现有文档
- [ ] 重命名 `MCP_COMPATIBILITY_ANALYSIS.md` → `compatibility.md`
- [ ] 删除重复内容（接口定义）
- [ ] 添加差异对比表格

### 删除旧文档
- [ ] 删除 `MCP_INTERFACE_SPEC.md`（内容已拆分）

### 更新引用
- [ ] 更新 `docs/README.md`
- [ ] 更新根目录 `README.md`
- [ ] 更新 `docs/architecture/UNIFIED_SERVER_ARCHITECTURE.md`

### 验证
- [ ] 检查所有链接有效性
- [ ] 验证内容完整性
- [ ] 确认无重复内容

---

## 💡 后续优化建议

### 1. 添加代码示例

在 `implementation-guide.md` 中添加：
- Python 实现示例
- 错误处理示例
- 测试用例示例

### 2. 创建快速参考

创建 `docs/api/quick-reference.md`：
- 所有 Tools/端点的参数速查表
- 返回值格式速查
- 常见错误码

### 3. 版本管理

为 API 规范添加版本标记：
- `mcp-tools.md` 添加 `@version 1.0.0`
- `http-endpoints.md` 添加 `@version 1.0.0`
- 变更日志记录

---

**建议采用**: 方案一（按协议类型拆分）
**预计工作量**: 2-3小时
**维护者**: 待定
