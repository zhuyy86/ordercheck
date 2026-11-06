"""Publish a complete local report without replacing another report."""
import os
from pathlib import Path
import tempfile


def publish_report(path: Path, payload: bytes) -> None:
    """Stage, sync and exclusively publish bytes on one filesystem.

    The final name is absent until all bytes are written. Hard-link creation
    fails if another writer (or a symlink) already owns that name. Filesystems
    without hard links fail closed; this is not a power-loss durability promise.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".ordercheck-", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
