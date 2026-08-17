"""Storage abstraction - local filesystem with Azure Blob placeholder."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod


class StorageBackend(ABC):
    """Abstract storage backend."""

    @abstractmethod
    def save(self, local_path: str, remote_key: str) -> str:
        """Save a file and return the storage path/URL."""
        ...

    @abstractmethod
    def exists(self, remote_key: str) -> bool:
        """Check if a file exists in storage."""
        ...

    @abstractmethod
    def load(self, remote_key: str, local_path: str) -> str:
        """Download a file from storage to local path."""
        ...


class LocalStorage(StorageBackend):
    """Local filesystem storage."""

    def __init__(self, base_dir: str = "downloads"):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    def save(self, local_path: str, remote_key: str) -> str:
        """Copy file to local storage directory."""
        dest = os.path.join(self.base_dir, remote_key)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if local_path != dest:
            import shutil
            shutil.copy2(local_path, dest)
        return dest

    def exists(self, remote_key: str) -> bool:
        return os.path.exists(os.path.join(self.base_dir, remote_key))

    def load(self, remote_key: str, local_path: str) -> str:
        src = os.path.join(self.base_dir, remote_key)
        if os.path.exists(src):
            import shutil
            shutil.copy2(src, local_path)
            return local_path
        raise FileNotFoundError(f"File not found: {src}")


class AzureBlobStorage(StorageBackend):
    """Azure Blob Storage backend (placeholder)."""

    def __init__(self, connection_string: str, container: str):
        self.connection_string = connection_string
        self.container = container

    def save(self, local_path: str, remote_key: str) -> str:
        raise NotImplementedError("Azure Blob Storage not yet implemented")

    def exists(self, remote_key: str) -> bool:
        raise NotImplementedError("Azure Blob Storage not yet implemented")

    def load(self, remote_key: str, local_path: str) -> str:
        raise NotImplementedError("Azure Blob Storage not yet implemented")


def get_storage(backend: str = "local", **kwargs) -> StorageBackend:
    """Factory for storage backends."""
    if backend == "local":
        return LocalStorage(base_dir=kwargs.get("base_dir", "downloads"))
    elif backend == "azure":
        return AzureBlobStorage(
            connection_string=kwargs.get("connection_string", ""),
            container=kwargs.get("container", "scrap-snaps"),
        )
    raise ValueError(f"Unknown storage backend: {backend}")
