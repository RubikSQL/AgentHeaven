import base64
import os
from pathlib import Path

import pytest

from ahvn.ukf.templates.basic.resource import ResourceUKFT


def _write_sample_tree(root: Path) -> None:
    (root / "nested").mkdir(parents=True)
    (root / "root.txt").write_text("root-level", encoding="utf-8")
    (root / "nested" / "child.txt").write_text("child-level", encoding="utf-8")


def test_from_path_populates_resource_metadata(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    sample_file = source_dir / "example.txt"
    sample_file.write_text("hello resource", encoding="utf-8")

    resource = ResourceUKFT.from_path(str(source_dir))

    assert resource.name == "source"
    assert resource.type == "resource"
    assert resource.content_resources["path"] == str(source_dir.resolve())

    data = resource.content_resources["data"]
    assert set(data.keys()) == {"example.txt"}
    decoded = base64.b64decode(data["example.txt"].encode()).decode("utf-8")
    assert decoded == "hello resource"

    assert "diagram" in resource.content_composers
    assert "[UKF_TYPE:resource]" in resource.tags
    diagram_text = resource.text("diagram")
    assert "example.txt" in diagram_text


def test_from_data_requires_name_or_path():
    with pytest.raises(ValueError):
        ResourceUKFT.from_data({})


def test_from_data_infers_name_from_path(tmp_path):
    sample_path = tmp_path / "my_bundle"
    data = {"file.txt": base64.b64encode(b"content").decode()}

    resource = ResourceUKFT.from_data(data, path=str(sample_path))

    assert resource.name == "my_bundle"
    assert resource.content_resources["path"] == str(sample_path.resolve())
    assert resource.content_resources["data"] == data


def test_annotate_returns_new_instance(tmp_path):
    source_dir = tmp_path / "annotate"
    source_dir.mkdir()
    (source_dir / "file.txt").write_text("data", encoding="utf-8")
    resource = ResourceUKFT.from_path(str(source_dir))

    annotated = resource.annotate("file.txt", "important")

    assert annotated is not resource
    assert annotated.content_resources["annotations"]["file.txt"] == "important"
    assert resource.content_resources["annotations"] == {}


def test_to_path_restores_content(tmp_path):
    source_dir = tmp_path / "serialize"
    _write_sample_tree(source_dir)
    resource = ResourceUKFT.from_path(str(source_dir))

    target_dir = tmp_path / "restored"
    resource.to_path(str(target_dir))

    assert (target_dir / "root.txt").read_text(encoding="utf-8") == "root-level"
    assert (target_dir / "nested" / "child.txt").read_text(encoding="utf-8") == "child-level"


def test_context_manager_extracts_and_cleans(tmp_path):
    source_dir = tmp_path / "ctx"
    _write_sample_tree(source_dir)
    resource = ResourceUKFT.from_path(str(source_dir))

    with resource(cleanup=True) as temp_path:
        temp_path = Path(temp_path)
        assert temp_path.exists()
        assert (temp_path / "nested" / "child.txt").read_text(encoding="utf-8") == "child-level"

    assert not hasattr(resource, "_temp_path")


def test_context_manager_persistent_skips_cleanup(tmp_path):
    source_dir = tmp_path / "ctx_persist"
    _write_sample_tree(source_dir)
    resource = ResourceUKFT.from_path(str(source_dir))

    destination = tmp_path / "persisted"
    with resource(path=str(destination), overwrite=True, cleanup=False):
        assert (destination / "nested" / "child.txt").read_text(encoding="utf-8") == "child-level"

    assert destination.exists()
    assert (destination / "root.txt").read_text(encoding="utf-8") == "root-level"


def test_context_manager_existing_directory_not_removed(tmp_path):
    source_dir = tmp_path / "ctx_existing"
    _write_sample_tree(source_dir)
    resource = ResourceUKFT.from_path(str(source_dir))

    destination = tmp_path / "preexisting"
    destination.mkdir()

    with resource(path=str(destination)):
        assert (destination / "nested" / "child.txt").read_text(encoding="utf-8") == "child-level"

    assert destination.exists()
    assert (destination / "root.txt").read_text(encoding="utf-8") == "root-level"
