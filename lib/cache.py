"""
Caching layer using the Storage abstraction.

Provides a simple cache-aside pattern where data is retrieved from storage
if available, otherwise fetched using a retriever function and then stored.
"""
from typing import Callable

from lib.storage import Storage


class Cache:
    """
    Cache implementation using a storage backend.

    Uses a cache-aside pattern: checks storage first, and if not found,
    executes a retriever function to fetch the data and stores it.
    """

    def __init__(self, storage: Storage):
        """
        Initialize cache with a storage backend.

        Args:
            storage: Storage instance to use for caching
        """
        self.storage = storage

    def get(self, filename: str, retriever: Callable[[], bytes]) -> bytes:
        """
        Get data from cache or retrieve and store it.

        Args:
            filename: Name of the file to retrieve
            retriever: Function that returns bytes if data not in cache

        Returns:
            Cached or retrieved data as bytes
        """
        # Try to get from cache
        data = self.storage.get(filename)

        if data is not None:
            return data

        # Not in cache - retrieve the data
        data = retriever()

        # Store in cache for next time
        self.storage.put(filename, data)

        return data


class NoOpCache(Cache):
    """Cache implementation that never caches - always fetches fresh data."""

    class _NoOpStorage(Storage):
        """Internal storage that never stores or retrieves anything."""

        def get(self, filename: str):
            return None  # Always miss, forcing fresh fetch

        def put(self, filename: str, data: bytes):
            pass  # Don't actually store anything

    def __init__(self):
        """Initialize a no-op cache that always fetches fresh data."""
        super().__init__(self._NoOpStorage())
