import os
import sys
import tempfile
import pytest
from unittest.mock import patch
from .test_utils import (
    FLIGHT_CONDITIONS,
    assert_valid_png,
    get_test_airports,
    mock_requests_get,
)

# Import the CLI module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from cli.metar_analyzer import main  # noqa: E402


class TestCLI:
    @pytest.mark.parametrize("airport", get_test_airports())
    @patch('lib.raw_metar_retriever.requests.get')
    @patch('appdirs.user_cache_dir')
    def test_chart_generation(self, mock_cache_dir, mock_requests, airport):
        """Test chart generation with all test datasets."""
        mock_requests.side_effect = mock_requests_get

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_cache_dir.return_value = tmpdir

            # Simulate command line arguments with chart generation
            test_args = ['prog', '-a', airport, '-m', '6', '-c', '-d', tmpdir]
            with patch('sys.argv', test_args):
                main()

            # Verify file was written with standard naming
            expected_file = os.path.join(tmpdir, f'{airport}-06.png')
            assert os.path.exists(expected_file)
            assert_valid_png(expected_file)

    @pytest.mark.parametrize("airport", get_test_airports())
    @patch('lib.raw_metar_retriever.requests.get')
    @patch('appdirs.user_cache_dir')
    @patch('builtins.print')
    def test_table_option(self, mock_print, mock_cache_dir, mock_requests, airport):
        """Test -t/--table option with real data for all test datasets."""
        mock_requests.side_effect = mock_requests_get

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_cache_dir.return_value = tmpdir

            # Simulate command line arguments with --table (no chart)
            test_args = ['prog', '-a', airport, '-m', '1', '--table']
            with patch('sys.argv', test_args):
                main()

            # CLI should print the formatted table once
            assert mock_print.call_count == 1
            # Should be the formatted table (string with multiple lines)
            table_output = mock_print.call_args_list[0][0][0]
            assert isinstance(table_output, str)

            # Verify all flight conditions are present
            for condition in FLIGHT_CONDITIONS:
                assert condition in table_output

            assert airport in table_output
            assert 'January' in table_output

            # Verify all 24 hours are present and in order
            lines = table_output.split('\n')
            hour_lines = [line for line in lines if line.strip() and line.strip()[0].isdigit()]
            assert len(hour_lines) == 24, f"Expected 24 hour lines, got {len(hour_lines)}"
            for i, line in enumerate(hour_lines):
                hour_str = line.split()[0]
                assert int(hour_str) == i, f"Expected hour {i}, got {hour_str}"

    @patch('lib.raw_metar_retriever.requests.get')
    @patch('appdirs.user_cache_dir')
    def test_chart_without_directory(self, mock_cache_dir, mock_requests):
        """Test chart generation uses current directory by default."""
        mock_requests.side_effect = mock_requests_get

        # Change to temp directory to avoid polluting project
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_cache_dir.return_value = tmpdir
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)

                # Simulate command line arguments with -c but no -d
                test_args = ['prog', '-a', 'KPAO', '-m', '6', '-c']
                with patch('sys.argv', test_args):
                    main()

                # Verify default filename in current directory
                expected_file = 'KPAO-06.png'
                assert os.path.exists(expected_file)
                assert_valid_png(expected_file)
            finally:
                os.chdir(original_cwd)

    def test_no_output_options_error(self):
        """Test that CLI errors when no output options are specified."""
        test_args = ['prog', '-a', 'KPAO', '-m', '6']
        with patch('sys.argv', test_args):
            with pytest.raises(SystemExit):
                main()

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
