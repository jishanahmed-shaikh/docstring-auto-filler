"""
File filler — inserts generated docstrings into Python source files.

Reads a Python file, finds undocumented functions, generates docstrings
via the LLM, and writes the updated source back to disk (or a new file).
Processes functions in reverse line order so that inserting lines does
not shift the positions of functions not yet processed.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional

from docfiller.extractor import FunctionInfo, extract_functions
from docfiller.generator import generate_docstring


def _indent_docstring(docstring_body: str, col_offset: int) -> str:
    """Wrap a docstring body in triple quotes with correct indentation.

    Parameters
    ----------
    docstring_body:
        The raw docstring text (no triple quotes).
    col_offset:
        Column offset of the ``def`` keyword (used to compute body indent).

    Returns
    -------
    str
        Fully formatted docstring lines ready to insert.
    """
    # Body is indented one level deeper than the def
    indent = " " * (col_offset + 4)
    lines  = docstring_body.splitlines()

    if len(lines) == 1:
        # Single-line docstring
        return f'{indent}"""{lines[0]}"""\n'

    # Multi-line docstring
    result = [f'{indent}"""{lines[0]}']
    for line in lines[1:]:
        result.append(f"{indent}{line}" if line.strip() else "")
    result.append(f'{indent}"""')
    return "\n".join(result) + "\n"


def fill_file(
    path: str,
    adapter: str = "ollama",
    model: str = "llama3",
    base_url: str = "http://localhost:11434",
    api_key: str = "",
    timeout: int = 60,
    output_path: Optional[str] = None,
    skip_private: bool = False,
    dry_run: bool = False,
    on_progress: Optional[Callable[[str, int, int], None]] = None,
) -> Dict:
    """Fill missing docstrings in a Python file.

    Reads *path*, finds all undocumented functions, generates Google-style
    docstrings for each, and writes the updated source.

    Parameters
    ----------
    path:
        Path to the Python source file.
    adapter:
        LLM backend: ``"ollama"`` or ``"openai"``.
    model:
        Model name.
    base_url:
        API base URL.
    api_key:
        API key (for OpenAI adapter).
    timeout:
        Per-function LLM timeout in seconds.
    output_path:
        Write output to this path instead of overwriting *path*.
        If ``None``, overwrites *path* in-place.
    skip_private:
        Skip functions whose names start with ``_``.
    dry_run:
        If ``True``, generate and print docstrings but do not write to disk.
    on_progress:
        Optional callback ``(func_name, done, total)`` called after each function.

    Returns
    -------
    Dict
        Summary with keys: ``filled``, ``skipped``, ``errors``, ``output_path``.
    """
    src_path = Path(path)
    source   = src_path.read_text(encoding="utf-8")
    funcs    = extract_functions(source, skip_private=skip_private, skip_documented=True)

    result = {"filled": 0, "skipped": 0, "errors": [], "output_path": output_path or path}

    if not funcs:
        return result

    # Work on lines list; process in reverse order to preserve line numbers
    lines = source.splitlines(keepends=True)
    total = len(funcs)

    for i, func in enumerate(reversed(funcs)):
        try:
            docstring_body = generate_docstring(
                func,
                adapter=adapter,
                model=model,
                base_url=base_url,
                api_key=api_key,
                timeout=timeout,
            )
        except Exception as exc:
            result["errors"].append(f"{func.qualname}: {exc}")
            result["skipped"] += 1
            if on_progress:
                on_progress(func.name, i + 1, total)
            continue

        if dry_run:
            print(f"\n  {func.qualname}:")
            print(f'  """{docstring_body}"""')
            result["filled"] += 1
            if on_progress:
                on_progress(func.name, i + 1, total)
            continue

        # Find the line after the def signature to insert the docstring
        # The def may span multiple lines (e.g. multi-line args)
        insert_line = func.lineno  # 1-indexed; we insert after this line
        # Scan forward to find the colon that ends the signature
        for offset in range(0, 10):
            check_idx = func.lineno - 1 + offset
            if check_idx < len(lines) and lines[check_idx].rstrip().endswith(":"):
                insert_line = func.lineno + offset
                break

        docstring_text = _indent_docstring(docstring_body, func.col_offset)
        lines.insert(insert_line, docstring_text)
        result["filled"] += 1

        if on_progress:
            on_progress(func.name, i + 1, total)

    if not dry_run:
        dest = Path(output_path or path)
        dest.write_text("".join(lines), encoding="utf-8")
        result["output_path"] = str(dest)

    return result
