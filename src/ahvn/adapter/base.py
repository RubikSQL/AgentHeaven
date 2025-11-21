__all__ = [
    "parse_ukf_include",
    "BaseUKFAdapter",
]

from ..ukf import BaseUKF

from ..utils.basic.misc_utils import unique

from typing import Any, Optional, List, Tuple, Dict, Iterable

from abc import ABC, abstractmethod


def parse_ukf_include(
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    virtual_fields: Optional[Iterable[str]] = None,
) -> Tuple[List[str], bool]:
    """\
    Parse include parameter for engine initialization.

    Args:
        include: List of BaseUKF field names to include. If None, includes all fields.
        exclude: List of BaseUKF field names to exclude. If None, excludes no fields.
            Notice that exclude is applied after include, so if a field is in both include and exclude,
            it will be excluded. It is recommended to use only one of include or exclude.
        virtual_fields: Additional virtual fields to include.

    Returns:
        A tuple containing:
        - List of field names to include.
        - Boolean indicating if the included fields are sufficient to reconstruct a full BaseUKF object.
    """
    if include is None:
        include = [BaseUKF.id_field] + list(BaseUKF.schema().keys())
    else:
        include = [BaseUKF.id_field] + list(include)
    if virtual_fields is not None:
        include.extend(virtual_fields)
    include = unique(include)
    if exclude is not None:
        include = [f for f in include if f not in exclude]
    recoverable = set(BaseUKF.schema().keys()).issubset(set(include))
    return include, recoverable


class BaseUKFAdapter(ABC):
    """\
    Base adapter class for converting between UKF objects and backend representations.

    This class should be extended to implement specific adapters for different backends.
    """

    virtual_fields = None

    def __init__(self, name, include: Optional[List[str]] = None, exclude: Optional[List[str]] = None):
        """Initialize the adapter with specified field inclusion.

        Args:
            name: Name of the adapter instance.
            include: List of BaseUKF field names to include. If None, includes all fields. Default is None.
            exclude: List of BaseUKF field names to exclude. If None, excludes no fields. Default is None.
                Notice that exclude is applied after include, so if a field is in both include and exclude,
                it will be excluded. It is recommended to use only one of include or exclude.
        """
        self.name = name
        self.fields, self.recoverable = parse_ukf_include(
            include=include,
            exclude=exclude,
            virtual_fields=self.virtual_fields,
        )

    @abstractmethod
    def from_ukf(self, ukf: BaseUKF) -> Any:
        """\
        Convert a BaseUKF object to a dictionary representation entity for backend.

        Args:
            ukf: BaseUKF object to convert.

        Returns:
            The converted entity that can be stored in the backend.
        """
        pass

    @abstractmethod
    def to_ukf_data(self, entity: Any) -> Dict[str, Any]:
        """\
        Convert a backend entity representation to a dictionary suitable for BaseUKF initialization.

        Args:
            entity: The backend entity to convert.

        Returns:
            A dictionary of field names and values for BaseUKF initialization.
        """
        pass

    def to_ukf(self, entity: Any) -> BaseUKF:
        """\
        Convert a backend entity representation to a BaseUKF object.

        Args:
            entity: The backend entity to convert.

        Returns:
            The converted BaseUKF object.
        """
        if not self.recoverable:
            raise ValueError(f"Cannot convert to BaseUKF: included fields are insufficient to reconstruct a full BaseUKF object. ({self.__class__.__name__})")
        data = self.to_ukf_data(entity)
        return BaseUKF.from_dict(data, polymorphic=True)

    @abstractmethod
    def from_result(self, result: Any) -> Any:
        """\
        Convert a query result from the backend to the appropriate entity representation.

        Args:
            result: The raw result from a backend query.

        Returns:
            The converted entity representation.
        """
        pass
