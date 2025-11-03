import os
import sys
import tempfile
import pytest
from unittest.mock import patch
from .test_utils import mock_requests_get

# Import the CLI module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from cli.metar_analyzer import main  # noqa: E402


class TestCLI:
    @patch('lib.raw_metar_retriever.requests.get')
    @patch('appdirs.user_cache_dir')
    def test_basic_execution(self, mock_cache_dir, mock_requests):
        """Test basic CLI execution with real data."""
        mock_requests.side_effect = mock_requests_get

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_cache_dir.return_value = tmpdir
            output_file = os.path.join(tmpdir, 'test.png')

            # Simulate command line arguments
            test_args = ['prog', '-a', 'KPAO', '-m', '6', '-o', output_file]
            with patch('sys.argv', test_args):
                main()

            # Verify file was written and is a valid PNG
            assert os.path.exists(output_file)
            with open(output_file, 'rb') as f:
                png_data = f.read()
                # PNG files start with these magic bytes
                assert png_data[:8] == b'\x89PNG\r\n\x1a\n'

    @patch('lib.raw_metar_retriever.requests.get')
    @patch('appdirs.user_cache_dir')
    @patch('builtins.print')
    def test_print_table_option(self, mock_print, mock_cache_dir, mock_requests):
        """Test --print-table option with real data."""
        mock_requests.side_effect = mock_requests_get

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_cache_dir.return_value = tmpdir
            output_file = os.path.join(tmpdir, 'test.png')

            # Simulate command line arguments with --print-table
            test_args = ['prog', '-a', 'KPAO', '-m', '1', '-o', output_file, '--print-table']
            with patch('sys.argv', test_args):
                main()

            # CLI prints the hourly DataFrame first, then the formatted table
            assert mock_print.call_count == 2
            # Second call should be the formatted table (string with multiple lines)
            table_output = mock_print.call_args_list[1][0][0]
            assert isinstance(table_output, str)
            assert 'VFR' in table_output
            assert 'MVFR' in table_output

    @patch('lib.raw_metar_retriever.requests.get')
    @patch('appdirs.user_cache_dir')
    def test_default_output_filename(self, mock_cache_dir, mock_requests):
        """Test default output filename generation."""
        mock_requests.side_effect = mock_requests_get

        # Change to temp directory to avoid polluting project
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_cache_dir.return_value = tmpdir
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)

                # Simulate command line arguments without -o
                test_args = ['prog', '-a', 'KPAO', '-m', '6']
                with patch('sys.argv', test_args):
                    main()

                # Verify default filename was used
                expected_file = 'KPAO-06.png'
                assert os.path.exists(expected_file)

                # Verify it's a valid PNG
                with open(expected_file, 'rb') as f:
                    assert f.read()[:8] == b'\x89PNG\r\n\x1a\n'
            finally:
                os.chdir(original_cwd)

    def test_invalid_month(self):
        # Test that invalid month raises error
        test_args = ['prog', '-a', 'KTEST', '-m', '13']
        with patch('sys.argv', test_args):
            with pytest.raises(SystemExit):
                main()

    def test_missing_required_args(self):
        # Test that missing required arguments raises error
        test_args = ['prog', '-m', '6']  # Missing airport
        with patch('sys.argv', test_args):
            with pytest.raises(SystemExit):
                main()
