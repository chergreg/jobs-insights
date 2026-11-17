"""Requêtes HTTP communes à toutes les sources."""

from __future__ import annotations

import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen


USER_AGENT = "jobs-insights-atelier/1.0 (educational project)"
MAX_RESPONSE_BYTES = 10_000_000
RETRY_STATUS_CODES = {429, 503}
RETRY_WAIT_SECONDS = 30


def fetch_url(url: str, accept: str) -> bytes:
    """Télécharge une URL. Réessaie une fois après 30 s sur HTTP 429 ou 503."""
    request = Request(url, headers={"Accept": accept, "User-Agent": USER_AGENT})
    for attempt in (1, 2):
        try:
            with urlopen(request, timeout=30) as response:
                content = response.read(MAX_RESPONSE_BYTES + 1)
            break
        except HTTPError as error:
            if attempt == 1 and error.code in RETRY_STATUS_CODES:
                time.sleep(RETRY_WAIT_SECONDS)
                continue
            raise

    if len(content) > MAX_RESPONSE_BYTES:
        raise ValueError(f"Réponse trop volumineuse (plus de {MAX_RESPONSE_BYTES} octets).")
    return content
