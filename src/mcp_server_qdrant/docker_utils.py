import subprocess
import time
import os
import requests
import logging

logger = logging.getLogger(__name__)

QDRANT_CONTAINER_NAME = "qdrant_mcp_server"

def is_qdrant_container_running():
    """Checks if the Qdrant Docker container is running."""
    try:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", QDRANT_CONTAINER_NAME],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip() == "true"
    except subprocess.CalledProcessError:
        return False

def start_qdrant_container():
    """Starts the Qdrant Docker container if it's not already running."""
    if is_qdrant_container_running():
        logger.info(f"Qdrant container '{QDRANT_CONTAINER_NAME}' is already running.")
        return

    logger.info(f"Starting Qdrant container '{QDRANT_CONTAINER_NAME}'...")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
    qdrant_storage_path = os.path.join(project_root, "qdrant_storage")

    # Ensure the qdrant_storage directory exists
    os.makedirs(qdrant_storage_path, exist_ok=True)

    command = [
        "docker", "run", "-d",
        "--name", QDRANT_CONTAINER_NAME,
        "-p", "6333:6333",
        "-p", "6334:6334",
        "-v", f"{qdrant_storage_path}:/qdrant/storage:z",
        "qdrant/qdrant"
    ]

    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        logger.info(f"Qdrant container '{QDRANT_CONTAINER_NAME}' started successfully.")
        wait_for_qdrant_ready()
    except subprocess.CalledProcessError as e:
        logger.error(f"Error starting Qdrant container: {e}")
        logger.error(f"Stdout: {e.stdout}")
        logger.error(f"Stderr: {e.stderr}")
        # Attempt to remove the container if it exists but failed to start (e.g., name conflict)
        if "The container name" in e.stderr and "is already in use" in e.stderr:
            logger.warning(f"Container '{QDRANT_CONTAINER_NAME}' already exists. Attempting to remove and restart...")
            try:
                subprocess.run(["docker", "rm", "-f", QDRANT_CONTAINER_NAME], check=True, capture_output=True, text=True)
                logger.info(f"Removed existing container '{QDRANT_CONTAINER_NAME}'. Retrying start...")
                subprocess.run(command, check=True, capture_output=True, text=True)
                logger.info(f"Qdrant container '{QDRANT_CONTAINER_NAME}' started successfully after retry.")
                wait_for_qdrant_ready()
            except Exception as retry_e:
                logger.error(f"Failed to start Qdrant container even after retry: {retry_e}")
        else:
            raise

def wait_for_qdrant_ready(timeout=60, interval=1):
    """Waits until the Qdrant service is ready."""
    qdrant_url = "http://localhost:6333/readyz"
    start_time = time.time()
    logger.info(f"Waiting for Qdrant to be ready at {qdrant_url}...")
    while time.time() - start_time < timeout:
        try:
            response = requests.get(qdrant_url, timeout=interval)
            if response.status_code == 200:
                # Qdrant health endpoints return plain text, not JSON
                # /readyz returns "all shards are ready" when fully ready
                response_text = response.text.strip().lower()
                if "ready" in response_text:
                    logger.info("Qdrant is ready!")
                    return
        except requests.exceptions.ConnectionError:
            pass  # Qdrant not yet available
        except Exception as e:
            logger.error(f"Error checking Qdrant health: {e}")
        time.sleep(interval)
    raise RuntimeError("Qdrant did not become ready in time.")

def stop_qdrant_container():
    """Stops the Qdrant Docker container."""
    if not is_qdrant_container_running():
        logger.info(f"Qdrant container '{QDRANT_CONTAINER_NAME}' is not running.")
        return

    logger.info(f"Stopping Qdrant container '{QDRANT_CONTAINER_NAME}'...")
    try:
        subprocess.run(["docker", "stop", QDRANT_CONTAINER_NAME], check=True, capture_output=True, text=True)
        logger.info(f"Qdrant container '{QDRANT_CONTAINER_NAME}' stopped successfully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error stopping Qdrant container: {e}")
        logger.error(f"Stdout: {e.stdout}")
        logger.error(f"Stderr: {e.stderr}")
        raise
