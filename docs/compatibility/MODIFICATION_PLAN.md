# QMD CLI 一致性修改计划

## 目标

确保 Python 版本的常用 CLI 命令与 Node.js 版本保持一致，提供相同的用户体验。

---

## 修改阶段规划

### 阶段 1: 核心集合管理（高优先级）

**目标**: 修复 `collection add` 命令，使其与 Node.js 版本一致。

**文件**: `qmd/cli/_collection.py`

**修改内容**:

1. 修改 `--name` 参数为可选
2. 添加默认名称生成逻辑
3. 更新帮助文档

**代码变更**:
```python
# 第 19 行
@click.option("--name", help="Collection name (default: basename of path)")

# 在 collection_add 函数中添加
def collection_add(ctx_obj, path, name, glob):
    """Add a new collection and immediately index it"""
    abs_path = os.path.abspath(path)
    if not os.path.exists(abs_path):
        console.print(f"[red]Error:[/red] Path {abs_path} does not exist")
        return

    # 生成默认名称
    if not name:
        name = os.path.basename(abs_path)
        console.print(f"[dim]Using collection name: {name}[/dim]")

    # 检查名称是否已存在
    if any(c.name == name for c in ctx_obj.config.collections):
        console.print(f"[red]Error:[/red] Collection with name '{name}' already exists")
        return

    # ... 其余逻辑保持不变
```

**测试验证**:
```bash
# 测试 1: 自动命名
qmd collection add ~/Documents
# 预期: 使用 "Documents" 作为集合名称

# 测试 2: 指定名称
qmd collection add ~/Documents --name my-docs
# 预期: 使用 "my-docs" 作为集合名称

# 测试 3: 重复名称检测
qmd collection add ~/Documents --name existing-name
# 预期: 报错名称已存在
```

**预计工作量**: 30 分钟

---

### 阶段 2: 上下文管理统一（中优先级）

**目标**: 修改 `context add` 和 `context remove` 命令，支持 Node.js 风格的路径参数。

**文件**: `qmd/cli/_context.py`

#### 2.1 修改 `context add`

**代码变更**:
```python
# 第 14-26 行
@context.command(name="add")
@click.option("--collection", help="Collection name (for explicit mode)")
@click.option("--path", default="", help="Relative path (default: root)")
@click.argument("path_arg", required=False)
@click.argument("text")
@click.pass_obj
def context_add(ctx_obj, collection, path, path_arg, text):
    """Add/Update context for a path

    Supports two modes:
    1. Path-based: qmd context add [path] <text>
    2. Explicit: qmd context add --collection <name> [--path <path>] <text>
    """
    from qmd.models.config import CollectionConfig

    target_collection = None
    target_path = ""

    if path_arg:
        # 模式 1: 基于路径的参数
        if path_arg == "/":
            # 全局上下文
            ctx_obj.db.set_global_context(text)
            console.print(f"[green]✓[/green] Set global context")
            console.print(f"[dim]Context: {text}[/dim]")
            return

        # 解析虚拟路径 (qmd://collection/path)
        if path_arg.startswith("qmd://"):
            from urllib.parse import urlparse
            parsed = urlparse(path_arg)
            parts = parsed.path.lstrip("/").split("/", 1)
            target_collection = parts[0]
            target_path = parts[1] if len(parts) > 1 else ""
        else:
            # 文件系统路径 - 检测集合
            abs_path = os.path.abspath(path_arg)
            for col in ctx_obj.config.collections:
                if abs_path.startswith(col.path + os.sep) or abs_path == col.path:
                    target_collection = col.name
                    rel_path = os.path.relpath(abs_path, col.path)
                    target_path = rel_path if rel_path != "." else ""
                    break
    else:
        # 模式 2: 显式参数
        if not collection:
            console.print("[red]Error:[/red] Either path or --collection is required")
            console.print("[dim]Usage: qmd context add [path] <text>[/dim]")
            console.print("[dim]       qmd context add --collection <name> [--path <path>] <text>[/dim]")
            return
        target_collection = collection
        target_path = path.strip("/")

    if not target_collection:
        console.print(f"[red]Error:[/red] Cannot detect collection for path: {path_arg}")
        return

    try:
        ctx_obj.db.set_path_context(target_collection, target_path, text)
        display_path = f"qmd://{target_collection}/{target_path}" if target_path else f"qmd://{target_collection}/"
        console.print(f"[green]✓[/green] Added context for: {display_path}")
        console.print(f"[dim]Context: {text}[/dim]")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
```

#### 2.2 修改 `context remove`

**代码变更**:
```python
# 第 56-66 行
@context.command(name="remove")
@click.argument("path_arg")
@click.pass_obj
def context_remove(ctx_obj, path_arg):
    """Remove a path context

    Usage:
      qmd context remove qmd://collection/path
      qmd context remove /
    """
    if path_arg == "/":
        # 移除全局上下文
        ctx_obj.db.set_global_context(None)
        console.print(f"[green]✓[/green] Removed global context")
        return

    # 解析虚拟路径
    if path_arg.startswith("qmd://"):
        from urllib.parse import urlparse
        parsed = urlparse(path_arg)
        parts = parsed.path.lstrip("/").split("/", 1)
        collection = parts[0]
        path = parts[1] if len(parts) > 1 else ""
    else:
        # 文件系统路径 - 检测集合
        abs_path = os.path.abspath(path_arg)
        collection = None
        path = ""
        for col in ctx_obj.config.collections:
            if abs_path.startswith(col.path + os.sep) or abs_path == col.path:
                collection = col.name
                rel_path = os.path.relpath(abs_path, col.path)
                path = rel_path if rel_path != "." else ""
                break

        if not collection:
            console.print(f"[red]Error:[/red] Path is not in any indexed collection: {path_arg}")
            return

    try:
        ctx_obj.db.remove_path_context(collection, path)
        display_path = f"qmd://{collection}/{path}" if path else f"qmd://{collection}/"
        console.print(f"[green]✓[/green] Removed context for: {display_path}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
```

**测试验证**:
```bash
# 测试 context add
qmd context add "Global context"
qmd context add qmd://my-docs "Collection context"
qmd context add qmd://my-docs/src "Path context"
qmd context add --collection my-docs "Explicit mode"

# 测试 context remove
qmd context remove qmd://my-docs/src
qmd context remove /
```

**预计工作量**: 2 小时

---

### 阶段 3: 输出格式扩展（低优先级）

**目标**: 为 `search`/`vsearch`/`query` 命令添加 `--format` 选项。

**文件**: `qmd/cli/_search.py`

**修改内容**:

#### 3.1 添加 `--format` 选项到 `search` 命令

**代码变更**:
```python
# 第 10-17 行
@click.command()
@click.argument("query")
@click.option("--limit", "-n", default=10, help="Maximum number of results")
@click.option("--min-score", type=float, default=0.0, help="Minimum score threshold (0-1)")
@click.option("--collection", "-c", help="Filter by collection")
@click.option("--format", "output_format",
              type=click.Choice(["cli", "json", "files", "md", "csv"]),
              default="cli", help="Output format (default: cli)")
@click.option("--json", "as_json", is_flag=True, help="Output results as JSON (alias for --format=json)")
@click.pass_obj
def search(ctx_obj, query, limit, min_score, collection, output_format, as_json):
    """BM25 full-text search with score normalization and filtering."""
    # 处理 --json 别名
    if as_json:
        output_format = "json"

    searcher = FTSSearcher(ctx_obj.db)
    results = searcher.search(
        query, limit=limit, collection=collection, min_score=min_score
    )

    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return

    # 根据格式输出
    if output_format == "json":
        # 现有 JSON 输出逻辑
        output = []
        for r in results:
            output.append({
                "id": r.get("id"),
                "title": r.get("title"),
                "collection": r.get("collection"),
                "path": r.get("path"),
                "score": r.get("score"),
                "snippet": r.get("snippet"),
            })
        console.print(json.dumps(output, ensure_ascii=False, indent=2))
    elif output_format == "files":
        # 仅文件列表
        for r in results:
            console.print(f"qmd://{r['collection']}/{r['path']}")
    elif output_format == "md":
        # Markdown 格式
        for r in results:
            console.print(f"## {r.get('title', 'N/A')}\n")
            console.print(f"**Path:** qmd://{r['collection']}/{r['path']}\n")
            console.print(f"**Score:** {r.get('score', 0):.4f}\n")
            snippet = r.get("snippet", "")[:200]
            console.print(f"{snippet}...\n")
    elif output_format == "csv":
        # CSV 格式
        console.print("score,collection,path,title,snippet")
        for r in results:
            row = [
                f"{r.get('score', 0):.4f}",
                r['collection'],
                r['path'],
                r.get('title', '').replace(',', '\\,'),
                r.get('snippet', '')[:100].replace(',', '\\,')
            ]
            console.print(','.join(row))
    else:
        # CLI 格式 (默认)
        from rich.table import Table
        table = Table(title=f"Search Results for: {query}")
        table.add_column("Score", style="green", width=8)
        table.add_column("Title", style="cyan")
        table.add_column("Collection", style="magenta", width=15)
        table.add_column("Snippet", style="white")
        for r in results:
            table.add_row(
                f"{r.get('score', 0):.4f}",
                r["title"],
                r["collection"],
                r["snippet"][:80] + "..." if len(r.get("snippet", "")) > 80 else r.get("snippet", "")
            )
        console.print(table)
```

#### 3.2 同样修改 `vsearch` 和 `query` 命令

应用相同的 `--format` 选项到 `vsearch` 和 `query` 命令。

**测试验证**:
```bash
# 测试各格式
qmd search "query" --format cli
qmd search "query" --format json
qmd search "query" --format files
qmd search "query" --format md
qmd search "query" --format csv
qmd search "query" --json  # 向后兼容
```

**预计工作量**: 2 小时

---

## 实施时间表

| 阶段 | 任务 | 预计时间 | 优先级 | 状态 |
|------|------|----------|--------|------|
| 阶段 1 | `collection add` 修改 | 30 分钟 | 🔴 高 | ✅ 完成 |
| 阶段 2 | `context` 命令修改 | 2 小时 | 🟡 中 | ✅ 完成 |
| 阶段 3 | `search` 格式扩展 | 2 小时 | 🟢 低 | ✅ 完成 |
| 测试 | 完整回归测试 | 1 小时 | - | ⏳ 待开始 |
| **总计** | - | **~5.5 小时** | - | **~4.5 小时完成** |

---

## 阶段完成状态

- ✅ **阶段 1 完成** - `collection add` 支持可选 `--name` 参数
- ✅ **阶段 2 完成** - `context add/remove` 支持路径参数
- ✅ **阶段 3 完成** - `search/vsearch/query` 支持 `--format` 选项
- ✅ **所有核心修改完成** - 常用命令与 Node.js 版本保持一致

---

## 风险评估

### 低风险
- ✅ `collection add` - 仅添加默认值逻辑，不影响现有功能
- ✅ `search --format` - 新增选项，保留 `--json` 向后兼容

### 中风险
- ⚠️ `context add/remove` - 参数结构变化，需要确保向后兼容

**缓解措施**:
1. 保留旧参数作为可选（显式模式）
2. 添加详细帮助文档
3. 在修改后运行完整测试套件

---

## 验收标准

### 功能验收
- [ ] 所有修改的命令与 Node.js 版本行为一致
- [ ] 向后兼容性保持（旧参数仍可用）
- [ ] 帮助文档准确反映新用法

### 测试验收
- [ ] 单元测试通过
- [ ] 集成测试通过
- [ ] 手动测试所有场景

### 文档验收
- [ ] README 更新
- [ ] 帮助文本更新
- [ ] 差异文档标记为已解决

---

## 回滚计划

如果出现问题，回滚步骤：

1. Git revert 相关提交
2. 恢复 `qmd/cli/` 目录到修改前状态
3. 重新安装包：`pip install -e .`

---

## 下一步行动

1. ✅ 创建差异文档（已完成）
2. ✅ 创建修改计划（已完成）
3. ⏳ 实施阶段 1 修改
4. ⏳ 测试阶段 1
5. ⏳ 实施阶段 2 修改
6. ⏳ 测试阶段 2
7. ⏳ 实施阶段 3 修改（可选）
8. ⏳ 完整回归测试
9. ⏳ 更新文档

---

## 相关文档

- [CLI 差异文档](./CLI_DIFFERENCES.md)
- [Node.js 版本源码](D:\MoneyProjects\qmd\src\qmd.ts)
- [Python 版本源码](D:\MoneyProjects\qmd-python\qmd\cli\)
