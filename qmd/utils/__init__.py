"""
文档分块工具，对齐 TypeScript 的 chunkDocument 实现。

按段落/句子/换行/空格边界切分，支持 overlap。
适用于 jina-embeddings-v2-base-zh 长文档处理（8192 tokens）。
"""

from typing import List, Dict
import struct

# Chunking 参数（与 TS 对齐）
# TS: CHUNK_SIZE_TOKENS = 800, CHUNK_OVERLAP_TOKENS = 120
# Python: 按字符近似（无 tokenizer 时）
CHUNK_SIZE_CHARS = 3200  # ~800 tokens * 4 chars/token
CHUNK_OVERLAP_CHARS = 480  # ~120 tokens * 4 chars/token


def chunk_document(
    content: str,
    max_chars: int = CHUNK_SIZE_CHARS,
    overlap_chars: int = CHUNK_OVERLAP_CHARS,
) -> List[Dict]:
    """
    将文档切分为多个 chunk，返回 [{text, pos, seq}]。

    切分策略（优先级）：
    1. 段落分隔（`\n\n`）
    2. 句子结尾（`. `、`.\n`、`? `、`! `）
    3. 换行（`\n`）
    4. 空格（` `）

    Args:
        content: 原始文本
        max_chars: 每个 chunk 最大字符数（默认 3200，约 800 tokens）
        overlap_chars: 相邻 chunk 的重叠字符数（默认 480，约 120 tokens）

    Returns:
        List of {"text": str, "pos": int, "seq": int}
    """
    if len(content) <= max_chars:
        return [{"text": content, "pos": 0, "seq": 0}]

    chunks = []
    char_pos = 0
    seq = 0

    while char_pos < len(content):
        end_pos = min(char_pos + max_chars, len(content))

        if end_pos < len(content):
            # 在最后 30% 范围内寻找合适的断点
            search_start = int((end_pos - char_pos) * 0.7) + char_pos
            search_slice = content[search_start:end_pos]

            break_offset = -1

            # 优先级：段落 > 句子 > 换行 > 空格
            para_break = search_slice.rfind("\n\n")
            if para_break >= 0:
                break_offset = search_start + para_break + 2
            else:
                # 句子结尾：`. `、`.\n`、`? `、`?\n`、`! `、`!\n`
                sent_end = max(
                    search_slice.rfind(". "),
                    search_slice.rfind(".\n"),
                    search_slice.rfind("? "),
                    search_slice.rfind("?\n"),
                    search_slice.rfind("! "),
                    search_slice.rfind("!\n"),
                )
                if sent_end >= 0:
                    break_offset = search_start + sent_end + 2
                else:
                    line_break = search_slice.rfind("\n")
                    if line_break >= 0:
                        break_offset = search_start + line_break + 1
                    else:
                        space = search_slice.rfind(" ")
                        if space >= 0:
                            break_offset = search_start + space + 1

            if break_offset > char_pos:
                end_pos = break_offset

        chunk_text = content[char_pos:end_pos]
        chunks.append({"text": chunk_text, "pos": char_pos, "seq": seq})
        seq += 1
        char_pos = max(char_pos + 1, end_pos - overlap_chars)

    return chunks


def embedding_to_bytes(embedding: List[float]) -> bytes:
    """
    将 float 列表转换为 sqlite-vec 所需的 bytes 格式（float32 LE）。

    Args:
        embedding: float 列表（通常是 1024 维）

    Returns:
        bytes: packed float32 in little-endian format

    Example:
        >>> emb = [0.1, 0.2, 0.3]
        >>> embedding_to_bytes(emb)
        b'\\xcd\\xcc\\xcc=\\xcd\\xcc\\xcc>\\x9a\\x99\\x99?'
    """
    return struct.pack(f"{len(embedding)}f", *embedding)
