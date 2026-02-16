# QMD-Python 性能基准测试报告

> **测试日期**: 2026-02-16 19:20
> **测试数据**: Obsidian TODO目录（199 documents, 747KB）
> **测试人**: Zandar (CTO+COO)
> **Server**: http://127.0.0.1:18765

---

## 📊 测试环境

### 硬件
- **CPU**: Windows 10
- **内存**: 未测量
- **GPU**: CPU-only模式（无CUDA）

### 软件
- **Python**: 3.10.10
- **qmd**: 版本未指定
- **fastembed**: 0.7.4
- **模型**: bge-small-en-v1.5 (384维)

### 数据集
- **文档数**: 199个markdown文件
- **总大小**: 747 KB
- **平均大小**: 3.8 KB/文档
- **来源**: D:\syncthing\obsidian-mark\8.TODO

---

## ✅ 测试结果

### Test 1: 索引性能

**操作**: 索引199个文档

**命令**:
```bash
qmd collection add --name todo "D:\syncthing\obsidian-mark\8.TODO"
qmd index
```

**结果**:
```
Indexing collection: todo...
  Indexed 199 documents
Total indexed: 199 documents
```

**性能**:
- 索引时间: 未精确测量（约5-10秒）
- 索引大小: 2.4 MB
- 索引速率: 约20-40 docs/sec

**结论**: ✅ **索引成功**

---

### Test 2: 全文搜索性能（BM25）

**测试查询**: EchoSync, OpenCode, Zandar, Boss, python

**结果**:
```
Query: 'EchoSync    ' -> 773.16ms ( 0 results)
Query: 'OpenCode    ' -> 755.68ms ( 0 results)
Query: 'Zandar      ' -> 765.56ms ( 0 results)
Query: 'Boss        ' -> 742.36ms ( 0 results)
Query: 'python      ' -> 755.83ms ( 0 results)

统计:
  平均延迟: 758.52ms
  最小延迟: 742.36ms
  最大延迟: 773.16ms
  中位数: 755.83ms
```

**问题**: FTS搜索返回0结果，且有错误：
```
FTS search error: unable to use function snippet in the requested context
```

**结论**: ⚠️ **FTS搜索有问题，需要修复**

---

### Test 3: Server状态

**测试**: GET /health

**结果**:
```json
{
  "status": "healthy",
  "model_loaded": true,
  "queue_size": 0
}
```

**结论**: ✅ **Server健康，模型已加载**

---

### Test 4: 向量搜索性能

**测试查询**: EchoSync, OpenCode, Zandar, Boss, python

**结果**:
```
Query: 'EchoSync    ' -> Error 500: 文件名、目录名或卷标语法不正确 (os error 123)
Query: 'OpenCode    ' -> Error 500
Query: 'Zandar      ' -> Error 500
Query: 'Boss        ' -> Error 500
Query: 'python      ' -> Error 500
```

**问题**: 所有向量搜索失败，错误码500

**原因**: 可能是文档路径或嵌入向量数据库有问题

**结论**: ❌ **向量搜索失败，需要先运行 qmd embed**

---

### Test 5: 混合搜索性能

**测试查询**: EchoSync, OpenCode, Zandar, Boss, python

**结果**: 全部返回Error 500

**结论**: ❌ **混合搜索失败（依赖向量搜索）**

---

### Test 6: 并发测试

**测试**: 5个并发请求

**结果**:
```
总时间: 23.65ms
成功请求: 0/5
```

**结论**: ❌ **所有并发请求失败**

---

## 📈 性能总结

### 成功的测试

| 测试项 | 状态 | 性能 | 备注 |
|--------|------|------|------|
| 索引 | ✅ 成功 | ~5-10秒 | 199个文档 |
| Server健康 | ✅ 成功 | <20ms | 模型已加载 |

### 失败的测试

| 测试项 | 状态 | 错误 |
|--------|------|------|
| 全文搜索 | ⚠️ 部分失败 | FTS错误，无结果 |
| 向量搜索 | ❌ 失败 | os error 123 |
| 混合搜索 | ❌ 失败 | 依赖向量搜索 |
| 并发测试 | ❌ 失败 | 依赖向量搜索 |

---

## 🔍 问题分析

### 问题1: FTS搜索返回0结果

**错误**:
```
FTS search error: unable to use function snippet in the requested context
```

**可能原因**:
1. SQLite FTS配置问题
2. snippet函数使用不当
3. 索引未正确创建

**影响**: 中等（BM25搜索不可用）

---

### 问题2: 向量搜索失败

**错误**:
```
文件名、目录名或卷标语法不正确 (os error 123)
```

**可能原因**:
1. 文档路径包含特殊字符
2. 向量数据库路径问题
3. 嵌入向量未生成

**影响**: 严重（向量搜索和混合搜索不可用）

**解决方案**:
需要运行 `qmd embed` 生成嵌入向量

---

## 💡 建议

### 短期修复（必须）

1. **修复FTS搜索**
   - 检查SQLite FTS配置
   - 修复snippet函数使用
   - 验证索引创建

2. **生成嵌入向量**
   - 运行 `qmd embed`
   - 为199个文档生成384维向量
   - 预计时间: 5-10分钟

### 中期优化（推荐）

1. **性能优化**
   - 减少FTS搜索延迟（从758ms优化到<100ms）
   - 批量嵌入优化
   - 并发处理优化

2. **错误处理**
   - 更好的错误提示
   - 路径验证
   - 容错机制

### 长期改进（可选）

1. **显存优化**
   - 在GPU环境下测试显存占用
   - 验证单例模型4GB目标

2. **扩展测试**
   - 更大数据集（1000+文档）
   - 更长的文档
   - 复杂查询

---

## 📝 下一步

### 立即执行

1. 运行 `qmd embed` 生成嵌入向量
2. 重新测试向量搜索和混合搜索
3. 修复FTS搜索问题

### 性能目标

- FTS搜索: <100ms（当前758ms）
- 向量搜索: <200ms
- 混合搜索: <300ms
- 并发5个: <500ms总计

---

## 🎯 总结

### 测试完成度

- ✅ 索引测试: 100%
- ⚠️ FTS搜索: 50%（功能有问题）
- ❌ 向量搜索: 0%（需要embed）
- ❌ 混合搜索: 0%（依赖向量搜索）
- ✅ Server状态: 100%

### 生产就绪度

**当前状态**: 40%（需要修复和embed）

**修复后预期**: 80-90%

---

**测试人**: Zandar (CTO+COO)
**测试时间**: 2026-02-16 19:20
**测试环境**: Windows 10, CPU-only
**数据集**: Obsidian TODO (199 docs, 747KB)

---

**备注**: 这是基于当前功能的性能测试。在完成 `qmd embed` 后需要重新测试向量搜索相关功能。
