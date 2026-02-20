# QMD CLI 命令一致性差异文档

## 文档目的

记录 **Node.js 版本** (D:\MoneyProjects\qmd) 和 **Python 版本** (qmd-python) 之间的 CLI 命令差异，以确保用户体验一致。

---

## 需要修改的命令

### 1. `collection add` - 名称参数可选性

**优先级**: 🔴 高

**Node.js 版本**:
```bash
qmd collection add <path> [--name <name>] [--glob <pattern>]
# --name 是可选的，默认使用路径的 basename 作为集合名称
```

**Python 版本** (当前):
```bash
qmd collection add <path> --name <name> [--glob <pattern>]
# --name 是必需的 (required=True)
```

**差异影响**:
- 用户在使用 Python 版本时必须手动指定 `--name`
- Node.js 版本可以自动生成名称，体验更流畅

**修改方案**:
```python
# 文件: qmd/cli/_collection.py
# 行: 19

# 修改前:
@click.option("--name", required=True, help="Collection name")

# 修改后:
@click.option("--name", help="Collection name (default: basename of path)")

# 同时需要在 collection_add 函数中添加默认名称生成逻辑:
# if not name:
#     name = os.path.basename(os.path.abspath(path))
```

---

### 2. `context add` - 参数风格统一

**优先级**: 🟡 中

**Node.js 版本**:
```bash
qmd context add [<path>] <text>
# - path 可以省略（默认当前目录）
# - 支持 qmd:// 虚拟路径格式
# - 支持文件系统路径
# - 自动检测集合
```

**Python 版本** (当前):
```bash
qmd context add --collection <collection> [--path <path>] <text>
# - 必须指定 --collection
# - --path 可选（默认为根路径）
```

**差异影响**:
- 参数风格完全不同，用户需要记忆两套命令格式
- Node.js 版本更灵活，支持虚拟路径和自动检测

**修改方案**:
```python
# 文件: qmd/cli/_context.py
# 行: 14-17

# 修改前:
@context.command(name="add")
@click.option("--collection", required=True, help="Collection name")
@click.option("--path", default="", help="Relative path (default: root)")
@click.argument("text")

# 修改后:
@context.command(name="add")
@click.option("--collection", help="Collection name (for explicit mode)")
@click.option("--path", default="", help="Relative path (default: root)")
@click.argument("path_arg", required=False)  # 新增可选路径参数
@click.argument("text")
```

**实现要点**:
1. `path_arg` 为可选位置参数
2. 如果提供 `path_arg`，解析为虚拟路径或文件系统路径
3. 如果 `path_arg` 为空，使用当前目录
4. 自动检测集合（类似 Node.js 版本的 `detectCollectionFromPath` 逻辑）

---

### 3. `context remove` - 参数风格统一

**优先级**: 🟡 中

**Node.js 版本**:
```bash
qmd context remove <path>
# - 直接使用路径参数
# - 支持 qmd:// 虚拟路径
# - 支持文件系统路径
```

**Python 版本** (当前):
```bash
qmd context remove --collection <collection> [--path <path>]
# - 必须使用 --collection 指定
```

**差异影响**:
- 与 `context add` 类似，参数风格不一致
- Node.js 版本更直观

**修改方案**:
```python
# 文件: qmd/cli/_context.py
# 行: 56-59

# 修改前:
@context.command(name="remove")
@click.option("--collection", required=True, help="Collection name")
@click.option("--path", default="", help="Relative path")

# 修改后:
@context.command(name="remove")
@click.argument("path_arg")
```

**实现要点**:
1. 移除 `--collection` 和 `--path` 选项
2. 使用单个 `path_arg` 位置参数
3. 解析虚拟路径或文件系统路径
4. 自动检测集合

---

### 4. `search`/`vsearch`/`query` - 输出格式扩展

**优先级**: 🟢 低

**Node.js 版本**:
```bash
qmd search <query> [--format {cli,json,files,md,xml,csv}] [-n LIMIT] [-c COLLECTION]
# 支持 6 种输出格式
```

**Python 版本** (当前):
```bash
qmd search <query> [-n LIMIT] [--min-score] [-c COLLECTION] [--json]
# 只支持 JSON 格式
```

**差异影响**:
- Python 版本输出格式较单一
- 对于自动化脚本，JSON 已足够
- 对于人类阅读，CLI 格式更友好

**修改方案**:
```python
# 文件: qmd/cli/_search.py
# 行: 11-17 (search 命令)

# 修改前:
@click.command()
@click.argument("query")
@click.option("--limit", "-n", default=10, help="Maximum number of results")
@click.option("--min-score", type=float, default=0.0, help="Minimum score threshold (0-1)")
@click.option("--collection", "-c", help="Filter by collection")
@click.option("--json", "as_json", is_flag=True, help="Output results as JSON")

# 修改后:
@click.command()
@click.argument("query")
@click.option("--limit", "-n", default=10, help="Maximum number of results")
@click.option("--min-score", type=float, default=0.0, help="Minimum score threshold (0-1)")
@click.option("--collection", "-c", help="Filter by collection")
@click.option("--format", "output_format",
              type=click.Choice(["cli", "json", "files", "md", "csv"]),
              default="cli", help="Output format")
@click.option("--json", "as_json", is_flag=True, help="Output results as JSON (alias for --format=json)")
```

**实现要点**:
1. 添加 `--format` 选项，支持 `cli`, `json`, `files`, `md`, `csv`
2. 保留 `--json` 作为 `--format=json` 的别名（向后兼容）
3. 同样修改 `vsearch` 和 `query` 命令

---

## 不需要修改的命令

以下命令已经一致，无需修改：

| 命令 | 说明 |
|------|------|
| `qmd status` | ✅ 完全一致 |
| `qmd update` | ✅ 完全一致 |
| `qmd index` | ✅ 完全一致 |
| `qmd embed` | ✅ 完全一致 |
| `qmd ls` | ✅ 完全一致 |
| `qmd get` | ✅ 完全一致 |
| `qmd multi-get` | ✅ 完全一致 |
| `qmd cleanup` | ✅ 完全一致 |
| `qmd context list` | ✅ 完全一致 |
| `qmd context check` | ✅ 完全一致 |
| `qmd collection list` | ✅ 完全一致 |
| `qmd collection remove` | ✅ 完全一致 |
| `qmd collection rename` | ✅ 完全一致 |

---

## Python 独有命令（保留）

以下命令是 Python 版本独有的，不需要与 Node.js 对齐：

| 命令 | 说明 |
|------|------|
| `qmd config show` | 配置管理 |
| `qmd config set` | 配置设置 |
| `qmd check` | 系统检查（依赖、CUDA、模型） |
| `qmd download` | 模型下载 |
| `qmd server` | HTTP Server 启动 |

这些命令是 Python 版本为了更好的用户体验而添加的增强功能。

---

## 修改优先级总结

| 优先级 | 命令 | 影响范围 | 建议顺序 |
|--------|------|----------|----------|
| 🔴 高 | `collection add` | 集合创建基础功能 | 1 |
| 🟡 中 | `context add` | 上下文管理 | 2 |
| 🟡 中 | `context remove` | 上下文管理 | 3 |
| 🟢 低 | `search/vsearch/query --format` | 输出格式 | 4 |

---

## 测试检查清单

修改完成后，需要验证以下场景：

### `collection add`
- [ ] `qmd collection add /path/to/docs` (自动使用目录名)
- [ ] `qmd collection add /path/to/docs --name my-docs` (指定名称)
- [ ] `qmd collection add /path/to/docs --name my-docs --glob "**/*.txt"` (完整参数)

### `context add`
- [ ] `qmd context add "This is global context"` (当前目录)
- [ ] `qmd context add qmd://my-docs "Collection context"` (虚拟路径)
- [ ] `qmd context add qmd://my-docs/src "Path context"` (子路径)
- [ ] `qmd context add --collection my-docs "Collection context"` (兼容旧格式)

### `context remove`
- [ ] `qmd context remove qmd://my-docs` (虚拟路径)
- [ ] `qmd context remove qmd://my-docs/src` (子路径)

### `search --format`
- [ ] `qmd search "query" --format cli` (默认输出)
- [ ] `qmd search "query" --format json` (JSON 格式)
- [ ] `qmd search "query" --format files` (仅文件列表)
- [ ] `qmd search "query" --format md` (Markdown)
- [ ] `qmd search "query" --json` (向后兼容)

---

## 参考文档

- Node.js 版本: `D:\MoneyProjects\qmd\src\qmd.ts`
- Python 版本: `D:\MoneyProjects\qmd-python\qmd\cli\`
- Python CLI 文件:
  - `_collection.py` - 集合管理
  - `_context.py` - 上下文管理
  - `_search.py` - 搜索命令
  - `_doc.py` - 文档操作
