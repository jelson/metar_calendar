"""
Storage abstraction for METAR data.

Provides a common interface for storing and retrieving files,
with multiple backend implementations.
"""
import os
import tempfile
from abc import ABC, abstractmethod
from typing import Optional

import boto3
from botocore.exceptions import ClientError


class Storage(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    def get(self, filename: str) -> Optional[bytes]:
        """
        Retrieve a file from storage.

        Args:
            filename: Name of the file to retrieve

        Returns:
            File contents as bytes, or None if file doesn't exist

        Raises:
            IOError: If there's an error reading the file
        """
        pass

    @abstractmethod
    def put(self, filename: str, data: bytes) -> None:
        """
        Store a file in storage.

        Args:
            filename: Name of the file to store
            data: File contents as bytes

        Raises:
            IOError: If there's an error writing the file
        """
        pass


class LocalFileStorage(Storage):
    """
    Local filesystem storage implementation.

    Stores files in a specified directory on the local filesystem.
    Uses atomic writes (write to .tmp, then rename) to ensure consistency.
    """

    def __init__(self, base_dir: str):
        self.base_dir = base_dir

        # Create base directory if it doesn't exist
        if not os.path.exists(base_dir):
            os.makedirs(base_dir, exist_ok=True)

    def get(self, filename: str) -> Optional[bytes]:
        path = os.path.join(self.base_dir, filename)

        if not os.path.exists(path):
            return None

        with open(path, 'rb') as f:
            return f.read()

    def put(self, filename: str, data: bytes) -> None:
        """Atomic write using temporary file + rename."""
        path = os.path.join(self.base_dir, filename)

        # Create a unique temporary file in the same directory to ensure atomic rename works
        # (rename is only atomic when source and destination are on the same filesystem)
        fd, temp_path = tempfile.mkstemp(dir=self.base_dir, prefix='.tmp_', suffix='')

        try:
            # Write to temporary file
            with os.fdopen(fd, 'wb') as f:
                f.write(data)

            # Atomic rename (overwrites destination if it exists)
            os.rename(temp_path, path)
        except Exception:
            # Clean up temp file if something went wrong
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise


class S3Storage(Storage):
    """Amazon S3 storage implementation."""

    def __init__(self, bucket_name: str, prefix: str = '', **kwargs):
        """
        Initialize S3 storage.

        Args:
            bucket_name: Name of the S3 bucket
            prefix: Optional prefix (folder) for all keys
            **kwargs: Additional arguments passed to boto3.client()
                     (e.g., aws_access_key_id, aws_secret_access_key, region_name)
        """
        self.bucket_name = bucket_name
        self.prefix = prefix.rstrip('/') + '/' if prefix else ''
        self.s3_client = boto3.client('s3', **kwargs)

    def _get_key(self, filename: str) -> str:
        """Get the full S3 key for a filename."""
        return self.prefix + filename

    def get(self, filename: str) -> Optional[bytes]:
        key = self._get_key(filename)

        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            return response['Body'].read()
        except ClientError as e:
            # If the error is 404 (NoSuchKey), return None
            if e.response['Error']['Code'] == 'NoSuchKey':
                return None
            # Re-raise other errors
            raise

    def put(self, filename: str, data: bytes) -> None:
        """S3 PUT operations are atomic by default."""
        key = self._get_key(filename)
        self.s3_client.put_object(Bucket=self.bucket_name, Key=key, Body=data)
