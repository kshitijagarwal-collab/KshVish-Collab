from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID


def get_uploads_dir() -> Path:
    raw = os.environ.get("UPLOADS_DIR", "./data/uploads")
    path = Path(raw)
    path.mkdir(parents=True, exist_ok=True)
    return path


def store_upload(document_id: UUID, original_filename: str, payload: bytes) -> str:
    uploads = get_uploads_dir()
    suffix = Path(original_filename).suffix or ""
    target = uploads / f"{document_id}{suffix}"
    target.write_bytes(payload)
    return f"file://{target.resolve()}"
