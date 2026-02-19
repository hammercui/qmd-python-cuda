"""Embed worker for server-side embedding jobs."""

import asyncio
import json as json_lib
import logging
from typing import TYPE_CHECKING

from qmd.server._state import (
    embed_job,
    srv_console,
    GPU_EMBED_BATCH_SIZE,
)
import qmd.server._state as _state

if TYPE_CHECKING:
    from qmd.server._state import EmbedJobState

logger = logging.getLogger(__name__)


async def embed_worker() -> None:
    """Run the full embed pipeline server-side and broadcast SSE progress events.

    Reads documents from the DB, chunks them, runs GPU embedding, writes vectors
    back to the DB, and broadcasts incremental progress to all subscribed SSE
    clients via asyncio.Queue.  Runs as a background asyncio.Task.
    """
    from datetime import datetime

    async def broadcast(event: dict) -> None:
        data = json_lib.dumps(event)
        for q in list(embed_job._queues):
            try:
                await q.put(data)
            except Exception:
                pass

    loop = asyncio.get_running_loop()

    try:
        from qmd.database.manager import DatabaseManager
        from qmd.utils.chunker import chunk_document, embedding_to_bytes

        db = DatabaseManager(_state.config.db_path)
        db.ensure_vec_table(dimensions=768)

        docs = db.get_all_active_documents()
        if embed_job.collection:
            docs = [d for d in docs if d["collection"] == embed_job.collection]

        if embed_job.force:
            db.clear_all_embeddings()
            needs_embed_set = {d["hash"] for d in docs}
        else:
            needs_embed_set = set(db.get_hashes_for_embedding())

        to_embed = [d for d in docs if d["hash"] in needs_embed_set]

        # Pre-chunk to get accurate total_chunks for progress bar
        all_chunks: list = []
        for doc in to_embed:
            for chunk in chunk_document(doc["content"]):
                all_chunks.append(
                    {
                        "hash": doc["hash"],
                        "seq": chunk["seq"],
                        "pos": chunk["pos"],
                        "text": chunk["text"],
                    }
                )

        embed_job.total_docs = len(to_embed)
        embed_job.total_chunks = len(all_chunks)

        if not all_chunks:
            srv_console.print(
                f"[green]✓ Embed:[/green] all {len(docs)} docs already embedded"
            )
            await broadcast(
                {
                    "status": "complete",
                    "done_chunks": 0,
                    "total_chunks": 0,
                    "done_docs": 0,
                    "total_docs": len(docs),
                }
            )
            return

        col_label = f" [{embed_job.collection}]" if embed_job.collection else ""
        srv_console.print(
            f"[cyan]▶ Embed{col_label}:[/cyan]"
            f" {len(to_embed)} docs, {len(all_chunks)} chunks"
        )

        await broadcast(
            {
                "status": "running",
                "done_chunks": 0,
                "total_chunks": embed_job.total_chunks,
                "done_docs": 0,
                "total_docs": embed_job.total_docs,
            }
        )

        done_hashes: set = set()
        now = datetime.now().isoformat()
        last_report_pct: int = -1  # track last reported 5%-milestone
        t0 = asyncio.get_event_loop().time()

        for i in range(0, len(all_chunks), GPU_EMBED_BATCH_SIZE):
            batch = all_chunks[i : i + GPU_EMBED_BATCH_SIZE]
            texts = [c["text"] for c in batch]

            # Run model inference in thread-pool executor to avoid blocking
            # the uvicorn event loop while the GPU is busy.
            raw_embeddings = await loop.run_in_executor(
                None,
                lambda t=texts: list(_state.model.embed(t)),
            )

            for chunk, emb in zip(batch, raw_embeddings):
                db.insert_embedding(
                    doc_hash=chunk["hash"],
                    seq=chunk["seq"],
                    pos=chunk["pos"],
                    embedding=embedding_to_bytes(emb.tolist()),
                    model="jinaai/jina-embeddings-v2-base-zh-q4f16",
                    embedded_at=now,
                )
                done_hashes.add(chunk["hash"])

            embed_job.done_chunks += len(batch)
            embed_job.done_docs = len(done_hashes)

            # Print server-side progress every 5% milestone
            total = embed_job.total_chunks
            pct = int(embed_job.done_chunks * 100 / total) if total else 100
            milestone = (pct // 5) * 5
            if milestone > last_report_pct:
                last_report_pct = milestone
                elapsed = asyncio.get_event_loop().time() - t0
                rate = embed_job.done_chunks / elapsed if elapsed > 0 else 0
                eta = int((total - embed_job.done_chunks) / rate) if rate > 0 else 0
                bar_filled = milestone // 5  # 0-20 blocks
                bar = "█" * bar_filled + "░" * (20 - bar_filled)
                eta_str = f"  ETA {eta}s" if eta > 0 else ""
                srv_console.print(
                    f"  [dim]{bar}[/dim] {pct:3d}%"
                    f"  {embed_job.done_chunks}/{total} chunks"
                    f"  {embed_job.done_docs}/{embed_job.total_docs} docs"
                    f"{eta_str}"
                )

            await broadcast(
                {
                    "status": "running",
                    "done_chunks": embed_job.done_chunks,
                    "total_chunks": embed_job.total_chunks,
                    "done_docs": embed_job.done_docs,
                    "total_docs": embed_job.total_docs,
                }
            )

        elapsed_total = asyncio.get_event_loop().time() - t0
        srv_console.print(
            f"[bold green]✓ Embed complete:[/bold green]"
            f" {embed_job.done_chunks} chunks, {embed_job.done_docs} docs"
            f"  ({elapsed_total:.1f}s)"
        )
        await broadcast(
            {
                "status": "complete",
                "done_chunks": embed_job.done_chunks,
                "total_chunks": embed_job.total_chunks,
                "done_docs": embed_job.done_docs,
                "total_docs": embed_job.total_docs,
            }
        )

    except Exception as exc:
        logger.error("Embed worker error: %s", exc, exc_info=True)
        srv_console.print(f"[red]✗ Embed error:[/red] {exc}")
        embed_job.error = str(exc)
        await broadcast({"status": "error", "error": str(exc)})

    finally:
        embed_job.running = False
        embed_job.finished = True
        # Send sentinel so all SSE generators terminate cleanly
        for q in list(embed_job._queues):
            await q.put(None)
        embed_job._queues.clear()
