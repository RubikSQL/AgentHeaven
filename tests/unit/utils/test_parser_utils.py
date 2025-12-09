import pytest

from ahvn.utils.basic.parser_utils import parse_keys, parse_md, parse_fc


class TestParseKeys:
    """Test the parse_keys function."""

    def test_parse_keys_list_mode_basic(self):
        """Test parsing keys in list mode with basic input."""
        response = "name: John Doe\nage: 30"
        keys = ["name", "age", "height"]
        expected = [{"key": "name", "value": "John Doe"}, {"key": "age", "value": "30"}]
        result = parse_keys(response, keys=keys, mode="list")
        assert result == expected

    def test_parse_keys_dict_mode_basic(self):
        """Test parsing keys in dictionary mode with basic input."""
        response = "name: John Doe\nage: 30"
        keys = ["name", "age", "height"]
        expected = {"name": "John Doe", "age": "30", "height": None}
        result = parse_keys(response, keys=keys, mode="dict")
        assert result == expected

    def test_parse_keys_none_list_mode(self):
        """Test parsing all keys when keys=None in list mode."""
        response = "name: John Doe\nage: 30\ncity: New York"
        expected = [
            {"key": "name", "value": "John Doe"},
            {"key": "age", "value": "30"},
            {"key": "city", "value": "New York"},
        ]
        result = parse_keys(response, keys=None, mode="list")
        assert result == expected

    def test_parse_keys_none_dict_mode(self):
        """Test parsing all keys when keys=None in dictionary mode."""
        response = "name: John Doe\nage: 30\ncity: New York"
        expected = {"name": "John Doe", "age": "30", "city": "New York"}
        result = parse_keys(response, keys=None, mode="dict")
        assert result == expected

    def test_parse_keys_multiline_values(self):
        """Test parsing keys with multiline values."""
        response = "description: This is a long description\n" "that spans multiple lines\n" "age: 25\n" "notes: Some additional notes here"
        expected = [
            {"key": "description", "value": "This is a long description\nthat spans multiple lines"},
            {"key": "age", "value": "25"},
            {"key": "notes", "value": "Some additional notes here"},
        ]
        result = parse_keys(response, keys=None, mode="list")
        assert result == expected

    def test_parse_keys_empty_response(self):
        """Test parsing empty response."""
        response = ""
        expected = []
        result = parse_keys(response, keys=None, mode="list")
        assert result == expected

    def test_parse_keys_empty_response_dict_mode(self):
        """Test parsing empty response in dict mode."""
        response = ""
        keys = ["name", "age"]
        expected = {"name": None, "age": None}
        result = parse_keys(response, keys=keys, mode="dict")
        assert result == expected

    def test_parse_keys_with_special_characters(self):
        """Test parsing keys with special characters in values."""
        response = "email: user@example.com\nurl: https://example.com/path?param=value"
        expected = [
            {"key": "email", "value": "user@example.com"},
            {"key": "url", "value": "https://example.com/path?param=value"},
        ]
        result = parse_keys(response, keys=None, mode="list")
        assert result == expected

    def test_parse_keys_missing_values(self):
        """Test parsing keys with missing or empty values."""
        response = "name: John\nage:\nempty_key:"
        expected = [
            {"key": "name", "value": "John"},
            {"key": "age", "value": ""},
            {"key": "empty_key", "value": ""},
        ]
        result = parse_keys(response, keys=None, mode="list")
        assert result == expected

    def test_parse_keys_missing_values_dict_mode(self):
        """Test parsing keys with missing or empty values in dict mode."""
        response = "name: John\nage:\nempty_key:"
        expected = {"name": "John", "age": "", "empty_key": ""}
        result = parse_keys(response, keys=None, mode="dict")
        assert result == expected

    def test_parse_keys_unicode_content(self):
        """Test parsing unicode content."""
        response = "名前: 田中太郎\n年齢: 30\nemoji: 🚀🎉"
        expected = {"名前": "田中太郎", "年齢": "30", "emoji": "🚀🎉"}
        result = parse_keys(response, keys=None, mode="dict")
        assert result == expected

    def test_parse_keys_invalid_mode(self):
        """Test that invalid mode raises an error."""
        response = "name: John"
        with pytest.raises(Exception):  # Should raise from raise_mismatch
            parse_keys(response, keys=None, mode="invalid")


class TestParseMarkdown:
    """Test the parse_md function."""

    def test_parse_md_basic_xml_tags(self):
        """Test basic markdown parsing with XML tags."""
        md_content = "<think>Hello!</think>\nSome textual output.\n<rating>5</rating>"
        expected = {"think": "Hello!", "text": "Some textual output.", "rating": "5"}
        result = parse_md(md_content)
        assert result == expected

    def test_parse_md_code_blocks(self):
        """Test parsing markdown with code blocks."""
        md_content = '```python\ndef hello():\n    return "world"\n```\n\nRegular text here.\n\n```sql\nSELECT * FROM table;\n```'
        expected = {
            "python": 'def hello():\n    return "world"',
            "text": "Regular text here.",
            "sql": "SELECT * FROM table;",
        }
        result = parse_md(md_content)
        assert result == expected

    def test_parse_md_empty_content(self):
        """Test parsing empty markdown content."""
        result = parse_md("")
        expected = {}
        assert result == expected

    def test_parse_md_list_mode(self):
        """Test parsing markdown in list mode."""
        md_content = "<think>Hello!</think>\nSome textual output.\n```sql\nSELECT *\nFROM table;\n```"
        expected = [
            {"key": "think", "value": "Hello!"},
            {"key": "text", "value": "Some textual output."},
            {"key": "sql", "value": "SELECT *\nFROM table;"},
        ]
        result = parse_md(md_content, mode="list")
        assert result == expected

    def test_parse_md_code_blocks_without_language(self):
        """Test parsing code blocks without language specification."""
        md_content = "```\nsome code\n```"
        expected = {"markdown": "some code"}
        result = parse_md(md_content)
        assert result == expected

    def test_parse_md_complex_nested_content(self):
        """Test parsing complex nested content."""
        md_content = '<think>Hello!</think>\nSome textual output.\n```sql\nSELECT *\nFROM table;\n```\n<rating>\n```json\n{"rating": 5}\n```</rating>'
        expected = {
            "think": "Hello!",
            "text": "Some textual output.",
            "sql": "SELECT *\nFROM table;",
            "rating": '```json\n{"rating": 5}\n```',
        }
        result = parse_md(md_content)
        assert result == expected

    def test_parse_md_recursive_parsing(self):
        """Test recursive parsing of nested content."""
        md_content = '<think>Hello!</think>\nSome textual output.\n```sql\nSELECT *\nFROM table;\n```\n<rating>\n```json\n{"rating": 5}\n```</rating>'
        expected = {
            "think.text": "Hello!",
            "text": "Some textual output.",
            "sql": "SELECT *\nFROM table;",
            "rating.json": '{"rating": 5}',
        }
        result = parse_md(md_content, recurse=True)
        assert result == expected

    def test_parse_md_multiple_text_blocks(self):
        """Test parsing multiple text blocks between tags."""
        md_content = "First text\n<tag1>content1</tag1>\nMiddle text\n<tag2>content2</tag2>\nLast text"
        result = parse_md(md_content)
        # Should handle multiple text blocks appropriately
        assert isinstance(result, dict)
        assert "tag1" in result
        assert "tag2" in result
        assert result["tag1"] == "content1"
        assert result["tag2"] == "content2"

    def test_parse_md_nested_tags_without_recursion(self):
        """Test nested tags without recursion enabled."""
        md_content = "<outer><inner>nested content</inner></outer>"
        result = parse_md(md_content, recurse=False)
        expected = {"outer": "<inner>nested content</inner>"}
        assert result == expected

    def test_parse_md_mixed_content_types(self):
        """Test mixing XML tags, code blocks, and text."""
        md_content = "Initial text\n<tag>xml content</tag>\n```python\ncode content\n```\nFinal text"
        result = parse_md(md_content)
        assert isinstance(result, dict)
        assert "tag" in result
        assert "python" in result
        assert result["tag"] == "xml content"
        assert result["python"] == "code content"

    def test_parse_md_invalid_mode(self):
        """Test that invalid mode returns None."""
        md_content = "<tag>content</tag>"
        with pytest.raises(Exception):  # Should raise from raise_mismatch
            parse_md(md_content, mode="invalid")


class TestParserEdgeCases:
    """Test edge cases and error handling in parsers."""

    def test_parse_keys_large_input(self):
        """Test parsing very large input."""
        # Generate large input
        large_input = "\n".join([f"key_{i}: value_{i}" for i in range(100)])
        result = parse_keys(large_input, keys=None, mode="dict")

        # Should handle large input efficiently
        assert isinstance(result, dict)
        assert len(result) == 100
        assert result["key_50"] == "value_50"

    def test_parse_keys_malformed_input_graceful_handling(self):
        """Test that malformed input is handled gracefully."""
        malformed_inputs = [
            "key_without_colon value",
            "key: value\nmalformed line without colon",
            "::empty_key:",
        ]

        for input_text in malformed_inputs:
            # Should handle malformed input gracefully without crashing
            result = parse_keys(input_text, keys=None, mode="list")
            assert isinstance(result, list)

    def test_parse_keys_whitespace_handling(self):
        """Test handling of various whitespace scenarios."""
        response = "  key1  :  value1  \n\n  key2  :  value2  \n"
        result = parse_keys(response, keys=None, mode="dict")
        # Should handle whitespace appropriately
        assert isinstance(result, dict)

    def test_parse_md_malformed_tags(self):
        """Test handling of malformed XML tags."""
        malformed_content = "<unclosed>content\n<tag>content</wrongtag>"
        result = parse_md(malformed_content)
        # Should handle malformed tags gracefully
        assert isinstance(result, dict)

    def test_parse_md_empty_tags(self):
        """Test handling of empty tags."""
        md_content = "<empty></empty>\n<nonempty>content</nonempty>"
        result = parse_md(md_content)
        expected = {"empty": "", "nonempty": "content"}
        assert result == expected

    def test_parse_md_consecutive_code_blocks(self):
        """Test handling of consecutive code blocks."""
        md_content = "```python\ncode1\n```\n```sql\ncode2\n```"
        result = parse_md(md_content)
        expected = {"python": "code1", "sql": "code2"}
        assert result == expected


class TestParseFunctionCall:
    """Test the parse_fc function."""

    def test_parse_fc_basic(self):
        call = "fibonacci(n=32)"
        expected = {"name": "fibonacci", "arguments": {"n": 32}}
        assert parse_fc(call) == expected

    def test_parse_fc_whitespace_and_types(self):
        call = " foo ( bar = 'baz' , qux = 1.5 , ok=true , nada=None ) "
        expected = {"name": "foo", "arguments": {"bar": "baz", "qux": 1.5, "ok": True, "nada": None}}
        assert parse_fc(call) == expected

    def test_parse_fc_empty_args(self):
        call = "ping()"
        expected = {"name": "ping", "arguments": {}}
        assert parse_fc(call) == expected

    def test_parse_fc_nested_literals(self):
        call = "mix(a=[1, 2], b={'x': 3})"
        expected = {"name": "mix", "arguments": {"a": [1, 2], "b": {"x": 3}}}
        assert parse_fc(call) == expected

    def test_parse_fc_trailing_comma(self):
        call = "noop(a=1,)"
        expected = {"name": "noop", "arguments": {"a": 1}}
        assert parse_fc(call) == expected

    def test_parse_fc_invalid_missing_paren(self):
        call = "broken(a=1"
        with pytest.raises(ValueError):
            parse_fc(call)

    def test_parse_fc_invalid_positional(self):
        call = "func(1, b=2)"
        with pytest.raises(ValueError):
            parse_fc(call)
