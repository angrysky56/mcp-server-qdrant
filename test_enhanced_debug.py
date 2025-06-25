#!/usr/bin/env python3
"""
Enhanced debug script to diagnose vector storage issues in Qdrant.
This script will add extensive logging to see exactly what's happening.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path for importing
sys.path.insert(0, str(Path(__file__).parent / "src"))

from mcp_server_qdrant.qdrant import QdrantConnector, Entry
from mcp_server_qdrant.embeddings.fastembed import FastEmbedProvider

# Configure logging to see all details
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def debug_vector_storage():
    """Debug vector storage step by step."""

    print("=== Enhanced Vector Storage Debug ===")

    # Initialize embedding provider
    print("\n1. Initializing FastEmbed provider...")
    embedding_provider = FastEmbedProvider("BAAI/bge-small-en-v1.5")

    # Get embedding provider details
    vector_name = embedding_provider.get_vector_name()
    vector_size = embedding_provider.get_vector_size()
    model_name = embedding_provider.get_model_name()

    print(f"   Model: {model_name}")
    print(f"   Vector name: {vector_name}")
    print(f"   Vector size: {vector_size}")

    # Initialize Qdrant connector
    print("\n2. Initializing Qdrant connector...")
    qdrant = QdrantConnector(
        qdrant_url="http://localhost:6333",
        qdrant_api_key=None,
        collection_name="debug_vectors",
        embedding_provider=embedding_provider
    )

    try:
        # Get available collections
        print("\n3. Checking existing collections...")
        collections = await qdrant.get_collection_names()
        print(f"   Existing collections: {collections}")

        # Test embedding generation
        print("\n4. Testing embedding generation...")
        test_content = "This is a test document for vector storage debugging."
        embeddings = await embedding_provider.embed_documents([test_content])

        print(f"   Test content: {test_content}")
        print(f"   Generated embedding length: {len(embeddings[0])}")
        print(f"   Embedding first 5 values: {embeddings[0][:5]}")
        print(f"   Embedding type: {type(embeddings[0])}")

        # Check if collection exists, get info if it does
        collection_name = "debug_vectors"
        if collection_name in collections:
            print(f"\n5a. Collection '{collection_name}' exists, getting info...")
            info = await qdrant.get_detailed_collection_info(collection_name)
            if info:
                print(f"   Points: {info.points_count}")
                print(f"   Vectors: {info.vectors_count}")
                print(f"   Vector size: {info.vector_size}")
                print(f"   Distance metric: {info.distance_metric}")

            # Get collection config directly from Qdrant client
            collection_info = await qdrant._client.get_collection(collection_name)
            print(f"   Raw collection info: {collection_info}")

            if hasattr(collection_info, 'config') and collection_info.config:
                print(f"   Config: {collection_info.config}")
                if hasattr(collection_info.config, 'params'):
                    print(f"   Params: {collection_info.config.params}")
                    if hasattr(collection_info.config.params, 'vectors'):
                        vectors_config = collection_info.config.params.vectors
                        print(f"   Vectors config: {vectors_config}")
                        print(f"   Vectors config type: {type(vectors_config)}")

                        if isinstance(vectors_config, dict):
                            for vname, vconfig in vectors_config.items():
                                print(f"   Vector '{vname}': {vconfig}")
        else:
            print(f"\n5b. Collection '{collection_name}' does not exist, will be created during store.")

        # Store an entry
        print(f"\n6. Storing entry in collection '{collection_name}'...")
        entry = Entry(
            content=test_content,
            metadata={"test": True, "debug": "vector_storage"}
        )

        await qdrant.store(entry, collection_name=collection_name)
        print("   ✓ Store operation completed")

        # Get collection info after storing
        print("\n7. Checking collection after storage...")
        info = await qdrant.get_detailed_collection_info(collection_name)
        if info:
            print(f"   Points: {info.points_count}")
            print(f"   Vectors: {info.vectors_count}")
            print(f"   Indexed vectors: {info.indexed_vectors_count}")
            print(f"   Status: {info.status}")
            print(f"   Vector size: {info.vector_size}")
            print(f"   Distance metric: {info.distance_metric}")

        # Get raw collection info again
        collection_info = await qdrant._client.get_collection(collection_name)
        print(f"   Raw points_count: {getattr(collection_info, 'points_count', 'N/A')}")
        print(f"   Raw vectors_count: {getattr(collection_info, 'vectors_count', 'N/A')}")
        print(f"   Raw indexed_vectors_count: {getattr(collection_info, 'indexed_vectors_count', 'N/A')}")

        # Try to search
        print("\n8. Testing search...")
        search_results = await qdrant.search("test document", collection_name=collection_name, limit=5)
        print(f"   Search results count: {len(search_results)}")
        for i, result in enumerate(search_results):
            print(f"   Result {i+1}: {result.content[:50]}...")

        # Try to retrieve all points manually using scroll
        print("\n9. Manually checking stored points...")
        try:
            scroll_result = await qdrant._client.scroll(
                collection_name=collection_name,
                limit=10,
                with_payload=True,
                with_vectors=True
            )

            print(f"   Scroll found {len(scroll_result[0])} points")
            for i, point in enumerate(scroll_result[0]):
                print(f"   Point {i+1}:")
                print(f"     ID: {point.id}")
                print(f"     Payload keys: {list(point.payload.keys()) if point.payload else 'None'}")
                print(f"     Vector keys: {list(point.vector.keys()) if isinstance(point.vector, dict) else 'Single vector' if point.vector else 'No vector'}")

                if isinstance(point.vector, dict):
                    for vname, vector in point.vector.items():
                        try:
                            vector_len = len(vector) if isinstance(vector, (list, tuple)) else 'Unknown'
                            print(f"     Vector '{vname}' length: {vector_len}")
                        except Exception:
                            print(f"     Vector '{vname}': {type(vector)}")
                elif point.vector:
                    try:
                        vector_len = len(point.vector) if hasattr(point.vector, '__len__') else 'Unknown'
                        print(f"     Single vector length: {vector_len}")
                    except Exception:
                        print(f"     Single vector: {type(point.vector)}")
                else:
                    print("     No vector data")

        except Exception as e:
            print(f"   Error during manual scroll: {e}")

        print("\n=== Debug Complete ===")

    except Exception as e:
        logger.error(f"Error during debug: {e}", exc_info=True)
        print(f"\n❌ Error during debug: {e}")

if __name__ == "__main__":
    asyncio.run(debug_vector_storage())
