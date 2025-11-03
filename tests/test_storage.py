import os
import tempfile
import pytest
import boto3
from moto import mock_aws

from lib.storage import Storage, LocalFileStorage, S3Storage


@pytest.fixture
def local_storage():
    """Create a LocalFileStorage instance for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield LocalFileStorage(tmpdir)


@pytest.fixture
def s3_storage():
    """Create an S3Storage instance for testing."""
    bucket_name = 'test-metar-bucket'
    with mock_aws():
        client = boto3.client('s3', region_name='us-east-1')
        client.create_bucket(Bucket=bucket_name)
        yield S3Storage(bucket_name, region_name='us-east-1')


@pytest.fixture(params=['local', 's3'])
def storage(request, local_storage, s3_storage):
    """Parametrized fixture that provides both storage backends."""
    return local_storage if request.param == 'local' else s3_storage


class TestStorage:
    """Tests that run against both LocalFileStorage and S3Storage."""

    def test_put_and_get(self, storage):
        """Test storing and retrieving a file."""
        filename = 'test.txt'
        data = b'Hello, World!'

        # Store the file
        storage.put(filename, data)

        # Retrieve the file
        result = storage.get(filename)

        assert result == data

    def test_get_nonexistent_file(self, storage):
        """Test retrieving a file that doesn't exist."""
        result = storage.get('nonexistent.txt')
        assert result is None

    def test_put_overwrites_existing(self, storage):
        """Test that put overwrites existing files."""
        filename = 'test.txt'
        original_data = b'Original content'
        new_data = b'New content'

        # Store original
        storage.put(filename, original_data)
        assert storage.get(filename) == original_data

        # Overwrite with new data
        storage.put(filename, new_data)
        assert storage.get(filename) == new_data

    def test_put_binary_data(self, storage):
        """Test storing and retrieving binary data."""
        filename = 'binary.dat'
        # Create some binary data with null bytes and high-value bytes
        data = bytes(range(256))

        storage.put(filename, data)
        result = storage.get(filename)

        assert result == data
        assert len(result) == 256

    def test_put_empty_file(self, storage):
        """Test storing and retrieving an empty file."""
        filename = 'empty.txt'
        data = b''

        storage.put(filename, data)
        result = storage.get(filename)

        assert result == data
        assert len(result) == 0

    def test_put_large_file(self, storage):
        """Test storing and retrieving a large file."""
        filename = 'large.bin'
        # Create 1MB of data
        data = b'x' * (1024 * 1024)

        storage.put(filename, data)
        result = storage.get(filename)

        assert result == data
        assert len(result) == 1024 * 1024

    def test_multiple_files(self, storage):
        """Test storing multiple files."""
        files = {
            'file1.txt': b'Content 1',
            'file2.txt': b'Content 2',
            'file3.txt': b'Content 3',
        }

        # Store all files
        for filename, data in files.items():
            storage.put(filename, data)

        # Retrieve and verify all files
        for filename, expected_data in files.items():
            result = storage.get(filename)
            assert result == expected_data

    def test_storage_is_abstract(self):
        """Test that Storage base class cannot be instantiated."""
        with pytest.raises(TypeError):
            Storage()  # Should raise TypeError because it's abstract


class TestLocalFileStorageSpecific:
    """Tests specific to LocalFileStorage implementation."""

    def test_init_creates_directory(self):
        """Test that storage creates base directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = os.path.join(tmpdir, 'new_storage_dir')
            assert not os.path.exists(new_dir)

            storage = LocalFileStorage(new_dir)

            assert os.path.exists(new_dir)
            assert os.path.isdir(new_dir)

    def test_put_atomic_write(self):
        """Test that put uses atomic write (tmp file + rename)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalFileStorage(tmpdir)
            filename = 'atomic.txt'
            data = b'Atomic content'

            # Store the file
            storage.put(filename, data)

            # Verify the final file exists
            final_path = os.path.join(tmpdir, filename)
            assert os.path.exists(final_path)

            # Verify the temp file doesn't exist
            temp_path = final_path + '.tmp'
            assert not os.path.exists(temp_path)

    def test_filename_with_subdirectory(self):
        """Test that filenames are treated as relative to base_dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalFileStorage(tmpdir)
            # Note: This tests current behavior - no subdirectory support
            filename = 'subdir/file.txt'
            data = b'Content'

            # This should fail or create a file named 'subdir/file.txt' in base_dir
            # depending on implementation
            with pytest.raises(FileNotFoundError):
                storage.put(filename, data)


class TestS3StorageSpecific:
    """Tests specific to S3Storage implementation."""

    def test_prefix_handling(self):
        """Test that prefix is correctly applied to keys."""
        bucket_name = 'test-prefix-bucket'
        prefix = 'test-prefix'

        with mock_aws():
            client = boto3.client('s3', region_name='us-east-1')
            client.create_bucket(Bucket=bucket_name)

            storage = S3Storage(bucket_name, prefix=prefix, region_name='us-east-1')

            filename = 'test.txt'
            data = b'Prefixed content'

            # Store with prefix
            storage.put(filename, data)

            # Verify the key in S3 includes the prefix
            expected_key = f'{prefix}/{filename}'
            response = client.get_object(Bucket=bucket_name, Key=expected_key)
            assert response['Body'].read() == data

            # Retrieve through storage interface
            result = storage.get(filename)
            assert result == data

    def test_prefix_with_trailing_slash(self):
        """Test that trailing slashes in prefix are handled correctly."""
        bucket_name = 'test-slash-bucket'

        with mock_aws():
            client = boto3.client('s3', region_name='us-east-1')
            client.create_bucket(Bucket=bucket_name)

            storage = S3Storage(bucket_name, prefix='folder/', region_name='us-east-1')

            filename = 'test.txt'
            data = b'Content'

            storage.put(filename, data)

            # Should create key as 'folder/test.txt', not 'folder//test.txt'
            expected_key = 'folder/test.txt'
            response = client.get_object(Bucket=bucket_name, Key=expected_key)
            assert response['Body'].read() == data

    def test_empty_prefix(self):
        """Test storage with empty prefix."""
        bucket_name = 'test-empty-prefix-bucket'

        with mock_aws():
            client = boto3.client('s3', region_name='us-east-1')
            client.create_bucket(Bucket=bucket_name)

            storage = S3Storage(bucket_name, prefix='', region_name='us-east-1')

            filename = 'test.txt'
            data = b'No prefix'

            storage.put(filename, data)

            # Key should be just the filename
            response = client.get_object(Bucket=bucket_name, Key=filename)
            assert response['Body'].read() == data
