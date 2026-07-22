"""Filesystem-backed :class:`Storage`."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path, PurePosixPath

from .base import Storage


class LocalStorage(Storage):
    """Store blobs under a root directory, keyed by POSIX-style relative paths.

    Writes are atomic (write-to-temp then replace) so an interrupted run never
    leaves a half-written cache entry that a resume would trust.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        # Normalise the POSIX key onto the local filesystem separator.
        return self.root.joinpath(*PurePosixPath(key).parts)

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def read_bytes(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def write_bytes(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.tmp")
        tmp.write_bytes(data)
        tmp.replace(path)

    def list_keys(self, prefix: str) -> Iterator[str]:
        base = self._path(prefix)
        if not base.exists():
            return
        for path in sorted(base.rglob("*")):
            if path.is_file() and path.suffix != ".tmp":
                yield path.relative_to(self.root).as_posix()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)
