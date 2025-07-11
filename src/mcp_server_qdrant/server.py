import os
import sys
import logging

from mcp_server_qdrant.mcp_server import QdrantMCPServer
from mcp_server_qdrant.settings import (
    EmbeddingProviderSettings,
    QdrantSettings,
    ToolSettings,
)

# Configure logging to stderr to avoid stdout contamination in MCP mode
logging.basicConfig(
    level=logging.INFO,  # Set to INFO to see informational messages from docker_utils
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    stream=sys.stderr  # Always use stderr for logs
)

# Detect MCP stdio mode more reliably
def is_mcp_stdio_mode() -> bool:
    """Check if we're running in MCP stdio mode."""
    # Check command line arguments
    if "--transport" in sys.argv and "stdio" in sys.argv:
        return True

    # Check environment variables that indicate MCP client
    mcp_indicators = ["MCP_CLIENT", "LM_STUDIO", "CLAUDE_DESKTOP"]
    if any(os.getenv(var) for var in mcp_indicators):
        return True

    # If stdin/stdout appear to be pipes (not terminal), assume MCP mode
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return True

    return False

# Only do port management for interactive/non-MCP usage
if not is_mcp_stdio_mode():
    try:
        from mcp_server_qdrant.port_manager import initialize_port_management, print_server_info
        port = initialize_port_management()
        print_server_info()
    except Exception as e:
        # Log to stderr, don't print to stdout
        logging.warning(f"Port management initialization failed: {e}")

# Initialize the MCP server with error handling
try:
    mcp = QdrantMCPServer(
        tool_settings=ToolSettings(),
        qdrant_settings=QdrantSettings(),
        embedding_provider_settings=EmbeddingProviderSettings(),
    )
except Exception as e:
    logging.error(f"Failed to initialize MCP server: {e}")
    sys.exit(1)
