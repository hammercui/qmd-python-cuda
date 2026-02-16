# QMD-Python 简化任务清单

> **项目**: qmd-python
> **负责人**: Zandar (CTO+COO)
> **更新时间**: 2026-02-16

---

## 当前状态

- **完成度**: 75%
- **剩余估算**: 4.5 小时
- **核心目标**: 解决多进程显存爆炸（12GB → 4GB）

**核心架构**: Client-Server分离 + HTTP MCP Server + 队列串行

---

## 剩余任务（4个Phase，4.5小时）

### Phase 0: 自动服务发现（1.5h）
**文件**:
- `qmd/server/port_manager.py`（新建）
- `qmd/server/process.py`（新建）
- `qmd/server/client.py`（修改）

**任务**:
- [x] 端口检测和递增（18765冲突→18766）
- [x] 进程检测（Server是否运行）
- [x] 智能连接（自动检测/启动Server）
- [ ] CLI命令更新（默认端口18765）

### Phase 1: HTTP端点（1h）⬇️
**文件**: `qmd/server/app.py`（扩展）

**4个端点**:
- [ ] `POST /embed` - 文本向量化
- [ ] `POST /vsearch` - 向量搜索
- [ ] `POST /query` - 混合搜索
- [ ] `GET /health` - 健康检查

### Phase 2: HTTP客户端（1h）
**文件**: `qmd/server/client.py`（扩展）

**任务**:
- [ ] `QmdHttpClient`类
- [ ] 自动服务发现
- [ ] 5个HTTP方法（embed, vsearch, query, health, search）

### Phase 3: CLI智能路由（1h）⬇️
**文件**: `qmd/cli.py`（修改）

**路由策略**:
- 不需要模型（search, collection, index, config）→ 直接CLI
- 需要模型（vsearch, query）→ HTTP Client

---

## 验收标准

### 功能
- [ ] `qmd server` 启动在18765端口
- [ ] 端口冲突自动递增
- [ ] CLI自动检测并启动Server
- [ ] 4个HTTP端点正常工作
- [ ] 智能路由（search→CLI，vsearch→HTTP）

### 性能
- [ ] 显存占用 ≤ 4GB
- [ ] embed延迟 < 100ms
- [ ] Server启动 < 10秒

---

## 实施顺序

1. **Phase 0**（1.5h）→ 自动服务发现
2. **Phase 1**（1h）→ HTTP端点
3. **Phase 2**（1h）→ HTTP客户端
4. **Phase 3**（1h）→ CLI集成

---

## 相关文档

- **详细版**: `FINAL_TASKS.md`
- **项目状态**: `PROJECT_STATUS.md`
- **Obsidian TODO**: `D:\syncthing\obsidian-mark\8.TODO\公司\qmd-python\`

---

**开始实现？**
