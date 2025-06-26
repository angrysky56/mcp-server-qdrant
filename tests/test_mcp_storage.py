#!/usr/bin/env python3
"""
Test script to debug MCP server storage issues.
"""

import asyncio
import sys
import os
import json

# Add src to Python path
sys.path.insert(0, '/home/ty/Repositories/mcp-server-qdrant/src')

from mcp_server_qdrant.mcp_server import QdrantMCPServer
from mcp_server_qdrant.settings import (
    EmbeddingProviderSettings,
    QdrantSettings,
    ToolSettings,
)


async def test_mcp_storage():
    """Test MCP server storage functionality directly."""
    
    print("🧪 Testing MCP server storage...")
    
    try:
        # Initialize the MCP server
        mcp_server = QdrantMCPServer(
            tool_settings=ToolSettings(),
            qdrant_settings=QdrantSettings(),
            embedding_provider_settings=EmbeddingProviderSettings(),
        )
        
        print("✅ MCP server initialized")
        
        # Try to create a test collection
        collection_name = "mcp_storage_test"
        
        # Test qdrant_store function directly
        print(f"📝 Testing storage in collection: {collection_name}")
        
        # Get the qdrant_store function from the server's registered tools
        # We need to simulate the MCP context
        class MockContext:
            async def debug(self, message):
                print(f"DEBUG: {message}")
        
        ctx = MockContext()
        
        # Try the batch_store method on the connector directly
        from mcp_server_qdrant.qdrant import BatchEntry
        
        batch_entry = BatchEntry(
            content="Test content for MCP storage debugging",
            metadata={"test": "mcp_debug", "timestamp": "2025-06-25"},
            id="mcp_test_1"
        )
        
        print("🔄 Testing batch_store directly...")
        result = await mcp_server.qdrant_connector.batch_store([batch_entry], collection_name)
        print(f"   Batch store result: {result}")
        
        # Get collection info
        info = await mcp_server.qdrant_connector.get_detailed_collection_info(collection_name)
        if info:
            print("📊 Collection info after storage:")
            print(f"  Points: {info.points_count}")
            print(f"  Vectors: {info.vectors_count}")
            print(f"  Vector size: {info.vector_size}")
        else:
            print("❌ Could not get collection info")
            
        return result > 0
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_mcp_storage())
    if success:
        print("🎉 MCP storage is working!")
    else:
        print("💥 MCP storage is broken")
