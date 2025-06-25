FROM python:3.14-slim

WORKDIR /app

# Install uv for package management
RUN pip install --no-cache-dir uv

# Install the mcp-server-qdrant package and optional docker support
RUN uv pip install --system --no-cache-dir mcp-server-qdrant docker requests

# Expose the default port for SSE transport
EXPOSE 8000

# Set environment variables with defaults that can be overridden at runtime
ENV QDRANT_MODE="docker"
ENV QDRANT_AUTO_DOCKER="true"
ENV QDRANT_API_KEY=""
ENV QDRANT_ENABLE_COLLECTION_MANAGEMENT="true"
ENV QDRANT_ENABLE_DYNAMIC_EMBEDDING_MODELS="true"
ENV QDRANT_ENABLE_RESOURCES="true"
ENV FASTMCP_PORT="8000"
# Run the server with SSE transport
CMD ["uvx", "mcp-server-qdrant", "--transport", "sse"]
