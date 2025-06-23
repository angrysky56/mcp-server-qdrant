# Enhanced Tool Descriptions for Qdrant MCP Server

## Improved Tool Descriptions with Clear Usage Examples

DEFAULT_TOOL_STORE_DESCRIPTION = (
    "Store a single piece of information in a Qdrant collection. "
    "Usage: qdrant_store(content='Your text here', collection_name='my_collection', "
    "metadata='{\"key\": \"value\"}', entry_id='optional-custom-id'). "
    "The metadata must be a JSON string. Returns success/failure message."
)

DEFAULT_TOOL_FIND_DESCRIPTION = (
    "Search for information in a Qdrant collection using semantic similarity. "
    "Usage: qdrant_find(query='search terms', collection_name='my_collection'). "
    "Returns relevant entries with their content and metadata."
)

DEFAULT_TOOL_BATCH_STORE_DESCRIPTION = (
    "Store multiple entries efficiently in one operation. "
    "Usage: qdrant_store_batch(entries=[{\"content\": \"text1\", \"metadata\": {\"key\": \"val1\"}}, "
    "{\"content\": \"text2\", \"metadata\": {\"key\": \"val2\"}}], collection_name='my_collection'). "
    "Each entry is a dict with 'content' (required), 'metadata' (optional dict), and 'id' (optional string). "
    "No limit on batch size for storage - processes all entries provided."
)

DEFAULT_TOOL_LIST_COLLECTIONS_DESCRIPTION = (
    "List all Qdrant collections in the database. "
    "Usage: list_collections(). Returns list of collection names."
)

DEFAULT_TOOL_CREATE_COLLECTION_DESCRIPTION = (
    "Create a new Qdrant collection with specified vector size and embedding model. "
    "Usage: create_collection(collection_name='my_collection', vector_size=768, "
    "distance='cosine', embedding_model='sentence-transformers/all-mpnet-base-v2'). "
    "Common vector sizes: 384 (MiniLM), 768 (MPNet/BGE-base), 1024 (BGE-large). "
    "Model name should NOT include provider suffix like '(fastembed)'."
)

DEFAULT_TOOL_GET_COLLECTION_INFO_DESCRIPTION = (
    "Get detailed information about a collection including size, vector config, and embedding model. "
    "Usage: get_collection_info(collection_name='my_collection'). "
    "Returns points count, vector size, distance metric, and assigned embedding model."
)

DEFAULT_TOOL_DELETE_COLLECTION_DESCRIPTION = (
    "Permanently delete a collection and all its data. "
    "Usage: delete_collection(collection_name='my_collection', confirm=True). "
    "Requires confirm=True to prevent accidental deletion."
)

DEFAULT_TOOL_HYBRID_SEARCH_DESCRIPTION = (
    "Advanced search with similarity scores and filtering options. "
    "Usage: hybrid_search(query='search terms', collection_name='my_collection', "
    "limit=10, min_score=0.7, include_scores=True). "
    "Returns entries with similarity scores for ranking results."
)

DEFAULT_TOOL_SET_COLLECTION_EMBEDDING_MODEL_DESCRIPTION = (
    "Assign a specific embedding model to a collection. "
    "Usage: set_collection_embedding_model(collection_name='my_collection', "
    "model_name='sentence-transformers/all-mpnet-base-v2'). "
    "Model name should be exact as shown in list_embedding_models, WITHOUT provider suffix. "
    "Collection vector size must match model output size."
)

DEFAULT_TOOL_LIST_EMBEDDING_MODELS_DESCRIPTION = (
    "List all available embedding models with their specifications. "
    "Usage: list_embedding_models(). "
    "Returns model names, vector sizes, and descriptions. "
    "When using a model name in other tools, use ONLY the model name without '(fastembed)' suffix."
)

DEFAULT_TOOL_SCROLL_DESCRIPTION = (
    "Browse collection contents with pagination. "
    "Usage: scroll_collection(collection_name='my_collection', limit=20, offset='point_id'). "
    "Returns entries and next offset for pagination."
)
