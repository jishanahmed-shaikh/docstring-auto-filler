"""CLI for docstring-auto-filler."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from docfiller import __version__
from docfiller.extractor import extract_functions
from docfiller.filler import fill_file

_GREEN = "\033[92m"
_CYAN  = "\033[96m"
_YELLOW = "\033[93m"
_BOLD  = "\033[1m"
_RESET = "\033[0m"


def _progress(name: str, done: int, total: int) -> None:
    pct = int(done / total * 100)
    print(f"\r  [{pct:>3}%] {done}/{total} — {name:<40}", end="", file=sys.stderr)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        prog="docfiller",
        description="Automatically write Google-style docstrings for undocumented Python functions.",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    # fill command
    fill = sub.add_parser("fill", help="Fill missing docstrings in a Python file")
    fill.add_argument("file", help="Python file to process")
    fill.add_argument("--output", "-o", metavar="FILE",
                      help="Write output to FILE instead of overwriting (default: in-place)")
    fill.add_argument("--adapter", "-a", choices=["ollama", "openai"], default="ollama",
                      help="LLM backend (default: ollama)")
    fill.add_argument("--model", "-m", default="llama3",
                      help="Model name (default: llama3)")
    fill.add_argument("--url", default="http://localhost:11434",
                      help="API base URL (default: http://localhost:11434)")
    fill.add_argument("--api-key", metavar="KEY",
                      default=os.environ.get("OPENAI_API_KEY", ""),
                      help="API key for openai adapter (or set OPENAI_API_KEY)")
    fill.add_argument("--timeout", type=int, default=60,
                      help="Per-function timeout seconds (default: 60)")
    fill.add_argument("--skip-private", action="store_true",
                      help="Skip functions whose names start with _")
    fill.add_argument("--dry-run", action="store_true",
                      help="Print generated docstrings without modifying files")
    fill.add_argument("--quiet", "-q", action="store_true",
                      help="Suppress progress output")

    # scan command
    scan = sub.add_parser("scan", help="List undocumented functions without generating docstrings")
    scan.add_argument("file", help="Python file to scan")
    scan.add_argument("--skip-private", action="store_true",
                      help="Skip functions whose names start with _")
    scan.add_argument("--check", action="store_true",
                      help="Exit with status 1 if any undocumented functions are found (CI mode)")

    parser.add_argument("--version", "-V", action="version", version=f"%(prog)s {__version__}")

    args = parser.parse_args(argv)
    use_color = sys.stderr.isatty()

    if args.command == "scan":
        source = Path(args.file).read_text(encoding="utf-8")
        funcs  = extract_functions(source, skip_private=args.skip_private, skip_documented=True)
        if not funcs:
            if args.check:
                print(f"  PASS: all functions in {args.file} are documented.")
            else:
                print(f"  All functions in {args.file} are documented.")
            return
        print(f"\n  {len(funcs)} undocumented function(s) in {args.file}:\n")
        for f in funcs:
            print(f"  Line {f.lineno:<5} {f.qualname}")
        print()
        if args.check:
            print(f"FAIL: {len(funcs)} undocumented function(s) found", file=sys.stderr)
            sys.exit(1)
        return

    if args.command == "fill":
        if not Path(args.file).exists():
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            sys.exit(1)

        b = _BOLD if use_color else ""
        r = _RESET if use_color else ""
        g = _GREEN if use_color else ""

        print(f"\n  {b}docfiller{r} — {args.file}", file=sys.stderr)
        print(f"  Adapter: {args.adapter}  Model: {args.model}", file=sys.stderr)
        if args.dry_run:
            print(f"  {_YELLOW if use_color else ''}DRY RUN — no files will be modified{r}", file=sys.stderr)
        print(file=sys.stderr)

        result = fill_file(
            args.file,
            adapter=args.adapter,
            model=args.model,
            base_url=args.url,
            api_key=args.api_key,
            timeout=args.timeout,
            output_path=args.output,
            skip_private=args.skip_private,
            dry_run=args.dry_run,
            on_progress=_progress if not args.quiet else None,
        )

        if not args.quiet:
            print(file=sys.stderr)

        print(f"\n  {g}Filled:{r} {result['filled']}  "
              f"Skipped: {result['skipped']}  "
              f"Errors: {len(result['errors'])}")

        if result["errors"]:
            for err in result["errors"]:
                print(f"  Error: {err}", file=sys.stderr)

        if not args.dry_run:
            print(f"  Output: {result['output_path']}")
        print()
        return

    parser.print_help()


if __name__ == "__main__":
    main()
