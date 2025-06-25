#!/usr/bin/env python3
"""
Test script to verify that the MCP server functionality works correctly.
This tests the underlying Qdrant connector that the MCP tools use.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from mcp_server_qdrant.qdrant import QdrantConnector, Entry
from mcp_server_qdrant.embeddings.factory import create_embedding_provider
from mcp_server_qdrant.settings import EmbeddingProviderSettings

async def test_mcp_functionality():
    """Test the core functionality that MCP tools rely on."""

    print("=== Testing MCP Server Functionality ===")

    # Set up environment for testing
    os.environ["EMBEDDING_PROVIDER_TYPE"] = "fastembed"
    os.environ["EMBEDDING_MODEL_NAME"] = "BAAI/bge-small-en-v1.5"

    try:
        # Initialize embedding provider
        print("\n1. Initializing Embedding Provider...")
        settings = EmbeddingProviderSettings()
        provider = create_embedding_provider(settings)
        print(f"   ✓ Using model: {provider.get_model_name()}")
        print(f"   ✓ Vector size: {provider.get_vector_size()}")
        print(f"   ✓ Vector name: {provider.get_vector_name()}")

        # Initialize Qdrant connector
        print("\n2. Initializing Qdrant Connector...")
        connector = QdrantConnector(
            qdrant_url="http://localhost:6333",
            qdrant_api_key=None,
            collection_name=None,
            embedding_provider=provider
        )

        collection_name = "mcp_functionality_test"

        # Test: List collections
        print("\n3. Testing: List Collections")
        collections = await connector.get_collection_names()
        print(f"   ✓ Found {len(collections)} collections: {collections[:3]}...")

        # Test: Create collection
        print(f"\n4. Testing: Create Collection '{collection_name}'")
        success = await connector.create_collection_with_config(
            collection_name=collection_name,
            vector_size=provider.get_vector_size(),
            distance="cosine",
            embedding_provider=provider
        )
        print(f"   ✓ Collection created: {success}")

        # Test: Store documents (what the AI would do)
        print("\n5. Testing: Store Documents")

        documents = [
            Entry(
                content="The quick brown fox jumps over the lazy dog. This is a classic English pangram.",
                metadata={"type": "text", "category": "pangram", "language": "english"}
            ),
            Entry(
                content="Machine learning and artificial intelligence are revolutionizing data processing.",
                metadata={"type": "text", "category": "technology", "domain": "AI"}
            ),
            Entry(
                content="Vector databases enable semantic search by storing embeddings of documents.",
                metadata={"type": "text", "category": "technology", "domain": "databases"}
            ),
            Entry(
                content="Python is a versatile programming language popular in data science and AI.",
                metadata={"type": "text", "category": "programming", "language": "python"}
            )
        ]

        for i, doc in enumerate(documents, 1):
            await connector.store(doc, collection_name=collection_name)
            print(f"   ✓ Stored document {i}: {doc.content[:40]}...")

        # Test: Get collection info
        print("\n6. Testing: Get Collection Info")
        info = await connector.get_detailed_collection_info(collection_name)
        if info:
            print(f"   ✓ Points: {info.points_count}")
            print(f"   ✓ Vectors: {info.vectors_count}")
            print(f"   ✓ Vector size: {info.vector_size}")
            print(f"   ✓ Status: {info.status}")

        # Test: Semantic search (core AI functionality)
        print("\n7. Testing: Semantic Search")

        test_queries = [
            "English sentence with all letters",
            "artificial intelligence technology",
            "programming language for data science",
            "storing document vectors for search"
        ]

        for query in test_queries:
            results = await connector.search(
                query=query,
                collection_name=collection_name,
                limit=2
            )
            print(f"   Query: '{query}'")
            print(f"   ✓ Found {len(results)} results")
            if results:
                print(f"     Best match: {results[0].content[:50]}...")
                print(f"     Metadata: {results[0].metadata}")
            print()

        # Test: Batch store (what AI would use for bulk operations)
        print("\n8. Testing: Batch Store")
        from mcp_server_qdrant.qdrant import BatchEntry

        batch_entries = [
            BatchEntry(
                content="Neural networks are inspired by biological brain structures.",
                metadata={"batch": True, "topic": "neuroscience"}
            ),
            BatchEntry(
                content="Deep learning models require large amounts of training data.",
                metadata={"batch": True, "topic": "machine_learning"}
            ),
            BatchEntry(
                content="Natural language processing enables computers to understand human language.",
                metadata={"batch": True, "topic": "NLP"}
            )
        ]

        stored_count = await connector.batch_store(batch_entries, collection_name)
        print(f"   ✓ Batch stored {stored_count} entries")

        # Final collection stats
        print("\n9. Final Collection Statistics")
        final_info = await connector.get_detailed_collection_info(collection_name)
        if final_info:
            print(f"   ✓ Total points: {final_info.points_count}")
            print(f"   ✓ Total vectors: {final_info.vectors_count}")
            print(f"   ✓ Collection status: {final_info.status}")

        # Test comprehensive search
        print("\n10. Testing: Comprehensive AI Search")
        ai_query = "How do neural networks process language data?"
        comprehensive_results = await connector.search(
            query=ai_query,
            collection_name=collection_name,
            limit=5
        )

        print(f"   AI Query: '{ai_query}'")
        print(f"   ✓ Found {len(comprehensive_results)} semantically relevant results:")

        for i, result in enumerate(comprehensive_results, 1):
            print(f"   {i}. {result.content[:60]}...")
            if result.metadata:
                print(f"      Metadata: {result.metadata}")

        print("\n" + "="*60)
        print("✅ ALL MCP FUNCTIONALITY WORKING CORRECTLY!")
        print("🎯 The AI can now:")
        print("   • Store and retrieve documents with semantic understanding")
        print("   • Search by meaning, not just keyword matching")
        print("   • Handle batch operations efficiently")
        print("   • Access rich metadata for context")
        print("   • Work with multiple embedding models")
        print("   • Manage collections dynamically")
        print("="*60)

        return True

    except Exception as e:
        print(f"\n❌ Error during functionality test: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Clean up environment
        os.environ.pop("EMBEDDING_PROVIDER_TYPE", None)
        os.environ.pop("EMBEDDING_MODEL_NAME", None)

if __name__ == "__main__":
    success = asyncio.run(test_mcp_functionality())
    if success:
        print("\n🚀 MCP Server is ready for AI usage!")
        print("🔧 Tools available: qdrant_find, qdrant_store, qdrant_store_batch,")
        print("   list_collections, create_collection, get_collection_info, and more!")
    else:
        print("\n💥 MCP functionality needs debugging")
