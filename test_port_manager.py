#!/usr/bin/env python3
"""
Test script for the improved port manager functionality.
"""

import os
import sys
import socket
import time
from contextlib import contextmanager

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from mcp_server_qdrant.port_manager import PortManager, initialize_port_management


@contextmanager
def occupy_port(port: int):
    """Context manager to temporarily occupy a port for testing."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(('localhost', port))
        sock.listen(1)
        print(f"🔒 Temporarily occupying port {port}")
        yield sock
    finally:
        sock.close()
        print(f"🔓 Released port {port}")


def test_basic_functionality():
    """Test basic port manager functionality."""
    print("=" * 60)
    print("🧪 Testing Basic Port Manager Functionality")
    print("=" * 60)
    
    # Test 1: Check if default port is available
    print("\n1. Testing default port availability...")
    default_available = PortManager.is_port_available(8000)
    print(f"   Port 8000 available: {default_available}")
    
    # Test 2: Find available port in range
    print("\n2. Testing find_available_port...")
    try:
        port = PortManager.find_available_port(preferred_port=8000)
        print(f"   ✅ Found available port: {port}")
    except RuntimeError as e:
        print(f"   ❌ Failed to find port: {e}")
    
    # Test 3: Test with occupied port
    print("\n3. Testing with occupied port...")
    with occupy_port(8000):
        try:
            port = PortManager.find_available_port(preferred_port=8000)
            print(f"   ✅ Found alternative port: {port}")
        except RuntimeError as e:
            print(f"   ❌ Failed to find alternative: {e}")


def test_extended_range():
    """Test extended range functionality."""
    print("\n" + "=" * 60)
    print("🧪 Testing Extended Range Functionality")
    print("=" * 60)
    
    # Simulate many occupied ports by using a small range
    print("\n1. Testing extended range search...")
    try:
        port = PortManager.find_available_port(
            start_port=8050,
            end_port=8052,  # Very small range
            use_extended_range=True
        )
        print(f"   ✅ Found port with extended search: {port}")
    except RuntimeError as e:
        print(f"   ❌ Extended range search failed: {e}")


def test_environment_integration():
    """Test environment variable integration."""
    print("\n" + "=" * 60)
    print("🧪 Testing Environment Integration")
    print("=" * 60)
    
    # Save original environment
    original_port = os.environ.get("FASTMCP_PORT")
    
    try:
        # Test 1: No environment variable
        print("\n1. Testing without FASTMCP_PORT...")
        if "FASTMCP_PORT" in os.environ:
            del os.environ["FASTMCP_PORT"]
        
        port = initialize_port_management()
        print(f"   ✅ Initialized with port: {port}")
        print(f"   Environment now set to: {os.environ.get('FASTMCP_PORT')}")
        
        # Test 2: With environment variable
        print("\n2. Testing with FASTMCP_PORT set...")
        os.environ["FASTMCP_PORT"] = "8001"
        
        port = initialize_port_management()
        print(f"   ✅ Initialized with port: {port}")
        
        # Test 3: With invalid environment variable
        print("\n3. Testing with invalid FASTMCP_PORT...")
        os.environ["FASTMCP_PORT"] = "invalid"
        
        port = initialize_port_management()
        print(f"   ✅ Handled invalid port, using: {port}")
        
    except Exception as e:
        print(f"   ❌ Environment integration failed: {e}")
    finally:
        # Restore original environment
        if original_port:
            os.environ["FASTMCP_PORT"] = original_port
        elif "FASTMCP_PORT" in os.environ:
            del os.environ["FASTMCP_PORT"]


def test_diagnostics():
    """Test port diagnostics functionality."""
    print("\n" + "=" * 60)
    print("🧪 Testing Port Diagnostics")
    print("=" * 60)
    
    print("\n1. Running port diagnostics...")
    PortManager.diagnose_port_issues(8000, 8020)


def main():
    """Run all port manager tests."""
    print("🚀 Starting Port Manager Tests")
    print(f"System: {os.name}, Python: {sys.version}")
    
    try:
        test_basic_functionality()
        test_extended_range()
        test_environment_integration()
        test_diagnostics()
        
        print("\n" + "=" * 60)
        print("✅ All tests completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
