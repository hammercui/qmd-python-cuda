# 模型下载失败原因分析

> **日期**: 2026-02-16
> **问题**: `python -m qmd.models.downloader` 执行时UnicodeEncodeError

---

## 问题症状

```bash
.venv\Scripts\python.exe -m qmd.models.downloader
```

**错误信息**:
```
UnicodeEncodeError: 'gbk' codec can't encode character '\u2717' in position 0: illegal multibyte sequence
```

**发生位置**: `qmd/models/downloader.py` 第240行

---

## 根本原因

### 1. Windows GBK编码限制
- Windows PowerShell默认使用GBK（代码页936）编码
- GBK不支持emoji字符（✓, ✗, ⚠, ✔, ❌等）
- Rich console在输出时会调用Windows API
- Windows API尝试将Unicode字符转换为GBK时失败

### 2. 代码中的Emoji字符

**文件**: `qmd/models/downloader.py`

| 行号 | 代码 | 字符 |
|------|------|------|
| 134 | `[green][HF] ✓ Downloaded[/green]` | ✓ (U+2713) |
| 138 | `[red][HF] ✗ Failed[/red]` | ✗ (U+2717) |
| 163 | `[green][MoT] ✓ Downloaded[/green]` | ✓ (U+2713) |
| 167 | `[red][MoT] ✗ Failed[/red]` | ✗ (U+2717) |
| 205 | `[green]✓ Model already cached[/green]` | ✓ (U+2713) |
| 240 | `[red]✗ Download failed[/red]` | ✗ (U+2717) |
| 263 | `[red]✗ Failed to download[/red]` | ✗ (U+2717) |

**问题**: Rich console尝试渲染这些字符时，Windows底层API无法将它们转换为GBK编码。

---

## 错误发生流程

```
1. python -m qmd.models.downloader
   ↓
2. 开始下载模型（成功）
   ↓
3. 尝试打印 "✗ Download failed for embedding"
   ↓
4. Rich console.render() 调用
   ↓
5. legacy_windows_render() (检测到Windows)
   ↓
6. term.write_styled(text, style)
   ↓
7. Windows WriteConsoleW() API
   ↓
8. Unicode → GBK 转换失败
   ↓
9. UnicodeEncodeError: 'gbk' codec can't encode '\u2717'
```

---

## 为什么cli.py修复有效？

我们之前修复了`qmd/cli.py`中的同样问题：

**修复前**:
```python
console.print(f"  [green]✓ CUDA[/green]")
console.print(f"  [yellow]⚠ CPU-only[/yellow]")
console.print(f"  [red]✗ Cannot detect[/red]")
```

**修复后**:
```python
console.print(f"  [green]OK CUDA[/green]")
console.print(f"  [yellow]WARN CPU-only[/yellow]")
console.print(f"  [red]X Cannot detect[/red]")
```

**结果**: `qmd check` 命令现在可以正常工作

---

## 解决方案

### 方案1: 替换Emoji字符（推荐）

将所有emoji替换为ASCII字符：

| Emoji | ASCII替代 | 说明 |
|-------|-----------|------|
| ✓ | OK | 成功 |
| ✗ | X | 失败 |
| ⚠ | WARN | 警告 |
| ✔ | OK | 成功 |
| ❌ | X | 失败 |

**修改位置**:
- `qmd/models/downloader.py` - 7处
- 需要修改的行: 134, 138, 163, 167, 205, 240, 263

### 方案2: 设置UTF-8编码（不推荐）

在Python代码中设置：
```python
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
```

**问题**: 
- 不一定能解决Rich console的底层调用
- 可能影响其他输出
- 不如直接替换字符简单

### 方案3: 使用Python 3.9+的unicode字符（已验证无效）

在PowerShell中：
```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```

**问题**: Rich console使用的是Windows API，不受这个设置影响

---

## 实施计划

### 立即修复（5分钟）

1. 编辑 `qmd/models/downloader.py`
2. 批量替换emoji字符：
   - ✓ → OK
   - ✗ → X
3. 重新测试模型下载

### 测试验证

```bash
# 1. 修复后测试
.venv\Scripts\python.exe -m qmd.models.downloader

# 2. 预期输出
Starting model download...
Cache directory: C:\Users\Administrator\.cache\qmd\models
Detected location: China - Using ModelScope
[HuggingFace] Downloading embedding...
[green][HF] OK Downloaded to C:\...\embedding[/green]
...

# 3. 验证模型已下载
.venv\Scripts\qmd.exe check
# 应该显示:
#  OK Embedding    (130MB)
#  OK Reranker     (110MB)
#  OK Expansion    (1000MB)
```

---

## 为什么不在一开始就发现？

1. **测试顺序**: 先测试了Server启动（通过）
2. **模型下载测试**: 在最后才测试
3. **编码问题**: 只在Windows GBK环境下出现
4. **Linux/macOS**: 不会有这个问题（默认UTF-8）

---

## 预防措施

### 代码规范
- **禁止使用emoji字符** 在用户可见的输出中
- 使用ASCII字符: OK, X, WARN, INFO
- 或使用文本: [成功], [失败], [警告]

### 测试清单
- ✅ Windows GBK编码环境测试
- ✅ Linux UTF-8编码环境测试
- ✅ PowerShell测试
- ✅ CMD测试

---

## 总结

**问题**: Emoji字符导致Windows GBK编码失败  
**影响**: 模型下载器无法运行  
**解决**: 批量替换emoji为ASCII字符  
**时间**: 5分钟  
**优先级**: 高（阻塞完整测试）

---

**下一步**: 执行修复，完成模型下载测试
