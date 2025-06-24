# Enhanced Qdrant MCP Server - Fixes Documentation

## Overview of Issues Fixed

### 1. Vector Dimension Mismatch (Primary Issue)
**Problem**: When creating a collection with a specific vector size (e.g., 768), the system would still use the default embedding model (384 dimensions), causing a dimension mismatch error.

**Root Cause**: The association between collections and their embedding models was not persisted, causing the system to always fall back to the default model.

**Solution**: 
- Embedding model associations are now stored in Qdrant collection metadata
- Each collection remembers its configured embedding model
- The correct model is automatically used for all operations on that collection

### 2. API Key Security
**Problem**: API keys could be sent over insecure HTTP connections, triggering security warnings.

**Solution**: 
- API keys are only sent over HTTPS connections or to localhost
- Insecure connections are detected and API keys are withheld
- Clear warning messages inform users about security considerations

## Technical Details

### Enhanced Components

1. **EnhancedEmbeddingModelManager** (`embedding_manager_enhanced.py`)
   - Persists embedding model associations in collection metadata
   - Automatically retrieves the correct model for each collection
   - Provides model discovery based on vector size
   - Caches embedding providers for performance

2. **EnhancedQdrantMCPServer** (`mcp_server_enhanced.py`)
   - Uses the enhanced embedding manager
   - Ensures correct embedding models are used for all operations
   - Implements secure API key handling
   - Provides better error messages and debugging

### Key Changes

1. **Metadata Storage**: Embedding model information is stored in collection metadata under the key `_mcp_embedding_model`

2. **Automatic Model Selection**: When creating a collection, if no model is specified, the system automatically selects one matching the requested vector size

3. **Model Validation**: The system validates that embedding models match collection vector sizes

4. **Persistent Configuration**: Model associations survive server restarts

## Usage

### Creating a Collection with Specific Embeddings

```python
# The system will automatically use a 768D model
await create_collection(
    collection_name="my_collection",
    vector_size=768,
    distance="cosine"
)

# Or explicitly specify the model
await create_collection(
    collection_name="my_collection",
    vector_size=768,
    distance="cosine",
    embedding_model="sentence-transformers/all-mpnet-base-v2"
)
```

### Available Embedding Models

| Model | Vector Size | Description |
|-------|-------------|-------------|
| sentence-transformers/all-MiniLM-L6-v2 | 384 | Lightweight, fast model good for general use |
| sentence-transformers/all-mpnet-base-v2 | 768 | High quality, balanced performance |
| BAAI/bge-small-en-v1.5 | 384 | Compact model optimized for English |
| BAAI/bge-base-en-v1.5 | 768 | Better quality English embeddings |
| BAAI/bge-large-en-v1.5 | 1024 | Highest quality English embeddings |
| thenlper/gte-small | 384 | General text embeddings, small variant |
| thenlper/gte-base | 768 | General text embeddings, base variant |
| thenlper/gte-large | 1024 | General text embeddings, large variant |

## Configuration

### Environment Variables

No changes to environment variables are needed. The enhanced server uses the same configuration as before.

### Secure Connection Setup

For production use with API keys:
```bash
# Secure (API key will be used)
QDRANT_URL="https://your-instance.qdrant.io:6333"
QDRANT_API_KEY="your-api-key"

# Local development (API key will be used)
QDRANT_URL="http://localhost:6333"
QDRANT_API_KEY="your-api-key"

# Insecure (API key will NOT be sent)
QDRANT_URL="http://remote-server.com:6333"
QDRANT_API_KEY="your-api-key"  # Will trigger warning
```

## Migration Guide

### For Existing Collections

Existing collections will continue to work with the default embedding model. To assign a specific model:

1. Use the `set_collection_embedding_model` tool
2. Ensure the model's vector size matches the collection's vector size

### Backward Compatibility

The enhanced server maintains full backward compatibility:
- Falls back to standard server if enhanced components aren't available
- Existing collections work without modification
- All existing tools and APIs remain unchanged

## Testing

Run the test script to verify the fixes:

```bash
python test_enhanced_server.py
```

This will:
1. Create a test collection with 768D vectors
2. Verify embedding model metadata is stored
3. Confirm the fixes are working correctly

## Troubleshooting

### Vector Dimension Errors

If you still see dimension errors:
1. Check the collection info to see its vector size
2. Verify an appropriate embedding model is set
3. Use `list_embedding_models` to find compatible models

### API Key Warnings

If you see API key security warnings:
1. Use HTTPS for remote connections
2. Or use the server locally
3. Or remove the API key for insecure connections

## Future Enhancements

Potential improvements for consideration:
1. Support for custom embedding models
2. Automatic model migration tools
3. Model performance benchmarking
4. Multi-vector support per collection
