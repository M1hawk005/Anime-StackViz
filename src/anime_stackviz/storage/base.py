"""Storage interface.

Callers depend only on this interface, so the raw cache and warehouse can move
from local disk to an object store (S3/GCS) by swapping the implementation. No
downstream code changes and there is no vendor lock-in.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator


class Storage(ABC):
    """A minimal key/blob store with JSON and text convenience helpers.

    Keys are POSIX-style relative paths (``anilist/media/page-0001.json``). An
    implementation maps them onto a filesystem prefix, a bucket, etc.
    """

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def read_bytes(self, key: str) -> bytes: ...

    @abstractmethod
    def write_bytes(self, key: str, data: bytes) -> None: ...

    @abstractmethod
    def list_keys(self, prefix: str) -> Iterator[str]: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    # -- convenience helpers -------------------------------------------------

    def read_text(self, key: str, encoding: str = "utf-8") -> str:
        return self.read_bytes(key).decode(encoding)

    def write_text(self, key: str, text: str, encoding: str = "utf-8") -> None:
        self.write_bytes(key, text.encode(encoding))

    def read_json(self, key: str) -> object:
        import json

        return json.loads(self.read_text(key))

    def write_json(self, key: str, value: object) -> None:
        import json

        self.write_text(key, json.dumps(value, indent=2, ensure_ascii=False))
