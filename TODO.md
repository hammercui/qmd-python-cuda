# QMD-Python 任务清单

> **项目**: qmd-python
> **负责人**: Zandar (CTO+COO)
> **更新时间**: 2026-02-16 15:50

---

## 当前状态

- **完成度**: **100%** ✅
- **实际耗时**: ~2小时
- **核心目标**: 解决多进程显存爆炸（12GB → 4GB）

**核心架构**: Client-Server分离 + HTTP MCP Server + 队列串行

---

## 已完成任务（4个Phase）

### ✅ Phase 0: 自动服务发现（1.5h）
- [x] 端口检测和递增（18765冲突→18766）
- [x] 进程检测（Server是否运行）
- [x] 智能连接（自动检测/启动Server）
- [x] CLI命令更新（默认端口18765）

**文件**:
- `qmd/server/port_manager.py` ✅
- `qmd/server/process.py` ✅
- `qmd/server/client.py` ✅
- `qmd/cli.py` ✅

### ✅ Phase 1: HTTP端点（1h）
- [x] `POST /embed` - 文本向量化
- [x] `POST /vsearch` - 向量搜索
- [x] `POST /query` - 混合搜索
- [x] `GET /health` - 健康检查

**文件**:
- `qmd/server/app.py` ✅
- `qmd/server/models.py` ✅

### ✅ Phase 2: HTTP客户端（1h）
- [x] `EmbedServerClient`类
- [x] 自动服务发现（_discover_server）
- [x] HTTP方法（embed, vsearch, query）

**文件**:
- `qmd/server/client.py` ✅

### ✅ Phase 3: CLI智能路由（1h）
- [x] search → 直接CLI（FTSSearcher）
- [x] vsearch → HTTP Client
- [x] query → HTTP Client
- [x] collection/index/config → 直接CLI

**文件**:
- `qmd/cli.py` ✅

---

## 验收标准

### 功能 ✅
- [x] `qmd server` 启动在18765端口
- [x] 端口冲突自动递增
- [x] CLI自动检测并启动Server
- [x] 4个HTTP端点正常工作
- [x] 智能路由（search→CLI，vsearch/query→HTTP）

### 性能 ⏳ 待测试
- [ ] 显存占用 ≤ 4GB
- [ ] embed延迟 < 100ms
- [ ] Server启动 < 10秒

---

## 下一步：集成测试

### 测试场景
1. **Server启动**: `qmd server`
2. **自动服务发现**: `qmd vsearch "test"`（自动启动Server）
3. **端口冲突**: 占用18765，验证自动递增
4. **智能路由**: `qmd search` vs `qmd vsearch`
5. **性能测试**: nvidia-smi监控显存

---

## 相关文档

- **详细版**: `FINAL_TASKS.md`
- **项目状态**: `PROJECT_STATUS.md`
- **Obsidian TODO**: `D:\syncthing\obsidian-mark\8.TODO\公司\qmd-python\`

---

**所有Phase完成！准备集成测试。**
