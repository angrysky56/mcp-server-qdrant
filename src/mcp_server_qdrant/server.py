from mcp_server_qdrant.mcp_server import QdrantMCPServer
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

mcp = QdrantMCPServer(
    tool_settings=ToolSettings(),
    qdrant_settings=QdrantSettings(),
    embedding_provider_settings=EmbeddingProviderSettings(),
)
