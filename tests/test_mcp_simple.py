#!/usr/bin/env python3
"""
Simple test to debug the exact MCP stdio issue.
"""

import subprocess
import sys
import os
import json
import time

def test_mcp_stdio():
    """Test basic MCP stdio communication."""

    print("🔍 Debugging MCP stdio communication...")

    # Set up environment
    env = os.environ.copy()
    env.update({
        "QDRANT_MODE": "embedded",
        "MCP_CLIENT": "debug",
        "PYTHONPATH": str(os.path.join(os.getcwd(), "src"))
    })

    # Start the server
    cmd = [sys.executable, "-m", "mcp_server_qdrant.main", "--transport", "stdio"]

    print(f"Starting: {' '.join(cmd)}")
    print("Environment: QDRANT_MODE=embedded, MCP_CLIENT=debug")

    try:
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
            bufsize=0  # Unbuffered
        )

        print("✅ Process started")

        # Give the server a moment to initialize
        time.sleep(2)

        # Check if process is still running
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            print(f"❌ Process exited early with code: {process.returncode}")
            print(f"Stdout: {stdout}")
            print(f"Stderr: {stderr}")
            return False

        print("✅ Process is running")

        # Send a very simple initialize message
        init_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"}
            }
        }

        message = json.dumps(init_msg) + "\n"
        print(f"Sending: {message.strip()}")

        try:
            process.stdin.write(message)
            process.stdin.flush()
            print("✅ Message sent successfully")
        except BrokenPipeError:
            print("❌ BrokenPipeError when sending message")
            stdout, stderr = process.communicate()
            print(f"Stdout: {stdout}")
            print(f"Stderr: {stderr}")
            return False

        # Try to read response with timeout
        import select

        # Wait for response (with timeout)
        timeout = 5
        start_time = time.time()

        while time.time() - start_time < timeout:
            if process.poll() is not None:
                print(f"❌ Process exited during communication with code: {process.returncode}")
                stdout, stderr = process.communicate()
                print(f"Stdout: {stdout}")
                print(f"Stderr: {stderr}")
                return False

            # Check for output (Unix only)
            if hasattr(select, 'select'):
                ready, _, _ = select.select([process.stdout], [], [], 0.1)
                if ready:
                    try:
                        line = process.stdout.readline()
                        if line:
                            print(f"📥 Response: {line.strip()}")
                            # Try to parse as JSON
                            try:
                                response = json.loads(line)
                                if response.get("id") == 1:
                                    print("✅ Got valid MCP response!")
                                    break
                            except json.JSONDecodeError:
                                print("⚠️  Response is not valid JSON")
                                continue
                    except Exception as e:
                        print(f"❌ Error reading stdout: {e}")
                        break
            else:
                time.sleep(0.1)
        else:
            print("⚠️  Timeout waiting for response")

        # Clean shutdown
        print("🔄 Attempting graceful shutdown...")
        try:
            process.terminate()
            process.wait(timeout=3)
            print("✅ Process terminated gracefully")
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            print("⚠️  Process had to be killed")

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_mcp_stdio()
    print(f"\n{'✅ SUCCESS' if success else '❌ FAILED'}")
