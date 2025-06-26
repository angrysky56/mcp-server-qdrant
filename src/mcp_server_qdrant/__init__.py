"""
Enhanced MCP Server for Qdrant Vector Database.

This package provides a Model Context Protocol (MCP) server for interacting with Qdrant vector databases.
It supports advanced embedding management, collection operations, and hybrid search capabilities.

Key Features:
- Multiple embedding model support (FastEmbed, OpenAI, etc.)
- Dynamic collection management with proper vector sizing
- Hybrid search with similarity scoring and metadata filtering
- Batch operations for efficient data processing
- UUID-validated point storage for Qdrant compatibility
- Enhanced error handling and logging for MCP clients

Main Components:
- QdrantMCPServer: Main MCP server class with tool registration
- QdrantConnector: Low-level Qdrant client wrapper with embedding support
- EnhancedEmbeddingModelManager: Multi-model embedding provider management
- Various embedding providers (FastEmbed, OpenAI, etc.)

Usage:
    from mcp_server_qdrant import QdrantMCPServer
    from mcp_server_qdrant.settings import QdrantSettings, EmbeddingProviderSettings, ToolSettings
    
    server = QdrantMCPServer(
        tool_settings=ToolSettings(),
        qdrant_settings=QdrantSettings(),
        embedding_provider_settings=EmbeddingProviderSettings(),
    )

Compatible with:
- Claude Desktop (MCP client)
- LM Studio (MCP client)  
- Custom MCP implementations
- Direct FastMCP usage

Version: 0.7.1
License: Apache-2.0
"""

__version__ = "0.7.1"
__author__ = "MCP Server Qdrant Contributors"
__license__ = "Apache-2.0"

from .mcp_server import QdrantMCPServer
from .qdrant import QdrantConnector, Entry, BatchEntry, CollectionInfo
from .embedding_manager import EnhancedEmbeddingModelManager, EmbeddingModelInfo
from .settings import (
    QdrantSettings,
    EmbeddingProviderSettings, 
    ToolSettings,
    FilterableField,
)

__all__ = [
    "QdrantMCPServer",
    "QdrantConnector", 
    "Entry",
    "BatchEntry",
    "CollectionInfo",
    "EnhancedEmbeddingModelManager",
    "EmbeddingModelInfo",
    "QdrantSettings",
    "EmbeddingProviderSettings",
    "ToolSettings", 
    "FilterableField",
]
