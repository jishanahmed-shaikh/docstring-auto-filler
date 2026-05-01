"""
Function extractor — uses ``ast`` to find undocumented functions.

Parses a Python source file without executing it and returns
structured information about every function and method that is
missing a docstring.
"""

from __future__ import annotations

import ast
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class FunctionInfo:
    """Metadata about a single Python function or method.

    Attributes
    ----------
    name:
        Function name.
    qualname:
        Qualified name including class (e.g. ``"MyClass.my_method"``).
    source:
        The raw source code of the function (signature + body).
    signature:
        The function signature line (e.g. ``"def foo(x: int) -> str:"``).
    args:
        List of argument names (excluding ``self`` and ``cls``).
    return_annotation:
        Return type annotation string, or empty string if absent.
    has_docstring:
        Whether the function already has a docstring.
    lineno:
        Line number where the function is defined (1-indexed).
    col_offset:
        Column offset (indentation level) of the ``def`` keyword.
    class_name:
        Name of the enclosing class, or empty string for module-level functions.
    """

    name: str
    qualname: str
    source: str
    signature: str
    args: List[str] = field(default_factory=list)
    return_annotation: str = ""
    has_docstring: bool = False
    lineno: int = 0
    col_offset: int = 0
    class_name: str = ""


def _get_source_segment(source_lines: List[str], node: ast.FunctionDef) -> str:
    """Extract the source lines for a function node."""
    start = node.lineno - 1
    end   = node.end_lineno if hasattr(node, "end_lineno") else start + 1
    lines = source_lines[start:end]
    # Dedent to remove class/function indentation
    return textwrap.dedent("".join(lines))


def _get_signature(node: ast.FunctionDef, source_lines: List[str]) -> str:
    """Extract just the ``def`` line of a function."""
    line = source_lines[node.lineno - 1].rstrip()
    return line.strip()


def _get_args(node: ast.FunctionDef) -> List[str]:
    """Return argument names, excluding self and cls."""
    args = []
    for arg in node.args.args:
        if arg.arg not in ("self", "cls"):
            args.append(arg.arg)
    return args


def _get_return_annotation(node: ast.FunctionDef) -> str:
    """Return the return annotation as a string, or empty string."""
    if node.returns is None:
        return ""
    try:
        return ast.unparse(node.returns)
    except AttributeError:
        # Python 3.8 fallback
        return ""


def _has_docstring(node: ast.FunctionDef) -> bool:
    """Return True if the function already has a docstring."""
    return (
        len(node.body) > 0
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    )


def extract_functions(
    source: str,
    skip_private: bool = False,
    skip_documented: bool = True,
) -> List[FunctionInfo]:
    """Parse Python source and return function metadata.

    Parameters
    ----------
    source:
        Python source code string.
    skip_private:
        If ``True``, skip functions whose names start with ``_``.
    skip_documented:
        If ``True`` (default), skip functions that already have docstrings.

    Returns
    -------
    List[FunctionInfo]
        Metadata for each matching function, in source order.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    source_lines = source.splitlines(keepends=True)
    results: List[FunctionInfo] = []

    def visit(node: ast.AST, class_name: str = "") -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                visit(child, class_name=child.name)
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                has_doc = _has_docstring(child)

                if skip_documented and has_doc:
                    visit(child, class_name=class_name)
                    continue
                if skip_private and child.name.startswith("_"):
                    visit(child, class_name=class_name)
                    continue

                qualname = f"{class_name}.{child.name}" if class_name else child.name
                seg = _get_source_segment(source_lines, child)

                results.append(FunctionInfo(
                    name=child.name,
                    qualname=qualname,
                    source=seg,
                    signature=_get_signature(child, source_lines),
                    args=_get_args(child),
                    return_annotation=_get_return_annotation(child),
                    has_docstring=has_doc,
                    lineno=child.lineno,
                    col_offset=child.col_offset,
                    class_name=class_name,
                ))
                # Recurse into nested functions
                visit(child, class_name=class_name)

    visit(tree)
    return results
