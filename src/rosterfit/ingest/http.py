"""Polite, disk-cached HTTP fetching.

Every response is cached under data/raw so the pipeline is reproducible and we
never hit a source twice for the same page. Requests to each host are spaced
out to respect published rate limits.
"""
from __future__ import annotations

import hashlib
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

from rosterfit.config import BREF_DELAY_SECONDS, RAW_DIR, USER_AGENT

_last_hit: dict[str, float] = {}
_HOST_DELAY = {"www.basketball-reference.com": BREF_DELAY_SECONDS, "barttorvik.com": 1.5}


def _cache_path(url: str, suffix: str) -> Path:
    host = urlparse(url).netloc.replace("www.", "")
    digest = hashlib.sha1(url.encode()).hexdigest()[:16]
    slug = urlparse(url).path.strip("/").replace("/", "_")[:60] or "index"
    return RAW_DIR / host / f"{slug}_{digest}{suffix}"


def fetch(url: str, *, suffix: str = ".html", refresh: bool = False, timeout: int = 45) -> str:
    """Return the body of ``url``, from cache unless ``refresh`` is set."""
    path = _cache_path(url, suffix)
    if path.exists() and not refresh:
        return path.read_text(encoding="utf-8")

    host = urlparse(url).netloc
    wait = _HOST_DELAY.get(host, 0.5) - (time.monotonic() - _last_hit.get(host, 0.0))
    if wait > 0:
        time.sleep(wait)

    for attempt in range(4):
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        except (requests.ConnectionError, requests.Timeout):
            _last_hit[host] = time.monotonic()
            time.sleep(10 * (attempt + 1))
            continue
        _last_hit[host] = time.monotonic()
        if resp.status_code == 429:  # back off hard if asked to
            time.sleep(60 * (attempt + 1))
            continue
        resp.raise_for_status()
        path.parent.mkdir(parents=True, exist_ok=True)
        # requests defaults text/html without a charset to ISO-8859-1; these sources are UTF-8.
        try:
            text = resp.content.decode("utf-8")
        except UnicodeDecodeError:
            text = resp.content.decode(resp.apparent_encoding or "latin-1", errors="replace")
        path.write_text(text, encoding="utf-8")
        return text
    raise RuntimeError(f"Failed repeatedly fetching {url}")
