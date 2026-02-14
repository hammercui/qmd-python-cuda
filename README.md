# QMD-Python

> **致敬原作**: [qmd-ts](https://github.com/t0has/qmd) - TypeScript实现的混合搜索引擎

**Python重写版本** - 专为Windows稳定性优化和更高质量的检索体验而生

## 为什么重写？

原版[qmd-ts](https://github.com/t0has/qmd)使用`node-llama-cpp`在Windows上存在严重的稳定性问题（随机崩溃）。本项目改用`transformers + PyTorch`技术栈：

✅ **Windows完美兼容** - 不再崩溃  
✅ **更高质量模型** - MTEB基准+7%，检索准确率+15%  
✅ **更小体积** - 1.24GB vs 2.04GB（-38%）  
✅ **100% CLI兼容** - 所有命令和接口保持一致  

## 核心功能

- 🔍 **混合搜索**: BM25全文 + 向量语义 + RRF融合
- 🎯 **智能重排**: LLM查询扩展 + Cross-Encoder重排序
- 📂 **多格式支持**: Markdown, HTML, Text, JSON
- 🔒 **隐私优先**: 完全本地运行，无遥测，无网络请求
- 💾 **高效缓存**: 内容可寻址嵌入缓存，避免重复计算
- 🚀 **快速索引**: 基于SQLite的元数据和全文索引

## 技术栈

```
嵌入模型: bge-small-en-v1.5 (130MB) - 384维向量
重排模型: ms-marco-MiniLM-L-6-v2 (110MB) - 任务专用
查询扩展: Qwen3-0.5B-Instruct (1.0GB) - 本地运行
```

## 安装

```bash
pip install .
```

**系统要求**:
- Python 3.9+
- Windows/Linux/macOS
- 首次运行会自动下载模型（约1.24GB）

## 快速开始

### 1. 添加文档集合
```bash
qmd collection add ~/docs --name my-docs
```

### 2. 索引文档
```bash
qmd index
```

### 3. 生成向量嵌入
```bash
qmd embed
```

### 4. 搜索文档

#### BM25全文搜索
```bash
qmd search "如何使用向量检索"
```

#### 向量语义搜索
```bash
qmd vsearch "semantic query"
```

#### 混合搜索（推荐）
```bash
qmd query "智能查询扩展和重排序"
```

## 性能指标

- **混合搜索**: 10k文档 <3秒
- **嵌入生成**: 批处理支持高吞吐量
- **缓存机制**: 未更改文档跳过重复计算

## 文档

详细技术分析请查看：
- [技术栈对比](docs/report/TECH_STACK_ANALYSIS.md) - GGUF vs PyTorch
- [兼容性分析](docs/report/COMPATIBILITY_ANALYSIS.md) - 为什么模型更换不影响工具集成
- [模型清单](docs/report/MODEL_INVENTORY.md) - 完整模型使用说明
- [审计报告](docs/report/AUDIT_REPORT.md) - 合规性评估（85% → 95%）

## 致谢

感谢原版[qmd-ts](https://github.com/t0has/qmd)的优秀设计理念。本Python重写版在保持100% CLI兼容性的同时，通过更稳定的技术栈和更高质量的模型，为Windows用户提供了可靠的本地文档搜索解决方案。

## 许可证

MIT License - 与原版保持一致

---

**原项目地址**: [qmd-ts](https://github.com/t0has/qmd)  
**本仓库**: [qmd-python-cuda](https://github.com/hammercui/qmd-python-cuda)
