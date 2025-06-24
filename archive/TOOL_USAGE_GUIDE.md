# Qdrant MCP Server - Tool Usage Workflow Guide

This guide explains the correct workflow for using Qdrant MCP tools to store and retrieve information.

## 🔧 Tool Usage Patterns

### 1. Creating a Collection

```python
# Step 1: Check available models
list_embedding_models()
# Returns list like: "sentence-transformers/all-mpnet-base-v2 (fastembed) - 768D"

# Step 2: Create collection with model (DO NOT include "(fastembed)")
create_collection(
    collection_name="my_documents",
    vector_size=768,
    distance="cosine",
    embedding_model="sentence-transformers/all-mpnet-base-v2"  # ✅ Correct
    # NOT: "sentence-transformers/all-mpnet-base-v2 (fastembed)" ❌ Wrong
)
```

### 2. Storing Single Entry

```python
# Store with metadata (metadata MUST be JSON string)
qdrant_store(
    content="Your text content here",
    collection_name="my_documents",
    metadata='{"source": "web", "date": "2024-05-16", "type": "article"}'
)
```

### 3. Storing Multiple Entries (Batch)

```python
# Prepare entries as list of dicts
entries = [
    {
        "content": "First document text",
        "metadata": {"source": "doc1", "page": 1}  # Dict, not string
    },
    {
        "content": "Second document text", 
        "metadata": {"source": "doc2", "page": 2}
    }
]

# Store batch - NO LIMIT on size
qdrant_store_batch(
    entries=entries,
    collection_name="my_documents"
)
```

### 4. Searching/Finding

```python
# Basic search
qdrant_find(
    query="ethical AI principles",
    collection_name="my_documents"
)

# Advanced search with scores
hybrid_search(
    query="ethical AI principles",
    collection_name="my_documents",
    limit=20,  # Get more results
    min_score=0.5,  # Filter by relevance
    include_scores=True
)
```

## ⚠️ Common Mistakes to Avoid

### ❌ Wrong Model Name Format
```python
# WRONG - includes provider type
set_collection_embedding_model(
    collection_name="my_collection",
    model_name="sentence-transformers/all-mpnet-base-v2 (fastembed)"  # ❌
)

# CORRECT - just the model name
set_collection_embedding_model(
    collection_name="my_collection", 
    model_name="sentence-transformers/all-mpnet-base-v2"  # ✅
)
```

### ❌ Wrong Metadata Format in qdrant_store
```python
# WRONG - dict instead of JSON string
qdrant_store(
    content="text",
    collection_name="col",
    metadata={"key": "value"}  # ❌ Dict not allowed
)

# CORRECT - JSON string
qdrant_store(
    content="text",
    collection_name="col",
    metadata='{"key": "value"}'  # ✅ JSON string
)
```

### ❌ Wrong Entry Format in Batch
```python
# WRONG - mixed formats
entries = [
    "Just a string",  # ❌
    {"content": "text"}  # ✅
]

# CORRECT - all entries as dicts with 'content'
entries = [
    {"content": "First text", "metadata": {"id": 1}},
    {"content": "Second text", "metadata": {"id": 2}}
]
```

## 📋 Complete Workflow Example

```python
# 1. List available collections
collections = list_collections()

# 2. Create new collection if needed
if "ethical_ai_docs" not in collections:
    create_collection(
        collection_name="ethical_ai_docs",
        vector_size=768,
        distance="cosine",
        embedding_model="sentence-transformers/all-mpnet-base-v2"
    )

# 3. Prepare data
docs = [
    {
        "content": "AI transparency means making AI decision-making processes understandable",
        "metadata": {"principle": "transparency", "source": "ethics_guide"}
    },
    {
        "content": "Fairness in AI requires eliminating bias and discrimination",
        "metadata": {"principle": "fairness", "source": "ethics_guide"}
    },
    {
        "content": "AI systems must respect user privacy and data protection laws",
        "metadata": {"principle": "privacy", "source": "ethics_guide"}
    }
]

# 4. Store all documents
result = qdrant_store_batch(
    entries=docs,
    collection_name="ethical_ai_docs"
)

# 5. Verify storage
info = get_collection_info("ethical_ai_docs")
# Should show Points: 3

# 6. Search for information
results = qdrant_find(
    query="AI fairness and bias",
    collection_name="ethical_ai_docs"
)
```

## 🚀 Key Points

1. **No Batch Limits**: The enhanced server removes artificial batch size limits
2. **Model Names**: Never include "(fastembed)" or other provider suffixes
3. **Metadata Format**: 
   - `qdrant_store`: Use JSON string
   - `qdrant_store_batch`: Use Python dicts
4. **Collection Creation**: Always specify embedding model for correct vector size
5. **Error Handling**: Check collection info after operations to verify success

## 🔍 Debugging Tips

If you get "0 entries stored":
1. Check collection exists: `get_collection_info("collection_name")`
2. Verify embedding model: Model vector size must match collection vector size
3. Check entry format: All entries need 'content' field
4. Restart MCP server if needed to load enhanced version

## 📊 Configuration

The enhanced server uses these improved defaults:
- `QDRANT_SEARCH_LIMIT`: 50 (up from 10)
- `QDRANT_MAX_BATCH_SIZE`: 10000 (effectively unlimited)
- No artificial limits on storage operations
