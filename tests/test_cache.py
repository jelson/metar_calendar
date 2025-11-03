import tempfile
import pytest
import boto3
from moto import mock_aws

from lib.cache import Cache
from lib.storage import LocalFileStorage, S3Storage


@pytest.fixture
def local_storage():
    """Create a LocalFileStorage instance for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield LocalFileStorage(tmpdir)


@pytest.fixture
def s3_storage():
    """Create an S3Storage instance for testing."""
    bucket_name = 'test-cache-bucket'
    with mock_aws():
        client = boto3.client('s3', region_name='us-east-1')
        client.create_bucket(Bucket=bucket_name)
        yield S3Storage(bucket_name, region_name='us-east-1')


@pytest.fixture(params=['local', 's3'])
def storage(request, local_storage, s3_storage):
    """Parametrized fixture that provides both storage backends."""
    if request.param == 'local':
        return local_storage
    else:
        return s3_storage


@pytest.fixture
def cache(storage):
    """Create a Cache instance with the parametrized storage backend."""
    return Cache(storage)


class TestCache:
    def test_cache_miss_calls_retriever(self, cache):
        """Test that retriever is called when data not in cache."""
        filename = 'test.txt'
        expected_data = b'Retrieved data'
        retriever_called = []

        def retriever():
            retriever_called.append(True)
            return expected_data

        # First call should invoke retriever
        result = cache.get(filename, retriever)

        assert result == expected_data
        assert len(retriever_called) == 1

    def test_cache_hit_skips_retriever(self, cache):
        """Test that retriever is not called when data is in cache."""
        filename = 'test.txt'
        cached_data = b'Cached data'
        retriever_called = []

        def retriever():
            retriever_called.append(True)
            return b'Should not be called'

        # Pre-populate cache
        cache.storage.put(filename, cached_data)

        # Get should return cached data without calling retriever
        result = cache.get(filename, retriever)

        assert result == cached_data
        assert len(retriever_called) == 0

    def test_multiple_calls_same_file(self, cache):
        """Test that retriever is only called once for multiple requests."""
        filename = 'test.txt'
        expected_data = b'Data'
        call_count = []

        def retriever():
            call_count.append(True)
            return expected_data

        # First call
        result1 = cache.get(filename, retriever)
        assert result1 == expected_data
        assert len(call_count) == 1

        # Second call should use cached data
        result2 = cache.get(filename, retriever)
        assert result2 == expected_data
        assert len(call_count) == 1  # Still only 1 call

    def test_different_files_independent(self, cache):
        """Test that different files are cached independently."""
        file1 = 'file1.txt'
        file2 = 'file2.txt'
        data1 = b'Data 1'
        data2 = b'Data 2'

        retriever1_called = []
        retriever2_called = []

        def retriever1():
            retriever1_called.append(True)
            return data1

        def retriever2():
            retriever2_called.append(True)
            return data2

        # Get file1
        result1 = cache.get(file1, retriever1)
        assert result1 == data1
        assert len(retriever1_called) == 1
        assert len(retriever2_called) == 0

        # Get file2
        result2 = cache.get(file2, retriever2)
        assert result2 == data2
        assert len(retriever1_called) == 1
        assert len(retriever2_called) == 1

        # Get file1 again (should be cached)
        result1_again = cache.get(file1, retriever1)
        assert result1_again == data1
        assert len(retriever1_called) == 1  # No additional call

    def test_cache_stores_binary_data(self, cache):
        """Test that cache correctly handles binary data."""
        filename = 'binary.dat'
        binary_data = bytes(range(256))

        def retriever():
            return binary_data

        result = cache.get(filename, retriever)
        assert result == binary_data

        # Verify it's stored correctly
        result2 = cache.get(filename, retriever)
        assert result2 == binary_data

    def test_cache_stores_empty_data(self, cache):
        """Test that cache handles empty byte strings."""
        filename = 'empty.txt'
        empty_data = b''

        def retriever():
            return empty_data

        result = cache.get(filename, retriever)
        assert result == empty_data
        assert len(result) == 0

    def test_cache_stores_large_data(self, cache):
        """Test that cache handles large data."""
        filename = 'large.bin'
        large_data = b'x' * (1024 * 1024)  # 1MB

        def retriever():
            return large_data

        result = cache.get(filename, retriever)
        assert result == large_data
        assert len(result) == 1024 * 1024


class TestCacheS3Specific:
    """Tests specific to S3 storage features like prefixes."""

    def test_cache_with_prefix(self):
        """Test that cache works with S3 prefix."""
        bucket_name = 'test-prefix-bucket'
        prefix = 'cache-prefix'

        with mock_aws():
            client = boto3.client('s3', region_name='us-east-1')
            client.create_bucket(Bucket=bucket_name)

            storage = S3Storage(bucket_name, prefix=prefix, region_name='us-east-1')
            cache = Cache(storage)

            filename = 'test.txt'
            data = b'Prefixed data'

            def retriever():
                return data

            result = cache.get(filename, retriever)
            assert result == data

            # Verify it's stored with prefix in S3
            expected_key = f'{prefix}/{filename}'
            response = client.get_object(Bucket=bucket_name, Key=expected_key)
            assert response['Body'].read() == data
