from mcp_server_qdrant.mcp_server import EnhancedQdrantMCPServer
from mcp_server_qdrant.settings import (
    EmbeddingProviderSettings,
    QdrantSettings,
    ToolSettings,
)
from mcp_server_qdrant.port_manager import initialize_port_management, print_server_info

# Initialize port management
port = initialize_port_management()
print_server_info()

mcp = EnhancedQdrantMCPServer(
    tool_settings=ToolSettings(),
    qdrant_settings=QdrantSettings(),
    embedding_provider_settings=EmbeddingProviderSettings(),
)
