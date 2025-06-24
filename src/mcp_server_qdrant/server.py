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
except RuntimeError as e:
    print(f"❌ Critical port management error: {e}")
    print("🛑 Server cannot start - please resolve port conflicts or restart system")
    exit(1)
except Exception as e:
    print(f"⚠️  Port management initialization failed: {e}")
    print("🔄 Attempting to continue with default configuration...")
    # Set a fallback port in environment
    import os
    if not os.environ.get("FASTMCP_PORT"):
        os.environ["FASTMCP_PORT"] = "8000"

mcp = ServerClass(
    tool_settings=ToolSettings(),
    qdrant_settings=QdrantSettings(),
    embedding_provider_settings=EmbeddingProviderSettings(),
)
