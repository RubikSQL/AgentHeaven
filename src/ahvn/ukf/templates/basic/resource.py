__all__ = [
    "ResourceUKFT",
    "diagram_composer",
    "list_composer",
]

from ...base import BaseUKF
from ...registry import register_ukft
from ....utils.basic.serialize_utils import serialize_path, deserialize_path
from ....utils.basic.config_utils import hpj, HEAVEN_CM
from ....utils.basic.path_utils import get_file_basename, has_file_ext
from ....utils.basic.file_utils import folder_diagram, exists_file, exists_path, nonempty_dir, touch_dir, delete_path
from ....utils.basic.hash_utils import md5hash, fmt_hash
from ....utils.basic.log_utils import get_logger

logger = get_logger(__name__)

from typing import Union, Dict, Any, Optional, List, ClassVar
import os
import tempfile


RESOURCE_UNZIP_TEMP_PATH = hpj(HEAVEN_CM.get("core.tmp_path", tempfile.gettempdir()), "resource_unzip")


class _ResourceTempContext:
    """Context manager that materializes a resource on disk and cleans it up if requested."""

    def __init__(self, resource: "ResourceUKFT", path: Optional[str] = None, overwrite: bool = False, cleanup: bool = False):
        self._resource = resource
        self._path = path
        self._overwrite = overwrite
        self._cleanup = cleanup
        self._tmp_path = None
        self._exists = False

    def __enter__(self):
        if self._path is not None:
            self._tmp_path = hpj(self._path)
        else:
            identifier = fmt_hash(md5hash(self._resource.content_hash_str, salt=self._resource.id_str))
            self._tmp_path = hpj(RESOURCE_UNZIP_TEMP_PATH, identifier)
        if nonempty_dir(self._tmp_path) and (not self._overwrite):
            self._exists = True
            return self._tmp_path
        touch_dir(self._tmp_path)
        deserialize_path(self._resource.content_resources["data"], self._tmp_path)
        return self._tmp_path

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self._cleanup:
            return False
        if self._tmp_path is None:
            return False
        if (self._path is not None) and self._exists:
            logger.warning(f"Not deleting existing user path: {self._path}")
            return False  # Don't delete existing user path
        delete_path(self._tmp_path)
        self._tmp_path = None
        self._exists = False
        return False


def diagram_composer(kl, **kwargs):
    """\
    Compose a well-structured folder/tree diagram for LLM consumption.

    Creates a hierarchical tree structure showing the file/folder organization
    with optional annotations using the folder_diagram utility.

    Recommended Knowledge Types:
        Resource

    Args:
        kl (BaseUKF): Knowledge object containing resource data.
        **kwargs: Optional keyword arguments to override content_resources:
            - path (str): Original file/directory path.
            - annotations (Dict): File-level annotations.

    Returns:
        str: Formatted tree structure diagram with optional annotations.

    Example:
        >>> kl.content_resources = {
        ...     "path": "project",
        ...     "annotations": {"src/main.py": "Main entry point"}
        ... }
        >>> diagram_composer(kl)
        '''
        project/
        ├── src/
        │   └── main.py  # Main entry point
        '''
    """
    path = kwargs.get("path", kl.get("path", ""))
    data = kwargs.get("data", kl.get("data", {}))
    annotations = kwargs.get("annotations", kl.get("annotations", {}))

    custom_name = kwargs.get("name")
    if custom_name is None:
        custom_name = getattr(kl, "name", None) or (get_file_basename(path) if path else None)

    # If we have a real path and it exists, use it directly
    if path and os.path.exists(path):
        return folder_diagram(path=path, annotations=annotations, name=custom_name)

    # Otherwise, extract to temporary directory and build diagram
    if data:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = os.path.join(temp_dir, "resource")
        deserialize_path(data, temp_path)
        return folder_diagram(path=temp_path, annotations=annotations, name=custom_name)

    # Fallback to simple text
    fallback_name = custom_name or (get_file_basename(path) if path else "unknown")
    return f"ResourceUKFT: {fallback_name}"


def list_composer(kl, ext: Union[None, str, List[str]] = None, **kwargs):
    """\
    Compose a simple list of file paths in the resource with optional extension filtering.

    Creates a flat listing of files (not directories) in the resource,
    with optional annotations and extension filtering.

    Recommended Knowledge Types:
        ResourceUKFT

    Args:
        kl (BaseUKF): Knowledge object containing resource data.
        ext (Union[None, str, List[str]]): File extension filter. Defaults to None.
            - If None (default): List all files.
            - If a string: Filter by that extension (e.g., "py", "md").
            - If a list: Filter by any of the extensions in the list.
            Multiple extensions can be separated by commas or semicolons.
        **kwargs: Optional keyword arguments to override content_resources:
            - data (Dict): Serialized file/directory structure.
            - annotations (Dict): File-level annotations.

    Returns:
        str: Formatted list of file paths with annotations.

    Example:
        >>> kl.content_resources = {
        ...     "data": {"file1.py": "...", "src/main.py": "...", "src/": None},
        ...     "annotations": {"src/main.py": "Main entry point"}
        ... }
        >>> list_composer(kl)
        '''
        - file1.py
        - src/main.py  # Main entry point
        '''
        >>> list_composer(kl, ext="py")
        '''
        - file1.py
        - src/main.py  # Main entry point
        '''
    """
    data = kwargs.get("data", kl.get("data", {}))
    annotations = kwargs.get("annotations", kl.get("annotations", {}))

    # Extract only files (not directories, which have None as value)
    all_files = sorted([path for path, content in data.items() if content is not None])

    # Filter by extension if specified
    if ext is None:
        files = all_files
    else:
        files = [f for f in all_files if has_file_ext(f, ext)]

    if not files:
        return "(no files found)"

    lines = list()
    for file_path in files:
        annotation = annotations.get(file_path, "")
        if annotation:
            lines.append(f"- {file_path}  # {annotation}")
        else:
            lines.append(f"- {file_path}")

    return "\n".join(lines)


@register_ukft
class ResourceUKFT(BaseUKF):
    """\
    Resource class for storing file/folder contents as base64 encoded data.

    UKF Type: resource
    Recommended Components of `content_resources`:
        - path (str): The original file/directory path.
        - data (Dict[str, Optional[str]]): Serialized file/directory structure from serialize_path.
        - annotations (Dict[str, str]): File-level annotations for context.

    Recommended Composers:
        diagram:
            Examples:
            ```
            project/
            ├── README.md
            ├── src/
            │   ├── main.py
            │   └── utils.py
            └── tests/
                └── test_main.py  # Unit tests for main functionality
            ```
    """

    type_default: ClassVar[str] = "resource"

    @classmethod
    def from_path(cls, path: str, name: Optional[str] = None, keep_path: bool = True, **updates):
        """\
        Create a ResourceUKFT instance from a file or directory path.

        Serializes the file or directory contents using serialize_path and
        automatically configures the resource with appropriate metadata and composers.
        Only stores essential information (file names and paths) without redundant metadata.

        Args:
            path (str): Path to the file or directory to serialize.
            name (str, optional): ResourceUKFT name. If None and path is a directory, generates name from
                the basename of the path. Required if path is a file.
            keep_path (bool): Whether to keep the original path in content_resources. Defaults to True.
            **updates: Additional keyword arguments to update the ResourceUKFT
                instance attributes.

        Returns:
            ResourceUKFT: New ResourceUKFT instance with pre-configured composers:
                - diagram: diagram_composer for LLM-friendly folder structure diagram

        Example:
            >>> resource = ResourceUKFT.from_path("/path/to/project")
            >>> resource.name
            "project"
            >>> resource.text("diagram")
            '''\
            project/
            ├── file1.py
            └── src/
                └── main.py
            '''
        """
        path = hpj(path)
        if exists_file(path) and name is None:
            raise ValueError("Name must be provided when path is a file")
        serialized_data = serialize_path(path)

        return cls(
            name=(name if name is not None else get_file_basename(path)),
            content_resources=({"path": path} if keep_path else dict())
            | {
                "data": serialized_data,
                "annotations": {},
            },
            content_composers={
                "default": diagram_composer,
                "diagram": diagram_composer,
                "list": list_composer,
            },
            **updates,
        )

    @classmethod
    def from_data(cls, data: Dict[str, Any], name: str = None, path: str = None, **updates):
        """\
        Create a ResourceUKFT instance from serialized data.

        Allows creating a ResourceUKFT from pre-serialized data without requiring
        the original file/directory to exist.

        Args:
            data (Dict[str, Any]): Serialized file/directory structure from serialize_path.
            name (str, optional): ResourceUKFT name. If None, generates from path or uses "resource".
            path (str, optional): Original path for reference. Used in diagram generation.
            **updates: Additional keyword arguments to update the ResourceUKFT
                instance attributes.

        Returns:
            ResourceUKFT: New ResourceUKFT instance with pre-configured composers.

        Example:
            >>> data = {"file.txt": "base64content", "folder/": None}
            >>> resource = ResourceUKFT.from_data(data, name="my_resource")
            >>> resource.name
            "my_resource"
        """
        path = None if path is None else hpj(path)

        if (name is None) and (path is not None):
            name = get_file_basename(path)

        if name is None:
            raise ValueError("Either name or path must be provided to determine resource name")

        return cls(
            name=name,
            content_resources={
                "path": path or "",
                "data": data,
                "annotations": {},
            },
            content_composers={
                "default": diagram_composer,
                "diagram": diagram_composer,
                "list": list_composer,
            },
            **updates,
        )

    def annotate(self, file_path: str, annotation: str) -> "ResourceUKFT":
        """\
        Add an annotation to a specific file in the resource.

        Allows adding contextual information about files that will appear
        in the diagram tree, making it more useful for LLM consumption.

        Args:
            file_path (str): Relative path to the file within the resource.
            annotation (str): Annotation text to display after the file name.

        Returns:
            ResourceUKFT: A new ResourceUKFT instance with the annotation added.

        Example:
            >>> resource = ResourceUKFT.from_path("/path/to/project")
            >>> annotated = resource.annotate("src/main.py", "Main entry point")
            >>> annotated.text("diagram")
            '''\
            project/
            └── src/
                └── main.py  # Main entry point
            '''
        """
        annotations = self.get("annotations", {}).copy()
        annotations[file_path] = annotation

        content_resources = self.content_resources.copy()
        content_resources["annotations"] = annotations

        return self.clone(content_resources=content_resources)

    def to_path(self, path: str):
        """\
        Extract the resource contents to a specified path.

        Deserializes the stored data and recreates the original file or
        directory structure at the specified destination.

        Args:
            path (str): Path where the resource should be extracted.

        Example:
            >>> resource = ResourceUKFT.from_path("/source/data/")
            >>> resource.to_path("/destination/restored_data/")
            # Recreates the original directory structure at destination
        """
        deserialize_path(self.get("data"), path=path)

    def _temp_context(self, path: Optional[str] = None, overwrite: bool = False, cleanup: bool = False) -> _ResourceTempContext:
        if not path:
            path = hpj(self.get("path"), abs=True)
            if (path is not None) and (not exists_path(path)):  # If not specified, and the path in knowledge does not exist, use a temporary path
                path = None
        return _ResourceTempContext(self, path=path, overwrite=overwrite, cleanup=cleanup)

    def __call__(self, path: Optional[str] = None, overwrite: bool = False, cleanup: bool = False) -> _ResourceTempContext:
        """\
        Return a context manager that extracts the resource to disk.

        Args:
            path (str, optional): Destination directory for the extracted files. Defaults to a temp location.
            overwrite (bool): Whether to overwrite existing files at the destination. Defaults to False.
            cleanup (bool): Whether to delete the extracted files upon exiting the context. Defaults to False.
                Notice that when a user-specified path is provided and the path already exists,
                cleanup will not delete the existing path to avoid data loss.

        Returns:
            _ResourceTempContext: Context manager handling extraction and optional cleanup.
        """
        return self._temp_context(path=path, overwrite=overwrite, cleanup=cleanup)

    def __enter__(self):
        """\
        Extract the resource to a temporary directory using default settings.

        Returns:
            ResourceUKFT: Self with `_temp_path` set during the context lifetime.
        """
        self._active_context = self._temp_context()
        return self._active_context.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """\
        Delegate cleanup to the active temporary context.
        """
        context = getattr(self, "_active_context", None)
        try:
            if context is not None:
                return context.__exit__(exc_type, exc_val, exc_tb)
            return False
        finally:
            if hasattr(self, "_active_context"):
                delattr(self, "_active_context")
