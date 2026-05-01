<div align="center">

# docstring-auto-filler

**Stop writing docstrings by hand. Let AI do it.**

Reads Python functions with `ast`, generates Google-style docstrings via Ollama or any OpenAI-compatible API, and writes them back into your source files.

[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![Zero Runtime Deps](https://img.shields.io/badge/Runtime%20Deps-Zero-22c55e?style=flat)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e?style=flat)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen?style=flat)](CONTRIBUTING.md)
[![CI](https://github.com/jishanahmed-shaikh/docstring-auto-filler/actions/workflows/ci.yml/badge.svg)](https://github.com/jishanahmed-shaikh/docstring-auto-filler/actions)

</div>

---

## Why this exists

You have a 2,000-line Python module with 40 functions and zero docstrings. Writing them by hand takes hours. `docfiller` reads each function with Python's `ast` module, sends the source to a local LLM, and inserts the generated docstring directly into your file — in seconds.

---

## Install

```bash
pip install docstring-auto-filler
```

Requires [Ollama](https://ollama.com) running locally, or an OpenAI-compatible API key.

---

## Quick start

```bash
# Scan a file to see what needs documenting
docfiller scan mymodule.py

# Fill all missing docstrings using Ollama (local, free)
docfiller fill mymodule.py

# Preview without modifying the file
docfiller fill mymodule.py --dry-run

# Use a specific model
docfiller fill mymodule.py --model mistral

# Use OpenAI instead
docfiller fill mymodule.py --adapter openai --model gpt-4o-mini --api-key sk-...

# Write to a new file instead of overwriting
docfiller fill mymodule.py --output mymodule_documented.py

# Skip private functions (starting with _)
docfiller fill mymodule.py --skip-private
```

---

## Example

**Before:**
```python
def calculate_discount(price: float, pct: float) -> float:
    if pct < 0 or pct > 100:
        raise ValueError("Percentage must be between 0 and 100")
    return price * (1 - pct / 100)
```

**After `docfiller fill pricing.py`:**
```python
def calculate_discount(price: float, pct: float) -> float:
    """Calculate the discounted price.

    Args:
        price: The original price.
        pct: Discount percentage (0-100).

    Returns:
        The price after applying the discount.

    Raises:
        ValueError: If pct is not between 0 and 100.
    """
    if pct < 0 or pct > 100:
        raise ValueError("Percentage must be between 0 and 100")
    return price * (1 - pct / 100)
```

---

## All flags

### `docfiller fill`

| Flag | Description |
|------|-------------|
| `file` | Python file to process (required) |
| `--output FILE` | Write to FILE instead of overwriting |
| `--adapter` | `ollama` or `openai` (default: `ollama`) |
| `--model` | Model name (default: `llama3`) |
| `--url` | API base URL (default: `http://localhost:11434`) |
| `--api-key` | API key for openai adapter |
| `--timeout` | Per-function timeout seconds (default: 60) |
| `--skip-private` | Skip functions starting with `_` |
| `--dry-run` | Print docstrings without modifying files |

### `docfiller scan`

| Flag | Description |
|------|-------------|
| `file` | Python file to scan |
| `--skip-private` | Skip private functions |

---

## Library usage

```python
from docfiller import extract_functions, generate_docstring, fill_file
from docfiller.extractor import FunctionInfo

# Find undocumented functions
source = open("mymodule.py").read()
funcs = extract_functions(source, skip_documented=True)

for func in funcs:
    print(f"  {func.qualname} — line {func.lineno}")

# Generate a docstring for one function
docstring = generate_docstring(funcs[0], adapter="ollama", model="llama3")
print(docstring)

# Fill an entire file
result = fill_file("mymodule.py", adapter="ollama", model="llama3")
print(f"Filled: {result['filled']}")
```

---

## How it works

1. Parses the file with `ast.parse()` — no code execution
2. Finds every function/method missing a docstring
3. Sends the function source to the LLM with a structured prompt
4. Cleans the response (strips accidental triple quotes)
5. Inserts the docstring at the correct indentation level
6. Processes functions in reverse line order so insertions don't shift positions

---

## Project structure

```
docstring-auto-filler/
├── docfiller/
│   ├── __init__.py      # Public API
│   ├── extractor.py     # AST-based function extractor
│   ├── generator.py     # LLM docstring generator (Ollama + OpenAI)
│   ├── filler.py        # File filler with reverse-order insertion
│   └── cli.py           # CLI: fill and scan subcommands
├── tests/
│   └── test_docfiller.py
├── docs/
│   └── index.html
└── pyproject.toml
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Issues labelled [`good first issue`](https://github.com/jishanahmed-shaikh/docstring-auto-filler/issues?q=label%3A%22good+first+issue%22) are a great place to start.

---

## License

[MIT](LICENSE) © 2026 [Jishanahmed AR Shaikh](https://github.com/jishanahmed-shaikh)
