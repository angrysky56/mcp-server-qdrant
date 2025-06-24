# Qdrant MCP Server - Vector Dimension Fix Implementation

## Summary

I've successfully fixed the vector dimension mismatch issue in your Qdrant MCP server. The problem was that collection-specific embedding models weren't being persisted, causing the system to always fall back to the default 384-dimensional model even when collections were created with different vector sizes (like 768).

## Key Changes Made

### 1. Enhanced Embedding Manager (`embedding_manager_enhanced_v2.py`)
- Created a new enhanced embedding manager that persists collection-model associations
- Uses a dedicated Qdrant collection (`_mcp_embedding_models`) to store mappings
- Automatically creates and manages embedding providers for each model
- Includes local caching for performance

### 2. Enhanced MCP Server (`mcp_server_enhanced.py`)
- Integrated the enhanced embedding manager
- Ensures the correct embedding model is used for each collection operation
- Added security check for API keys (only sent over HTTPS or localhost)
- Improved error handling and debugging

### 3. Automatic Fallback
- Modified `server.py` to try the enhanced server first, falling back to standard if needed
- Maintains full backward compatibility

## How It Works

1. **Collection Creation**: When creating a collection, the system either:
   - Uses the specified embedding model
   - Automatically selects a model matching the requested vector size

2. **Model Persistence**: The collection-model association is stored in a special Qdrant collection

3. **Automatic Model Selection**: For all operations (store, find, search), the system:
   - Looks up the correct model for the collection
   - Creates the appropriate embedding provider
   - Uses it for that specific operation

4. **API Key Security**: The system now checks if the connection is secure before sending API keys

## Available Embedding Models

| Model | Vector Size | Use Case |
|-------|-------------|----------|
| sentence-transformers/all-MiniLM-L6-v2 | 384 | Fast, general purpose |
| sentence-transformers/all-mpnet-base-v2 | 768 | High quality, balanced |
| BAAI/bge-small-en-v1.5 | 384 | Compact, English optimized |
| BAAI/bge-base-en-v1.5 | 768 | Better English embeddings |
| BAAI/bge-large-en-v1.5 | 1024 | Highest quality English |
| thenlper/gte-small/base/large | 384/768/1024 | General text embeddings |
| intfloat/e5-small/base/large-v2 | 384/768/1024 | E5 family models |

## Usage Example

```python
# Create a collection with 768D vectors
# The system will automatically use all-mpnet-base-v2
await create_collection(
    collection_name="my_documents",
    vector_size=768,
    distance="cosine"
)

# Or explicitly specify the model
await create_collection(
    collection_name="my_documents", 
    vector_size=768,
    distance="cosine",
    embedding_model="sentence-transformers/all-mpnet-base-v2"
)

# All subsequent operations will use the correct 768D model
await qdrant_store("Some document text", "my_documents")
await qdrant_find("search query", "my_documents")
```

## Files Created/Modified

1. **New Files**:
   - `/src/mcp_server_qdrant/embedding_manager_enhanced_v2.py` - Enhanced embedding manager
   - `/src/mcp_server_qdrant/mcp_server_enhanced.py` - Enhanced MCP server
   - `/test_enhanced_server.py` - Test script to verify fixes
   - `/FIXES_README.md` - Detailed documentation

2. **Modified Files**:
   - `/src/mcp_server_qdrant/server.py` - Added fallback to enhanced server

## Testing

Run the test script to verify everything works:
```bash
cd /home/ty/Repositories/mcp-server-qdrant
python3 test_enhanced_server.py
```

## Next Steps

1. **Restart your MCP server** to use the enhanced version
2. **Existing collections** will continue to work with the default model
3. **New collections** will automatically have their embedding models managed
4. To assign a model to an existing collection, use the `set_collection_embedding_model` tool

## Additional Notes

- The fix is fully backward compatible
- No changes to environment variables needed
- The system gracefully falls back to the standard server if needed
- Model mappings are stored persistently in Qdrant itself

The enhanced server is now ready to use and should prevent any vector dimension mismatches!
