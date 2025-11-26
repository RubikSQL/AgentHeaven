"""UKF Type Registry for polymorphic deserialization.

This module provides a central registry for all UKF Template (UKFT) classes,
enabling polymorphic deserialization based on the `type` field. The registry
follows the naming convention of HEAVEN_CM and HEAVEN_KB.
"""

__all__ = [
    "UKFTypeRegistry",
    "HEAVEN_UR",
    "register_ukft",
]

from ..utils.basic.log_utils import get_logger

logger = get_logger(__name__)

from typing import Dict, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from .base import BaseUKF


class UKFTypeRegistry:
    """Central registry for UKF Template types.

    This registry maps UKF type strings (from the `type` field) to their
    corresponding UKFT class implementations. It enables polymorphic
    deserialization where `from_dict` and `from_ukf` can return the
    appropriate subclass based on the type field.

    Example:
        >>> @register_ukft
        ... class MyUKFT(BaseUKF):
        ...     type: str = Field(default="my_type", frozen=True)
        >>>
        >>> data = {"type": "my_type", "name": "test", ...}
        >>> ukf = BaseUKF.from_dict(data)  # Returns MyUKFT instance
        >>> isinstance(ukf, MyUKFT)
        True
    """

    def __init__(self):
        self._registry: Dict[str, Type["BaseUKF"]] = {}

    def register(self, ukft_class: Type["BaseUKF"]) -> Type["BaseUKF"]:
        """Register a UKFT class in the registry.

        Args:
            ukft_class: A BaseUKF subclass to register.

        Returns:
            The same class (for use as a decorator).

        Raises:
            ValueError: If the class doesn't have a `type` field or if
                       the type is already registered.
        """
        # Get the default type value from the class
        type_value = getattr(ukft_class, "type_default", None)

        if type_value is None:
            if "type" not in ukft_class.model_fields:
                raise ValueError(f"Class {ukft_class.__name__} must have a 'type' field or 'type_default' to be registered")

            type_field = ukft_class.model_fields["type"]
            type_value = type_field.default

        if type_value is None:
            raise ValueError(f"Class {ukft_class.__name__} must have a default value for 'type' field")

        if type_value in self._registry and self._registry[type_value] != ukft_class:
            logger.warning(f"Type '{type_value}' is already registered to {self._registry[type_value].__name__}. " f"Overriding with {ukft_class.__name__}.")

        self._registry[type_value] = ukft_class
        logger.debug(f"Registered UKFT class {ukft_class.__name__} with type '{type_value}'")

        return ukft_class

    def get(self, type_name: str, default: Type["BaseUKF"] = None) -> Type["BaseUKF"]:
        """Get a UKFT class by its type name.

        Args:
            type_name: The type string to look up.
            default: Default value to return if type not found.

        Returns:
            The registered UKFT class for this type, or the default value if not found.
        """
        return self._registry.get(type_name, default)

    def list_types(self) -> list[str]:
        """List all registered type names.

        Returns:
            List of registered type strings.
        """
        return list(self._registry.keys())

    def is_registered(self, type_name: str) -> bool:
        """Check if a type is registered.

        Args:
            type_name: The type string to check.

        Returns:
            True if the type is registered, False otherwise.
        """
        return type_name in self._registry


# Global registry instance following HEAVEN_* naming convention
HEAVEN_UR = UKFTypeRegistry()


def register_ukft(ukft_class: Type["BaseUKF"]) -> Type["BaseUKF"]:
    """Decorator to register a UKFT class in the global registry.

    This decorator should be applied to all BaseUKF subclasses that
    represent concrete UKF types. It automatically registers the class
    in HEAVEN_UR for polymorphic deserialization.

    Args:
        ukft_class: A BaseUKF subclass to register.

    Returns:
        The same class (for use as a decorator).

    Example:
        >>> @register_ukft
        ... class KnowledgeUKFT(BaseUKF):
        ...     type: str = Field(default="knowledge", frozen=True)
    """
    return HEAVEN_UR.register(ukft_class)
