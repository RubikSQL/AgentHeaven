"""
Unit tests for function serialization and deserialization utilities.

Tests the serialize_func and deserialize_func functions, AhvnJsonEncoder/Decoder,
and related function serialization capabilities in serialize_utils.
"""

import pytest
import json
import base64
from pathlib import Path
from typing import Any, Optional


class TestSerializeFunc:
    """Test function serialization utilities."""

    def setup_method(self):
        """Set up test fixtures."""
        try:
            from ahvn.utils.basic.serialize_utils import (
                serialize_func,
                deserialize_func,
                AhvnJsonEncoder,
                AhvnJsonDecoder,
                dumps_json,
                loads_json,
            )
            from ahvn.utils.basic.debug_utils import FunctionDeserializationError

            self.serialize_func = serialize_func
            self.deserialize_func = deserialize_func
            self.AhvnJsonEncoder = AhvnJsonEncoder
            self.AhvnJsonDecoder = AhvnJsonDecoder
            self.dumps_json = dumps_json
            self.loads_json = loads_json
            self.FunctionDeserializationError = FunctionDeserializationError
        except ImportError as e:
            pytest.skip(f"Required modules not available: {e}")

    def test_basic_function_serialization(self):
        """Test basic function serialization and deserialization."""

        def test_func(x: int, y: int) -> int:
            """Add two numbers."""
            return x + y

        # Test serialization
        serialized = self.serialize_func(test_func)

        # Verify serialized structure
        assert isinstance(serialized, dict)
        assert serialized["name"] == "test_func"
        assert serialized["qualname"] == "TestSerializeFunc.test_basic_function_serialization.<locals>.test_func"
        assert serialized["doc"] == "Add two numbers."
        assert "code" in serialized
        assert "hex_dumps" in serialized
        assert serialized["stream"] is False
        assert "annotations" in serialized

        # Test deserialization with both methods
        deserialized_hex = self.deserialize_func(serialized, prefer="hex_dumps")
        deserialized_code = self.deserialize_func(serialized, prefer="code")

        # Test functionality
        assert callable(deserialized_hex)
        assert callable(deserialized_code)
        assert deserialized_hex(3, 4) == 7
        assert deserialized_code(3, 4) == 7

    def test_function_with_defaults(self):
        """Test function with default arguments."""

        def func_with_defaults(x: int, y: int = 10, z: str = "hello") -> str:
            """Function with default arguments."""
            return f"{x}-{y}-{z}"

        serialized = self.serialize_func(func_with_defaults)

        # Check defaults are captured
        assert serialized["defaults"] == (10, "hello")

        deserialized = self.deserialize_func(serialized)
        assert deserialized(5) == "5-10-hello"
        assert deserialized(5, 20) == "5-20-hello"
        assert deserialized(5, 20, "world") == "5-20-world"

    def test_function_with_keyword_only_args(self):
        """Test function with keyword-only arguments."""

        def func_with_kwargs(x: int, *, y: int = 5, z: str = "test") -> str:
            """Function with keyword-only arguments."""
            return f"{x}_{y}_{z}"

        serialized = self.serialize_func(func_with_kwargs)

        # Check kwdefaults are captured
        assert serialized["kwdefaults"] == {"y": 5, "z": "test"}

        deserialized = self.deserialize_func(serialized)
        assert deserialized(3) == "3_5_test"
        assert deserialized(3, y=10) == "3_10_test"
        assert deserialized(3, z="custom") == "3_5_custom"

    def test_generator_function(self):
        """Test generator function serialization."""

        def gen_func(n: int):
            """Generator function."""
            for i in range(n):
                yield i * 2

        serialized = self.serialize_func(gen_func)

        # Check stream flag
        assert serialized["stream"] is True

        deserialized = self.deserialize_func(serialized)
        gen = deserialized(3)
        assert list(gen) == [0, 2, 4]

    def test_lambda_serialization(self):
        """Test lambda function serialization."""

        # Create lambda function for testing
        def create_lambda():
            return lambda x, y: x * y + 1

        lambda_func = create_lambda()

        serialized = self.serialize_func(lambda_func)
        assert serialized["name"] == "<lambda>"

        # Lambda should prefer hex_dumps method
        deserialized = self.deserialize_func(serialized)
        assert callable(deserialized)
        assert deserialized(3, 4) == 13

    def test_function_with_annotations(self):
        """Test function with type annotations."""

        def annotated_func(x: int, y: float, z: Optional[str] = None) -> tuple[int, float]:
            """Function with type annotations."""
            return x, y

        serialized = self.serialize_func(annotated_func)

        # Check annotations are stringified
        annotations = serialized["annotations"]
        assert "x" in annotations
        assert "y" in annotations
        assert "z" in annotations
        assert "return" in annotations

        deserialized = self.deserialize_func(serialized)
        result = deserialized(5, 3.14)
        assert result == (5, 3.14)

    def test_function_with_custom_attributes(self):
        """Test function with custom attributes in __dict__."""

        def custom_func(x: int) -> int:
            return x * 2

        # Add custom attributes
        custom_func.custom_attr = "test_value"
        custom_func.number_attr = 42

        serialized = self.serialize_func(custom_func)

        # Check custom attributes are captured (stringified)
        func_dict = serialized["dict"]
        assert "custom_attr" in func_dict
        assert "number_attr" in func_dict
        assert func_dict["custom_attr"] == "test_value"
        assert func_dict["number_attr"] == "42"

    def test_nested_function_serialization(self):
        """Test serialization of nested functions."""

        def outer_func(multiplier: int):
            def inner_func(x: int) -> int:
                return x * multiplier

            return inner_func

        inner = outer_func(5)
        serialized = self.serialize_func(inner)

        # Note: This test demonstrates limitations - nested functions with closures
        # may not deserialize correctly from source code due to missing closure variables
        # but should work with hex_dumps (cloudpickle handles closures)
        try:
            deserialized = self.deserialize_func(serialized, prefer="hex_dumps")
            assert deserialized(3) == 15
        except self.FunctionDeserializationError:
            # Expected for complex closures in some cases
            pass

    def test_deserialization_preference(self):
        """Test deserialization method preference."""

        def simple_func(x: int) -> int:
            return x + 1

        serialized = self.serialize_func(simple_func)

        # Test explicit preference for code
        deserialized_code = self.deserialize_func(serialized, prefer="code")
        assert deserialized_code(5) == 6

        # Test explicit preference for hex_dumps
        deserialized_hex = self.deserialize_func(serialized, prefer="hex_dumps")
        assert deserialized_hex(5) == 6

    def test_deserialization_fallback(self):
        """Test deserialization fallback between methods."""

        def test_func(x: int) -> int:
            return x * 3

        serialized = self.serialize_func(test_func)

        # Corrupt the code to test fallback to hex_dumps
        corrupted_serialized = serialized.copy()
        corrupted_serialized["code"] = "invalid python code!!!"

        # Should fall back to hex_dumps
        deserialized = self.deserialize_func(corrupted_serialized, prefer="code")
        assert deserialized(4) == 12

    def test_json_encoder_decoder_with_functions(self):
        """Test AhvnJsonEncoder and AhvnJsonDecoder with functions."""

        def test_func(x: int, y: int) -> int:
            """Test function for JSON encoding."""
            return x * y

        # Test encoding function in a data structure
        data = {"function": test_func, "numbers": [1, 2, 3], "nested": {"func": test_func}}

        # Encode to JSON string
        json_str = self.dumps_json(data)
        assert isinstance(json_str, str)
        assert "__obj_type__" in json_str
        assert "function" in json_str

        # Decode back from JSON
        decoded_data = self.loads_json(json_str)

        # Test that functions are properly restored
        assert callable(decoded_data["function"])
        assert callable(decoded_data["nested"]["func"])
        assert decoded_data["function"](3, 4) == 12
        assert decoded_data["nested"]["func"](5, 6) == 30
        assert decoded_data["numbers"] == [1, 2, 3]

    def test_json_encoder_with_other_types(self):
        """Test AhvnJsonEncoder handles other special types."""

        def sample_func(x: int) -> int:
            return x + 1

        data = {"function": sample_func, "tuple": (1, 2, 3), "set": {4, 5, 6}, "ellipsis": ..., "nested_list": [sample_func, (7, 8), {9, 10}]}

        # Round-trip through JSON
        json_str = self.dumps_json(data)
        decoded = self.loads_json(json_str)

        # Verify all types are preserved
        assert callable(decoded["function"])
        assert decoded["function"](5) == 6
        assert decoded["tuple"] == (1, 2, 3)
        assert decoded["set"] == {4, 5, 6}
        assert decoded["ellipsis"] is ...
        assert callable(decoded["nested_list"][0])
        assert decoded["nested_list"][1] == (7, 8)
        assert decoded["nested_list"][2] == {9, 10}

    def test_error_handling_invalid_serialized_data(self):
        """Test error handling with invalid serialized function data."""
        # Test with completely invalid data
        invalid_data = {"name": "test", "invalid": True}

        with pytest.raises(self.FunctionDeserializationError):
            self.deserialize_func(invalid_data)

    def test_error_handling_corrupted_hex_dumps(self):
        """Test error handling with corrupted hex dumps."""

        def test_func(x: int) -> int:
            return x + 1

        serialized = self.serialize_func(test_func)

        # Corrupt the hex_dumps
        corrupted_serialized = serialized.copy()
        corrupted_serialized["hex_dumps"] = "invalid_hex_data"
        corrupted_serialized["code"] = None  # Force to use hex_dumps

        with pytest.raises(self.FunctionDeserializationError):
            self.deserialize_func(corrupted_serialized, prefer="hex_dumps")

    def test_error_handling_missing_function_name(self):
        """Test error handling when function name is missing from exec'd code."""
        serialized = {"name": "missing_func", "code": "def other_func(x): return x", "hex_dumps": None}  # Wrong function name

        with pytest.raises(self.FunctionDeserializationError):
            self.deserialize_func(serialized, prefer="code")

    def test_json_decoder_function_deserialization_error(self):
        """Test JSON decoder handles function deserialization errors gracefully."""
        # Create invalid function data that will cause deserialization error
        invalid_func_data = {"__obj_type__": "function", "__obj_data__": {"name": "invalid", "code": None, "hex_dumps": None}}

        # Should return None instead of raising exception
        result = self.AhvnJsonDecoder.transform(invalid_func_data)
        assert result is None

    def test_function_without_source_attribute(self):
        """Test _patched_getsource fallback behavior."""

        def test_func(x: int) -> int:
            """Test function."""
            return x + 1

        # Remove __source__ attribute if it exists
        if hasattr(test_func, "__source__"):
            delattr(test_func, "__source__")

        # Should still work using dill.source.getsource
        serialized = self.serialize_func(test_func)
        assert "code" in serialized
        assert len(serialized["code"]) > 0

        deserialized = self.deserialize_func(serialized)
        assert deserialized(5) == 6

    def test_serialization_roundtrip_comprehensive(self):
        """Comprehensive round-trip test with complex function."""

        def complex_func(a: int, b: float = 3.14, *, c: str = "test", **kwargs) -> dict:
            """Complex function with various argument types."""
            result = {"a": a, "b": b, "c": c}
            result.update(kwargs)
            return result

        # Add custom attribute
        complex_func.metadata = {"version": "1.0", "author": "test"}

        # Serialize
        serialized = self.serialize_func(complex_func)

        # Verify serialized structure is complete
        assert serialized["name"] == "complex_func"
        assert serialized["doc"] == "Complex function with various argument types."
        assert serialized["defaults"] == (3.14,)
        assert serialized["kwdefaults"] == {"c": "test"}
        assert "metadata" in serialized["dict"]

        # Test both deserialization methods
        for prefer in ["code", "hex_dumps"]:
            deserialized = self.deserialize_func(serialized, prefer=prefer)

            # Test functionality
            result = deserialized(42, d="extra")
            expected = {"a": 42, "b": 3.14, "c": "test", "d": "extra"}
            assert result == expected

            # Test with custom arguments
            result2 = deserialized(10, 2.71, c="custom", extra="value")
            expected2 = {"a": 10, "b": 2.71, "c": "custom", "extra": "value"}
            assert result2 == expected2


class TestBinarySerialization:
    """Test Base64 and path serialization helpers."""

    def setup_method(self):
        """Set up serialization utilities for binary operations."""
        try:
            from ahvn.utils.basic.serialize_utils import load_b64, dump_b64, serialize_path, deserialize_path

            self.load_b64 = load_b64
            self.dump_b64 = dump_b64
            self.serialize_path = serialize_path
            self.deserialize_path = deserialize_path
        except ImportError as e:
            pytest.skip(f"Required modules not available: {e}")

    def test_b64_roundtrip(self, tmp_path: Path):
        """Verify load_b64 and dump_b64 preserve binary content."""
        source = tmp_path / "data.bin"
        payload = b"\x00\x01binary-data"
        source.write_bytes(payload)

        encoded = self.load_b64(str(source))
        assert encoded == base64.b64encode(payload).decode("utf-8")

        restored = tmp_path / "restored.bin"
        self.dump_b64(encoded, str(restored))
        assert restored.read_bytes() == payload

    def test_serialize_deserialize_directory(self, tmp_path: Path):
        """Ensure path serialization captures full directory trees."""
        src_root = tmp_path / "src"
        nested = src_root / "nested"
        deeper = nested / "inner"
        deeper.mkdir(parents=True)

        (src_root / "root.txt").write_text("root-level", encoding="utf-8")
        (nested / "note.md").write_text("nested", encoding="utf-8")
        binary_payload = b"\xff\x00"
        (deeper / "payload.bin").write_bytes(binary_payload)

        serialized = self.serialize_path(str(src_root))

        dirs = {path for path, content in serialized.items() if content is None}
        expected_dirs = {str(Path("nested")), str(Path("nested/inner"))}
        assert dirs == expected_dirs

        file_entries = {path: content for path, content in serialized.items() if content is not None}
        assert set(file_entries.keys()) == {str(Path("root.txt")), str(Path("nested/note.md")), str(Path("nested/inner/payload.bin"))}
        assert base64.b64decode(file_entries[str(Path("nested/inner/payload.bin"))].encode("utf-8")) == binary_payload

        dest_root = tmp_path / "dest"
        self.deserialize_path(serialized, str(dest_root))

        assert (dest_root / "nested").is_dir()
        assert (dest_root / "nested" / "inner").is_dir()
        assert (dest_root / "root.txt").read_text(encoding="utf-8") == "root-level"
        assert (dest_root / "nested" / "note.md").read_text(encoding="utf-8") == "nested"
        assert (dest_root / "nested" / "inner" / "payload.bin").read_bytes() == binary_payload

    def test_serialize_deserialize_file(self, tmp_path: Path):
        """Serialize a single file and restore it under a new directory."""
        file_path = tmp_path / "single.bin"
        payload = b"single-file"
        file_path.write_bytes(payload)

        serialized = self.serialize_path(str(file_path))
        assert list(serialized.keys()) == [file_path.name]
        assert base64.b64decode(serialized[file_path.name].encode("utf-8")) == payload

        dest = tmp_path / "file_dest"
        self.deserialize_path(serialized, str(dest))
        restored = dest / file_path.name
        assert restored.read_bytes() == payload
