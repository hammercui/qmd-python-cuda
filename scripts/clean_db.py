#!/usr/bin/env python
"""
QMD 数据库清理脚本

支持以下清理级别：
  --embeddings   仅清空向量数据（content_vectors + vectors_vec），保留文档索引
  --all          删除整个数据库文件，完全重置（等同于删库重建）
  --dry-run      只显示将要执行的操作，不实际修改

用法：
    python scripts/clean_db.py --embeddings           # 清空向量，保留文档
    python scripts/clean_db.py --embeddings --dry-run # 预览操作
    python scripts/clean_db.py --all                  # 删除整个数据库
    python scripts/clean_db.py --all --db-path D:/my/custom.db

清理后需要重新生成嵌入：
    qmd embed --force
"""

import sys
import sqlite3
from pathlib import Path


# ──────────────────────────────────────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────────────────────────────────────

def _get_default_db_path() -> Path:
    """读取 qmd 配置文件获取数据库路径。"""
    try:
        from qmd.models.config import AppConfig
        config = AppConfig.load()
        return Path(config.db_path)
    except Exception:
        return Path.home() / ".qmd" / "qmd.db"


def _db_stats(db_path: Path) -> dict:
    """查询数据库统计信息。"""
    stats = {
        "documents": 0,
        "collections": 0,
        "content": 0,
        "content_vectors": 0,
        "vectors_vec": 0,
        "size_mb": 0.0,
    }

    if not db_path.exists():
        return stats

    stats["size_mb"] = db_path.stat().st_size / (1024 * 1024)

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        for table in ("documents", "collections", "content", "content_vectors"):
            try:
                row = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
                stats[table] = row["n"]
            except sqlite3.OperationalError:
                pass

        # vectors_vec 是虚拟表，直接 COUNT 可能报错
        try:
            row = conn.execute("SELECT COUNT(*) AS n FROM vectors_vec").fetchone()
            stats["vectors_vec"] = row["n"]
        except sqlite3.OperationalError:
            pass

        conn.close()
    except Exception as e:
        print(f"⚠️  读取数据库统计失败：{e}")

    return stats


def _print_stats(label: str, stats: dict) -> None:
    """打印统计信息。"""
    print(f"{label}")
    print(f"  数据库大小   : {stats['size_mb']:.1f} MB")
    print(f"  collections  : {stats['collections']}")
    print(f"  documents    : {stats['documents']}")
    print(f"  content      : {stats['content']}")
    print(f"  content_vectors : {stats['content_vectors']} (chunk 元数据)")
    print(f"  vectors_vec  : {stats['vectors_vec']} (向量数据)")


# ──────────────────────────────────────────────────────────────────────────────
# 清理操作
# ──────────────────────────────────────────────────────────────────────────────

def clean_embeddings(db_path: Path, dry_run: bool = False) -> bool:
    """
    仅清空向量数据，保留文档元数据和内容。

    清空的表：
      - content_vectors  (chunk 级向量元数据)
      - vectors_vec      (sqlite-vec 虚拟表，存储实际浮点向量)

    保留的表：
      - documents    (文档路径、hash、collection 等)
      - collections  (collection 配置)
      - content      (原始文档内容)
      - documents_fts (全文搜索索引)
    """
    if not db_path.exists():
        print(f"❌ 数据库不存在：{db_path}")
        return False

    print("=" * 60)
    print("  清空向量数据（保留文档索引）")
    print("=" * 60)
    print()

    before = _db_stats(db_path)
    _print_stats("清理前：", before)
    print()

    if before["content_vectors"] == 0 and before["vectors_vec"] == 0:
        print("✅ 向量数据本已为空，无需清理。")
        print()
        print("直接运行以下命令生成嵌入：")
        print("  qmd embed")
        return True

    print("将要执行的操作：")
    print(f"  DELETE FROM content_vectors   -- 删除 {before['content_vectors']} 行")
    print(f"  DELETE FROM vectors_vec       -- 删除 {before['vectors_vec']} 行")
    print()

    if dry_run:
        print("🔍 [dry-run] 模拟运行完成，未做任何修改。")
        return True

    # 确认
    try:
        answer = input("确认清空向量数据？[y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n取消。")
        return False

    if answer not in ("y", "yes"):
        print("取消。")
        return False

    # 执行清理
    print()
    print("正在清空...")
    try:
        conn = sqlite3.connect(str(db_path))

        conn.execute("DELETE FROM content_vectors")
        print(f"  ✅ content_vectors 已清空")

        try:
            conn.execute("DELETE FROM vectors_vec")
            print(f"  ✅ vectors_vec 已清空")
        except sqlite3.OperationalError as e:
            if "no such table" in str(e):
                print(f"  ⚠️  vectors_vec 表不存在（旧数据库），跳过")
            else:
                raise

        conn.execute("VACUUM")   # 回收空间
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ 清理失败：{e}")
        import traceback
        traceback.print_exc()
        return False

    after = _db_stats(db_path)
    print()
    _print_stats("清理后：", after)
    print()
    freed = before["size_mb"] - after["size_mb"]
    print(f"✅ 清理完成，释放约 {freed:.1f} MB 磁盘空间。")
    print()
    print("后续步骤：重新生成嵌入")
    print("  qmd embed")
    return True


def clean_all(db_path: Path, dry_run: bool = False) -> bool:
    """
    删除整个数据库文件，完全重置。

    等效操作：
      - 删除 qmd.db
      - 下次运行 qmd 命令时会自动重建 schema

    注意：collections 配置存储在 index.yml，不会被删除。
    删除后需要重新 `qmd index` 和 `qmd embed`。
    """
    print("=" * 60)
    print("  删除整个数据库（完全重置）")
    print("=" * 60)
    print()

    if not db_path.exists():
        print(f"✅ 数据库不存在，无需清理：{db_path}")
        return True

    stats = _db_stats(db_path)
    _print_stats("当前数据库：", stats)
    print()

    print(f"⚠️  将要删除：{db_path}  ({stats['size_mb']:.1f} MB)")
    print()
    print("  注意：collections 配置（index.yml）不会被删除。")
    print("  删除后需要重新运行：")
    print("    qmd index")
    print("    qmd embed")
    print()

    if dry_run:
        print("🔍 [dry-run] 模拟运行完成，未做任何修改。")
        return True

    # 确认（需要输入 yes 全拼）
    print("此操作不可撤销！请输入 'yes' 确认删除：", end=" ")
    try:
        answer = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n取消。")
        return False

    if answer != "yes":
        print("取消（需要输入完整的 'yes'）。")
        return False

    # 删除 WAL / SHM 附属文件
    for suffix in ("", "-wal", "-shm"):
        target = db_path.with_name(db_path.name + suffix)
        if target.exists():
            target.unlink()
            print(f"  🗑️  已删除 {target.name}")

    print()
    print(f"✅ 数据库已删除：{db_path}")
    print()
    print("后续步骤：")
    print("  1. 重新建立索引：")
    print("     qmd index")
    print("  2. 生成嵌入：")
    print("     qmd embed")
    return True


# ──────────────────────────────────────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="QMD 数据库清理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
清理级别说明：
  --embeddings   仅删除向量数据（content_vectors + vectors_vec），保留文档
                 → 用于切换嵌入模型或重建向量时
  --all          删除整个数据库文件，完全重置
                 → 用于彻底清理或迁移时

示例：
  # 只清空向量（最常用），保留文档元数据
  python scripts/clean_db.py --embeddings

  # 预览将要做什么（不实际修改）
  python scripts/clean_db.py --embeddings --dry-run

  # 完全重置数据库
  python scripts/clean_db.py --all

  # 指定数据库路径
  python scripts/clean_db.py --embeddings --db-path D:/mydata/qmd.db
        """,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--embeddings",
        action="store_true",
        help="清空向量数据（content_vectors + vectors_vec），保留文档索引",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="删除整个数据库文件，完全重置（不可撤销）",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只显示将要执行的操作，不实际修改数据库",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help=f"指定数据库路径（默认：从 qmd 配置读取）",
    )

    args = parser.parse_args()

    # 确定数据库路径
    if args.db_path:
        db_path = Path(args.db_path)
    else:
        db_path = _get_default_db_path()
        print(f"数据库路径：{db_path}")
        print()

    # 执行清理
    if args.embeddings:
        success = clean_embeddings(db_path, dry_run=args.dry_run)
    else:  # --all
        success = clean_all(db_path, dry_run=args.dry_run)

    sys.exit(0 if success else 1)
