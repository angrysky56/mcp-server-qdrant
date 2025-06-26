#!/usr/bin/env python3
"""Debug script to test 768D embedding issues"""

import asyncio
from fastembed import TextEmbedding

def test_fastembed_dimensions():
    """Test different fastembed models and their dimensions"""
    models_to_test = [
        "sentence-transformers/all-MiniLM-L6-v2",  # 384D
        "BAAI/bge-base-en-v1.5",  # 768D
        "BAAI/bge-large-en-v1.5",  # 1024D
        "jinaai/jina-embeddings-v2-base-en",  # 768D
    ]

    test_text = "This is a test sentence for embedding"

    for model_name in models_to_test:
        try:
            print(f"\nTesting model: {model_name}")

            # Create embedding model
            model = TextEmbedding(model_name)

            # Get model description
            model_desc = model._get_model_description(model_name)
            print(f"  Expected dimension: {model_desc.dim}")

            # Generate embedding
            embeddings = list(model.passage_embed([test_text]))
            actual_dim = len(embeddings[0])
            print(f"  Actual dimension: {actual_dim}")

            # Check if dimensions match
            if actual_dim != model_desc.dim:
                print(f"  ⚠️  DIMENSION MISMATCH! Expected {model_desc.dim}, got {actual_dim}")
            else:
                print("  ✓ Dimensions match")

        except Exception as e:
            print(f"  ❌ Error: {e}")


async def test_qdrant_connector():
    """Test the Qdrant connector with different models"""
    import sys
    import os
    sys.path.append('/home/ty/Repositories/mcp-server-qdrant/src')

    from mcp_server_qdrant.embeddings.factory import create_embedding_provider
    from mcp_server_qdrant.settings import EmbeddingProviderSettings
    from mcp_server_qdrant.qdrant import QdrantConnector

    test_text = "Test content for 768D collection"

    # Test with 768D model - set environment variables
    print("\n\nTesting Qdrant connector with 768D model:")

    # Set environment variables for settings
    os.environ["EMBEDDING_PROVIDER_TYPE"] = "fastembed"
    os.environ["EMBEDDING_MODEL_NAME"] = "BAAI/bge-base-en-v1.5"

    settings_768 = EmbeddingProviderSettings()

    provider_768 = create_embedding_provider(settings_768)
    print(f"Provider model: {provider_768.get_model_name()}")
    print(f"Provider vector size: {provider_768.get_vector_size()}")

    # Test embedding
    embedding = await provider_768.embed_query(test_text)
    print(f"Actual embedding dimension: {len(embedding)}")

    # Create connector
    connector = QdrantConnector(
        "http://localhost:6333",
        None,
        None,
        provider_768,
        None,
        None
    )

    # Check collection info
    try:
        info = await connector.get_detailed_collection_info("agent_ai_768")
        print("\nCollection 'agent_ai_768' info:")
        if info is not None:
            print(f"  Vector size: {info.vector_size}")
            print(f"  Points count: {info.points_count}")
        else:
            print("  Collection info not found (info is None)")
    except Exception as e:
        print(f"Error getting collection info: {e}")

    # Clean up environment variables
    os.environ.pop("EMBEDDING_PROVIDER_TYPE", None)
    os.environ.pop("EMBEDDING_MODEL_NAME", None)


if __name__ == "__main__":
    print("=== Testing FastEmbed dimensions ===")
    test_fastembed_dimensions()

    print("\n\n=== Testing Qdrant connector ===")
    asyncio.run(test_qdrant_connector())
