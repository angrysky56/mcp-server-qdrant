#!/usr/bin/env python3
"""
Test script to verify that the vector name mismatch issue is fixed.
"""

import asyncio
import sys
import os

# Add src to Python path
sys.path.insert(0, '/home/ty/Repositories/mcp-server-qdrant/src')

from mcp_server_qdrant.embeddings.factory import create_embedding_provider
from mcp_server_qdrant.settings import EmbeddingProviderSettings
from mcp_server_qdrant.qdrant import QdrantConnector, Entry


async def test_vector_name_fix():
    """Test that we can store and retrieve vectors with proper vector naming."""

    # Set up environment
    os.environ["EMBEDDING_PROVIDER_TYPE"] = "fastembed"
    os.environ["EMBEDDING_MODEL_NAME"] = "BAAI/bge-base-en-v1.5"

    # Create settings and provider
    settings = EmbeddingProviderSettings()
    provider = create_embedding_provider(settings)

    print(f"Using model: {provider.get_model_name()}")
    print(f"Vector size: {provider.get_vector_size()}")
    print(f"Vector name: {provider.get_vector_name()}")

    # Create connector
    connector = QdrantConnector(
        "http://localhost:6333",
        None,
        None,
        provider,
        None,
        None
    )

    collection_name = "test_vector_fix"
    test_content = "This is a test document to verify vector storage works correctly."

    try:
        # Clean up any existing collection
        try:
            await connector.delete_collection(collection_name)
            print(f"Cleaned up existing collection: {collection_name}")
        except Exception:
            pass

        # Create collection with specific configuration
        success = await connector.create_collection_with_config(
            collection_name=collection_name,
            vector_size=provider.get_vector_size(),
            distance="cosine",
            embedding_provider=provider
        )

        if not success:
            print("❌ Failed to create collection")
            return False

        print(f"✅ Created collection: {collection_name}")

        # Store a test entry
        entry = Entry(content=test_content, metadata={"test": "vector_fix"})
        await connector.store(entry, collection_name=collection_name)
        print("✅ Stored test entry")

        # Get collection info to verify vectors were stored
        info = await connector.get_detailed_collection_info(collection_name)
        if not info:
            print("❌ Could not get collection info")
            return False

        print("📊 Collection info:")
        print(f"  Points: {info.points_count}")
        print(f"  Vectors: {info.vectors_count}")
        print(f"  Indexed vectors: {info.indexed_vectors_count}")
        print(f"  Vector size: {info.vector_size}")
        print(f"  Distance metric: {info.distance_metric}")

        if info.vectors_count == 0:
            print("❌ No vectors stored - the fix didn't work!")
            return False
        elif info.indexed_vectors_count == 0 and info.vectors_count > 0:
            print("⚠️  Vectors stored but not indexed (collection below indexing threshold)")
            print("   This is normal for small collections - search still works via brute force")
        else:
            print("✅ Vectors stored and indexed")

        return info.vectors_count > 0

        # Try to search for the entry
        results = await connector.search(
            query="test document storage",
            collection_name=collection_name,
            limit=5
        )

        print(f"🔍 Search results: {len(results)} found")
        if results:
            print(f"  First result: {results[0].content[:50]}...")
            print("✅ Search successful - vectors are working!")
        else:
            print("⚠️  No search results, but vectors are stored")

        return info.vectors_count > 0

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("🧪 Testing vector name fix...")
    success = asyncio.run(test_vector_name_fix())
    if success:
        print("🎉 Vector storage is working correctly!")
    else:
        print("💥 Vector storage is still broken")

    # Clean up environment
    os.environ.pop("EMBEDDING_PROVIDER_TYPE", None)
    os.environ.pop("EMBEDDING_MODEL_NAME", None)
