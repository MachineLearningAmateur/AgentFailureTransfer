"""SHA-256 helpers. Hashes, not timestamps, are the identity of an artifact."""

from __future__ import annotations

import hashlib
from pathlib import Path

_CHUNK = 1024 * 1024


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            chunk = handle.read(_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()
