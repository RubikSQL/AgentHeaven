"""
Unit tests for Jinja template utilities.

This module tests the Jinja template loading and rendering functionality
for different path types, languages, filters, and template composition.
Tests use only system/ templates to avoid dependencies on legacy templates.
"""

import pytest
from ahvn import load_jinja_env, create_jinja
from ahvn.utils.basic.config_utils import hpj
from ahvn.utils.basic.file_utils import exists_dir, touch_dir
from ahvn.ukf.templates.basic.prompt import PromptUKFT
from jinja2 import TemplateNotFound
import tempfile


class TestJinjaEnvironmentLoading:
    """Test loading Jinja environments with different path configurations."""

    def test_load_jinja_env_single_path(self):
        """Test loading Jinja environment from a single path."""
        env = load_jinja_env("& prompts/system", lang="en")
        assert env is not None

        # Verify templates can be loaded
        template = env.get_template("prompt.jinja")
        assert template is not None

    def test_load_jinja_env_list_paths(self):
        """Test loading Jinja environment from multiple paths (ChoiceLoader)."""
        paths = ["& prompts/system", "& prompts/autotask"]
        env = load_jinja_env(paths, lang="en")
        assert env is not None

        # Should be able to load templates from either path
        template1 = env.get_template("prompt.jinja")  # from system
        assert template1 is not None

    def test_load_jinja_env_dict_paths(self):
        """Test loading Jinja environment with prefixed paths (PrefixLoader)."""
        paths = {"system": "& prompts/system", "autotask": "& prompts/autotask"}
        env = load_jinja_env(paths, lang="en")
        assert env is not None

        # Templates should be accessible with prefix
        template = env.get_template("system/prompt.jinja")
        assert template is not None

    def test_load_jinja_env_default_scan_paths(self):
        """Test loading Jinja environment with default scan paths from config."""
        # When path is None, it should use prompts.scan from config
        env = load_jinja_env(lang="en")
        assert env is not None

    def test_load_jinja_env_nonexistent_path(self):
        """Test loading Jinja environment with nonexistent path."""
        # Should not raise error, just won't find templates in that path
        env = load_jinja_env("/nonexistent/path", lang="en")
        assert env is not None


class TestJinjaI18n:
    """Test Jinja i18n (internationalization) functionality."""

    def test_i18n_english(self):
        """Test rendering templates with English translations."""
        env = load_jinja_env("& prompts/system", lang="en")
        template = env.get_template("prompt_instance.jinja")

        instance = {"inputs": {"x": 1, "y": 2}, "output": 3, "metadata": {"hints": ["Test hint"]}}
        rendered = template.render(instance=instance)

        # Should contain English text
        assert "Inputs:" in rendered
        assert "Output:" in rendered
        assert "Hints:" in rendered

    def test_i18n_chinese(self):
        """Test rendering templates with Chinese translations."""
        env = load_jinja_env("& prompts/system", lang="zh")
        template = env.get_template("prompt_instance.jinja")

        instance = {"inputs": {"x": 1, "y": 2}, "output": 3, "metadata": {"hints": ["测试提示"]}}
        rendered = template.render(instance=instance)

        # Should contain Chinese text
        assert "输入:" in rendered
        assert "输出:" in rendered
        assert "提示:" in rendered

    def test_i18n_full_prompt_english(self):
        """Test rendering full prompt template with English."""
        env = load_jinja_env("& prompts/system", lang="en")
        template = env.get_template("prompt.jinja")

        rendered = template.render(
            system="You are a helpful assistant.", descriptions=["Task 1", "Task 2"], instance={"inputs": {"query": "test"}, "metadata": {}}
        )

        assert "Task Descriptions" in rendered
        assert "New Instance" in rendered

    def test_i18n_full_prompt_chinese(self):
        """Test rendering full prompt template with Chinese."""
        env = load_jinja_env("& prompts/system", lang="zh")
        template = env.get_template("prompt.jinja")

        rendered = template.render(system="你是一个乐于助人的助手。", descriptions=["任务 1", "任务 2"], instance={"inputs": {"query": "测试"}, "metadata": {}})

        assert "任务描述" in rendered
        assert "新实例" in rendered


class TestJinjaFilters:
    """Test custom Jinja filters loaded from system/filters/."""

    def test_value_repr_filter(self):
        """Test value_repr filter for string representation with cutoff."""
        env = load_jinja_env("& prompts/system", lang="en")

        # Create a simple template to test the filter
        from jinja2 import Template

        template = env.from_string("{{ content | value_repr(cutoff=20) }}")

        long_string = "This is a very long string that should be truncated"
        rendered = template.render(content=long_string)

        # Should be truncated with ...
        assert len(rendered) <= 20
        assert rendered.endswith("...")

    def test_value_repr_filter_no_cutoff(self):
        """Test value_repr filter without cutoff."""
        env = load_jinja_env("& prompts/system", lang="en")
        template = env.from_string("{{ content | value_repr(cutoff=-1) }}")

        long_string = "This is a very long string that should NOT be truncated"
        rendered = template.render(content=long_string)

        # Should not be truncated
        assert "..." not in rendered
        assert "long string" in rendered

    def test_json_repr_filter(self):
        """Test json_repr filter for JSON representation."""
        env = load_jinja_env("& prompts/system", lang="en")
        template = env.from_string("{{ content | json_repr(cutoff=50, indent=2) }}")

        data = {"key1": "value1", "key2": [1, 2, 3]}
        rendered = template.render(content=data)

        # Should be valid JSON format
        assert "key1" in rendered
        assert "value1" in rendered

    def test_line_numbered_filter(self):
        """Test line_numbered filter for adding line numbers to code."""
        env = load_jinja_env("& prompts/system", lang="en")
        template = env.from_string("{{ content | line_numbered(start=1) }}")

        code = "def foo():\n    pass\n    return 42"
        rendered = template.render(content=code)

        # Should have line numbers
        assert "(   1)" in rendered
        assert "(   2)" in rendered


class TestJinjaTemplateRendering:
    """Test rendering of system templates with various inputs."""

    def test_block_template_base_mode(self):
        """Test block.jinja template with base mode."""
        env = load_jinja_env("& prompts/system", lang="en")
        template = env.get_template("block.jinja")

        rendered = template.render(content="Simple text", mode="base")
        assert "Simple text" in rendered

    def test_block_template_repr_mode(self):
        """Test block.jinja template with repr mode."""
        env = load_jinja_env("& prompts/system", lang="en")
        template = env.get_template("block.jinja")

        data = {"key": "value"}
        rendered = template.render(content=data, mode="repr", cutoff=100)
        assert "key" in rendered

    def test_block_template_json_mode(self):
        """Test block.jinja template with json mode."""
        env = load_jinja_env("& prompts/system", lang="en")
        template = env.get_template("block.jinja")

        data = {"test": [1, 2, 3]}
        rendered = template.render(content=data, mode="json", indent=2)
        assert "test" in rendered

    def test_block_template_code_mode(self):
        """Test block.jinja template with code mode."""
        env = load_jinja_env("& prompts/system", lang="en")
        template = env.get_template("block.jinja")

        code = "def add(a, b):\n    return a + b"
        rendered = template.render(content=code, mode="code", language="python", start=1)
        assert "def add" in rendered

    def test_prompt_instance_with_inputs(self):
        """Test prompt_instance.jinja with various inputs."""
        env = load_jinja_env("& prompts/system", lang="en")
        template = env.get_template("prompt_instance.jinja")

        instance = {
            "inputs": {"x": 10, "y": 20, "data": [1, 2, 3]},
            "output": 30,
            "expected": 30,
            "metadata": {"hints": ["Add x and y", "Result should be 30"], "notes": ["This is a test"]},
        }

        rendered = template.render(instance=instance)

        # Verify all sections are present
        assert "Inputs:" in rendered
        assert "Output:" in rendered
        assert "Expected:" in rendered
        assert "Hints:" in rendered
        assert "Notes:" in rendered
        assert "x: 10" in rendered
        assert "y: 20" in rendered

    def test_prompt_instance_minimal(self):
        """Test prompt_instance.jinja with minimal data."""
        env = load_jinja_env("& prompts/system", lang="en")
        template = env.get_template("prompt_instance.jinja")

        instance = {"inputs": {"query": "test"}, "metadata": {}}

        rendered = template.render(instance=instance)

        # Should render without errors
        assert "Inputs:" in rendered
        assert "query" in rendered

    def test_prompt_template_full(self):
        """Test full prompt.jinja template with all sections."""
        env = load_jinja_env("& prompts/system", lang="en")
        template = env.get_template("prompt.jinja")

        rendered = template.render(
            system="You are a helpful AI assistant.",
            descriptions=["Complete the task", "Be accurate"],
            examples=[{"inputs": {"x": 1, "y": 2}, "output": 3, "metadata": {}}],
            instructions=["Follow the examples", "Show your work"],
            instance={"inputs": {"x": 5, "y": 7}, "metadata": {}},
        )

        # Verify all sections
        assert "You are a helpful AI assistant." in rendered
        assert "Task Descriptions" in rendered
        assert "Examples" in rendered
        assert "Instructions" in rendered
        assert "New Instance" in rendered


class TestJinjaUtilityFunctions:
    """Test utility functions like create_jinja."""

    def test_create_jinja_basic(self):
        """Test creating a simple Jinja template."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = hpj(tmpdir, "test_prompt")

            content = "Hello {{ name }}!"
            create_jinja(path=test_path, entry="greeting.jinja", content=content, autojinja=False, autoi18n=False)

            # Verify template was created
            assert exists_dir(test_path)

            # Load and test the template
            env = load_jinja_env(test_path, lang="en")
            template = env.get_template("greeting.jinja")
            rendered = template.render(name="World")

            assert rendered == "Hello World!"

    def test_create_jinja_with_i18n(self):
        """Test creating a Jinja template with i18n support."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = hpj(tmpdir, "test_i18n_prompt")

            content = "{% trans %}Greeting{% endtrans %}: {{ name }}"
            create_jinja(path=test_path, entry="default.jinja", content=content, autojinja=False, autoi18n=False)  # Don't auto-translate, just set up structure

            # Verify locale structure was created
            locale_path = hpj(test_path, "locale")
            assert exists_dir(locale_path)


class TestJinjaBuiltinFeatures:
    """Test built-in Jinja features and extensions."""

    def test_builtin_filter_zip(self):
        """Test built-in zip filter."""
        env = load_jinja_env("& prompts/system", lang="en")
        template = env.from_string("{% for a, b in list1 | zip(list2) %}{{ a }}-{{ b }} {% endfor %}")

        rendered = template.render(list1=[1, 2, 3], list2=["a", "b", "c"])
        assert "1-a" in rendered
        assert "2-b" in rendered
        assert "3-c" in rendered

    def test_builtin_test_ellipsis(self):
        """Test built-in ellipsis test."""
        env = load_jinja_env("& prompts/system", lang="en")
        template = env.from_string("{% if value is ellipsis %}Ellipsis{% else %}Not Ellipsis{% endif %}")

        rendered = template.render(value=...)
        assert "Ellipsis" in rendered

        rendered = template.render(value=None)
        assert "Not Ellipsis" in rendered

    def test_builtin_global_ellipsis(self):
        """Test built-in Ellipsis global variable."""
        env = load_jinja_env("& prompts/system", lang="en")
        template = env.from_string("{% if value is not ellipsis %}{{ value }}{% else %}...{% endif %}")

        # NativeEnvironment returns native Python types, so 42 is int not str
        rendered = template.render(value=42)
        assert rendered == 42


class TestPromptUKFT:
    """Test PromptUKFT integration with Jinja utilities."""

    def test_prompt_ukft_from_path(self):
        """Test creating PromptUKFT from path."""
        prompt = PromptUKFT.from_path("& prompts/system", default_entry="prompt.jinja")

        assert prompt.name == "system"
        assert prompt.type == "prompt"

    def test_prompt_ukft_render(self):
        """Test rendering with PromptUKFT."""
        prompt = PromptUKFT.from_path("& prompts/system", default_entry="prompt_instance.jinja", lang="en")

        instance = {"inputs": {"value": 42}, "output": "result", "metadata": {}}

        rendered = prompt.render(instance=instance)
        assert "Inputs:" in rendered
        assert "value" in rendered

    def test_prompt_ukft_render_with_language(self):
        """Test rendering with PromptUKFT in different languages."""
        prompt = PromptUKFT.from_path("& prompts/system", default_entry="prompt_instance.jinja", lang="zh")

        instance = {"inputs": {"值": 42}, "output": "结果", "metadata": {}}

        rendered = prompt.render(instance=instance)
        assert "输入:" in rendered

    def test_prompt_ukft_list_templates(self):
        """Test listing templates in PromptUKFT."""
        prompt = PromptUKFT.from_path("& prompts/system")
        templates = prompt.list_templates()

        # Should contain system templates
        assert len(templates) > 0
        assert any("prompt" in t for t in templates)

    def test_prompt_ukft_from_jinja(self):
        """Test creating PromptUKFT from jinja content."""
        content = """
{% trans %}Task{% endtrans %}: {{ task_name }}

{% trans %}Instructions{% endtrans %}:
- {{ instruction }}
"""

        prompt = PromptUKFT.from_jinja(content=content, name="test_prompt", lang="en")

        rendered = prompt.render(task_name="Test Task", instruction="Do something")

        assert "Task: Test Task" in rendered
        assert "Instructions" in rendered
        assert "Do something" in rendered
