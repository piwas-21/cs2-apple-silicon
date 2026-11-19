"""`cs2kit app create` - a double-clickable launcher, so playing needs no terminal.

Generate a native applet that verifies the guarded binaries and launches CS2
through Steam, or a separate quit applet that stops only the selected bottle.
Both delegate to the CLI at runtime and embed no third-party code.
"""
from __future__ import annotations

import json
import os
import plistlib
import shlex
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional
from html import escape

from cs2kit import recipe as recipe_mod
from cs2kit.util import EXIT_OK, emit_error, repo_root, wineprefix

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

STOP_APPLESCRIPT = '''set repoPath to "{repo}"
set winePrefix to "{prefix}"
do shell script "cd " & quoted form of repoPath & " && WINEPREFIX=" & ¬
    quoted form of winePrefix & " ./bin/cs2kit stop"
'''

#: Fallback for a machine without osacompile: a plain script bundle. It works,
#: but LaunchServices is fussier about it (see docs/troubleshooting.md #25d).
LAUNCHER = r'''#!/bin/bash
set -uo pipefail
export CS2KIT_REPO={repo}
export WINEPREFIX={prefix}
LOG="$HOME/CS2/cs2kit-app.log"
mkdir -p "$(dirname "$LOG")"
"$CS2KIT_REPO/bin/cs2kit" play --profile {profile} --gui --detach >>"$LOG" 2>&1
exit 0
'''

STOP_LAUNCHER = r'''#!/bin/bash
set -euo pipefail
export WINEPREFIX={prefix}
{repo}/bin/cs2kit stop
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


def _compile_applet(dest: Path, prefix: Path, profile: str, stop: bool = False) -> Optional[str]:
    """Build the launcher as an AppleScript applet.

    A bundle whose executable is a shell script is not reliably launchable:
    LaunchServices waits for it to register as an application and gives up with
    `-1712` (measured 2026-08-25 - `open` simply refused). An applet is a real
    application bundle, so Finder, Spotlight and `open` all behave."""
    import subprocess

    osacompile = shutil.which("osacompile")
    if not osacompile:
        return None
    def literal(value) -> str:
        return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\r", "\\r").replace("\n", "\\n")

    template = STOP_APPLESCRIPT if stop else APPLESCRIPT
    script = template.format(repo=literal(repo_root()), prefix=literal(prefix), profile=literal(profile))
    if dest.exists():
        shutil.rmtree(dest)
    proc = subprocess.run([osacompile, "-o", str(dest), "-e", script],
                          capture_output=True, text=True, timeout=120)
    if proc.returncode != 0 or not dest.is_dir():
        return None
    return "applet"


def _write_script_app(dest: Path, prefix: Path, profile: str, name: str, stop: bool = False) -> str:
    from cs2kit import __version__

    exe_name = "cs2kit-launch"
    macos = dest / "Contents" / "MacOS"
    macos.mkdir(parents=True, exist_ok=True)
    (dest / "Contents" / "Resources").mkdir(parents=True, exist_ok=True)
    target = macos / exe_name
    template = STOP_LAUNCHER if stop else LAUNCHER
    target.write_text(template.format(repo=shlex.quote(str(repo_root())),
                                      prefix=shlex.quote(str(prefix)), profile=shlex.quote(profile)))
    target.chmod(target.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    (dest / "Contents" / "Info.plist").write_text(PLIST.format(
        name=escape(name), ident=escape(dest.stem.lower().replace(" ", "-")), version=__version__, exe=exe_name))
    (dest / "Contents" / "PkgInfo").write_text("APPL????")
    return "script"


def _sign_applet(dest: Path) -> None:
    # osacompile signs the applet; changing its plist or icon invalidates it.
    signer = shutil.which("codesign")
    if signer:
        signed = subprocess.run([signer, "--force", "--sign", "-", str(dest)],
                                capture_output=True, text=True, timeout=120)
        if signed.returncode:
            raise OSError(f"could not sign launcher: {signed.stderr.strip()}")


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


def _app_path(dest: Path) -> Path:
    dest = Path(dest).expanduser()
    return dest if dest.suffix == ".app" else dest.with_suffix(".app")


def _creation_dest(dest: Path, stop: bool) -> Path:
    dest = _app_path(dest)
    default = _app_path(default_dest())
    if stop and dest.resolve() == default.resolve():
        return default.with_name("Quit CS2Kit.app")
    return dest


def build_app(dest: Path, wine_root: Path, prefix: Optional[Path] = None,
              game_dir: Optional[Path] = None, profile: Optional[str] = None,
              name: str = "CS2Kit", stop: bool = False) -> Dict[str, Any]:

    dest = _app_path(dest)
    prefix = Path(prefix or wineprefix())
    game_dir = Path(game_dir or (default_game_dir() or (prefix / "cs2-not-installed")))

    rec = recipe_mod.resolve(profile).require_valid() if profile else None
    env = dict(rec.env) if rec else {}
    env.setdefault("WINEMSYNC", "1")
    env.setdefault("WINEDEBUG", "-all")
    options = " ".join(rec.launch_options) if rec else "-novid -nojoy -console"

    profile_name = rec.name if rec else "balanced-1080p"
    if dest.exists():
        shutil.rmtree(dest)
    # LaunchServices requires a native executable that registers as an app.
    # A shell bundle can hang in the Dock before its script ever runs (#26).
    kind = _compile_applet(dest, prefix, profile_name, stop=stop)
    if kind is None:
        kind = _write_script_app(dest, prefix, profile_name, name, stop=stop)
    else:
        from cs2kit import __version__

        info = dest / "Contents" / "Info.plist"
        metadata = plistlib.loads(info.read_bytes())
        metadata.update(CFBundleName=name, CFBundleDisplayName=name,
                        CFBundleIdentifier="org.cs2kit." + dest.stem.lower().replace(" ", "-"),
                        CFBundleVersion=__version__, CFBundleShortVersionString=__version__)
        info.write_bytes(plistlib.dumps(metadata))

    icon = repo_root() / "assets" / "cs2kit.icns"
    if icon.is_file():
        (dest / "Contents" / "Resources").mkdir(parents=True, exist_ok=True)
        shutil.copy2(icon, dest / "Contents" / "Resources" / "applet.icns")
        shutil.copy2(icon, dest / "Contents" / "Resources" / "cs2kit.icns")
    if kind == "applet":
        _sign_applet(dest)
    # Finder caches bundles by path; touching it makes the new icon appear at once.
    os.utime(dest, None)

    return {"app": str(dest), "kind": kind, "action": "stop" if stop else "play",
            "wine_root": str(wine_root),
            "prefix": str(prefix), "game_dir": str(game_dir),
            "profile": (rec.name if rec else None), "launch_options": options}


# --- CLI ---------------------------------------------------------------------
def cmd_create(args) -> int:
    from cs2kit import bottle

    prefix = Path(args.prefix or wineprefix()).expanduser().resolve()
    wine_root = Path(args.wine_root) if args.wine_root else bottle.wine_root(prefix=prefix)
    if not wine_root:
        return emit_error("app create",
                          "cannot locate the Wine installation - pass --wine-root or run "
                          "`cs2kit engine install` first", json_mode=args.json)
    try:
        stop = getattr(args, "stop", False)
        dest = _creation_dest(Path(args.dest), stop)
        name = args.name
        if stop and name == "CS2Kit":
            name = "Quit CS2Kit"
        result = build_app(dest, wine_root, prefix=prefix,
                           game_dir=args.game_dir, profile=args.profile, name=name, stop=stop)
    except (recipe_mod.RecipeError, OSError) as exc:
        return emit_error("app create", str(exc), json_mode=args.json)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return EXIT_OK
    print(f"Created {result['app']}")
    if result["action"] == "stop":
        print("Exit CS2 first to save settings, then double-click to stop this bottle's Steam and helpers.")
        return EXIT_OK
    print(f"  wine     {result['wine_root']}")
    print(f"  prefix   {result['prefix']}")
    print(f"  game     {result['game_dir']}")
    print(f"  profile  {result['profile'] or '(none)'} -> {result['launch_options']}")
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
    create.add_argument("--stop", action="store_true",
                        help="create Quit CS2Kit.app to stop the selected bottle")
    create.add_argument("--json", action="store_true")
    create.set_defaults(func=cmd_create)

    parser.set_defaults(func=cmd_create, dest=dest_default, wine_root=None, prefix=None,
                        game_dir=None, profile="balanced-1080p",
                        name="CS2Kit", json=False)
