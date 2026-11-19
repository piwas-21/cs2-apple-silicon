"""`cs2kit app create` - a double-clickable launcher, so playing needs no terminal.

The CLI is the right interface for building and diagnosing a bottle, and the
wrong interface for starting a game. This generates a small `.app` whose
launcher script runs the same integrity-guarded path as `cs2kit launch`: verify
the guarded binaries, start the Steam client if it is not up, then start CS2.
It embeds no third-party code - it is a plist and a shell script.

The app never reaches into the checkout at launch time. A checkout usually
lives in ~/Documents, and macOS (TCC) silently denies Finder-launched apps
access there - the exec fails with `Operation not permitted` and the app looks
dead (measured 2026-10-31). So `build_app` first stages a self-contained
runtime - the `cs2kit` package, the upstream `bin/cs2kit` entry point and
`profiles/` - into `~/.cs2kit/runtime`, and the generated scripts point there.
The copy is built and verified beside the live one and only then swapped in,
so a failed refresh cannot break the installed app. Re-run `cs2kit app create`
after updating the checkout to refresh the copy.
"""
from __future__ import annotations

import ast
import fcntl
import json
import os
import re
import shutil
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from cs2kit import recipe as recipe_mod
from cs2kit.util import EXIT_OK, emit_error, repo_root, state_dir, wineprefix

def _as_str(value: object) -> str:
    return str(value)


def _shell_quote(value: object) -> str:
    import shlex

    return shlex.quote(_as_str(value))


def _applescript_quote(value: object) -> str:
    """Escape a value for use inside an AppleScript double-quoted string."""
    return _as_str(value).replace("\\", "\\\\").replace('"', '\\"')


def _xml_quote(value: object) -> str:
    """Escape a value for use inside a plist XML text node."""
    return (_as_str(value).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


APPLESCRIPT = '''set repoPath to "{repo}"
set winePrefix to "{prefix}"
set profileName to "{profile}"
set logFile to (POSIX path of (path to home folder)) & "CS2/cs2kit-app.log"
do shell script "mkdir -p \\"$(dirname " & quoted form of logFile & ")\\""
do shell script "cd " & quoted form of repoPath & " && CS2KIT_REPO=" & quoted form of repoPath & ¬
    " WINEPREFIX=" & quoted form of winePrefix & ¬
    " ./bin/cs2kit play --profile " & quoted form of profileName & " --gui --detach >> " & ¬
    quoted form of logFile & " 2>&1"
'''

#: Fallback for a machine without osacompile: a plain script bundle. It works,
#: but LaunchServices is fussier about it (see docs/troubleshooting.md #25d).
#: Values are inserted pre-quoted with shlex.quote - the profile name and paths
#: come from a YAML file (or the command line) and must not be able to break
#: out of the generated script.
LAUNCHER = r'''#!/bin/bash
set -uo pipefail
export CS2KIT_REPO={repo}
export WINEPREFIX={prefix}
LOG="$HOME/CS2/cs2kit-app.log"
mkdir -p "$(dirname "$LOG")"
"$CS2KIT_REPO/bin/cs2kit" play --profile {profile} --gui --detach >>"$LOG" 2>&1
exit 0
'''

PLIST = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>{name}</string>
  <key>CFBundleDisplayName</key><string>{name}</string>
  <key>CFBundleIdentifier</key><string>org.cs2kit.{ident}</string>
  <key>CFBundleVersion</key><string>{version}</string>
  <key>CFBundleShortVersionString</key><string>{version}</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>{exe}</string>
  <key>CFBundleIconFile</key><string>cs2kit</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>LSApplicationCategoryType</key><string>public.app-category.action-games</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
'''


def _set_identity(dest: Path, name: str) -> None:
    """Give the bundle an identity of its own.

    `osacompile` names every applet `com.apple.ScriptEditor.id.<name>`, and
    macOS keeps state per identifier and per app name. The state of that
    Script Editor identity was stale, and macOS killed the processes the app
    started: the launcher ran, wrote its log line, and the Steam client it
    spawned died a second later - every single time, while an otherwise
    identical bundle with its own identifier worked (measured 2026-11-12).

    An installed app should carry its own identifier anyway. The bundle is
    re-sealed after this (see `build_app`), because editing the Info.plist
    invalidates the signature."""
    import subprocess

    ident = "org.cs2kit." + re.sub(r"[^A-Za-z0-9.-]", "-", name).strip("-").lower()
    plist = dest / "Contents" / "Info.plist"
    for key, value in (("CFBundleIdentifier", ident), ("CFBundleName", name)):
        proc = subprocess.run(["plutil", "-replace", key, "-string", value, str(plist)],
                              capture_output=True, text=True, timeout=30)
        if proc.returncode != 0:
            raise OSError(f"could not set {key} on the launcher bundle: "
                          f"{proc.stderr.strip()}")


def _compile_applet(dest: Path, prefix: Path, profile: str,
                    repo: Optional[Path] = None) -> Optional[str]:
    """Build the launcher as an AppleScript applet.

    A bundle whose executable is a shell script is not reliably launchable:
    LaunchServices waits for it to register as an application and gives up with
    `-1712`, and until then the Dock icon bounces endlessly (measured again
    2026-10-31). An applet is a real application bundle, so Finder, Spotlight
    and `open` all behave."""
    import subprocess

    osacompile = shutil.which("osacompile")
    if not osacompile:
        return None
    script = APPLESCRIPT.format(repo=_applescript_quote(Path(repo or repo_root())),
                                 prefix=_applescript_quote(prefix),
                                 profile=_applescript_quote(profile))
    if dest.exists():
        shutil.rmtree(dest)
    proc = subprocess.run([osacompile, "-o", str(dest), "-e", script],
                          capture_output=True, text=True, timeout=120)
    if proc.returncode != 0 or not dest.is_dir():
        return None
    return "applet"


def _write_script_app(dest: Path, prefix: Path, profile: str, name: str,
                      repo: Optional[Path] = None) -> str:
    from cs2kit import __version__

    repo = Path(repo or repo_root())
    exe_name = "cs2kit-launch"
    macos = dest / "Contents" / "MacOS"
    macos.mkdir(parents=True, exist_ok=True)
    (dest / "Contents" / "Resources").mkdir(parents=True, exist_ok=True)
    target = macos / exe_name
    target.write_text(LAUNCHER.format(repo=_shell_quote(repo),
                                      prefix=_shell_quote(prefix),
                                      profile=_shell_quote(profile)))
    target.chmod(target.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    (dest / "Contents" / "Info.plist").write_text(PLIST.format(
        name=_xml_quote(name), ident=_xml_quote(dest.stem.lower().replace(" ", "-")),
        version=__version__, exe=exe_name))
    (dest / "Contents" / "PkgInfo").write_text("APPL????")
    return "script"


def _upstream_launcher(root: Path) -> Path:
    """The single source of truth for the runtime's entry point."""
    launcher = root / "bin" / "cs2kit"
    if not launcher.is_file():
        raise OSError(f"{launcher}: upstream launcher is missing from the checkout")
    return launcher


def _runtime_is_complete(root: Path, candidate: Path) -> bool:
    """Cheap structural check, used both before publishing and on fallback."""
    if not candidate.is_dir():
        return False
    package = candidate / "cs2kit"
    launcher = candidate / "bin" / "cs2kit"
    if not (package / "__main__.py").is_file() or not (package / "cli.py").is_file():
        return False
    if not launcher.is_file() or not os.access(launcher, os.X_OK):
        return False
    if (root / "profiles").is_dir() and not (candidate / "profiles").is_dir():
        return False
    return True


def _verify_staged(root: Path, staged: Path) -> None:
    """Refuse to publish a tree that cannot start the CLI.

    Parsing rather than importing avoids leaving __pycache__ in the staged
    tree. Comparing the launcher byte-for-byte with the checkout keeps one
    entry point: a hand-written shim used to drift from the real bin/cs2kit."""
    if not _runtime_is_complete(root, staged):
        raise OSError(f"staged runtime at {staged} is incomplete")
    installed = staged / "bin" / "cs2kit"
    if installed.read_bytes() != _upstream_launcher(root).read_bytes():
        raise OSError("staged launcher differs from the upstream bin/cs2kit")
    for path in sorted((staged / "cs2kit").glob("*.py")):
        try:
            ast.parse(path.read_bytes(), filename=str(path))
        except SyntaxError as exc:
            raise OSError(f"staged runtime has a syntax error in {path}: {exc}") from exc


def _last_good_runtime() -> Optional[Path]:
    """The previously published copy, if it is still complete."""
    candidate = state_dir() / "runtime"
    return candidate if _runtime_is_complete(repo_root(), candidate) else None


def stage_runtime() -> Path:
    """Publish a fresh runtime without ever breaking the live one.

    The new tree is built in a sibling staging directory (same filesystem, so
    the final rename is atomic), verified, and only then swapped in: the live
    copy moves to a backup first and is restored if publishing fails. A lock
    serialises concurrent `app create` runs, and checkout/runtime paths are
    checked for overlap so a tree can never be copied into itself."""
    root = repo_root().resolve()
    state = state_dir().resolve()
    runtime = state / "runtime"

    def is_within(path: Path, parent: Path) -> bool:
        return path == parent or parent in path.parents

    # A runtime that contains the checkout would be moved out from under the
    # source; one inside a copied subtree would make copytree recurse into its
    # own destination. A state dir elsewhere under the checkout is fine.
    copied = (root / "cs2kit", root / "profiles")
    if is_within(root, runtime) or any(is_within(runtime, tree) for tree in copied):
        raise OSError(
            f"the checkout {root} overlaps the runtime directory {runtime}; "
            "set CS2KIT_HOME outside the source subtrees before building the app")

    lock = state / ".runtime.lock"
    with open(lock, "a+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        staged = Path(tempfile.mkdtemp(prefix=".runtime-", dir=state))
        backup = staged.with_name(staged.name + ".old")
        try:
            ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache",
                                            "*.egg-info")
            shutil.copytree(root / "cs2kit", staged / "cs2kit", ignore=ignore)
            if (root / "profiles").is_dir():
                shutil.copytree(root / "profiles", staged / "profiles")
            (staged / "bin").mkdir()
            shutil.copy2(_upstream_launcher(root), staged / "bin" / "cs2kit")
            _verify_staged(root, staged)

            if runtime.exists():
                os.rename(runtime, backup)       # keep the working copy intact
            try:
                os.rename(staged, runtime)       # atomic publish, same filesystem
            except OSError:
                if backup.exists():
                    os.rename(backup, runtime)   # restore what we moved aside
                raise
            # A running app may still hold the old tree open. Leaving it behind
            # is harmless; failing the build because of it is not.
            if backup.exists():
                shutil.rmtree(backup, ignore_errors=True)
            return runtime
        finally:
            # Only our own staging directory is disposable. A backup left by a
            # failed restore is the user's working copy - never delete it.
            if staged.exists():
                shutil.rmtree(staged, ignore_errors=True)


def default_dest() -> Path:
    """Where a Mac user looks for apps: /Applications.

    Finder's sidebar "Applications" is /Applications, not ~/Applications - an app
    installed in the home folder is effectively invisible, which is exactly the
    confusion this caused on 2026-08-25. Fall back to ~/Applications only when
    /Applications is not writable."""
    system = Path("/Applications")
    if os.access(system, os.W_OK):
        return system / "CS2Kit.app"
    return Path.home() / "Applications" / "CS2Kit.app"


def default_game_dir() -> Optional[Path]:
    from cs2kit import probe

    install = probe.cs2_install_dir()
    return (install / "game" / "bin" / "win64") if install else None


def build_app(dest: Path, wine_root: Path, prefix: Optional[Path] = None,
              game_dir: Optional[Path] = None, profile: Optional[str] = None,
              name: str = "CS2Kit") -> Dict[str, Any]:
    from cs2kit import __version__

    dest = Path(dest).expanduser()
    if dest.suffix != ".app":
        dest = dest.with_suffix(".app")
    prefix = Path(prefix or wineprefix())
    game_dir = Path(game_dir or (default_game_dir() or (prefix / "cs2-not-installed")))

    rec = recipe_mod.resolve(profile) if profile else None
    env = dict(rec.env) if rec else {}
    env.setdefault("WINEMSYNC", "1")
    env.setdefault("WINEDEBUG", "-all")
    options = " ".join(rec.launch_options) if rec else "-novid -nojoy -console"

    profile_name = rec.name if rec else "balanced-1080p"
    # Never point the generated scripts at the checkout: it usually lives in
    # ~/Documents, which TCC hides from Finder-launched apps. See module docstring.
    try:
        repo = stage_runtime()
    except OSError as exc:
        # A failed refresh must not break a working launcher: keep the last
        # verified copy (or the checkout, if this is the very first build).
        repo = _last_good_runtime() or repo_root()
        print(f"warning: runtime refresh failed ({exc}); using {repo}", file=sys.stderr)
    if dest.exists():
        shutil.rmtree(dest)
    # The applet is a real application (no endless Dock bouncing); the script
    # bundle is only the fallback for machines without osacompile.
    kind = (_compile_applet(dest, prefix, profile_name, repo)
            or _write_script_app(dest, prefix, profile_name, name, repo))
    if kind == "applet":
        _set_identity(dest, name)

    icon = repo_root() / "assets" / "cs2kit.icns"
    if icon.is_file():
        (dest / "Contents" / "Resources").mkdir(parents=True, exist_ok=True)
        shutil.copy2(icon, dest / "Contents" / "Resources" / "applet.icns")
        shutil.copy2(icon, dest / "Contents" / "Resources" / "cs2kit.icns")
    if kind == "applet":
        # osacompile seals the bundle with an ad-hoc signature, and the icon copy
        # above invalidates it. LaunchServices kills a modified-after-sign bundle
        # before its script runs, so double-click does nothing at all (measured
        # 2026-11-10: `open` succeeds, no applet process, `codesign -v` reports
        # "file added: Resources/cs2kit.icns"). Re-seal after touching Resources.
        import subprocess

        resign = subprocess.run(["codesign", "--force", "--sign", "-", str(dest)],
                                capture_output=True, text=True, timeout=120)
        if resign.returncode != 0:
            raise OSError(f"could not re-seal the applet after adding its icon: "
                          f"{resign.stderr.strip()}")
    # Finder caches bundles by path; touching it makes the new icon appear at once.
    os.utime(dest, None)

    return {"app": str(dest), "kind": kind, "wine_root": str(wine_root),
            "prefix": str(prefix), "game_dir": str(game_dir),
            "profile": (rec.name if rec else None), "launch_options": options,
            "runtime": str(repo)}


# --- CLI ---------------------------------------------------------------------
def cmd_create(args) -> int:
    from cs2kit import bottle

    wine_root = Path(args.wine_root) if args.wine_root else bottle.wine_root()
    if not wine_root:
        return emit_error("app create",
                          "cannot locate the Wine installation - pass --wine-root or run "
                          "`cs2kit engine install` first", json_mode=args.json)
    try:
        result = build_app(Path(args.dest), wine_root, prefix=args.prefix,
                           game_dir=args.game_dir, profile=args.profile, name=args.name)
    except (recipe_mod.RecipeError, OSError) as exc:
        return emit_error("app create", str(exc), json_mode=args.json)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return EXIT_OK
    print(f"Created {result['app']}")
    print(f"  wine     {result['wine_root']}")
    print(f"  prefix   {result['prefix']}")
    print(f"  game     {result['game_dir']}")
    print(f"  profile  {result['profile'] or '(none)'} -> {result['launch_options']}")
    if result.get("runtime"):
        print(f"  runtime  {result['runtime']}  (re-run app create after updating cs2kit)")
    print("")
    print("Double-click it to play. It verifies game-file integrity (T-021), starts the Steam")
    print("client if needed, then launches CS2. Logs go to ~/CS2/cs2kit-app.log")
    return EXIT_OK


def register(subparsers) -> None:
    dest_default = str(default_dest())
    parser = subparsers.add_parser(
        "app", help="generate a double-clickable launcher app",
        description="Playing should not need a terminal. This writes a small .app that runs the "
                    "same integrity-guarded launch path as `cs2kit launch`.")
    sub = parser.add_subparsers(dest="app_cmd")

    create = sub.add_parser("create", help="write the .app")
    create.add_argument("--dest", default=dest_default)
    create.add_argument("--wine-root", help="the Wine installation to bake in")
    create.add_argument("--prefix", help="WINEPREFIX to bake in")
    create.add_argument("--game-dir", help="directory containing cs2.exe")
    create.add_argument("--profile", default="balanced-1080p",
                        help="profile whose env and launch options to bake in")
    create.add_argument("--name", default="CS2Kit")
    create.add_argument("--json", action="store_true")
    create.set_defaults(func=cmd_create)

    parser.set_defaults(func=cmd_create, dest=dest_default, wine_root=None, prefix=None,
                        game_dir=None, profile="balanced-1080p",
                        name="CS2Kit", json=False)
