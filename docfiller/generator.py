"""
Docstring generator — calls an LLM to write Google-style docstrings.

Supports Ollama (local, free) and any OpenAI-compatible REST API.
Uses only ``urllib`` from the standard library.
"""

from __future__ import annotations

import json
import textwrap
import urllib.error
import urllib.request
from typing import Optional

from docfiller.extractor import FunctionInfo

_PROMPT_TEMPLATE = """\
You are an expert Python developer. Write a Google-style docstring for the following Python function.

Rules:
- Output ONLY the docstring content between triple quotes — no ```python, no def line, no extra text
- Start with a one-line summary sentence
- Add Args section if there are parameters (skip self/cls)
- Add Returns section if the function returns something
- Add Raises section only if the function clearly raises exceptions
- Keep it concise and accurate
- Do NOT include the triple quotes themselves in your output

Function:
{source}
"""


def _build_prompt(func: FunctionInfo) -> str:
    return _PROMPT_TEMPLATE.format(source=func.source.strip())


def _call_ollama(prompt: str, model: str, base_url: str, timeout: int) -> str:
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            return data.get("response", "").strip()
    except urllib.error.URLError as exc:
        raise ConnectionError(
            f"Cannot reach Ollama at {base_url}. Run: ollama serve"
        ) from exc


def _call_openai(prompt: str, model: str, base_url: str, api_key: str, timeout: int) -> str:
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 512,
        "temperature": 0.2,
    }).encode()
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            return data["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise RuntimeError(f"API error {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise ConnectionError(f"Cannot reach API at {base_url}") from exc


def _clean_docstring(raw: str) -> str:
    """Strip any accidental triple-quote wrappers the LLM may have added."""
    raw = raw.strip()
    for wrapper in ('"""', "'''"):
        if raw.startswith(wrapper):
            raw = raw[3:]
        if raw.endswith(wrapper):
            raw = raw[:-3]
    return raw.strip()


def generate_docstring(
    func: FunctionInfo,
    adapter: str = "ollama",
    model: str = "llama3",
    base_url: str = "http://localhost:11434",
    api_key: str = "",
    timeout: int = 60,
) -> str:
    """Generate a Google-style docstring for *func* using an LLM.

    Parameters
    ----------
    func:
        The :class:`~docfiller.extractor.FunctionInfo` to document.
    adapter:
        LLM backend: ``"ollama"`` or ``"openai"``.
    model:
        Model name (e.g. ``"llama3"`` or ``"gpt-4o-mini"``).
    base_url:
        API base URL.
    api_key:
        API key (required for ``"openai"`` adapter).
    timeout:
        Request timeout in seconds.

    Returns
    -------
    str
        The generated docstring body (without triple quotes).

    Raises
    ------
    ConnectionError
        If the LLM backend is unreachable.
    RuntimeError
        If the API returns an error response.
    """
    prompt = _build_prompt(func)

    if adapter == "ollama":
        raw = _call_ollama(prompt, model=model, base_url=base_url, timeout=timeout)
    else:
        raw = _call_openai(prompt, model=model, base_url=base_url, api_key=api_key, timeout=timeout)

    return _clean_docstring(raw)
