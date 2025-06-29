#!/usr/bin/env python3
"""
Diagnostic script to understand the embedding provider issue.
"""

import asyncio
import sys
import os

# Add src to Python path
sys.path.insert(0, '/home/ty/Repositories/mcp-server-qdrant/src')

from mcp_server_qdrant.mcp_server import QdrantMCPServer
from mcp_server_qdrant.settings import (
    EmbeddingProviderSettings,
    QdrantSettings,
    ToolSettings,
)


async def diagnose_embedding_providers():
    """Diagnose the embedding provider issue."""
    
    print("🔍 Diagnosing embedding provider configuration...")
    
    try:
        # Initialize MCP server
        mcp_server = QdrantMCPServer(
            tool_settings=ToolSettings(),
            qdrant_settings=QdrantSettings(),
            embedding_provider_settings=EmbeddingProviderSettings(),
        )
        
        print("✅ MCP server initialized")
        
        collection_name = "llm_research_papers"
        
        # Check default provider
        print("\n📋 Default Provider Info:")
        default_provider = mcp_server.embedding_provider
        print(f"   Model name: {default_provider.get_model_name()}")
        print(f"   Vector name: {default_provider.get_vector_name()}")
        print(f"   Vector size: {default_provider.get_vector_size()}")
        
        # Check what provider the embedding manager returns for our collection
        print(f"\n📋 Collection-specific Provider Info for '{collection_name}':")
        collection_provider = await mcp_server.embedding_manager.get_provider_for_collection(collection_name)
        print(f"   Model name: {collection_provider.get_model_name()}")
        print(f"   Vector name: {collection_provider.get_vector_name()}")
        print(f"   Vector size: {collection_provider.get_vector_size()}")
        
        # Check if they're the same object
        print(f"\n🔄 Provider Comparison:")
        print(f"   Are they the same object? {default_provider is collection_provider}")
        print(f"   Same model name? {default_provider.get_model_name() == collection_provider.get_model_name()}")
        print(f"   Same vector name? {default_provider.get_vector_name() == collection_provider.get_vector_name()}")
        
        # Check what model is stored for the collection
        stored_model = await mcp_server.embedding_manager.get_collection_model(collection_name)
        print(f"\n💾 Stored Model Mapping:")
        print(f"   Stored model for collection: {stored_model}")
        
        # Check if mapping collection exists
        mapping_exists = await mcp_server.qdrant_connector._client.collection_exists("_mcp_embedding_models")
        print(f"   Model mapping collection exists: {mapping_exists}")
        
        if mapping_exists:
            # Check mappings in the storage collection
            try:
                mappings = await mcp_server.qdrant_connector._client.scroll(
                    collection_name="_mcp_embedding_models",
                    limit=10,
                    with_payload=True,
                    with_vectors=False
                )
                print(f"   Mapping entries found: {len(mappings[0])}")
                for point in mappings[0]:
                    if point.payload:
                        print(f"   - Collection: {point.payload.get('collection_name')} -> Model: {point.payload.get('model_name')}")
            except Exception as e:
                print(f"   Error reading mappings: {e}")
        
        # Test provider creation for specific model
        print(f"\n🧪 Test Provider Creation:")
        test_model = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
        try:
            from mcp_server_qdrant.embeddings.types import EmbeddingProviderType
            from mcp_server_qdrant.embeddings.factory import create_embedding_provider
            
            test_settings = EmbeddingProviderSettings(
                provider_type=EmbeddingProviderType.FASTEMBED,
                model_name=test_model
            )
            test_provider = create_embedding_provider(test_settings)
            print(f"   Test model: {test_model}")
            print(f"   Generated vector name: {test_provider.get_vector_name()}")
            print(f"   Vector size: {test_provider.get_vector_size()}")
        except Exception as e:
            print(f"   Error creating test provider: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Diagnosis failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(diagnose_embedding_providers())
    if success:
        print("\n🎯 Diagnosis completed!")
    else:
        print("\n💥 Diagnosis failed!")
