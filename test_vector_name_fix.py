#!/usr/bin/env python3
"""
Test script to verify vector name mismatch fix.
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
from mcp_server_qdrant.qdrant import BatchEntry


async def test_vector_name_fix():
    """Test that vector name mismatch is resolved."""
    
    print("🧪 Testing vector name mismatch fix...")
    
    try:
        # Initialize MCP server
        mcp_server = QdrantMCPServer(
            tool_settings=ToolSettings(),
            qdrant_settings=QdrantSettings(),
            embedding_provider_settings=EmbeddingProviderSettings(),
        )
        
        print("✅ MCP server initialized")
        
        collection_name = "vector_name_fix_test"
        
        # Clean up any existing collection
        try:
            await mcp_server.qdrant_connector.delete_collection(collection_name)
            print(f"🧹 Cleaned up existing collection: {collection_name}")
        except Exception:
            pass
        
        # Test 1: Store with default provider
        print("📝 Test 1: Store with default embedding provider")
        batch_entry = BatchEntry(
            content="Testing vector name consistency with default provider",
            metadata={"test": "default_provider", "timestamp": "2025-06-25"},
            id="test_default_1"
        )
        
        result = await mcp_server.qdrant_connector.batch_store([batch_entry], collection_name)
        print(f"   Storage result: {result}")
        
        # Check collection info
        info = await mcp_server.qdrant_connector.get_detailed_collection_info(collection_name)
        if info:
            print(f"   Collection points: {info.points_count}, vectors: {info.vectors_count}")
        
        if result > 0 and info and info.points_count > 0:
            print("✅ Test 1 PASSED: Default provider storage works")
        else:
            print("❌ Test 1 FAILED: Default provider storage failed")
            return False
        
        # Test 2: Store with different provider (simulating MCP tool call)
        print("📝 Test 2: Store with embedding manager provider switching")
        
        # Get provider for collection (this is what MCP tools do)
        embedding_provider = await mcp_server.embedding_manager.get_provider_for_collection(collection_name)
        
        # Temporarily swap providers (this is what MCP qdrant_store does)
        original_provider = mcp_server.qdrant_connector._embedding_provider
        mcp_server.qdrant_connector._embedding_provider = embedding_provider
        
        try:
            batch_entry2 = BatchEntry(
                content="Testing vector name consistency with manager provider",
                metadata={"test": "manager_provider", "timestamp": "2025-06-25"},
                id="test_manager_1"
            )
            
            result2 = await mcp_server.qdrant_connector.batch_store([batch_entry2], collection_name)
            print(f"   Storage result: {result2}")
            
        finally:
            # Restore original provider
            mcp_server.qdrant_connector._embedding_provider = original_provider
        
        # Check final collection info
        info_final = await mcp_server.qdrant_connector.get_detailed_collection_info(collection_name)
        if info_final:
            print(f"   Final collection points: {info_final.points_count}, vectors: {info_final.vectors_count}")
        
        if result2 > 0 and info_final and info_final.points_count > 1:
            print("✅ Test 2 PASSED: Provider switching storage works")
            print("🎉 Vector name mismatch fix is working!")
            return True
        else:
            print("❌ Test 2 FAILED: Provider switching storage failed")
            return False
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_vector_name_fix())
    if success:
        print("🎉 Vector name fix verification successful!")
    else:
        print("💥 Vector name fix verification failed")
