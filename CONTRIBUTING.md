# Contributing

1. Fork and clone the repo
2. `python -m venv .venv && source .venv/bin/activate`
3. `pip install -e ".[dev]"`
4. Make changes, add tests, run `pytest`
5. Open a pull request

## Good first issues

- Add `--format numpy` flag to generate NumPy-style docstrings instead of Google-style
- Add support for scanning an entire directory recursively
- Add a `--check` mode that exits 1 if any undocumented functions are found (CI use)
