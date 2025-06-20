#!/usr/bin/env python3
"""
Quick test of port management functionality.
"""

import os
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from mcp_server_qdrant.port_manager import initialize_port_management, print_server_info

def test_port_management():
    """Test the port management system."""
    print("🔧 Testing Port Management System")
    print("=" * 40)
    
    # Test 1: Default behavior
    print("\n1️⃣ Testing default port detection...")
    try:
        port = initialize_port_management()
        print(f"✅ Successfully allocated port: {port}")
        print_server_info()
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 2: Explicit port override
    print("\n2️⃣ Testing explicit port override...")
    os.environ["FASTMCP_PORT"] = "9876"
    try:
        port = initialize_port_management()
        print(f"✅ Using configured port: {port}")
        print_server_info()
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 3: Port conflict detection
    print("\n3️⃣ Testing port conflict detection...")
    os.environ["FASTMCP_PORT"] = "8000"  # This should be busy
    try:
        port = initialize_port_management()
        print(f"✅ Resolved port conflict, using: {port}")
        print_server_info()
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n🎉 Port management testing complete!")

if __name__ == "__main__":
    test_port_management()
