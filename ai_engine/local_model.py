"""Private Ollama client shared by all local legal AI features."""
import ipaddress
import logging
import os
from urllib.parse import urlsplit

import requests

logger = logging.getLogger(__name__)

OLLAMA_API_URL = os.getenv(
    "OLLAMA_API_URL", "http://ollama.railway.internal:11434/api/generate"
).strip()
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b").strip()


def _is_private_endpoint(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            return False
        host = parsed.hostname.lower().rstrip(".")
        if host in {"localhost", "ollama", "host.docker.internal"} or host.endswith(
            (".localhost", ".local", ".railway.internal")
        ):
            return True
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            return False
        return address.is_private or address.is_loopback
    except (TypeError, ValueError):
        return False


def generate_local(prompt: str, *, system: str = "", timeout: int = 180) -> str | None:
    """Generate text only through a local/private Ollama endpoint."""
    if not prompt or not _is_private_endpoint(OLLAMA_API_URL):
        if OLLAMA_API_URL:
            logger.error("Ollama URL must be a loopback, private, or Railway internal address")
        return None
    try:
        response = requests.post(
            OLLAMA_API_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "system": system,
                "stream": False,
                "options": {"temperature": 0.3},
            },
            timeout=(3, timeout),
            allow_redirects=False,
        )
        response.raise_for_status()
        result = response.json().get("response", "").strip()
        return result or None
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Private Ollama model unavailable: %s", type(exc).__name__)
        return None
