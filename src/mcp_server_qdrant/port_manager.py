"""
Port management utilities for mcp-server-qdrant.
Handles automatic port detection and assignment to avoid conflicts.
"""

import logging
import socket
import os
from typing import Optional

logger = logging.getLogger(__name__)


class PortManager:
    """Manages port allocation and conflict detection for the MCP server."""

    DEFAULT_PORT = 8000
    PORT_RANGE_START = 8000
    PORT_RANGE_END = 8199  # Expanded range for better availability
    EXTENDED_RANGE_END = 9099  # Emergency extended range

    @staticmethod
    def is_port_available(port: int, host: str = "localhost") -> bool:
        """
        Check if a port is available for binding.

        :param port: Port number to check
        :param host: Host to check on (default: localhost)
        :return: True if port is available, False otherwise
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1)
                result = sock.connect_ex((host, port))
                return result != 0  # Port is available if connection fails
        except Exception as e:
            logger.debug(f"Error checking port {port}: {e}")
            return False

    @staticmethod
    def find_available_port(
        preferred_port: Optional[int] = None,
        start_port: Optional[int] = None,
        end_port: Optional[int] = None,
        host: str = "localhost",
        use_extended_range: bool = False
    ) -> int:
        """
        Find an available port within a range.

        :param preferred_port: Preferred port to try first
        :param start_port: Start of port range to search
        :param end_port: End of port range to search
        :param host: Host to check on
        :param use_extended_range: Whether to search extended range if primary fails
        :return: Available port number
        :raises RuntimeError: If no available port found in any range
        """
        start_port = start_port or PortManager.PORT_RANGE_START
        end_port = end_port or PortManager.PORT_RANGE_END

        # Try preferred port first
        if preferred_port and start_port <= preferred_port <= end_port:
            if PortManager.is_port_available(preferred_port, host):
                return preferred_port
            else:
                logger.debug(f"Preferred port {preferred_port} is not available")

        # Search primary range for available port
        logger.debug(f"Searching for available port in range {start_port}-{end_port}")
        for port in range(start_port, end_port + 1):
            if port == preferred_port:
                continue  # Already tried

            if PortManager.is_port_available(port, host):
                return port

        # If use_extended_range is True, try the extended range
        if use_extended_range and end_port < PortManager.EXTENDED_RANGE_END:
            logger.debug(f"Primary range {start_port}-{end_port} exhausted, searching extended range")
            extended_start = max(end_port + 1, PortManager.PORT_RANGE_END + 1)
            for port in range(extended_start, PortManager.EXTENDED_RANGE_END + 1):
                if PortManager.is_port_available(port, host):
                    return port

        # If still no port found, try system-assigned port as last resort
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('', 0))  # Let system assign port
            port = sock.getsockname()[1]
            sock.close()

            if port >= 1024:  # Ensure it's not a privileged port
                logger.debug(f"Using system-assigned port {port} as last resort")
                return port
        except Exception as e:
            logger.error(f"Failed to get system-assigned port: {e}")

        raise RuntimeError(f"No available ports found in any range (tried {start_port}-{PortManager.EXTENDED_RANGE_END})")

    @staticmethod
    def setup_port_from_env() -> int:
        """
        Setup port from environment variables with automatic detection fallback.

        :return: Port number to use
        :raises RuntimeError: If no available port can be found anywhere
        """
        # Check if port is explicitly set
        env_port = os.environ.get("FASTMCP_PORT")
        preferred_port = None

        if env_port:
            try:
                requested_port = int(env_port)
                if PortManager.is_port_available(requested_port):
                    return requested_port
                else:
                    logger.debug(f"Configured port {requested_port} is not available, finding alternative...")
                    preferred_port = requested_port
            except ValueError:
                logger.error(f"Invalid port number in FASTMCP_PORT: {env_port}")
                preferred_port = PortManager.DEFAULT_PORT
        else:
            preferred_port = PortManager.DEFAULT_PORT

        # Auto-detect available port with extended search
        try:
            available_port = PortManager.find_available_port(
                preferred_port=preferred_port,
                use_extended_range=True
            )

            # Update environment variable so FastMCP uses the found port
            os.environ["FASTMCP_PORT"] = str(available_port)

            if available_port != preferred_port:
                logger.debug(f"Port conflict detected. Using port {available_port} instead of {preferred_port}")
                print(f"⚠️  Port {preferred_port} was busy. MCP server will use port {available_port}")

            return available_port

        except RuntimeError as e:
            logger.error(f"Failed to find any available port: {e}")
            print("❌ Unable to find an available port for the MCP server")
            print("   This could indicate system port exhaustion or network issues")
            print("   Try freeing up some ports or restarting network services")
            raise RuntimeError(f"Port allocation failed: {e}") from e

    @staticmethod
    def get_server_url(port: Optional[int] = None, host: str = "localhost") -> str:
        """
        Get the server URL for the given port.

        :param port: Port number (if None, reads from environment)
        :param host: Host name
        :return: Complete server URL
        """
        if port is None:
            port = int(os.environ.get("FASTMCP_PORT", PortManager.DEFAULT_PORT))

        return f"http://{host}:{port}"


    @staticmethod
    def diagnose_port_issues(port_range_start: Optional[int] = None, port_range_end: Optional[int] = None) -> None:
        """
        Diagnose and report common port issues.

        :param port_range_start: Start of range to check
        :param port_range_end: End of range to check
        """
        start = port_range_start or PortManager.PORT_RANGE_START
        end = port_range_end or PortManager.EXTENDED_RANGE_END

        print(f"🔍 Diagnosing port availability in range {start}-{end}...")

        available_count = 0
        unavailable_ports = []

        sample_end = min(start + 49, end)
        for port in range(start, sample_end + 1):  # Check up to 50 ports or the full range
            if PortManager.is_port_available(port):
                available_count += 1
            else:
                unavailable_ports.append(port)
        print(f"📊 Found {available_count} available ports in sample range {start}-{min(start+49, end)}")
        print(f"📊 Found {available_count} available ports in sample range {start}-{sample_end}")

        if unavailable_ports:
            ellipsis = '...' if len(unavailable_ports) > 10 else ''
            print(f"🚫 Busy ports detected: {unavailable_ports[:10]}{ellipsis}")

        if available_count == 0:
            print("⚠️  No available ports found in sample range!")
            print("💡 Suggestions:")
            print("   • Check if other MCP servers are running")
            print("   • Kill any stuck processes: pkill -f mcp-server")
            print("   • Restart system network services")
            print("   • Use a different port range with FASTMCP_PORT environment variable")


def initialize_port_management() -> int:
    """
    Initialize port management for the MCP server.
    Also sets up Qdrant configuration (embedded by default).
    Call this early in server startup.

    :return: Port number that will be used
    :raises RuntimeError: If no available port can be found
    """
    # Setup Qdrant configuration first
    setup_qdrant_config()

    try:
        return PortManager.setup_port_from_env()
    except RuntimeError as e:
        # Run diagnostics to help user understand the issue
        print("🔧 Running port diagnostics...")
        PortManager.diagnose_port_issues()
        raise e


def setup_qdrant_config():
    """Setup Qdrant configuration - embedded by default, Docker optional."""
    qdrant_mode = os.environ.get("QDRANT_MODE", "embedded").lower()

    if qdrant_mode == "embedded":
        # Use embedded Qdrant (local file storage)
        local_path = os.environ.get("QDRANT_LOCAL_PATH", "./qdrant_data")
        os.environ["QDRANT_URL"] = local_path
        os.makedirs(local_path, exist_ok=True)
        print(f"📁 Using embedded Qdrant: {local_path}")

    elif qdrant_mode == "docker":
        # Docker auto-management (if requested)
        auto_docker = os.environ.get("QDRANT_AUTO_DOCKER", "false").lower() == "true"
        if auto_docker:
            # The docker container is now managed by docker_utils.py
            # No action needed here for auto-docker, as it's handled at main.py entry point
            pass
        else:
            # Use manual Docker setup
            qdrant_url = os.environ.get("QDRANT_URL", "http://localhost:6333")
            print(f"🐳 Using Docker Qdrant: {qdrant_url}")

    else:
        # Use existing URL
        qdrant_url = os.environ.get("QDRANT_URL", "http://localhost:6333")
        print(f"🌐 Using external Qdrant: {qdrant_url}")





def print_server_info():
    """Print server connection information."""
    port = int(os.environ.get("FASTMCP_PORT", PortManager.DEFAULT_PORT))
    url = PortManager.get_server_url(port)

    print(f"🚀 MCP Server starting on {url}")
    print(f"📡 SSE endpoint: {url}/sse")
    print(f"🔧 Configure Claude Desktop to use: {url}/sse")

    # Show Qdrant configuration
    qdrant_url = os.environ.get("QDRANT_URL", "http://localhost:6333")
    qdrant_mode = os.environ.get("QDRANT_MODE", "embedded")

    if qdrant_mode == "embedded":
        print(f"📁 Qdrant: Embedded mode ({qdrant_url})")
    elif qdrant_mode == "docker":
        auto_docker = os.environ.get("QDRANT_AUTO_DOCKER", "false").lower() == "true"
        if auto_docker:
            print(f"🐳 Qdrant: Auto-managed Docker ({qdrant_url})")
        else:
            print(f"🐳 Qdrant: Docker ({qdrant_url})")
    else:
        print(f"🌐 Qdrant: External ({qdrant_url})")
