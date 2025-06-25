# Qdrant Configuration Guide

The MCP server now supports multiple Qdrant deployment modes to suit different needs:

## 🧠 Option 1: In-Memory Mode (Simplest)
**Best for**: Development, testing, temporary use
**Pros**: No Docker required, instant startup, no external dependencies
**Cons**: Data lost when server stops

```bash
export QDRANT_MODE=memory
python -m mcp_server_qdrant.main --transport sse
```

## 💾 Option 2: Local File Storage
**Best for**: Development with persistence, single-user scenarios
**Pros**: No Docker required, data persists, lightweight
**Cons**: No clustering, limited performance for large datasets

```bash
export QDRANT_MODE=local
python -m mcp_server_qdrant.main --transport sse
```

Data will be stored in `./qdrant_local/` directory.

## 🐳 Option 3: Auto-Managed Docker (Recommended)
**Best for**: Production-like development, full Qdrant features
**Pros**: Full Qdrant features, automatic container management, persistent data
**Cons**: Requires Docker

```bash
export QDRANT_MODE=docker
export QDRANT_AUTO_DOCKER=true
python -m mcp_server_qdrant.main --transport sse
```

This will:
- Automatically start a Qdrant container if not running
- Use `./qdrant_data/` for persistent storage
- Find available ports automatically
- Stop the container when server exits

## 🌐 Option 4: External Qdrant (Production)
**Best for**: Production environments with dedicated Qdrant instances
**Pros**: Full control, can use cloud services, clustering support
**Cons**: Requires manual Qdrant setup

```bash
export QDRANT_URL=http://your-qdrant-server:6333
# Don't set QDRANT_MODE - it will use the external URL
python -m mcp_server_qdrant.main --transport sse
```

## Environment Variables

### Core Configuration
- `QDRANT_MODE`: `memory`, `local`, `docker-auto`, or unset (for external)
- `QDRANT_URL`: URL for external Qdrant (e.g., `http://localhost:6333`)
- `QDRANT_LOCAL_PATH`: Custom path for local storage (auto-set in local mode)

### Port Management
- `FASTMCP_PORT`: Preferred port for MCP server (default: 8000)

### Qdrant Settings
- `QDRANT_API_KEY`: API key for authentication (if needed)
- `QDRANT_ENABLE_COLLECTION_MANAGEMENT`: Enable/disable collection tools (default: true)

## Quick Start Examples

### Just want to try it out quickly?
```bash
export QDRANT_MODE=memory
python -c "from src.mcp_server_qdrant.server import mcp; print('Ready!')"
```

### Want persistence without Docker?
```bash
export QDRANT_MODE=local
python -c "from src.mcp_server_qdrant.server import mcp; print('Ready!')"
```

### Want full features with auto-setup?
```bash
export QDRANT_MODE=docker
export QDRANT_AUTO_DOCKER=true
python -c "from src.mcp_server_qdrant.server import mcp; print('Ready!')"
```

## Docker Auto-Management Features

When using `QDRANT_MODE=docker` with `QDRANT_AUTO_DOCKER=true`:

1. **Smart Container Detection**: Checks if Qdrant container already exists
2. **Port Conflict Resolution**: Automatically finds available ports
3. **Data Persistence**: Mounts `./qdrant_data` for persistent storage
4. **Graceful Cleanup**: Stops container when server exits
5. **Health Checking**: Waits for Qdrant API to be ready before proceeding

## Recommendations

- **Development**: Start with `memory` mode for quick testing
- **Prototyping**: Use `local` mode when you need persistence
- **Production-like**: Use `docker-auto` for full features with ease
- **Production**: Use external Qdrant with proper infrastructure

## Troubleshooting

### Container won't start
```bash
# Check if Docker is running
docker --version

# Check for port conflicts
docker ps

# Manual cleanup if needed
docker stop mcp-qdrant-auto
docker rm mcp-qdrant-auto
```

### Port conflicts
The server automatically finds available ports, but you can override:
```bash
export FASTMCP_PORT=8001  # Use different port
```

### Reset local data
```bash
# For local mode
rm -rf ./qdrant_local

# For docker-auto mode
rm -rf ./qdrant_data
```
