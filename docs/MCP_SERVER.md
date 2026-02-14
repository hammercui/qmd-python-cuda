# QMD MCP Server - Implementation Complete

## Overview

The MCP Server mode addresses the VRAM issue when multiple `qmd` processes run concurrently. Instead of each process loading its own model instance (2-4GB each), a single server process hosts the model and handles embedding requests via a queue.

## Architecture

```
┌──────────────────────────────────────────────────────┐
│  qmd CLI (multiple processes)         │
│  - qmd search "query1"     │
│  - qmd search "query2"     │
│  - qmd search "query3"     │
└───────────┬──────────────────────────────────────┘
            │ HTTP (localhost:8000)
            ↓
┌──────────────────────────────────────────────────────┐
│  MCP Server (single process)        │
│  ┌────────────────────────────────────┐   │
│  │ TextEmbedding Model (bge)   │   │
│  │ Single instance = 2-4GB VRAM         │   │
│  └────────────────────────────────────┘   │
│  ┌────────────────────────────────────┐   │
│  │ asyncio.Queue               │   │
│  │ Request queue (FIFO)                │   │
│  └────────────────────────────────────┘   │
└──────────────────────────────────────────────────────┘
```

## Installation

```bash
# Install with server dependencies
pip install -e .[server]

# Or install separately
pip install fastapi uvicorn httpx
```

## Usage

### Mode 1: Server Mode (Low VRAM < 8GB)

**Step 1: Start the MCP Server**

```bash
# Terminal 1: Start server
qmd server

# Or custom host/port
qmd server --host 0.0.0.0 --port 8000
```

**Step 2: Use CLI normally**

```bash
# Terminal 2, 3, 4: Run multiple searches
qmd search "query1"  # Uses server
qmd search "query2"  # Uses server (same model instance)
qmd search "query3"  # Uses server (same model instance)
```

**VRAM Usage**: 2-4GB (single model instance) vs 6-12GB (3 standalone processes)

### Mode 2: Standalone Mode (High VRAM ≥ 8GB)

The system automatically detects sufficient VRAM and uses standalone mode (default behavior).

```bash
# Just use CLI normally, server not needed
qmd search "query"
```

**VRAM Usage**: Each process uses 2-4GB (acceptable with sufficient VRAM)

## Mode Detection

The `LLMEngine` automatically detects the best mode:

```python
# Auto-detection logic
if VRAM < 8GB:
    mode = "server"      # Use MCP server
elif VRAM >= 8GB:
    mode = "standalone"  # Use local model
else:
    mode = "standalone"  # CPU fallback
```

### Manual Mode Selection

You can force a specific mode:

```python
# In code
from qmd.llm.engine import LLMEngine

# Force server mode
engine = LLMEngine(mode="server")

# Force standalone mode
engine = LLMEngine(mode="standalone")
```

## API Endpoints

### `POST /embed`

Generate embeddings for a list of texts.

**Request**:
```json
{
  "texts": ["text1", "text2", "text3"]
}
```

**Response**:
```json
{
  "embeddings": [
    [0.1, 0.2, ...],  // 384-dim vector for text1
    [0.3, 0.4, ...],  // 384-dim vector for text2
    [0.5, 0.6, ...]   // 384-dim vector for text3
  ]
}
```

### `GET /health`

Check server health.

**Response**:
```json
{
  "status": "healthy",
  "model_loaded": true
}
```

## Fallback Behavior

If the MCP server is unavailable:
1. Client detects connection failure
2. Automatic fallback to standalone mode
3. Model loaded locally (original behavior)
4. Warning logged

This ensures **backward compatibility** - existing workflows continue to work even if the server is down.

## Performance

| Metric | Standalone (3 processes) | MCP Server |
|--------|------------------------|-----------|
| VRAM Usage | 6-12GB | 2-4GB |
| Embedding Latency | ~50ms | ~100ms (queued) |
| Concurrent Requests | 3x model load | 1x model (queued) |

**Trade-off**: Slightly higher latency per request, but massive VRAM savings.

## Troubleshooting

### Server not starting

```bash
# Check if port is in use
netstat -an | grep 8000

# Use different port
qmd server --port 8001
```

### Client cannot connect

```bash
# Check server health
curl http://localhost:8000/health

# Check firewall (if running remotely)
# Ensure port 8000 is allowed
```

### Fallback to standalone mode

Check logs:
```
WARNING: MCP server unavailable at http://localhost:8000
WARNING: Falling back to standalone mode
```

**Solution**: Start the server or use standalone mode (sufficient VRAM).

## Development

To extend or modify the server:

```bash
# Install with dev dependencies
pip install -e .[server,dev]

# Run tests
pytest tests/test_server.py
```

## File Structure

```
qmd/
├── server/
│   ├── __init__.py      # Module exports
│   ├── app.py          # FastAPI application
│   ├── client.py        # HTTP client for CLI
│   └── models.py       # Pydantic models
├── llm/
│   └── engine.py       # Modified to support both modes
└── cli.py            # Added `qmd server` command
```

## Key Features

✅ **VRAM Optimization**: Single model instance for all CLI processes
✅ **Auto-detection**: Automatically chooses best mode based on VRAM
✅ **Fallback**: Gracefully degrades if server unavailable
✅ **Backward Compatible**: Existing workflows unchanged
✅ **Queue-based**: Prevents concurrent model access issues
✅ **Health Checks**: `/health` endpoint for monitoring
