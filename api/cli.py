"""Haske CLI: probe/fetch the Greenbook registry, and verify an NRN on NAPAMS.

Usage:
    uv run python -m api.cli probe
    uv run python -m api.cli fetch [--force]
    uv run python -m api.cli verify <NRN> [--category <name>]
"""

from __future__ import annotations

import argparse
import json
import sys

from .app.config import get_settings
from .registries.greenbook import GreenbookError, GreenbookSnapshotter
from .registries.napams import NapamsClient
from .registries.store import Store

_CATEGORY_NAMES = {
    "drug": "drug",
    "vaccine": "vaccine",
    "device": "device",
    "veterinary": "veterinary",
    "herbal": "herbal",
    "food": "food",
    "water": "water",
    "general": "general",
    "cosmetic": "cosmetic",
    "soap": "soap",
}


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


def cmd_verify(args: argparse.Namespace) -> int:
    from .registries.models import RegistryCategory

    settings = get_settings()
    category = RegistryCategory(_CATEGORY_NAMES.get(args.category, "general"))
    client = NapamsClient(settings)
    result = client.lookup(args.nrn, category)
    if result.reason == "playwright_not_installed":
        print("Playwright is not installed. Run:", file=sys.stderr)
        print("  uv run playwright install chromium", file=sys.stderr)
        return 1
    print(json.dumps(result.model_dump(mode="json"), indent=2, default=str))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="haske", description="Haske registry tools")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("probe", help="fetch 3 Greenbook rows and print raw fields")
    fetch = sub.add_parser("fetch", help="fetch the full Greenbook table into a dated snapshot")
    fetch.add_argument("--force", action="store_true", help="save even if suspiciously small")
    verify = sub.add_parser("verify", help="verify an NRN on the NAPAMS portal (Playwright)")
    verify.add_argument("nrn", help="NAFDAC registration number, e.g. 02-4139")
    verify.add_argument(
        "--category",
        choices=sorted(_CATEGORY_NAMES),
        default="general",
        help="product category hint (default: general)",
    )
    args = parser.parse_args(argv)
    if args.command == "probe":
        return cmd_probe(args)
    if args.command == "fetch":
        return cmd_fetch(args)
    if args.command == "verify":
        return cmd_verify(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
