# ai_engine/ollama_runner.py
import subprocess
import socket
import time
import logging
import requests  # Add this import


logger = logging.getLogger(__name__)


OLLAMA_HOST = "127.0.0.1"
OLLAMA_PORT = 11434
MODEL_NAME = "llama3.2:latest"  # Your model


def _is_ollama_running(host=OLLAMA_HOST, port=OLLAMA_PORT) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def preload_model():
    """Preload model and keep it loaded forever (no more cold starts)"""
    url = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/generate"
    payload = {
        "model": MODEL_NAME,
        "prompt": "preload: say nothing",
        "stream": False,
        "options": {"keep_alive": -1}  # -1 = forever in memory
    }
    try:
        response = requests.post(url, json=payload, timeout=120)  # 2min for first load
        if response.status_code == 200:
            logger.info(f"{MODEL_NAME} preloaded and kept in memory!")
            return True
        else:
            logger.error(f"Preload failed: {response.status_code}")
            return False
    except requests.exceptions.Timeout:
        logger.error("Model preload timed out - too slow hardware?")
        return False
    except Exception as e:
        logger.error(f"Preload error: {e}")
        return False


def ensure_ollama_running():
    """
    Start Ollama + preload model to eliminate cold starts & timeouts.
    """
    if not _is_ollama_running():
        logger.info("Ollama not running, starting...")
        try:
            subprocess.Popen(["ollama", "serve"], shell=True)
            # Wait longer for startup (20s)
            for _ in range(20):
                if _is_ollama_running():
                    logger.info("Ollama server started.")
                    break
                time.sleep(1)
            else:
                logger.error("Ollama server failed to start.")
                return False
        except Exception as e:
            logger.error(f"Failed to start Ollama: {type(e).__name__}: {e}")
            return False

    # Now preload model (this fixes your timeouts)
    logger.info("Preloading model...")
    if preload_model():
        logger.info("Ollama fully ready - no more cold starts!")
    else:
        logger.warning("Ollama running but model preload failed.")


# Usage: Call ensure_ollama_running() at Django startup (e.g., apps.py ready())