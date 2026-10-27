"""Haske CLI: probe and fetch the Greenbook registry.

Usage:
    uv run python -m api.cli probe
    uv run python -m api.cli fetch [--force]
"""

from __future__ import annotations

import argparse
import json
import sys

from .app.config import get_settings
from .registries.greenbook import GreenbookError, GreenbookSnapshotter
from .registries.store import Store


def _snapshotter():
    settings = get_settings()
    store = Store(settings.db_path)
    return GreenbookSnapshotter(settings, store), store


def cmd_probe(args: argparse.Namespace) -> int:
    snapper, store = _snapshotter()
    try:
        info = snapper.probe()
    except GreenbookError as exc:
        print(f"PROBE FAILED: {exc}", file=sys.stderr)
        return 1
    finally:
        store.close()
    print(json.dumps(info, indent=2, default=str))
    print("\nNOTE: verify the columns above against the normaliser in registries/greenbook.py")
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    snapper, store = _snapshotter()
    try:
        result = snapper.fetch(force=args.force)
    except GreenbookError as exc:
        print(f"FETCH FAILED: {exc}", file=sys.stderr)
        return 1
    finally:
        store.close()
    print(json.dumps(result, indent=2, default=str))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="haske", description="Greenbook registry tools")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("probe", help="fetch 3 rows and print raw fields")
    fetch = sub.add_parser("fetch", help="fetch the full table into a dated snapshot")
    fetch.add_argument("--force", action="store_true", help="save even if suspiciously small")
    args = parser.parse_args(argv)
    if args.command == "probe":
        return cmd_probe(args)
    if args.command == "fetch":
        return cmd_fetch(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
