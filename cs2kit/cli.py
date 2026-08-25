"""`cs2kit` - the command-line entry point.

Command modules are plugins: each exposes `register(subparsers)` and wires its
own `func`. That keeps the dispatcher free of per-command knowledge and lets a
module be added or removed without touching this file. A module that fails to
import degrades to a stub command that explains itself rather than taking the
whole CLI down with it.
"""
from __future__ import annotations

import argparse
import importlib
import sys
from typing import List, Optional

from cs2kit import __version__
from cs2kit.util import EXIT_FAIL, EXIT_OK, EXIT_USAGE

#: Order is the order they appear in `cs2kit --help`: the order a user needs them.
COMMAND_MODULES = [
    "cs2kit.setup",
    "cs2kit.play",
    "cs2kit.stop",
    "cs2kit.doctor",
    "cs2kit.engine",
    "cs2kit.bottle",
    "cs2kit.app",
    "cs2kit.config",
    "cs2kit.verify_cmd",
    "cs2kit.launch",
    "cs2kit.bench",
    "cs2kit.report",
    "cs2kit.watch",
]

EPILOG = """\
Scope rule: CS2Kit configures and diagnoses. It never patches the game, never
wraps Steam authentication, never implements graphics, never touches VAC.

Typical order:
  cs2kit doctor                       grade the machine
  cs2kit bottle create --dxmt <dir>   build the prefix from profiles/bottle-recipe.yaml
  cs2kit config apply balanced-1080p  env vars, launch options, cvars
  cs2kit verify baseline              after Steam's 'Verify integrity of game files'
  cs2kit launch                       integrity-guarded start
  cs2kit bench run                    the T-011 protocol
  cs2kit report                       a redacted bundle to share
"""


def _stub(name: str, error: Exception):
    def register(subparsers):
        parser = subparsers.add_parser(name, help=f"unavailable: {error}")
        parser.set_defaults(func=lambda args: (print(f"cs2kit: '{name}' failed to load: {error}"),
                                               EXIT_FAIL)[1])
    return register


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cs2kit", description="Configure, diagnose and measure CS2 on Apple Silicon.",
        epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=f"cs2kit {__version__}")
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")
    for dotted in COMMAND_MODULES:
        name = dotted.rsplit(".", 1)[-1].replace("_cmd", "")
        try:
            module = importlib.import_module(dotted)
            register = getattr(module, "register")
        except Exception as exc:  # a broken plugin must not break the CLI
            register = _stub(name, exc)
        register(subparsers)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return EXIT_USAGE
    try:
        return int(func(args) or EXIT_OK)
    except KeyboardInterrupt:  # pragma: no cover
        print("\ninterrupted")
        return EXIT_FAIL
    except BrokenPipeError:  # pragma: no cover
        return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
