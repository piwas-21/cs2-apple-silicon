"""T-004 - fetch and stage a Wine engine that can actually run CS2.

Three engines were measured on 2026-08-24 and only one does all three jobs:
render Steam's UI, pass Steam's client/helper websocket check, and export the
`winemac.drv` API that DXMT needs to create a Metal view. Encoding that here
means a user never has to rediscover it - `cs2kit engine list` says which build
to take and why the others fail.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import tarfile
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from cs2kit.util import EXIT_FAIL, EXIT_NOT_READY, EXIT_OK, emit_error, run, state_dir

#: Wrapper dylibs the Sikarugir/CrossOver engines link against. Without them
#: `wineserver` aborts with `Library not loaded: @rpath/libinotify.0.dylib`.
DYLIB_BUNDLE = {
    "url": "https://github.com/Sikarugir-App/Wrapper/releases/download/v1.0/Template-1.0.11.tar.xz",
    "member_dir": "Contents/Frameworks",
}


@dataclass
class Engine:
    name: str
    version: str
    url: str
    sha256: Optional[str]
    verdict: str                       # "recommended" | "broken" | "unsupported"
    why: str
    needs_dylibs: bool = False
    bundle_dir: str = "wswine.bundle"  # directory inside the archive holding bin/ and lib/

    def as_dict(self) -> Dict[str, object]:
        return {"name": self.name, "version": self.version, "verdict": self.verdict,
                "why": self.why, "url": self.url, "sha256": self.sha256}


ENGINES: Dict[str, Engine] = {
    "sikarugir-10": Engine(
        name="sikarugir-10", version="wine-10.0 (Sikarugir)",
        url="https://github.com/Sikarugir-App/Engines/releases/download/v1.0/WS12WineSikarugir10.0_6.tar.xz",
        sha256="9da7ee0cbf386522f3a9906943726d9c3c125dbbd9ab120e3cde80e88d6091b2",
        verdict="recommended", needs_dylibs=True,
        why="the only engine measured to render Steam, pass its websocket check and export the "
            "winemac.drv API DXMT needs"),
    "crossover-24": Engine(
        name="crossover-24", version="wine-9.0 (SikarugirCX 24.0.7)",
        url="https://github.com/Sikarugir-App/Engines/releases/download/v1.0/WS12WineCX24.0.7_7.tar.xz",
        sha256="203f9e9fd6c2cc77e6525d798a434ced326145db34a356355e05659d3445fd1c",
        verdict="broken", needs_dylibs=True,
        why="renders Steam and runs DXMT, but its Wine 9.0 base makes the client reject the helper's "
            "loopback websocket - 'Unexpected transport error (0x3008)', login impossible"),
    "gcenx-11": Engine(
        name="gcenx-11", version="wine-11.15 (staging)",
        url="https://github.com/Gcenx/macOS_Wine_builds/releases/download/11.15/wine-staging-11.15-osx64.tar.xz",
        sha256="a8c50d0e14fb7982a21506287e1e41e1990fe77c74fa2a32da7dbcf7b21de1e2",
        verdict="broken", bundle_dir="Wine Staging.app/Contents/Resources/wine",
        why="exports no winemac.drv symbols, so DXMT fails with 'Failed to create metal view'; "
            "Steam's window also renders black"),
}

RECOMMENDED = "sikarugir-10"


class EngineError(RuntimeError):
    pass


def engines_dir() -> Path:
    return Path(state_dir()) / "engines"


def _fetch(url: str, tmp: Path, progress=None) -> None:
    """Download with curl first, urllib second.

    Why curl leads: a Python installed from python.org ships no CA bundle, so
    `urllib` dies with `CERTIFICATE_VERIFY_FAILED` on a perfectly good machine -
    which is exactly what happened the first time `cs2kit setup` was run on a
    clean path. `curl` is on every Mac and uses the system trust store."""
    from cs2kit.util import which as _which

    curl = _which("curl")
    if curl:
        proc = run([curl, "-fL", "--retry", "3", "--connect-timeout", "30",
                    "-o", str(tmp), url], timeout=3600)
        if proc.ok and tmp.exists() and tmp.stat().st_size:
            return
    with urllib.request.urlopen(url, timeout=120) as src, open(tmp, "wb") as out:
        while True:
            chunk = src.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
            if progress:
                progress(out.tell())


def download(url: str, dest: Path, sha256: Optional[str] = None,
             progress=None) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        tmp = dest.with_suffix(dest.suffix + ".part")
        _fetch(url, tmp, progress)
        tmp.replace(dest)
    digest = sha256_of(dest)
    if sha256 and digest != sha256:
        dest.unlink(missing_ok=True)
        raise EngineError(f"{dest.name}: sha256 {digest} does not match the recorded {sha256}")
    return dest


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def extract(archive: Path, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as tar:
        try:                              # Python 3.12+: refuse paths outside dest
            tar.extractall(dest, filter="data")
        except TypeError:                 # 3.9-3.11 have no filter argument
            tar.extractall(dest)
    return dest


def stage_dylibs(engine_root: Path, source: Path) -> List[str]:
    """Copy the wrapper's dylibs next to the engine.

    The Sikarugir engines resolve `@rpath` against `<bundle>/lib`; without these
    `wineserver` aborts before Wine ever starts."""
    lib = Path(engine_root) / "lib"
    lib.mkdir(parents=True, exist_ok=True)
    copied = []
    for dylib in sorted(Path(source).rglob("*.dylib")):
        target = lib / dylib.name
        if not target.exists():
            shutil.copy2(dylib, target)
        copied.append(dylib.name)
    if not copied:
        raise EngineError(f"{source}: no .dylib files found to stage")
    return copied


def find_bundle(root: Path, engine: Engine) -> Optional[Path]:
    candidate = Path(root) / engine.bundle_dir
    if (candidate / "bin" / "wine").is_file():
        return candidate
    for path in Path(root).rglob("bin/wine"):
        return path.parent.parent
    return None


def install(name: str = RECOMMENDED, dest: Optional[Path] = None,
            keep_archive: bool = True, log=print) -> Dict[str, object]:
    """Download, verify, extract and stage an engine. Returns its wine root."""
    engine = ENGINES.get(name)
    if engine is None:
        raise EngineError(f"unknown engine {name!r} (known: {', '.join(sorted(ENGINES))})")
    if engine.verdict == "broken":
        log(f"warning: {name} is recorded as BROKEN - {engine.why}")
    root = Path(dest or (engines_dir() / name))
    archive = engines_dir() / Path(engine.url).name
    log(f"fetching {engine.url}")
    download(archive, archive, engine.sha256) if archive.exists() else download(engine.url, archive, engine.sha256)
    log(f"sha256 {sha256_of(archive)}")
    extract(archive, root)
    bundle = find_bundle(root, engine)
    if bundle is None:
        raise EngineError(f"{root}: no bin/wine found after extracting {archive.name}")
    staged: List[str] = []
    if engine.needs_dylibs:
        wrapper = engines_dir() / Path(DYLIB_BUNDLE["url"]).name
        log(f"fetching wrapper dylibs {DYLIB_BUNDLE['url']}")
        download(DYLIB_BUNDLE["url"], wrapper)
        wdir = engines_dir() / "wrapper"
        extract(wrapper, wdir)
        staged = stage_dylibs(bundle, wdir)
        log(f"staged {len(staged)} dylib(s) into {bundle / 'lib'}")
    if not keep_archive:
        archive.unlink(missing_ok=True)
    record = {"engine": name, "wine_root": str(bundle), "version": engine.version,
              "sha256": sha256_of(archive) if archive.exists() else None, "dylibs": len(staged)}
    (root / "cs2kit-engine.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


# --- CLI ---------------------------------------------------------------------
def cmd_list(args) -> int:
    if args.json:
        print(json.dumps([e.as_dict() for e in ENGINES.values()], indent=2))
        return EXIT_OK
    for engine in ENGINES.values():
        mark = "*" if engine.name == RECOMMENDED else " "
        print(f" {mark} {engine.name:<14} {engine.verdict:<12} {engine.version}")
        print(f"     {engine.why}")
    print("\n* = recommended. Install with: cs2kit engine install")
    return EXIT_OK


def cmd_install(args) -> int:
    try:
        record = install(args.name, Path(args.dest) if args.dest else None)
    except (EngineError, OSError) as exc:
        return emit_error("engine install", str(exc), json_mode=args.json)
    if args.json:
        print(json.dumps(record, indent=2))
        return EXIT_OK
    print(f"Installed {record['engine']} -> {record['wine_root']}")
    print(f"  version  {record['version']}")
    print(f"  sha256   {record['sha256']}")
    print("\nNext:")
    print(f'  export PATH="{record["wine_root"]}/bin:$PATH"')
    print("  cs2kit bottle create --dxmt <extracted DXMT release>")
    return EXIT_OK


def register(subparsers) -> None:
    parser = subparsers.add_parser(
        "engine", help="fetch a Wine engine that can run CS2 (T-004)",
        description="Only one measured engine renders Steam, passes its websocket check and gives "
                    "DXMT a Metal view. This command fetches it and stages its dylibs.")
    sub = parser.add_subparsers(dest="engine_cmd")

    lst = sub.add_parser("list", help="show known engines and why they pass or fail")
    lst.add_argument("--json", action="store_true")
    lst.set_defaults(func=cmd_list)

    ins = sub.add_parser("install", help="download, verify, extract and stage an engine")
    ins.add_argument("name", nargs="?", default=RECOMMENDED, choices=sorted(ENGINES))
    ins.add_argument("--dest", help="where to install (default: ~/.cs2kit/engines/<name>)")
    ins.add_argument("--json", action="store_true")
    ins.set_defaults(func=cmd_install)

    parser.set_defaults(func=cmd_list, json=False)
