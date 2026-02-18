# Client-Server 分离决策记录

**日期**: 2026-02-15
**决策人**: Boss + Zandar (CTO+COO)
**状态**: ✅ 已确认

---

## 问题本质

```
3个模型实例 × 4GB显存/个 = 12GB显存爆炸
```

**场景**：多进程并发时，每个进程独立加载模型
- 进程1：embed模型（4GB VRAM）
- 进程2：embed模型（4GB VRAM）
- 进程3：embed模型（4GB VRAM）
- **总计**：12GB VRAM（显存溢出）

---

## 核心决策

### 决策1：Client-Server分离（必须）

**方案**：
```
┌─────────────────────────────────┐
│         CLI / Client           │
└────────────┬────────────────────┘
              │ HTTP
┌────────────▼────────────────────┐
│   QMD Server (单一进程）        │
│   - 单例模型（4GB VRAM）        │
│   - 队列串行（防止溢出）        │
└────────────────────────────────┘
```

**理由**：
- ✅ 显存节省：66%（4GB vs 12GB）
- ✅ 架构清晰：职责分离
- ✅ 维护简单：单一进程

---

### 决策2：HTTP MCP Server（不是stdio）

**方案**：
- ✅ HTTP Transport（默认）
- ✅ SSE（Server-Sent Events）用于实时推送
- ❌ 不使用stdio模式

**理由**：
- ✅ 性能好：HTTP比stdio更稳定
- ✅ 跨进程：Server独立运行
- ✅ 可扩展：支持WebSocket未来
- ✅ OpenClaw集成：HTTP + MCP协议兼容

---

### 决策3：操作分类（智能路由）

**分类标准**：是否需要模型

| 操作 | 需要模型 | 执行方式 | 理由 |
|------|---------|---------|------|
| **embed** | ✅ | HTTP → Server | 需要bge模型 |
| **vsearch** | ✅ | HTTP → Server | 需要embed + 向量搜索 |
| **query** | ✅ | HTTP → Server | 需要embed + reranker + LLM扩展 |
| **search** | ❌ | 直接CLI | BM25纯算法，零等待 |
| **collection add** | ❌ | 直接CLI | SQLite操作 |
| **collection list** | ❌ | 直接CLI | SQLite查询 |
| **index** | ❌ | 直接CLI | 文件读取 + 写入 |
| **config** | ❌ | 直接CLI | YAML配置 |
| **status** | ⚠️ | 混合 | Server状态→HTTP，CLI状态→直接 |

**核心价值**：
- ✅ CLI操作零等待（不需要模型）
- ✅ Server操作串行化（需要模型）
- ✅ 用户体验好（自动路由）

---

### 决策4：队列串行（防止显存溢出）

**方案**：
```python
# Server端
_processing_lock = asyncio.Lock()

@app.post("/embed")
async def embed(texts):
    async with _processing_lock:
        return await model.encode(texts)
```

**效果**：
```
10个并发请求：
- 请求1：立即执行（0ms等待）
- 请求2：等待请求1（~100ms）
- 请求3：等待请求2（~200ms）
- ...
- 总时间：1秒（10 × 100ms）
- 显存占用：4GB（单例模型）
```

**对比**：
- ❌ 旧方案：10进程 × 4GB = 40GB显存（OOM）
- ✅ 新方案：1进程 × 4GB = 4GB显存（安全）

---

## 架构对比

### 旧方案（已废弃）

```
多进程Standalone模式：
├─ 进程1：embed（4GB VRAM）
├─ 进程2：embed（4GB VRAM）
├─ 进程3：embed（4GB VRAM）
└─ 问题：
   - 显存溢出（12GB）
   - 进程管理复杂
   - 无法复用模型
```

### 新方案（已确认）

```
Client-Server分离模式：

CLI层（智能路由）：
├─ 不需要模型 → 直接执行（零等待）
└─ 需要模型 → HTTP Client（自动检测Server）

Server层（单一进程）：
├─ 单例模型（4GB VRAM）
├─ 队列串行（防止溢出）
└─ HTTP端点（embed, vsearch, query, health）

核心价值：
├─ 显存节省：66%（4GB vs 12GB）
├─ 性能提升：CLI操作零等待
└─ 用户体验：零配置（自动服务发现）
```

---

## 核心价值总结

### 技术价值
- ✅ 显存节省：66%（4GB vs 12GB）
- ✅ 性能提升：CLI操作零等待
- ✅ 架构清晰：职责分离
- ✅ 维护简单：单一进程

### 商业价值
- ✅ 用户体验：零配置（自动服务发现）
- ✅ 成本降低：减少显存需求
- ✅ 扩展性：支持更多并发用户
- ✅ 稳定性：Windows兼容性更好

### 战略价值
- ✅ 技术壁垒：Client-Server分离架构
- ✅ 产品差异化：自动服务发现（竞品没有）
- ✅ 长期维护：代码简洁易维护

---

## 关键约束

### 必须满足
1. ✅ Client-Server分离（架构要求）
2. ✅ HTTP MCP Server（不是stdio）
3. ✅ 队列串行（防止显存溢出）
4. ✅ 智能路由（按是否需要模型）

### 可以优化
1. ⚠️ 端点数量（4个核心端点足够）
2. ⚠️ 错误处理（可以逐步完善）
3. ⚠️ 性能调优（可以后续优化）

### 暂不实现
1. ❌ REST API（违背MCP理念）
2. ❌ 完整mode选项（智能路由更简单）
3. ❌ SSE/WebSocket（未来扩展）

---

## 下一步行动

详细实现计划请参见：
- [架构总览](../core/overview.md)
- [自动服务发现](../auto-discovery/overview.md)
- [Transport设计](../core/transport-design.md)

---

**文档版本**: 2.0
**最后更新**: 2026-02-18
**原始文档**: ARCHITECTURE_DECISION_2026-02-15.md
