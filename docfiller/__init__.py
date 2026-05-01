"""
docstring-auto-filler
=====================
Use AI to read Python functions and automatically write Google-style
docstrings.  Supports Ollama (local, free) and any OpenAI-compatible API.

Zero runtime dependencies — uses only the standard library.

Public API
----------
- :func:`extract_functions`  — parse a Python file and extract undocumented functions
- :func:`generate_docstring` — generate a Google-style docstring for a function
- :func:`fill_file`          — fill all missing docstrings in a Python file
"""

__version__ = "1.0.0"
__author__  = "Jishanahmed AR Shaikh"
__license__ = "MIT"

from docfiller.extractor import extract_functions, FunctionInfo  # noqa: F401
from docfiller.filler import fill_file                           # noqa: F401
from docfiller.generator import generate_docstring               # noqa: F401
