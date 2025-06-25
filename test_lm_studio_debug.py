#!/usr/bin/env python3
"""
Test script to reproduce and debug LM Studio MCP connection issues.
"""

import asyncio
import sys
import os
import json
import subprocess
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

async def test_lm_studio_compatibility():
    """Test MCP server in a way that simulates LM Studio's usage."""

    print("🧪 Testing LM Studio MCP Compatibility...")

    print("1. Testing MCP server startup in stdio mode...")

    return_code = 1  # Default to error

    # Test stdio mode startup (what LM Studio uses)
    try:
        # Set environment variables like LM Studio would
        env = os.environ.copy()
        env.update({
            "QDRANT_MODE": "embedded",
            "QDRANT_COLLECTION_NAME": "lm_studio_test",
            "EMBEDDING_PROVIDER": "fastembed",
            "EMBEDDING_MODEL": "sentence-transformers/all-MiniLM-L6-v2",
            "MCP_CLIENT": "lm_studio"  # Flag to indicate MCP client usage
        })

        # Start the MCP server process
        cmd = [
            sys.executable,
            "-m", "mcp_server_qdrant.main",
            "--transport", "stdio"
        ]

        print(f"   Command: {' '.join(cmd)}")
        print("   Environment: QDRANT_MODE=embedded, MCP_CLIENT=lm_studio")

        # Start process with stdio pipes
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True
        )

        print("   ✅ Process started successfully")

        # Send a simple MCP initialization message
        init_message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "clientInfo": {
                    "name": "lm-studio-test",
                    "version": "1.0.0"
                }
            }
        }

        print("2. Testing MCP protocol initialization...")

        try:
            # Send initialization
            init_json = json.dumps(init_message) + "\n"
            if process.stdin:
                process.stdin.write(init_json)
                process.stdin.flush()

            # Wait for response with timeout
            import select
            import time

            timeout = 10  # 10 second timeout
            start_time = time.time()

            while time.time() - start_time < timeout:
                if process.poll() is not None:
                    # Process has terminated
                    break

                # Check if there's output available (Linux/macOS only)
                if hasattr(select, 'select') and process.stdout:
                    ready, _, _ = select.select([process.stdout], [], [], 0.1)
                    if ready:
                        line = process.stdout.readline()
                        if line:
                            print(f"   📥 Response: {line.strip()}")
                            try:
                                response = json.loads(line)
                                if response.get("id") == 1:
                                    print("   ✅ MCP initialization successful!")
                                    break
                            except json.JSONDecodeError:
                                continue
                else:
                    # Fallback for Windows or when select is not available
                    time.sleep(0.1)
            else:
                print("   ⚠️  Timeout waiting for MCP initialization response")

        except Exception as e:
            print(f"   ❌ Error during MCP communication: {e}")

        # Clean shutdown
        print("3. Testing graceful shutdown...")
        try:
            # Send shutdown notification
            shutdown_message = {
                "jsonrpc": "2.0",
                "method": "shutdown",
                "params": {}
            }
            shutdown_json = json.dumps(shutdown_message) + "\n"
            if process.stdin:
                process.stdin.write(shutdown_json)
                process.stdin.flush()
                process.stdin.close()

            # Wait for process to terminate
            return_code = process.wait(timeout=5)
            print(f"   ✅ Process terminated gracefully with code: {return_code}")

        except subprocess.TimeoutExpired:
            print("   ⚠️  Process didn't terminate gracefully, forcing shutdown...")
            process.terminate()
            try:
                return_code = process.wait(timeout=2)
                print("   ✅ Process terminated after SIGTERM")
            except subprocess.TimeoutExpired:
                process.kill()
                return_code = process.wait()
                print("   ⚠️  Process killed after timeout")

        # Check for errors
        if process.stderr:
            stderr_output = process.stderr.read()
            if stderr_output:
                print(f"   📋 Stderr output: {stderr_output}")

                # Check for specific LM Studio issues
                if "Connection closed" in stderr_output:
                    print("   🔍 Detected 'Connection closed' error - this matches LM Studio issue")
                if "MCP error -32000" in stderr_output:
                    print("   🔍 Detected MCP error -32000 - connection protocol issue")

        print("\n4. Analysis and Recommendations:")

        if return_code == 0:
            print("   ✅ Server starts and shuts down cleanly")
            print("   ✅ Compatible with MCP stdio protocol")
            print("   💡 If LM Studio still has issues, try:")
            print("      - Check LM Studio's MCP configuration syntax")
            print("      - Ensure Python path is correct in LM Studio config")
            print("      - Try different embedding models")
        else:
            print("   ❌ Server had issues during startup/shutdown")
            print("   💡 Potential fixes:")
            print("      - Check environment variable compatibility")
            print("      - Verify Qdrant embedded mode works")
            print("      - Check for port conflicts")

        return return_code == 0

    except Exception as e:
        print(f"   ❌ Failed to test MCP compatibility: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_lm_studio_config_example():
    """Create an example LM Studio configuration."""

    config = {
        "mcpServers": {
            "mcp-server-qdrant": {
                "command": "uv",
                "args": [
                    "--directory",
                    "/home/your-username/Repositories/mcp-server-qdrant/src",
                    "run",
                    "mcp-server-qdrant",
                    "--transport",
                    "stdio"
                ],
                "env": {
                    "QDRANT_MODE": "embedded",
                    "QDRANT_COLLECTION_NAME": "lm_studio_memories",
                    "QDRANT_ENABLE_COLLECTION_MANAGEMENT": "true",
                    "QDRANT_ENABLE_DYNAMIC_EMBEDDING_MODELS": "true",
                    "QDRANT_ENABLE_RESOURCES": "true"
                }
            }
        }
    }

    print("\n📋 LM Studio Configuration Example:")
    print("Add this to your LM Studio MCP settings:")
    print("```json")
    print(json.dumps(config, indent=2))
    print("```")

    print("\n🔧 Alternative: Using uvx (if installed globally):")
    print("```json")
    alt_config = {
        "mcpServers": {
            "mcp-server-qdrant": {
                "command": "uvx",
                "args": ["mcp-server-qdrant", "--transport", "stdio"],
                "env": {
                    "QDRANT_MODE": "embedded",
                    "QDRANT_COLLECTION_NAME": "lm_studio_memories",
                    "QDRANT_ENABLE_COLLECTION_MANAGEMENT": "true",
                    "QDRANT_ENABLE_DYNAMIC_EMBEDDING_MODELS": "true",
                    "QDRANT_ENABLE_RESOURCES": "true"
                }
            }
        }
    }
    print(json.dumps(alt_config, indent=2))
    print("```")

if __name__ == "__main__":
    success = asyncio.run(test_lm_studio_compatibility())

    create_lm_studio_config_example()

    if success:
        print("\n🎉 MCP server appears compatible with LM Studio!")
        print("💡 If you're still having issues:")
        print("   1. Check that Python path is correct in LM Studio config")
        print("   2. Ensure all environment variables are set properly")
        print("   3. Try the embedded mode first (simplest setup)")
    else:
        print("\n💥 Found compatibility issues that need fixing")
        print("📝 Please share the output above for debugging")
