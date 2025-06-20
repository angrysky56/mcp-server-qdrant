# Configuration Guide

## Quick Start Configurations

This directory contains example configurations for Claude Desktop to use with the enhanced mcp-server-qdrant.

### 1. Enhanced Mode (Recommended)
**File:** `enhanced_claude_config.json`

- **Multi-collection support** - No default collection, create collections as needed
- **All enhanced features enabled** - Collection management, dynamic embedding models, resources
- **Clean slate** - Perfect for new setups

### 2. Migration Mode (Upgrade Existing Setup)
**File:** `migration_claude_config.json`

- **Maintains existing collection** - Keeps your `claudes_chroma_collection` as default
- **All enhanced features enabled** - Adds new capabilities while preserving data
- **Backward compatible** - Your existing memories remain accessible

## How to Update Your Configuration

1. **Backup your current config:**
   ```bash
   cp ~/.config/Claude/claude_desktop_config.json ~/.config/Claude/claude_desktop_config.json.backup
   ```

2. **Choose your approach:**
   - **New setup:** Copy `enhanced_claude_config.json`
   - **Existing setup:** Copy `migration_claude_config.json`

3. **Update the path:** Change the directory path to match your local fork:
   ```json
   "/home/ty/Repositories/mcp-server-qdrant/src"
   ```

4. **Restart Claude Desktop** to load the new configuration

## Key Configuration Differences

### Original Config (Limited)
```json
{
  "mcp-server-qdrant": {
    "command": "uv",
    "args": ["--directory", "/path/to/src", "run", "mcp-server-qdrant"],
    "env": {
      "QDRANT_URL": "http://localhost:6333",
      "COLLECTION_NAME": "claudes_chroma_collection",
      "EMBEDDING_MODEL": "sentence-transformers/all-MiniLM-L6-v2"
    }
  }
}
```
**Tools:** 2 (store, find)
**Collections:** 1 hardcoded
**Features:** Basic storage only

### Enhanced Config (Full Power)
```json
{
  "mcp-server-qdrant-enhanced": {
    "command": "uv", 
    "args": ["--directory", "/path/to/src", "run", "mcp-server-qdrant"],
    "env": {
      "QDRANT_URL": "http://localhost:6333",
      "EMBEDDING_MODEL": "sentence-transformers/all-MiniLM-L6-v2",
      "QDRANT_ENABLE_COLLECTION_MANAGEMENT": "true",
      "QDRANT_ENABLE_DYNAMIC_EMBEDDING_MODELS": "true", 
      "QDRANT_ENABLE_RESOURCES": "true"
    }
  }
}
```
**Tools:** 13 (store, find, create_collection, list_collections, etc.)
**Collections:** Unlimited with dynamic creation
**Features:** Full Qdrant capabilities unlocked

## Testing Your Configuration

After updating your config:

1. **Check Claude Desktop logs** for any connection errors
2. **Test basic functionality:** Ask Claude to list collections
3. **Try enhanced features:** Create a new collection, list embedding models
4. **Verify resources:** Ask Claude about collection information

## Environment Variables Reference

| Variable | Enhanced | Migration | Purpose |
|----------|----------|-----------|---------|
| `QDRANT_URL` | ✅ | ✅ | Qdrant server URL |
| `COLLECTION_NAME` | ❌ | ✅ | Default collection (optional in enhanced) |
| `QDRANT_ENABLE_COLLECTION_MANAGEMENT` | ✅ | ✅ | Enable collection tools |
| `QDRANT_ENABLE_DYNAMIC_EMBEDDING_MODELS` | ✅ | ✅ | Enable model management |
| `QDRANT_ENABLE_RESOURCES` | ✅ | ✅ | Enable MCP resources |

## Troubleshooting

**Claude says "No tools available":**
- Check the directory path in your config
- Ensure you're using the enhanced fork, not the original repo

**"Collection not found" errors:**
- In enhanced mode, create collections first with `create_collection`
- In migration mode, your existing collection should work automatically

**Performance issues:**
- Adjust `QDRANT_MAX_BATCH_SIZE` (default: 100)
- Set appropriate `QDRANT_SEARCH_LIMIT` (default: 10)
