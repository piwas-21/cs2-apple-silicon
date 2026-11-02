"""`cs2kit setup` - one command from a bare Mac to a launcher you double-click.

Everything this runs was previously a manual step in a long guide: fetch the one
Wine build that works, fetch DXMT, build the bottle, install the Steam client,
reuse an existing CS2 library, write the launcher app. Each step is idempotent,
so re-running after a failure continues rather than starting over.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from cs2kit import app as app_mod, bottle, engine, probe, recipe as recipe_mod
from cs2kit.util import EXIT_FAIL, EXIT_NOT_READY, EXIT_OK, emit_error, run, state_dir

DXMT_RELEASE = {
    "version": "v0.80",
    "url": "https://github.com/3Shain/DXMT/releases/download/v0.80/dxmt-v0.80-builtin.tar.gz",
    "sha256": "8f260e36b5739e68f3bad613381441385c4dc7b85b78ba8de653d5a6a264529d",
}
STEAM_SETUP = {
    "url": "https://cdn.cloudflare.steamstatic.com/client/installer/SteamSetup.exe",
    # SteamSetup.exe is executable code fetched over the network, so like every
    # other artifact it is pinned. Unlike the others its digest can legitimately
    # drift: Valve reissues the installer in place between cs2kit releases. A
    # mismatch is therefore refused, not ignored - `--trust-steam-sha` accepts
    # the new file for this install once the user has checked where it came
    # from. Digest history lives in docs/reference/toolchain.md.
    "sha256": "7d3654531c32d941b8cae81c4137fc542172bfa9635f169cb392f245a0a12bcb",
    "recorded": "2026-08-24, re-verified against the live URL on 2026-10-03 (2 380 800 B)",
}


class SetupError(RuntimeError):
    pass


def home() -> Path:
    return Path(os.environ.get("CS2KIT_SETUP_HOME", Path.home() / "CS2"))


def install_dxmt(log: Callable[[str], None] = print) -> Path:
    """Download and unpack DXMT. Returns the directory to hand to `bottle create`."""
    dest = home() / "dxmt"
    existing = sorted(dest.glob("v*/x86_64-unix/winemetal.so"))
    if existing:
        return existing[0].parent.parent
    archive = home() / "downloads" / Path(DXMT_RELEASE["url"]).name
    log(f"    fetching DXMT {DXMT_RELEASE['version']}")
    engine.download(DXMT_RELEASE["url"], archive, DXMT_RELEASE["sha256"])
    engine.extract(archive, dest)
    found = sorted(dest.glob("**/x86_64-unix/winemetal.so"))
    if not found:
        raise SetupError(f"{archive.name}: no x86_64-unix/winemetal.so inside")
    return found[0].parent.parent


def fetch_steam_installer(log: Callable[[str], None] = print,
                          trust_unpinned: bool = False) -> Path:
    """Download SteamSetup.exe and hold it to the pinned sha256.

    The pin lags behind Valve by design: they replace this file in place, so a
    mismatch may be a newer installer rather than tampering. It is still
    unverified executable code, so the default is to refuse and tell the user
    how to make an informed choice - never to run it silently."""
    installer = home() / "downloads" / "SteamSetup.exe"
    try:
        return engine.download(STEAM_SETUP["url"], installer, STEAM_SETUP["sha256"])
    except engine.EngineError as exc:
        if not trust_unpinned:
            raise SetupError(
                f"{exc}. Valve reissues this installer in place, so a newer one is possible - "
                f"check that {STEAM_SETUP['url']} is where it came from, then re-run setup with "
                "--trust-steam-sha to accept it for this install.")
        log(f"    warning: accepting an unpinned Steam installer: {exc}")
        return engine.download(STEAM_SETUP["url"], installer, None)


def install_steam_client(prefix: Path, wine_root: Path,
                         log: Callable[[str], None] = print, timeout: float = 900.0,
                         trust_unpinned: bool = False) -> Path:
    """Run SteamSetup.exe silently inside the bottle."""
    steam_exe = prefix / "drive_c" / "Program Files (x86)" / "Steam" / "Steam.exe"
    if steam_exe.is_file():
        return steam_exe
    log("    fetching the Windows Steam client")
    installer = fetch_steam_installer(log=log, trust_unpinned=trust_unpinned)
    env = wine_env(prefix, wine_root)
    log("    installing it into the bottle (silent)")
    run([str(Path(wine_root) / "bin" / "wine"), str(installer), "/S"], timeout=timeout, env=env)
    for _ in range(60):
        if steam_exe.is_file():
            return steam_exe
        time.sleep(2)
    raise SetupError("SteamSetup.exe finished but no Steam.exe appeared in the bottle")


def wine_env(prefix: Path, wine_root: Path) -> Dict[str, str]:
    """The environment every wine call in this bottle must share.

    WINEMSYNC matters more than it looks: a wineserver started without it
    poisons the prefix, and every later process dies on `msync_init` with an
    empty log and no window."""
    return {"WINEPREFIX": str(prefix), "WINEDEBUG": "-all", "WINEMSYNC": "1",
            "DYLD_FALLBACK_LIBRARY_PATH": str(Path(wine_root) / "lib"),
            "CX_ROOT": str(wine_root),
            "PATH": f"{Path(wine_root) / 'bin'}:{os.environ.get('PATH', '')}"}


def plan(args) -> List[str]:
    return [
        "check the machine (arch, Rosetta, disk)",
        f"install the Wine engine ({args.engine})",
        f"install DXMT {DXMT_RELEASE['version']}",
        "build the bottle from profiles/bottle-recipe.yaml",
        "install the Windows Steam client into the bottle",
        "move any existing CS2 install into a bottle-only library",
        "write the double-clickable launcher app",
    ]


def preflight() -> List[str]:
    """Blocking problems only - warnings belong to `cs2kit doctor`."""
    problems = []
    snap = probe.snapshot()
    if snap["stable"]["arch"] != "arm64":
        problems.append(f"this needs an Apple Silicon Mac (found {snap['stable']['arch']})")
    if not snap["volatile"]["rosetta"]:
        problems.append("Rosetta 2 is not installed: "
                        "softwareupdate --install-rosetta --agree-to-license")
    if snap["volatile"]["free_gib"] < 20:
        problems.append(f"only {snap['volatile']['free_gib']} GiB free; the stack alone needs ~20 GiB "
                        "and CS2 needs ~70 GiB more")
    return problems


def cmd_setup(args) -> int:
    steps = plan(args)
    print("cs2kit setup will:")
    for i, step in enumerate(steps, 1):
        print(f"  {i}. {step}")
    print()
    if args.dry_run:
        print("(dry run - nothing was changed)")
        return EXIT_OK

    problems = preflight()
    if problems:
        for problem in problems:
            print(f"  blocked: {problem}")
        return EXIT_NOT_READY
    print("  1/7  machine looks fine")

    try:
        print(f"  2/7  Wine engine ({args.engine})")
        record = engine.install(args.engine, log=lambda m: print(f"    {m}"))
        wine_root = Path(record["wine_root"])
        print(f"       {record['version']}")

        print(f"  3/7  DXMT {DXMT_RELEASE['version']}")
        dxmt_dir = install_dxmt()

        prefix = Path(args.prefix) if args.prefix else Path(os.environ.get("WINEPREFIX", home() / "prefix"))
        print(f"  4/7  bottle at {prefix}")
        rec = recipe_mod.load_default()
        os.environ.update(wine_env(prefix, wine_root))
        bottle.create(rec, prefix=prefix, dxmt_source=dxmt_dir, wine=wine_root)

        print("  5/7  Windows Steam client")
        install_steam_client(prefix, wine_root,
                             trust_unpinned=getattr(args, "trust_steam_sha", False))

        print("  6/7  CS2 library (kept out of macOS Steam\'s reach)")
        moved = bottle.migrate_macos_install()
        if moved["moved"]:
            print(f"       moved your existing install into {moved['dest']}")
        try:
            linked = bottle.link_steamapps(prefix)
            print(f"       library: {linked['target']}")
        except bottle.BottleError as exc:
            print(f"       skipped: {exc}")

        print("  7/7  launcher app")
        built = app_mod.build_app(Path(args.app_dest), wine_root, prefix=prefix,
                                  profile=args.profile)
        print(f"       {built['app']}")
    except (engine.EngineError, bottle.BottleError, SetupError, recipe_mod.RecipeError, OSError) as exc:
        return emit_error("setup", str(exc), json_mode=args.json)

    print()
    print("Done. Two things left, and they are yours:")
    print(f"  1. Open {built['app']} and log in to Steam (the QR code is the easy way).")
    print("  2. Install Counter-Strike 2 from your Steam library, or let it find the copy you have.")
    print()
    print("After that, double-click the app to play. `cs2kit doctor` explains anything that breaks.")
    return EXIT_OK


def register(subparsers) -> None:
    default_app = str(app_mod.default_dest())
    parser = subparsers.add_parser(
        "setup", help="one command: engine, DXMT, bottle, Steam, launcher",
        description="Runs every install step in order. Idempotent: re-running continues "
                    "instead of starting over.")
    parser.add_argument("--engine", default=engine.RECOMMENDED, choices=sorted(engine.ENGINES))
    parser.add_argument("--prefix", help="WINEPREFIX to build (default: ~/CS2/prefix)")
    parser.add_argument("--profile", default="balanced-1080p")
    parser.add_argument("--app-dest", default=default_app)
    parser.add_argument("--trust-steam-sha", action="store_true",
                        help="run a SteamSetup.exe whose sha256 no longer matches the pinned "
                             "digest (Valve reissues it between cs2kit releases; check its "
                             "origin first)")
    parser.add_argument("--dry-run", action="store_true", help="print the plan and stop")
    parser.add_argument("--json", action="store_true")
    parser.set_defaults(func=cmd_setup)
