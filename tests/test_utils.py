"""Tests for utils module."""

import pytest
import os
from src.utils import (
    get_timestamp,
    get_human_timestamp,
    ensure_directory,
    safe_write_file,
    safe_read_file,
    list_files,
    format_device_list,
    print_separator,
    print_success,
    print_error,
    print_info
)


@pytest.mark.unit
class TestTimestampUtilities:
    """Test cases for timestamp utility functions."""

    def test_get_timestamp(self):
        """Test timestamp generation."""
        timestamp = get_timestamp()
        assert len(timestamp) == 15  # YYYYMMDD_HHMMSS
        assert '_' in timestamp

    def test_get_timestamp_custom_format(self):
        """Test timestamp with custom format."""
        timestamp = get_timestamp(format="%Y-%m-%d")
        assert '-' in timestamp
        assert len(timestamp) == 10  # YYYY-MM-DD

    def test_get_human_timestamp(self):
        """Test human-readable timestamp."""
        timestamp = get_human_timestamp()
        assert '-' in timestamp
        assert ':' in timestamp


@pytest.mark.unit
class TestFileOperations:
    """Test cases for file operation utilities."""

    def test_ensure_directory(self, temp_dir):
        """Test directory creation."""
        test_dir = os.path.join(temp_dir, 'test_subdir')
        result = ensure_directory(test_dir)
        assert result is True
        assert os.path.exists(test_dir)

    def test_ensure_directory_nested(self, temp_dir):
        """Test nested directory creation."""
        test_dir = os.path.join(temp_dir, 'level1', 'level2', 'level3')
        result = ensure_directory(test_dir)
        assert result is True
        assert os.path.exists(test_dir)

    def test_safe_write_file(self, temp_dir):
        """Test safe file writing."""
        filepath = os.path.join(temp_dir, 'test_file.txt')
        content = "Test content"
        result = safe_write_file(filepath, content)
        assert result is True
        assert os.path.exists(filepath)

    def test_safe_write_file_creates_directory(self, temp_dir):
        """Test that safe_write_file creates parent directories."""
        filepath = os.path.join(temp_dir, 'subdir', 'test_file.txt')
        content = "Test content"
        result = safe_write_file(filepath, content)
        assert result is True
        assert os.path.exists(filepath)

    def test_safe_read_file(self, temp_dir):
        """Test safe file reading."""
        filepath = os.path.join(temp_dir, 'test_file.txt')
        content = "Test content"
        safe_write_file(filepath, content)
        read_content = safe_read_file(filepath)
        assert read_content == content

    def test_safe_read_nonexistent_file(self):
        """Test reading non-existent file."""
        result = safe_read_file('/nonexistent/file.txt')
        assert result is None

    def test_list_files(self, temp_dir):
        """Test listing files in directory."""
        # Create some test files
        safe_write_file(os.path.join(temp_dir, 'file1.txt'), 'content1')
        safe_write_file(os.path.join(temp_dir, 'file2.txt'), 'content2')
        safe_write_file(os.path.join(temp_dir, 'file3.cfg'), 'content3')

        files = list_files(temp_dir)
        assert len(files) == 3

    def test_list_files_with_extension_filter(self, temp_dir):
        """Test listing files with extension filter."""
        # Create some test files
        safe_write_file(os.path.join(temp_dir, 'file1.txt'), 'content1')
        safe_write_file(os.path.join(temp_dir, 'file2.txt'), 'content2')
        safe_write_file(os.path.join(temp_dir, 'file3.cfg'), 'content3')

        txt_files = list_files(temp_dir, extension='.txt')
        assert len(txt_files) == 2

    def test_list_files_nonexistent_directory(self):
        """Test listing files in non-existent directory."""
        files = list_files('/nonexistent/directory')
        assert files == []


@pytest.mark.unit
class TestFormattingUtilities:
    """Test cases for formatting utility functions."""

    def test_format_device_list(self):
        """Test device list formatting."""
        devices = [
            {'name': 'spine1', 'ip': '192.168.1.1', 'role': 'spine', 'device_type': 'nokia_sros'},
            {'name': 'leaf1', 'ip': '192.168.1.2', 'role': 'leaf', 'device_type': 'nokia_sros'}
        ]
        result = format_device_list(devices)
        assert 'spine1' in result
        assert '192.168.1.1' in result
        assert 'spine' in result

    def test_format_device_list_empty(self):
        """Test formatting empty device list."""
        result = format_device_list([])
        assert result == "No devices to display"

    def test_format_device_list_missing_fields(self):
        """Test formatting device list with missing fields."""
        devices = [
            {'name': 'spine1'},  # Missing other fields
        ]
        result = format_device_list(devices)
        assert 'spine1' in result
        assert 'N/A' in result

    def test_print_separator(self, capsys):
        """Test separator printing."""
        print_separator(char="-", length=20)
        captured = capsys.readouterr()
        assert captured.out.strip() == "-" * 20

    def test_print_success(self, capsys):
        """Test success message printing."""
        print_success("Test success message")
        captured = capsys.readouterr()
        assert "Test success message" in captured.out

    def test_print_error(self, capsys):
        """Test error message printing."""
        print_error("Test error message")
        captured = capsys.readouterr()
        assert "Test error message" in captured.out

    def test_print_info(self, capsys):
        """Test info message printing."""
        print_info("Test info message")
        captured = capsys.readouterr()
        assert "Test info message" in captured.out
