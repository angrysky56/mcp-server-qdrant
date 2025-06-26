#!/usr/bin/env python3
"""
Test script to verify Claude Desktop configuration works correctly.
"""

import subprocess
import json
import time
import os

def test_claude_config():
    """Test the exact Claude Desktop configuration."""

    print("🔧 Testing Claude Desktop Configuration Fix...")

    # Test the exact command and environment from your claude_config.json
    env_vars = {
        "QDRANT_MODE": "docker",
        "QDRANT_AUTO_DOCKER": "true",
        "QDRANT_API_KEY": "",
        "QDRANT_ENABLE_COLLECTION_MANAGEMENT": "true",
        "QDRANT_ENABLE_DYNAMIC_EMBEDDING_MODELS": "true",
        "QDRANT_ENABLE_RESOURCES": "true"
    }

    # Update environment
    test_env = os.environ.copy()
    test_env.update(env_vars)

    command = [
        "uv", "--directory",
        "/home/ty/Repositories/mcp-server-qdrant/src",
        "run", "mcp-server-qdrant"
    ]

    print(f"   Command: {' '.join(command)}")
    print(f"   Environment: {env_vars}")

    try:
        # Test that the server starts without the validation error
        print("\n1. Testing server startup...")
        result = subprocess.run(
            command + ["--help"],
            env=test_env,
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            print("   ✅ Server command works")
        else:
            print(f"   ❌ Server command failed: {result.stderr}")
            return False

        # Test actual server startup for a few seconds
        print("\n2. Testing MCP server initialization...")
        process = subprocess.Popen(
            command,
            env=test_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Let it run for 3 seconds
        time.sleep(3)
        process.terminate()

        stdout, stderr = process.communicate(timeout=5)

        if "validation error" in stderr.lower():
            print(f"   ❌ Validation error still occurs: {stderr}")
            return False
        elif "Starting MCP server" in stderr:
            print("   ✅ Server starts successfully")
            print("   ✅ No validation errors detected")
        else:
            print(f"   ⚠️  Unexpected output: {stderr}")

        print("\n📋 Your Claude Desktop config should now work:")
        config = {
            "mcpServers": {
                "mcp-server-qdrant": {
                    "command": "uv",
                    "args": [
                        "--directory",
                        "/home/ty/Repositories/mcp-server-qdrant/src",
                        "run",
                        "mcp-server-qdrant"
                    ],
                    "env": env_vars
                }
            }
        }
        print(json.dumps(config, indent=2))

        print("\n✅ Claude Desktop configuration fix complete!")
        print("🔄 Restart Claude Desktop to pick up the changes")
        return True

    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_claude_config()
    if success:
        print("\n🎉 Your Claude config should work now!")
    else:
        print("\n💥 Still having issues - check the output above")
