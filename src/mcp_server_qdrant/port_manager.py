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
    PORT_RANGE_END = 8099
    
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
        host: str = "localhost"
    ) -> int:
        """
        Find an available port within a range.
        
        :param preferred_port: Preferred port to try first
        :param start_port: Start of port range to search
        :param end_port: End of port range to search  
        :param host: Host to check on
        :return: Available port number
        :raises RuntimeError: If no available port found in range
        """
        start_port = start_port or PortManager.PORT_RANGE_START
        end_port = end_port or PortManager.PORT_RANGE_END
        
        # Try preferred port first
        if preferred_port and start_port <= preferred_port <= end_port:
            if PortManager.is_port_available(preferred_port, host):
                logger.info(f"Using preferred port {preferred_port}")
                return preferred_port
            else:
                logger.warning(f"Preferred port {preferred_port} is not available")
        
        # Search range for available port
        for port in range(start_port, end_port + 1):
            if port == preferred_port:
                continue  # Already tried
                
            if PortManager.is_port_available(port, host):
                logger.info(f"Found available port {port}")
                return port
        
        raise RuntimeError(f"No available ports found in range {start_port}-{end_port}")
    
    @staticmethod
    def setup_port_from_env() -> int:
        """
        Setup port from environment variables with automatic detection fallback.
        
        :return: Port number to use
        """
        # Check if port is explicitly set
        env_port = os.environ.get("FASTMCP_PORT")
        if env_port:
            try:
                requested_port = int(env_port)
                if PortManager.is_port_available(requested_port):
                    logger.info(f"Using configured port {requested_port}")
                    return requested_port
                else:
                    logger.warning(f"Configured port {requested_port} is not available, finding alternative...")
                    # Fall through to auto-detection with this as preferred
                    preferred_port = requested_port
            except ValueError:
                logger.error(f"Invalid port number in FASTMCP_PORT: {env_port}")
                preferred_port = None
        else:
            preferred_port = PortManager.DEFAULT_PORT
        
        # Auto-detect available port
        try:
            available_port = PortManager.find_available_port(preferred_port)
            
            # Update environment variable so FastMCP uses the found port
            os.environ["FASTMCP_PORT"] = str(available_port)
            
            if available_port != preferred_port:
                logger.info(f"Port conflict detected. Using port {available_port} instead of {preferred_port}")
                print(f"⚠️  Port {preferred_port} was busy. MCP server will use port {available_port}")
            
            return available_port
            
        except RuntimeError as e:
            logger.error(f"Failed to find available port: {e}")
            # Fallback to original port and let it fail naturally with a clear error
            return preferred_port or PortManager.DEFAULT_PORT
    
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


def initialize_port_management() -> int:
    """
    Initialize port management for the MCP server.
    Call this early in server startup.
    
    :return: Port number that will be used
    """
    return PortManager.setup_port_from_env()


def print_server_info():
    """Print server connection information."""
    port = int(os.environ.get("FASTMCP_PORT", PortManager.DEFAULT_PORT))
    url = PortManager.get_server_url(port)
    
    print(f"🚀 MCP Server starting on {url}")
    print(f"📡 SSE endpoint: {url}/sse")
    print(f"🔧 Configure Claude Desktop to use: {url}/sse")
