"""扫描obsidian todo目录"""
from pathlib import Path

todo_dir = Path('D:/syncthing/obsidian-mark/8.TODO')

print(f"扫描目录: {todo_dir}")
print(f"存在: {todo_dir.exists()}")

if todo_dir.exists():
    # 递归查找所有markdown文件
    md_files = list(todo_dir.rglob('*.md'))

    print(f"\n找到 {len(md_files)} 个markdown文件:\n")

    for f in md_files[:20]:  # 只显示前20个
        size_kb = f.stat().st_size / 1024
        print(f"  {f.relative_to(todo_dir)} ({size_kb:.1f} KB)")

    if len(md_files) > 20:
        print(f"\n  ... 还有 {len(md_files) - 20} 个文件")

    # 统计
    total_size = sum(f.stat().st_size for f in md_files)
    print(f"\n统计:")
    print(f"  文件数: {len(md_files)}")
    print(f"  总大小: {total_size / 1024:.1f} KB")
    print(f"  平均大小: {total_size / len(md_files) / 1024:.1f} KB")
else:
    print("目录不存在！")
