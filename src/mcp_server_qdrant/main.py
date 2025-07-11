import argparse
import signal
import sys
from mcp_server_qdrant.docker_utils import start_qdrant_container, stop_qdrant_container


def main():
    """
    Main entry point for the mcp-server-qdrant script defined
    in pyproject.toml. It runs the MCP server with a specific transport
    protocol.
    """

    # Parse the command-line arguments to determine the transport protocol.
    parser = argparse.ArgumentParser(description="mcp-server-qdrant")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
    )
    args = parser.parse_args()

    # Start the Qdrant Docker container
    start_qdrant_container()

    # Define a signal handler for graceful shutdown
    def signal_handler(sig, frame):
        print(f"\nReceived signal {sig}, shutting down gracefully...")
        stop_qdrant_container()
        sys.exit(0)

    # Register the signal handlers
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler) # kill command

    # Import is done here to make sure environment variables are loaded
    # only after we make the changes.
    from mcp_server_qdrant.server import mcp

    try:
        mcp.run(transport=args.transport)
    except KeyboardInterrupt:
        # This handles cases where Ctrl+C might not be caught by signal_handler
        print("\nKeyboardInterrupt detected, shutting down...")
        stop_qdrant_container()
        sys.exit(0)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        stop_qdrant_container()
        sys.exit(1)
