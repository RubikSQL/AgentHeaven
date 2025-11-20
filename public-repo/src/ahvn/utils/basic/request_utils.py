"""\
Network and request helper utilities (proxies, contexts).
"""

__all__ = [
    "NetworkProxy",
    "google_download",
]

from .log_utils import get_logger

logger = get_logger(__name__)

import os
from typing import Optional, Dict, Any

from .file_utils import touch_dir, get_file_dir


class NetworkProxy:
    """A robust context manager for temporarily setting proxy environment variables.

    This implementation properly handles:
    - Both uppercase and lowercase proxy environment variables
    - Proper restoration of original values (including deletion when they didn't exist)
    - Empty string handling (removes proxy variables instead of setting to empty)
    - NO_PROXY support for bypassing proxy for specific hosts
    """

    PROXY_VARS = ["HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "NO_PROXY", "no_proxy"]

    def __init__(
        self,
        http_proxy: Optional[str] = None,
        https_proxy: Optional[str] = None,
        no_proxy: Optional[str] = None,
        **kwargs,
    ):
        """\
        Initialize the NetworkProxy with optional proxy settings.

        Args:
            http_proxy (Optional[str]): The HTTP proxy URL.
                If empty empty string, HTTP proxy will be disabled.
                If None, the existing setting will be preserved.
            https_proxy (Optional[str]): The HTTPS proxy URL.
                If empty empty string, HTTPS proxy will be disabled.
                If None, the existing setting will be preserved.
            no_proxy (Optional[str]): Comma-separated list of hosts to bypass proxy for.
                If empty empty string, no_proxy will be disabled.
                If None, the existing setting will be preserved.
            **kwargs: Additional keyword arguments for future extensions.
        """
        self.new_settings = {
            "HTTP_PROXY": http_proxy,
            "http_proxy": http_proxy,
            "HTTPS_PROXY": https_proxy,
            "https_proxy": https_proxy,
            "NO_PROXY": no_proxy,
            "no_proxy": no_proxy,
        }
        self.backup_env: Dict[str, Any] = {}

    def __enter__(self):
        """\
        Enter the context manager, saving current proxy settings and applying new ones.
        """
        for var in self.PROXY_VARS:
            self.backup_env[var] = os.environ.get(var, None)
        for var, value in self.new_settings.items():
            if value is None:
                continue
            os.environ[var] = value
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """\
        Exit the context manager, restoring the original proxy settings.
        """
        for var in self.PROXY_VARS:
            backup_val = self.backup_env.get(var, None)
            if self.new_settings.get(var, None) is None:
                continue
            if (backup_val is None) and (var in os.environ):
                del os.environ[var]
            elif backup_val is not None:
                os.environ[var] = backup_val
        self.backup_env.clear()


def google_download(file_id: str, path: str, http_proxy: Optional[str] = None, https_proxy: Optional[str] = None, *args, **kwargs) -> Optional[str]:
    """\
    Download a file from Google Drive using its file ID. The file must be publicly accessible.

    Args:
        file_id (str): The Google Drive file ID.
        path (str): The local path to save the downloaded file.
        http_proxy (Optional[str]): HTTP proxy URL. If empty string, disables HTTP proxy.
        https_proxy (Optional[str]): HTTPS proxy URL. If empty string, disables HTTPS proxy.
        *args: Additional positional arguments to pass to gdown.download.
        **kwargs: Additional keyword arguments to pass to gdown.download.

    Returns:
        str: The path to the downloaded file, or None if download failed.
    """
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    try:
        import gdown
    except ImportError:
        logger.error("gdown is not installed. Please install it with 'pip install gdown' to use google_download.")
        return None

    try:
        touch_dir(get_file_dir(path))
        with NetworkProxy(http_proxy=http_proxy, https_proxy=https_proxy):
            gdown.download(url=url, output=path, *args, **kwargs)
    except gdown.exceptions.FileException as e:
        logger.error(f"Failed to download file from Google Drive: {e}")
        return None
    return path
