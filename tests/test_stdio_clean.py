#!/usr/bin/env python3
"""
Simple test to verify MCP stdio mode works without stdout contamination.
"""

import subprocess
import sys
import json
import time
import os

def test_mcp_stdio_clean():
    """Test that MCP server starts cleanly in stdio mode."""

    print("🧪 Testing Clean MCP stdio Startup...")

    # Test command that LM Studio would use
    cmd = [
        sys.executable, "-m", "mcp_server_qdrant.main",
        "--transport", "stdio"
    ]

    env = {
        "QDRANT_MODE": "embedded",
        "MCP_CLIENT": "lm_studio",
        "QDRANT_COLLECTION_NAME": "test_collection",
        "EMBEDDING_PROVIDER": "fastembed",
        "EMBEDDING_MODEL": "sentence-transformers/all-MiniLM-L6-v2"
    }

    try:
        print(f"   Command: {' '.join(cmd)}")
        print(f"   Environment: {', '.join([f'{k}={v}' for k, v in env.items()])}")

        # Start the process
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**dict(os.environ), **env}
        )

        # Send MCP initialization
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }

        init_json = json.dumps(init_request) + "\n"
        print(f"   Sending: {init_json.strip()}")

        # Send the request (stdin should not be None with our Popen config)
        if process.stdin:
            process.stdin.write(init_json)
            process.stdin.flush()

        # Wait a bit for response
        time.sleep(2)

        # Check if process is still running
        if process.poll() is None:
            print("   ✅ Process is running")

            # Try to read any output
            stdout_data = ""
            stderr_data = ""

            # Set non-blocking and read available data
            if process.stdout and process.stderr:
                try:
                    os.set_blocking(process.stdout.fileno(), False)
                    os.set_blocking(process.stderr.fileno(), False)

                    stdout_data = process.stdout.read() or ""
                    stderr_data = process.stderr.read() or ""
                except Exception as e:
                    print(f"   Warning: Could not read output: {e}")

            print(f"   Stdout: {repr(stdout_data[:200])}")
            print(f"   Stderr: {repr(stderr_data[:200])}")

            if stdout_data and not stdout_data.startswith('{"jsonrpc"'):
                print("   ⚠️  Non-JSON output detected in stdout")
            else:
                print("   ✅ Clean stdout (no contamination)")

            # Terminate process
            process.terminate()
            process.wait(timeout=5)

            return True
        else:
            # Process exited
            stdout_data, stderr_data = process.communicate()
            print(f"   ❌ Process exited with code: {process.returncode}")
            print(f"   Stdout: {stdout_data}")
            print(f"   Stderr: {stderr_data}")
            return False

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = test_mcp_stdio_clean()
    if success:
        print("\n✅ MCP stdio mode works cleanly!")
        print("🔧 LM Studio should be able to connect without issues")
    else:
        print("\n❌ Issues detected with MCP stdio mode")
