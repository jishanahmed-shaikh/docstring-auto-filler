"""Tests for docstring-auto-filler."""

import os
import tempfile

import pytest

from docfiller.extractor import extract_functions, FunctionInfo
from docfiller.generator import _clean_docstring, _build_prompt
from docfiller.filler import _indent_docstring, fill_file
from docfiller.cli import main


# ---------------------------------------------------------------------------
# Sample source fixtures
# ---------------------------------------------------------------------------

UNDOCUMENTED = '''\
def add(x, y):
    return x + y

def greet(name: str) -> str:
    return f"Hello, {name}"

class MyClass:
    def method(self, value: int) -> None:
        self.value = value

    def _private(self):
        pass
'''

DOCUMENTED = '''\
def add(x, y):
    """Add two numbers."""
    return x + y
'''

MIXED = '''\
def documented(x):
    """Already has a docstring."""
    return x

def undocumented(y):
    return y * 2
'''


# ---------------------------------------------------------------------------
# Extractor tests
# ---------------------------------------------------------------------------

class TestExtractFunctions:
    def test_finds_undocumented(self):
        funcs = extract_functions(UNDOCUMENTED)
        names = [f.name for f in funcs]
        assert "add" in names
        assert "greet" in names

    def test_skips_documented(self):
        funcs = extract_functions(DOCUMENTED, skip_documented=True)
        assert funcs == []

    def test_mixed_only_undocumented(self):
        funcs = extract_functions(MIXED, skip_documented=True)
        assert len(funcs) == 1
        assert funcs[0].name == "undocumented"

    def test_finds_class_methods(self):
        funcs = extract_functions(UNDOCUMENTED)
        qualnames = [f.qualname for f in funcs]
        assert "MyClass.method" in qualnames

    def test_skip_private(self):
        funcs = extract_functions(UNDOCUMENTED, skip_private=True)
        names = [f.name for f in funcs]
        assert "_private" not in names

    def test_include_private_by_default(self):
        funcs = extract_functions(UNDOCUMENTED, skip_private=False)
        names = [f.name for f in funcs]
        assert "_private" in names

    def test_args_extracted(self):
        funcs = extract_functions(UNDOCUMENTED)
        add_func = next(f for f in funcs if f.name == "add")
        assert "x" in add_func.args
        assert "y" in add_func.args

    def test_self_excluded_from_args(self):
        funcs = extract_functions(UNDOCUMENTED)
        method = next(f for f in funcs if f.name == "method")
        assert "self" not in method.args
        assert "value" in method.args

    def test_return_annotation(self):
        funcs = extract_functions(UNDOCUMENTED)
        greet = next(f for f in funcs if f.name == "greet")
        assert greet.return_annotation == "str"

    def test_lineno_set(self):
        funcs = extract_functions(UNDOCUMENTED)
        add_func = next(f for f in funcs if f.name == "add")
        assert add_func.lineno == 1

    def test_syntax_error_returns_empty(self):
        funcs = extract_functions("def broken(:")
        assert funcs == []

    def test_empty_source(self):
        funcs = extract_functions("")
        assert funcs == []


# ---------------------------------------------------------------------------
# Generator helper tests (no LLM calls)
# ---------------------------------------------------------------------------

class TestCleanDocstring:
    def test_strips_triple_quotes(self):
        raw = '"""This is a docstring."""'
        assert _clean_docstring(raw) == "This is a docstring."

    def test_strips_single_triple_quotes(self):
        raw = "'''This is a docstring.'''"
        assert _clean_docstring(raw) == "This is a docstring."

    def test_no_quotes_unchanged(self):
        raw = "This is a docstring."
        assert _clean_docstring(raw) == "This is a docstring."

    def test_strips_whitespace(self):
        raw = "  \n  Some text.  \n  "
        assert _clean_docstring(raw) == "Some text."


class TestBuildPrompt:
    def test_prompt_contains_source(self):
        funcs = extract_functions("def foo(x): return x")
        assert funcs
        prompt = _build_prompt(funcs[0])
        assert "def foo" in prompt

    def test_prompt_mentions_google_style(self):
        funcs = extract_functions("def foo(x): return x")
        prompt = _build_prompt(funcs[0])
        assert "Google" in prompt


# ---------------------------------------------------------------------------
# CLI scan tests
# ---------------------------------------------------------------------------

class TestScanCheck:
    def test_check_passes_when_all_documented(self, capsys):
        src = 'def foo():\n    """Return nothing."""\n    return None\n'
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(src)
            path = f.name

        try:
            main(["scan", path, "--check"])
            captured = capsys.readouterr()
            assert "PASS" in captured.out
            assert captured.err == ""
        finally:
            os.unlink(path)

    def test_check_fails_when_undocumented(self, capsys):
        src = "def foo():\n    return None\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(src)
            path = f.name

        try:
            with pytest.raises(SystemExit) as excinfo:
                main(["scan", path, "--check"])
            captured = capsys.readouterr()
            assert excinfo.value.code == 1
            assert "foo" in captured.out
            assert "FAIL: 1 undocumented function(s) found" in captured.err
        finally:
            os.unlink(path)

    def test_scan_without_check_unchanged(self, capsys):
        src = "def foo():\n    return None\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(src)
            path = f.name

        try:
            main(["scan", path])
            captured = capsys.readouterr()
            assert "1 undocumented function(s)" in captured.out
            assert "foo" in captured.out
            assert captured.err == ""
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# Filler tests (no LLM — uses a mock generator)
# ---------------------------------------------------------------------------

class TestIndentDocstring:
    def test_single_line(self):
        result = _indent_docstring("Add two numbers.", col_offset=0)
        assert '"""Add two numbers."""' in result

    def test_indented(self):
        result = _indent_docstring("Do something.", col_offset=4)
        assert result.startswith("        ")

    def test_multiline(self):
        body = "Summary line.\n\nArgs:\n    x: A number."
        result = _indent_docstring(body, col_offset=0)
        assert '"""Summary line.' in result
        assert '"""' in result


class TestFillFile:
    def test_fills_undocumented_with_mock(self):
        """Test fill_file using a mock generator that returns a fixed docstring."""
        from unittest.mock import patch

        src = "def foo(x):\n    return x\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(src)
            path = f.name

        try:
            with patch("docfiller.filler.generate_docstring", return_value="Return x unchanged."):
                result = fill_file(path, adapter="ollama")
            assert result["filled"] == 1
            assert result["errors"] == []
            content = open(path).read()
            assert "Return x unchanged." in content
        finally:
            os.unlink(path)

    def test_dry_run_does_not_modify_file(self):
        from unittest.mock import patch

        src = "def bar(y):\n    return y\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(src)
            path = f.name

        try:
            with patch("docfiller.filler.generate_docstring", return_value="Return y."):
                result = fill_file(path, dry_run=True)
            assert result["filled"] == 1
            content = open(path).read()
            assert "Return y." not in content  # file unchanged
        finally:
            os.unlink(path)

    def test_already_documented_not_filled(self):
        from unittest.mock import patch

        src = 'def baz():\n    """Already documented."""\n    pass\n'
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(src)
            path = f.name

        try:
            with patch("docfiller.filler.generate_docstring") as mock_gen:
                result = fill_file(path)
            mock_gen.assert_not_called()
            assert result["filled"] == 0
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# --format / fmt tests
# ---------------------------------------------------------------------------

class TestBuildPromptFormat:
    def test_default_fmt_is_google(self):
        funcs = extract_functions("def foo(x): return x")
        prompt = _build_prompt(funcs[0])
        assert "Google" in prompt

    def test_google_fmt_prompt_contains_google(self):
        funcs = extract_functions("def foo(x): return x")
        prompt = _build_prompt(funcs[0], fmt="google")
        assert "Google" in prompt

    def test_google_fmt_prompt_excludes_numpy(self):
        funcs = extract_functions("def foo(x): return x")
        prompt = _build_prompt(funcs[0], fmt="google")
        assert "NumPy" not in prompt

    def test_numpy_fmt_prompt_contains_numpy(self):
        funcs = extract_functions("def foo(x): return x")
        prompt = _build_prompt(funcs[0], fmt="numpy")
        assert "NumPy" in prompt

    def test_numpy_fmt_prompt_excludes_google(self):
        funcs = extract_functions("def foo(x): return x")
        prompt = _build_prompt(funcs[0], fmt="numpy")
        assert "Google" not in prompt

    def test_numpy_prompt_has_underline_convention(self):
        funcs = extract_functions("def foo(x): return x")
        prompt = _build_prompt(funcs[0], fmt="numpy")
        assert "----------" in prompt


class TestFillFileFmt:
    def test_fmt_google_forwarded_to_generate(self):
        from unittest.mock import patch

        src = "def foo(x):\n    return x\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(src)
            path = f.name

        try:
            with patch("docfiller.filler.generate_docstring", return_value="Return x.") as mock_gen:
                fill_file(path, fmt="google")
            _, kwargs = mock_gen.call_args
            assert kwargs["fmt"] == "google"
        finally:
            os.unlink(path)

    def test_fmt_numpy_forwarded_to_generate(self):
        from unittest.mock import patch

        src = "def foo(x):\n    return x\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(src)
            path = f.name

        try:
            with patch("docfiller.filler.generate_docstring", return_value="Return x.") as mock_gen:
                fill_file(path, fmt="numpy")
            _, kwargs = mock_gen.call_args
            assert kwargs["fmt"] == "numpy"
        finally:
            os.unlink(path)

    def test_fmt_default_is_google(self):
        from unittest.mock import patch

        src = "def foo(x):\n    return x\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(src)
            path = f.name

        try:
            with patch("docfiller.filler.generate_docstring", return_value="Return x.") as mock_gen:
                fill_file(path)
            _, kwargs = mock_gen.call_args
            assert kwargs["fmt"] == "google"
        finally:
            os.unlink(path)


class TestCLIFormatFlag:
    def test_default_format_is_google(self):
        from unittest.mock import patch

        src = "def foo(x):\n    return x\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(src)
            path = f.name

        try:
            with patch("docfiller.filler.generate_docstring", return_value="x.") as mock_gen:
                main(["fill", path, "--quiet"])
            _, kwargs = mock_gen.call_args
            assert kwargs["fmt"] == "google"
        finally:
            os.unlink(path)

    def test_format_numpy_passed_through(self):
        from unittest.mock import patch

        src = "def foo(x):\n    return x\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(src)
            path = f.name

        try:
            with patch("docfiller.filler.generate_docstring", return_value="x.") as mock_gen:
                main(["fill", path, "--format", "numpy", "--quiet"])
            _, kwargs = mock_gen.call_args
            assert kwargs["fmt"] == "numpy"
        finally:
            os.unlink(path)

    def test_invalid_format_exits(self):
        with pytest.raises(SystemExit):
            main(["fill", "dummy.py", "--format", "sphinx"])

    def test_format_google_explicit(self):
        from unittest.mock import patch

        src = "def foo(x):\n    return x\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(src)
            path = f.name

        try:
            with patch("docfiller.filler.generate_docstring", return_value="x.") as mock_gen:
                main(["fill", path, "--format", "google", "--quiet"])
            _, kwargs = mock_gen.call_args
            assert kwargs["fmt"] == "google"
        finally:
            os.unlink(path)