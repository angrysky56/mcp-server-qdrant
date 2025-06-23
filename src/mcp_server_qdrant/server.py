# Try to use enhanced server first, fall back to original if not available
try:
    from mcp_server_qdrant.mcp_server_enhanced import EnhancedQdrantMCPServer
    ServerClass = EnhancedQdrantMCPServer
    print("✨ Using enhanced MCP server with improved embedding management")
except ImportError:
    from mcp_server_qdrant.mcp_server import QdrantMCPServer
    ServerClass = QdrantMCPServer
    print("📦 Using standard MCP server")

from mcp_server_qdrant.settings import (
    EmbeddingProviderSettings,
    QdrantSettings,
    ToolSettings,
)
from mcp_server_qdrant.port_manager import initialize_port_management, print_server_info

# Initialize port management before creating the server
try:
    port = initialize_port_management()
    print_server_info()
except Exception as e:
    print(f"⚠️  Port management initialization failed: {e}")
    print("🔄 Continuing with default configuration...")

mcp = ServerClass(
    tool_settings=ToolSettings(),
    qdrant_settings=QdrantSettings(),
    embedding_provider_settings=EmbeddingProviderSettings(),
)
