# 配置文件使用指南

## 配置文件位置

QMD-Python的配置文件存储在：

- **Windows**: `C:\Users\你的用户名\.qmd\index.yml`
- **Linux/macOS**: `~/.qmd/index.yml`

配置文件在首次运行时自动创建。

## 配置选项

### 基本配置

```yaml
# 数据库文件路径（可选，默认：~/.qmd/qmd.db）
db_path: "custom/path/to/qmd.db"

# 文档集合列表
collections:
  - name: "my-docs"
    path: "/path/to/documents"
    glob_pattern: "**/*.md"
```

### 模型下载源配置（重要）

```yaml
# 模型下载源选择
# 可选值：
#   - "auto": 自动检测地理位置（默认）
#              国内→ModelScope，海外→HuggingFace
#   - "huggingface": 强制使用HuggingFace
#   - "modelscope": 强制使用ModelScope
model_source: "auto"
```

## 完整配置示例

### 示例1：默认配置（推荐）

```yaml
# ~/.qmd/index.yml

# 数据库路径（可选）
db_path: "~/.qmd/qmd.db"

# 模型下载源（默认自动检测）
# 国内自动使用魔搭，海外使用HuggingFace
model_source: "auto"

# 文档集合
collections:
  - name: "personal-notes"
    path: "~/Documents/Notes"
    glob_pattern: "**/*.md"

  - name: "work-docs"
    path: "~/Work/Documents"
    glob_pattern: "**/*.md"
```

### 示例2：国内用户强制使用魔搭

```yaml
# ~/.qmd/index.yml

model_source: "modelscope"  # 强制使用魔搭社区

collections:
  - name: "docs"
    path: "~/docs"
    glob_pattern: "**/*.md"
```

### 示例3：海外用户使用HuggingFace

```yaml
# ~/.qmd/index.yml

model_source: "huggingface"  # 强制使用HuggingFace

collections:
  - name: "docs"
    path: "~/docs"
    glob_pattern: "**/*.md"
```

### 示例4：多项目配置

```yaml
# ~/.qmd/index.yml

db_path: "~/.qmd/projects.db"
model_source: "auto"

collections:
  # 个人笔记
  - name: "notes"
    path: "~/Sync/Notes"
    glob_pattern: "**/*.md"

  # 工作文档
  - name: "work"
    path: "~/Documents/Work"
    glob_pattern: "**/*.md"

  # 书籍收藏
  - name: "books"
    path: "~/Books"
    glob_pattern: "**/*.md"
```

## 配置命令

### 查看当前配置

```bash
qmd config show
```

输出示例：
```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
│           Configuration            │
├━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
│ Key          │ Value                   │
├━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
│ db_path      │ C:\Users\...\.qmd\qmd.db │
│ Collections  │ 3                       │
└──────────────┴───────────────────────────┘
```

### 修改配置选项

```bash
# 设置数据库路径
qmd config set db_path "custom/path/to/qmd.db"

# 注意：目前只支持设置db_path
# collection管理使用专用命令：
qmd collection add <path> --name <名称>
```

## 模型下载源详解

### `model_source` 选项说明

#### 1. `auto`（推荐，默认）

**工作原理**：
1. 检查系统时区
   - `Asia/Shanghai` → 中国
   - `Asia/Beijing` → 中国
   - `Asia/Chongqing` → 中国
2. 回退到IP检测
   - 访问 `ip-api.com` 检测国家代码
   - `CN` → 中国
3. 判定：
   - **中国** → 使用 ModelScope（魔搭社区）
   - **海外** → 使用 HuggingFace

**适用场景**：
- ✅ 国内用户（自动使用魔搭，下载更快）
- ✅ 海外用户（自动使用HF）
- ✅ 经常跨国移动的笔记本

#### 2. `modelscope`（魔搭社区）

**特点**：
- 国内访问速度极快
- 服务器位于中国大陆
- 无需翻墙

**适用场景**：
- 🇨🇳 国内用户
- 🇨🇳 访问不稳定时
- 🚀 希望最快下载速度

#### 3. `huggingface`

**特点**：
- 全球最大模型社区
- 模型更新最快
- 海外访问速度极快

**适用场景**：
- 🌍 海外用户
- 🌍 有稳定翻墙环境
- 🌍 需要最新模型版本

## 检测当前配置

### 检查系统状态

```bash
qmd check
```

输出示例：
```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
│            System Status Check          │
└────────────────────────────────────────┘

Dependencies:
  ✓ torch: v2.0.0
  ✓ transformers: v4.30.0
  ✓ fastembed: Installed

Device:
  ✓ CUDA: NVIDIA GeForce RTX 1660 Ti
  CUDA Version: 12.1

Models:
  ✓ Embedding    (130MB)
  ✓ Reranker    (110MB)
  ✗ Expansion  (1000MB)

Recommendations:
  [yellow]Run:[/yellow] qmd check --download
```

### 自动下载缺失模型

```bash
qmd check --download
```

会自动根据`model_source`配置选择下载源。

## Collection管理

### 添加文档集合

```bash
qmd collection add /path/to/docs --name mydocs
```

### 列出所有集合

```bash
qmd collection list
```

### 删除集合

```bash
qmd collection remove mydocs
```

### 重命名集合

```bash
qmd collection rename old-name new-name
```

## 常见问题

### Q: 配置文件不存在怎么办？

**A**: 首次运行时自动创建默认配置：

```yaml
db_path: "~/.qmd/qmd.db"
collections: []
model_source: "auto"
```

### Q: 如何切换模型下载源？

**A**: 编辑`~/.qmd/index.yml`：

```bash
# Windows
notepad ~/.qmd/index.yml

# Linux/macOS
nano ~/.qmd/index.yml
# 或
vim ~/.qmd/index.yml
```

修改`model_source`值。

### Q: 国内推荐使用哪个源？

**A**: 推荐保持默认`auto`，或明确设置为`modelsource`：

```yaml
model_source: "modelscope"  # 国内更快
```

### Q: 如何验证配置生效？

**A**:
```bash
# 查看配置
qmd config show

# 检查系统
qmd check
```

### Q: 多个项目如何管理？

**A**: 使用多个配置文件：

```bash
# 项目1
cd /project1
qmd collection add . --name project1

# 项目2
cd /project2
qmd collection add . --name project2
```

配置文件会记录所有集合。

## 高级配置

### 自定义缓存目录

模型默认缓存在`~/.cache/qmd/models/`，可通过环境变量自定义：

```bash
# Windows
set QMD_CACHE_DIR=D:\Models\QMD

# Linux/macOS
export QMD_CACHE_DIR=/path/to/models
```

### 禁用自动下载

如果只想手动下载模型：

```yaml
# ~/.qmd/index.yml
model_source: "none"  # 禁用自动下载
```

然后使用手动下载：

```bash
python -m qmd.models.downloader
```

## 相关文档

- [技术栈分析](TECH_STACK_ANALYSIS.md) - CPU/GPU依赖说明
- [兼容性分析](COMPATIBILITY_ANALYSIS.md) - 模型更换影响
- [模型清单](MODEL_INVENTORY.md) - 完整模型规格

## 更新日志

- **2025-02-14**: 添加`model_source`配置选项
- **2025-02-14**: 添加地理位置自动检测
- **2025-02-14**: 初始版本
