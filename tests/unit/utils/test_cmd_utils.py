"""
Unit tests for command-line utilities.

Tests cmd execution, platform detection, and file browsing utilities.
"""

import pytest
import platform
from pathlib import Path
from subprocess import Popen, PIPE
from unittest.mock import patch, MagicMock, call


class TestCmdUtils:
    """Test command-line utility functions."""

    def setup_method(self):
        """Set up test method."""
        # Import the module here to ensure it's available
        from ahvn.utils.basic.cmd_utils import cmd, is_macos, is_windows, is_linux, browse

        self.cmd = cmd
        self.is_macos = is_macos
        self.is_windows = is_windows
        self.is_linux = is_linux
        self.browse = browse

    def test_cmd_basic_execution_with_string_command(self):
        """Test basic command execution with string command."""
        # Test simple echo command
        result = self.cmd("echo hello", include="stdout")
        assert result == "hello"

    def test_cmd_basic_execution_with_list_command(self):
        """Test basic command execution with list command."""
        # Test command as list
        result = self.cmd(["echo", "hello world"], include="stdout")
        assert result == "hello world"

    def test_cmd_default_behavior_returns_handle(self):
        """Test that cmd returns process handle by default."""
        process = self.cmd("echo test")
        assert isinstance(process, Popen)
        assert process.returncode == 0  # Should have finished successfully

    def test_cmd_with_wait_false(self):
        """Test cmd with wait=False."""
        process = self.cmd("echo test", wait=False)
        assert isinstance(process, Popen)
        # Process might still be running
        process.wait()  # Wait for completion
        assert process.returncode == 0

    def test_cmd_include_multiple_values(self):
        """Test cmd with multiple include values."""
        result = self.cmd("echo hello", include=["stdout", "stderr", "returncode"])
        assert isinstance(result, dict)
        assert "stdout" in result
        assert "stderr" in result
        assert "returncode" in result
        assert result["stdout"] == "hello"
        assert result["stderr"] == ""
        assert result["returncode"] == 0

    def test_cmd_include_single_value_returns_value(self):
        """Test cmd with single include value returns just that value."""
        stdout = self.cmd("echo test", include="stdout")
        assert stdout == "test"

        returncode = self.cmd("echo test", include="returncode")
        assert returncode == 0

    def test_cmd_include_stderr(self):
        """Test cmd capturing stderr."""
        # Use a command that writes to stderr (python -c with a warning)
        result = self.cmd("python -c \"import sys; sys.stderr.write('error\\n')\"", include=["stdout", "stderr"])
        assert isinstance(result, dict)
        assert "stderr" in result
        assert "error" in result["stderr"]

    @patch("ahvn.utils.basic.cmd_utils.Popen")
    def test_cmd_with_sudo(self, mock_popen):
        """Test cmd with sudo=True."""
        mock_process = MagicMock()
        mock_process.communicate.return_value = ("output", "")
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        self.cmd("ls", sudo=True, include="stdout")

        # Check that sudo was prepended to the command
        args, kwargs = mock_popen.call_args
        assert "sudo ls" in args[0]

    @patch("ahvn.utils.basic.cmd_utils.Popen")
    def test_cmd_with_custom_kwargs(self, mock_popen):
        """Test cmd with custom subprocess kwargs."""
        mock_process = MagicMock()
        mock_process.communicate.return_value = ("output", "")
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        self.cmd("echo test", include="stdout", cwd="/tmp", env={"PATH": "/usr/bin"})

        args, kwargs = mock_popen.call_args
        assert kwargs.get("cwd") == "/tmp"
        assert kwargs.get("env") == {"PATH": "/usr/bin"}

    def test_cmd_invalid_include_parameter(self):
        """Test cmd with invalid include parameter."""
        with pytest.raises(ValueError) as exc_info:
            self.cmd("echo test", include="invalid")
        assert "Unsupported include 'invalid'" in str(exc_info.value)

    def test_cmd_wait_false_with_outputs(self):
        """Test cmd with wait=False and requesting outputs."""
        result = self.cmd("echo test", wait=False, include=["handle", "stdout", "stderr"])
        assert isinstance(result, dict)
        assert "handle" in result
        assert isinstance(result["handle"], Popen)
        # stdout/stderr should be file objects when wait=False
        assert result["stdout"] is not None  # Should be the stdout pipe
        assert result["stderr"] is not None  # Should be the stderr pipe

    def test_platform_detection_functions(self):
        """Test platform detection functions."""
        # At least one should be True
        platforms = [self.is_macos(), self.is_windows(), self.is_linux()]
        assert any(platforms), "At least one platform should be detected"

        # Only one should be True
        assert sum(platforms) == 1, "Only one platform should be detected"

    @patch("platform.system")
    def test_is_macos_detection(self, mock_system):
        """Test macOS detection."""
        mock_system.return_value = "Darwin"
        assert self.is_macos() is True

        mock_system.return_value = "Windows"
        assert self.is_macos() is False

        mock_system.return_value = "Linux"
        assert self.is_macos() is False

    @patch("platform.system")
    def test_is_windows_detection(self, mock_system):
        """Test Windows detection."""
        mock_system.return_value = "Windows"
        assert self.is_windows() is True

        mock_system.return_value = "Darwin"
        assert self.is_windows() is False

        mock_system.return_value = "Linux"
        assert self.is_windows() is False

    @patch("platform.system")
    def test_is_linux_detection(self, mock_system):
        """Test Linux detection."""
        mock_system.return_value = "Linux"
        assert self.is_linux() is True

        mock_system.return_value = "Darwin"
        assert self.is_linux() is False

        mock_system.return_value = "Windows"
        assert self.is_linux() is False

    @patch("platform.system")
    @patch("ahvn.utils.basic.cmd_utils.Popen")
    def test_browse_on_macos(self, mock_popen, mock_system):
        """Test browse function on macOS."""
        mock_system.return_value = "Darwin"

        self.browse("/path/to/file")

        mock_popen.assert_called_once_with(["open", "/path/to/file"])

    @patch("platform.system")
    def test_browse_on_windows(self, mock_system):
        """Test browse function on Windows."""
        mock_system.return_value = "Windows"

        # Mock os.startfile since it only exists on Windows
        # We need to patch it where it's imported inside the browse function
        import os

        original_startfile = getattr(os, "startfile", None)

        try:
            # Create startfile if it doesn't exist
            if not hasattr(os, "startfile"):
                os.startfile = MagicMock()

            with patch.object(os, "startfile") as mock_startfile:
                self.browse("/path/to/file")
                mock_startfile.assert_called_once_with("/path/to/file")
        finally:
            # Clean up - restore original or remove if it wasn't there
            if original_startfile is None and hasattr(os, "startfile"):
                delattr(os, "startfile")
            elif original_startfile is not None:
                os.startfile = original_startfile

    @patch("platform.system")
    @patch("ahvn.utils.basic.cmd_utils.Popen")
    def test_browse_on_linux(self, mock_popen, mock_system):
        """Test browse function on Linux."""
        mock_system.return_value = "Linux"

        self.browse("/path/to/file")

        mock_popen.assert_called_once_with(["xdg-open", "/path/to/file"])

    @patch("platform.system")
    @patch("ahvn.utils.basic.cmd_utils.Popen")
    def test_browse_on_unknown_platform(self, mock_popen, mock_system):
        """Test browse function on unknown platform (fallback to macOS)."""
        mock_system.return_value = "Unknown"

        self.browse("/path/to/file")

        mock_popen.assert_called_once_with(["open", "/path/to/file"])

    def test_cmd_text_mode_default(self):
        """Test that cmd uses text mode by default."""
        result = self.cmd("echo test", include="stdout")
        assert isinstance(result, str)
        assert result == "test"

    @patch("ahvn.utils.basic.cmd_utils.Popen")
    def test_cmd_preserves_user_text_settings(self, mock_popen):
        """Test that cmd preserves user-provided text/encoding settings."""
        mock_process = MagicMock()
        mock_process.communicate.return_value = (b"output", b"")
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        # Test with text=False (bytes mode)
        self.cmd("echo test", include="stdout", text=False)

        args, kwargs = mock_popen.call_args
        assert kwargs.get("text") is False
        assert "stdout" in kwargs  # Should still set stdout=PIPE

    def test_cmd_command_failure(self):
        """Test cmd with failing command."""
        result = self.cmd("false", include=["returncode", "stderr"])  # 'false' command always fails
        assert isinstance(result, dict)
        assert result["returncode"] != 0  # Should be non-zero for failure

    def test_cmd_include_as_string(self):
        """Test cmd with include as single string instead of list."""
        result = self.cmd("echo test", include="stdout")
        assert result == "test"
