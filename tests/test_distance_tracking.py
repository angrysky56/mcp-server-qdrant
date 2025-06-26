#!/usr/bin/env python3
"""
Quick test script to verify distance metric tracking functionality.
"""

import asyncio

# Test the embedding manager distance tracking
async def test_distance_tracking():
    """Test that distance metrics are properly stored and retrieved."""

    # Import the enhanced embedding manager
    from mcp_server_qdrant.embedding_manager import EnhancedEmbeddingModelManager
    from mcp_server_qdrant.settings import EmbeddingProviderSettings
    from mcp_server_qdrant.qdrant import QdrantConnector

    print("🧪 Testing distance metric tracking...")

    # Create a temporary Qdrant in-memory instance
    qdrant_url = ":memory:"

    try:        # Initialize embedding manager
        import os
        os.environ["EMBEDDING_PROVIDER"] = "fastembed"
        os.environ["EMBEDDING_MODEL"] = "sentence-transformers/all-MiniLM-L6-v2"

        settings = EmbeddingProviderSettings()

        embedding_manager = EnhancedEmbeddingModelManager(settings)

        # Create embedding provider
        from mcp_server_qdrant.embeddings.factory import create_embedding_provider
        embedding_provider = create_embedding_provider(settings)

        # Create Qdrant connector
        qdrant_connector = QdrantConnector(qdrant_url, None, "test_collection", embedding_provider)
        embedding_manager.set_qdrant_connector(qdrant_connector)

        # Test storing different distance metrics
        test_cases = [
            ("collection_cosine", "cosine"),
            ("collection_dot", "dot"),
            ("collection_euclidean", "euclidean"),
            ("collection_manhattan", "manhattan")
        ]

        for collection_name, distance in test_cases:
            print(f"📝 Testing {collection_name} with {distance} distance...")

            # Set collection model with distance
            success = await embedding_manager.set_collection_model(
                collection_name,
                "sentence-transformers/all-MiniLM-L6-v2",
                distance
            )

            if success:
                print(f"✅ Successfully set model for {collection_name}")

                # Retrieve the distance
                retrieved_distance = await embedding_manager.get_collection_distance(collection_name)
                print(f"📊 Retrieved distance for {collection_name}: {retrieved_distance}")

                if retrieved_distance == distance:
                    print("✅ Distance metric correctly stored and retrieved!")
                else:
                    print(f"❌ Distance mismatch! Expected: {distance}, Got: {retrieved_distance}")
            else:
                print(f"❌ Failed to set model for {collection_name}")

        print("\n🎯 Testing model info retrieval...")
        models = embedding_manager.list_available_models()
        print(f"Available models: {len(models)}")

        for model in models[:3]:  # Show first 3
            print(f"  • {model.model_name} - {model.vector_size}D")

        print("\n✨ Distance metric tracking test completed!")

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Clean up - no cleanup needed for in-memory Qdrant
        pass

if __name__ == "__main__":
    asyncio.run(test_distance_tracking())
