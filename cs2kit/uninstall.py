"""Read-only uninstall inventory (issue #3, discovery slice).

This module answers "what did CS2Kit create here?" without changing anything.
It deliberately refuses ``--apply``: removal needs installation records that
are written as setup progresses, plus a bounded, recoverable quarantine, and
neither exists yet.

No write, process, or network API is called from this module. Paths are read
lexically; symlinks are reported as links with their targets retained, never
traversed. Environment variables and unreadable records are evidence, not
proof of ownership, so anything that is not positively identified is reported
for review instead of as a removal candidate.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from cs2kit import engine as engine_mod
from cs2kit import recipe as recipe_mod
from cs2kit import setup as setup_mod
from cs2kit.util import EXIT_OK, EXIT_USAGE, emit_error, repo_root, steam_root

CANDIDATE = "candidate"
RETAIN = "retain"
REVIEW = "review"
MISSING = "missing"

CONTAINER = "container"
RECORDED = "recorded"
LIKELY = "likely"
AMBIGUOUS = "ambiguous"
EXTERNAL = "external"
REFUSED = "refused"

# A removal plan must never be allowed to name one of these as a target.
FORBIDDEN_ROOTS = ("/", "/Applications", "/Library", "/System", "/usr",
                   "/usr/local", "/opt/homebrew")

STATE_COMPONENTS = (
    ("active-profile.json", "Applied profile record"),
    ("env", "Generated environment scripts"),
    ("integrity", "Game-file integrity baselines"),
    ("bench", "Stored benchmark sessions"),
    ("reports", "Diagnostic reports"),
    ("watch.json", "Recorded game buildid"),
)


@dataclass
class Item:
    """One line of the plan: a path, the evidence for it, and its disposition."""

    id: str
    component: str
    path: str
    proposal: str
    ownership: str
    reason: str
    kind: str = "missing"
    evidence: List[str] = field(default_factory=list)
    target: Optional[str] = None
    retained: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _env_path(name: str, default: Path) -> Path:
    """Read an override without creating the path it names."""
    value = os.environ.get(name)
    return Path(value).expanduser() if value else Path(default).expanduser()


def _norm(path: Any) -> str:
    """Lexical absolute path: a symlink keeps its own identity."""
    return os.path.normpath(os.path.abspath(os.path.expanduser(str(path))))


def _resolved(path: Any) -> Path:
    return Path(os.path.realpath(os.path.expanduser(str(path))))


def _key(path: Any) -> str:
    return _norm(path)


def _kind(path: Path) -> str:
    if path.is_symlink():
        return "symlink"
    if path.is_dir():
        return "dir"
    if path.is_file():
        return "file"
    return "missing"


def _read_json(path: Path) -> Tuple[Optional[Any], Optional[str]]:
    """Return (data, error); a symlink is never followed for record data."""
    try:
        if path.is_symlink():
            return None, "record is a symlink"
        if not path.is_file():
            return None, "missing"
        data = json.loads(path.read_text())
        return data, None
    except (OSError, ValueError) as exc:
        return None, str(exc)


def _text(path: Path, limit: int = 1 << 20) -> str:
    """Read a small text file, or return an empty string. Never follow links."""
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
            return ""
        return path.read_text(errors="replace")
    except (OSError, ValueError):
        return ""


def _has_file(root: Path, relative: str) -> bool:
    """Look for a marker without following symlinked directories."""
    for parent, dirs, files in os.walk(str(root), followlinks=False):
        dirs[:] = [d for d in dirs if not (Path(parent) / d).is_symlink()]
        if relative in files and not (Path(parent) / relative).is_symlink():
            return True
    return False


def _inside(child: Any, parent: Any) -> bool:
    try:
        _resolved(child).relative_to(_resolved(parent))
        return True
    except ValueError:
        return False


def _forbidden(path: Any, home: Path) -> bool:
    candidate = Path(_norm(path))
    if candidate == Path(_norm(home)):
        return True
    return _norm(candidate) in {_norm(p) for p in FORBIDDEN_ROOTS}


def _add(items: List[Item], seen: Set[Tuple[str, str]], item: Item) -> None:
    key = (item.id, _key(item.path))
    if key in seen:
        return
    seen.add(key)
    items.append(item)


def _find(items: List[Item], path: Any) -> Optional[Item]:
    wanted = _key(path)
    for item in items:
        if _key(item.path) == wanted:
            return item
    return None


def _marker(path: Path, item_id: str, component: str,
            evidence: str, reason: str, proposal: str = CANDIDATE,
            ownership: str = LIKELY) -> Item:
    return Item(id=item_id, component=component, path=_norm(path), kind=_kind(path),
                proposal=proposal, ownership=ownership, reason=reason,
                evidence=[evidence])


def _retained(path: Any, item_id: str, component: str, reason: str,
              evidence: Iterable[str] = ()) -> Item:
    return Item(id=item_id, component=component, path=_norm(path), kind=_kind(Path(path)),
                proposal=RETAIN, ownership=EXTERNAL, reason=reason,
                evidence=list(evidence))


class Inventory:
    """Accumulate a plan. Construction and inspection only read the filesystem."""

    def __init__(self, args: Any) -> None:
        home = Path.home()
        self.home = home
        self.setup_home = (Path(args.setup_home).expanduser() if args.setup_home
                           else _env_path("CS2KIT_SETUP_HOME", home / "CS2"))
        self.state_home = (Path(args.state_home).expanduser() if args.state_home
                           else _env_path("CS2KIT_HOME", home / ".cs2kit"))
        self.library = (Path(args.library).expanduser() if args.library
                        else _env_path("CS2KIT_LIBRARY", self.setup_home / "library"))
        self.steam = steam_root()
        self.prefixes = [Path(p).expanduser() for p in (args.prefix or [])]
        if not self.prefixes:
            self.prefixes.append(_env_path("WINEPREFIX", self.setup_home / "prefix"))
        self.app_dests = ([Path(p).expanduser() for p in args.app_dest] if args.app_dest
                          else [Path("/Applications/CS2Kit.app"),
                                home / "Applications" / "CS2Kit.app",
                                self.setup_home / "CS2Kit.app"])
        self.engine_dests = ([Path(p).expanduser() for p in args.engine_dest]
                             if args.engine_dest else [self.state_home / "engines"])
        self.shader_caches = [Path(p).expanduser() for p in (args.shader_cache or [])]
        self.items: List[Item] = []
        self._seen: Set[Tuple[str, str]] = set()
        self.notes: List[str] = [
            "No installation manifest exists yet: paths not supplied on the command line "
            "cannot be rediscovered reliably.",
            "Environment variables describe this shell, not necessarily the install that "
            "created these paths.",
            "This slice is read-only. --apply is refused; removals stay a manual, "
            "recoverable operation documented in docs/uninstall.md.",
        ]
        self.engine_roots: Dict[str, Tuple[str, str]] = {}  # path -> (evidence, prefix)
        self.protected_found = False

    def add(self, item: Item) -> None:
        _add(self.items, self._seen, item)

    def note(self, text: str) -> None:
        if text not in self.notes:
            self.notes.append(text)

    # --- discovery ---------------------------------------------------------
    def discover_prefixes(self) -> None:
        """Add prefixes found one level below the setup home.

        Only immediate children are examined. A recursive scan of ~/CS2 would
        wander into game libraries and symlinked engines; that is exactly what
        this inventory must not do.
        """
        if self.setup_home.is_symlink() or not self.setup_home.is_dir():
            return
        try:
            children = sorted(self.setup_home.iterdir())
        except OSError as exc:
            self.note(f"could not list {self.setup_home}: {exc}")
            return
        for child in children:
            if child.is_symlink() or not child.is_dir():
                continue
            if ((child / "system.reg").is_file()
                    or (child / ".cs2kit" / "state.json").is_file()):
                if not any(_key(p) == _key(child) for p in self.prefixes):
                    self.prefixes.append(child)

    def discover_shader_caches(self) -> None:
        """Collect DXMT_SHADER_CACHE values from profiles and the active record."""
        self.shader_caches.append(self.state_home / "shader-cache")
        sources: List[Tuple[str, Dict[str, Any]]] = []
        for path in recipe_mod.list_profiles():
            try:
                sources.append((path.name, recipe_mod.load(path).env))
            except recipe_mod.RecipeError as exc:
                self.note(f"could not read shader cache from {path}: {exc}")
        active, error = _read_json(self.state_home / "active-profile.json")
        if error and error != "missing":
            self.note(f"could not read active profile: {error}")
        if isinstance(active, dict):
            env = active.get("env")
            if isinstance(env, dict):
                sources.append(("active-profile.json", {str(k): str(v) for k, v in env.items()}))
        for source, env in sources:
            value = env.get("DXMT_SHADER_CACHE")
            if value:
                expanded = os.path.expandvars(str(value))
                self.shader_caches.append(Path(expanded).expanduser())
                if expanded != str(value):
                    self.note(f"{source} DXMT_SHADER_CACHE contains a shell variable; "
                              "the expanded value is a hint for this shell only")

    def inspect_launchers(self) -> None:
        for path in self.app_dests:
            marker = _marker(path, f"launcher:{_key(path)}", "Launcher app",
                             "default/custom app destination",
                             "not present", proposal=MISSING, ownership="none")
            kind = _kind(path)
            if kind == "missing":
                self.add(marker)
                continue
            if kind == "symlink":
                self.add(Item(id=marker.id, component=marker.component, path=marker.path,
                              kind=kind, proposal=REVIEW, ownership=AMBIGUOUS,
                              reason="app path is a symlink; the target was not traversed",
                              evidence=marker.evidence, target=str(_resolved(path))))
                continue
            plist = _text(path / "Contents" / "Info.plist")
            scripts = ""
            macos = path / "Contents" / "MacOS"
            if macos.is_dir() and not macos.is_symlink():
                for child in sorted(macos.iterdir()):
                    if child.is_file() and not child.is_symlink():
                        scripts += _text(child)
            evidence: List[str] = []
            ownership = AMBIGUOUS
            proposal = REVIEW
            if "org.cs2kit." in plist:
                evidence.append("bundle identifier is org.cs2kit.*")
                ownership = RECORDED
                proposal = CANDIDATE
            elif "cs2kit" in scripts.lower():
                evidence.append("launcher script references cs2kit")
                ownership = LIKELY
                proposal = CANDIDATE
            elif path.name == "CS2Kit.app":
                evidence.append("bundle name is CS2Kit.app")
                ownership = LIKELY
            if not evidence:
                evidence.append("no CS2Kit marker in bundle or launcher script")
            reason = ("identified as a CS2Kit launcher; remove only the bundle itself"
                      if proposal == CANDIDATE else
                      "name or path matches, but ownership is not proven - inspect before removal")
            self.add(Item(id=marker.id, component=marker.component, path=marker.path,
                          kind=kind, proposal=proposal, ownership=ownership, reason=reason,
                          evidence=evidence))

    def inspect_prefix(self, prefix: Path) -> None:
        item_id = f"prefix:{_key(prefix)}"
        kind = _kind(prefix)
        if kind == "missing":
            self.add(_marker(prefix, item_id, "Wine prefix / bottle", "configured prefix path",
                             "not present", proposal=MISSING, ownership="none"))
            return
        if _forbidden(prefix, self.home) or _key(prefix) == _key(self.setup_home):
            self.add(Item(id=item_id, component="Wine prefix / bottle", path=_norm(prefix),
                          kind=kind, proposal=REFUSED, ownership=REFUSED,
                          reason="filesystem/home root or shared setup root cannot be a removal target",
                          evidence=["requested prefix path"]))
            return
        if kind == "symlink":
            self.add(Item(id=item_id, component="Wine prefix / bottle", path=_norm(prefix),
                          kind=kind, proposal=REVIEW, ownership=AMBIGUOUS,
                          reason="prefix path is a symlink; the target was not traversed",
                          evidence=["configured prefix path"], target=str(_resolved(prefix))))
            return

        state, error = _read_json(prefix / ".cs2kit" / "state.json")
        is_wine = (prefix / "system.reg").is_file()
        if not is_wine and not isinstance(state, dict):
            self.add(Item(id=item_id, component="Wine prefix / bottle", path=_norm(prefix),
                          kind=kind, proposal=REVIEW, ownership=AMBIGUOUS,
                          reason="no system.reg or readable CS2Kit record; not identified as a bottle",
                          evidence=[f"state record: {error or 'not an object'}"]))
            return

        evidence: List[str] = []
        ownership = AMBIGUOUS
        proposal = REVIEW
        prefix_protected = False
        protected_labels: List[str] = []
        if isinstance(state, dict):
            evidence.append("record: .cs2kit/state.json")
            if state.get("recipe_name"):
                evidence.append(f"recipe {state['recipe_name']}")
            if state.get("created"):
                evidence.append(f"created {state['created']}")
            wine_root = state.get("wine_root")
            if isinstance(wine_root, str) and wine_root:
                self.engine_roots[_norm(wine_root)] = (
                    f"wine_root in {prefix / '.cs2kit' / 'state.json'}", _norm(prefix))
            if error is None:
                ownership = RECORDED
                proposal = CANDIDATE
        elif error:
            evidence.append(f"unreadable record: {error}")
        if is_wine:
            evidence.append("system.reg present (Wine prefix)")

        steam_dir = prefix / "drive_c" / "Program Files (x86)" / "Steam"
        links = [(steam_dir / "steamapps", "Bottle Steam library link")]
        dosdevices = prefix / "dosdevices"
        if dosdevices.is_dir() and not dosdevices.is_symlink():
            for child in sorted(dosdevices.iterdir()):
                if child.is_symlink():
                    links.append((child, "Bottle drive link"))
        for link, label in links:
            if not link.is_symlink():
                continue
            target = _resolved(link)
            link_evidence = [f"symlink below {prefix}"]
            if _key(target) == _key(self.library / "steamapps") or _inside(target, self.library):
                link_evidence.append("library link points at CS2KIT_LIBRARY/default library "
                                     "(reused or migrated, not CS2Kit-owned game data)")
            if (target / "appmanifest_730.acf").is_file():
                link_evidence.append("appmanifest_730.acf present in the target")
            self.add(Item(id=f"link:{_key(link)}", component=label, path=_norm(link),
                          kind="symlink", proposal=CANDIDATE, ownership=RECORDED,
                          reason="only the symlink is removable; its target is retained",
                          evidence=link_evidence, target=str(target),
                          retained=[str(target)]))
            if not _inside(target, prefix):
                self.add(_retained(target, f"retained:{_key(target)}", "Link target",
                                   "game library or external data; never traverse the link to delete it",
                                   link_evidence[1:]))

        protected = (
            (steam_dir / "steamapps", "Steam game library in bottle"),
            (steam_dir / "userdata", "Steam userdata"),
            (steam_dir / "steamapps.cs2kit-backup", "Previous Steam library (backup)"),
            (prefix / "drive_c" / "users", "Windows user profiles"),
        )
        for path, label in protected:
            if path.is_symlink():
                continue  # already reported as a link with a retained target
            kind = _kind(path)
            if kind == "missing":
                continue
            add_retained = _retained(path, f"retained:{_key(path)}", label,
                                     "game, settings or save data; retain or copy before any prefix removal",
                                     [f"inside {prefix}"])
            if add_retained.path not in {i.path for i in self.items}:
                self.add(add_retained)
            protected_labels.append(label)
            prefix_protected = True

        if prefix_protected:
            names = ", ".join(sorted(set(protected_labels))) or "game/user data"
            proposal = REVIEW
            reason = (f"prefix contains retained {names}; copy them before any removal "
                      "and review each retained path")
        elif proposal == CANDIDATE:
            reason = "recorded as a CS2Kit-created prefix with no game/user data found"
        else:
            reason = "prefix ownership is not proven; inspect before removal"
        self.add(Item(id=item_id, component="Wine prefix / bottle", path=_norm(prefix),
                      kind=kind, proposal=proposal, ownership=ownership, reason=reason,
                      evidence=evidence))

    def inspect_engines(self) -> None:
        known_archives = {Path(e.url).name for e in engine_mod.ENGINES.values()}
        known_archives.add(Path(setup_mod.DXMT_RELEASE["url"]).name)
        known_archives.add(Path(engine_mod.DYLIB_BUNDLE["url"]).name)
        for root in self.engine_dests:
            if _kind(root) == "missing":
                self.add(_marker(root, f"engines:{_key(root)}", "Engine directory",
                                 "configured engine destination", "not present",
                                 proposal=MISSING, ownership="none"))
                continue
            if root.is_symlink():
                self.add(Item(id=f"engines:{_key(root)}", component="Engine directory",
                              path=_norm(root), kind="symlink", proposal=REVIEW,
                              ownership=AMBIGUOUS,
                              reason="engine directory is a symlink; the target was not traversed",
                              evidence=["configured engine destination"],
                              target=str(_resolved(root))))
                continue
            if not root.is_dir():
                continue
            self.add(Item(id=f"engines:{_key(root)}", component="Engine directory",
                          path=_norm(root), kind="dir", proposal=REVIEW, ownership=CONTAINER,
                          reason="container of engines and archives; review individual entries",
                          evidence=["configured engine destination"]))
            for child in sorted(root.iterdir()):
                if child.is_symlink():
                    self.add(Item(id=f"engine:{_key(child)}", component="Engine entry",
                                  path=_norm(child), kind="symlink", proposal=REVIEW,
                                  ownership=AMBIGUOUS,
                                  reason="symlink was not followed; inspect its target",
                                  evidence=["entry in engine directory"],
                                  target=str(_resolved(child))))
                    continue
                if child.is_file():
                    if child.name in known_archives:
                        self.add(_marker(child, f"archive:{_key(child)}", "Engine/download archive",
                                         f"known CS2Kit download name {child.name}",
                                         "downloaded artifact; can be fetched again after review"))
                    continue
                if not child.is_dir():
                    continue
                record, error = _read_json(child / "cs2kit-engine.json")
                if isinstance(record, dict) and error is None:
                    name = record.get("engine") or child.name
                    self.add(Item(id=f"engine:{_key(child)}", component=f"Engine: {name}",
                                  path=_norm(child), kind="dir", proposal=CANDIDATE,
                                  ownership=RECORDED,
                                  reason="CS2Kit engine record found; confirm no other bottle uses it",
                                  evidence=[f"cs2kit-engine.json: {name} {record.get('version', '')}".strip()]))
                elif error and error != "missing":
                    self.add(Item(id=f"engine:{_key(child)}", component="Engine directory",
                                  path=_norm(child), kind="dir", proposal=REVIEW,
                                  ownership=AMBIGUOUS,
                                  reason=f"unreadable engine record: {error}",
                                  evidence=["entry in engine directory"]))
                else:
                    self.add(Item(id=f"engine:{_key(child)}", component="Engine directory",
                                  path=_norm(child), kind="dir", proposal=REVIEW,
                                  ownership=AMBIGUOUS,
                                  reason="no cs2kit-engine.json; may be shared or hand-installed",
                                  evidence=["entry in engine directory"]))

        for path, (evidence, prefix) in sorted(self.engine_roots.items()):
            if _find(self.items, path):
                continue
            kind = _kind(Path(path))
            if kind == "missing":
                self.add(_marker(Path(path), f"engine-record:{_key(path)}", "Recorded Wine root",
                                 evidence, "not present", proposal=MISSING, ownership=RECORDED))
                continue
            recorded = (Path(path) / "cs2kit-engine.json").is_file()
            self.add(Item(id=f"engine-record:{_key(path)}", component="Recorded Wine root",
                          path=path, kind=kind, proposal=REVIEW,
                          ownership=RECORDED if recorded else LIKELY,
                          reason="recorded by a bottle but possibly shared; check "
                                 "`cs2kit bottle restore-wine --dry-run` first",
                          evidence=[evidence, f"recorded by {prefix}"]))
            backups = Path(path) / "lib" / "wine" / ".cs2kit-original"
            if _kind(backups) == "dir":
                self.add(Item(id=f"wine-backup:{_key(backups)}", component="Wine DLL backups",
                              path=_norm(backups), kind="dir", proposal=REVIEW,
                              ownership=RECORDED,
                              reason="original Wine DLLs; restore before removing a shared engine",
                              evidence=[f"CS2Kit backup tree under {path}"]))

    def inspect_setup(self) -> None:
        setup = self.setup_home
        kind = _kind(setup)
        if kind == "dir" and not setup.is_symlink():
            self.add(Item(id=f"setup:{_key(setup)}", component="Setup directory",
                          path=_norm(setup), kind=kind, proposal=REVIEW, ownership=CONTAINER,
                          reason="contains both retained game data and removable artifacts; "
                                 "never remove this root wholesale",
                          evidence=["CS2KIT_SETUP_HOME/default setup layout"]))
        elif kind != "missing":
            self.add(Item(id=f"setup:{_key(setup)}", component="Setup directory",
                          path=_norm(setup), kind=kind, proposal=REVIEW, ownership=AMBIGUOUS,
                          reason="setup path is a symlink or file; the target was not traversed",
                          evidence=["CS2KIT_SETUP_HOME/default setup layout"]))

        dxmt = setup / "dxmt"
        if _kind(dxmt) == "dir" and not dxmt.is_symlink():
            marker = _has_file(dxmt, "winemetal.so")
            self.add(Item(id=f"dxmt:{_key(dxmt)}", component="DXMT extract",
                          path=_norm(dxmt), kind="dir",
                          proposal=CANDIDATE if marker else REVIEW,
                          ownership=LIKELY if marker else AMBIGUOUS,
                          reason=("DXMT binaries found; extract can be fetched again"
                                  if marker else "no DXMT marker found; inspect before removal"),
                          evidence=[f"winemetal.so below {dxmt}" if marker
                                    else f"expected layout below {dxmt}"]))

        downloads = setup / "downloads"
        if _kind(downloads) == "dir" and not downloads.is_symlink():
            self.add(Item(id=f"downloads:{_key(downloads)}", component="Download directory",
                          path=_norm(downloads), kind="dir", proposal=REVIEW, ownership=CONTAINER,
                          reason="container of installer archives; review individual files",
                          evidence=["CS2Kit download layout"]))
            archives = {Path(setup_mod.DXMT_RELEASE["url"]).name, "SteamSetup.exe"}
            for child in sorted(downloads.iterdir()):
                if child.is_file() and not child.is_symlink() and child.name in archives:
                    self.add(_marker(child, f"download:{_key(child)}", "Installer download",
                                     f"known CS2Kit download name {child.name}",
                                     "downloaded artifact; can be fetched again after review"))

        for path in (setup / "cs2kit-app.log", self.home / "CS2" / "cs2kit-app.log"):
            if _kind(path) == "file":
                self.add(_marker(path, f"log:{_key(path)}", "Launcher log",
                                 "launcher writes this path",
                                 "log file only; no game or account data"))

        if _kind(self.library) == "dir":
            manifest = self.library / "steamapps" / "appmanifest_730.acf"
            evidence = [f"CS2KIT_LIBRARY/default library at {self.library}"]
            if manifest.is_file():
                evidence.append("appmanifest_730.acf present")
            self.add(_retained(self.library, f"retained:{_key(self.library)}", "Game library",
                               "game files and manifests; never removed automatically", evidence))
            self.protected_found = True
        if self.library.is_symlink():
            self.add(Item(id=f"retained:{_key(self.library)}", component="Game library",
                          path=_norm(self.library), kind="symlink", proposal=RETAIN,
                          ownership=EXTERNAL,
                          reason="library path is a symlink; target retained, link not traversed",
                          evidence=["CS2KIT_LIBRARY/default library path"],
                          target=str(_resolved(self.library))))
            self.protected_found = True

    def inspect_state(self) -> None:
        state = self.state_home
        if _kind(state) == "dir" and not state.is_symlink():
            self.add(Item(id=f"state:{_key(state)}", component="State directory",
                          path=_norm(state), kind="dir", proposal=REVIEW, ownership=CONTAINER,
                          reason="container of generated results and shared engines; "
                                 "review individual entries",
                          evidence=["CS2KIT_HOME/default state layout"]))
        for name, label in STATE_COMPONENTS:
            path = state / name
            if _kind(path) != "missing":
                self.add(_marker(path, f"state:{_key(path)}", label,
                                 "state directory layout (docs/cli-reference.md)",
                                 "CS2Kit-generated state; kept for review in this slice"))
        runtime = state / "runtime"
        if _kind(runtime) == "dir":
            staged = ((runtime / "bin" / "cs2kit").is_file()
                      and (runtime / "cs2kit" / "__init__.py").is_file())
            self.add(Item(id=f"runtime:{_key(runtime)}", component="Staged launcher runtime",
                          path=_norm(runtime), kind="dir",
                          proposal=CANDIDATE if staged else REVIEW,
                          ownership=LIKELY if staged else AMBIGUOUS,
                          reason=("staged cs2kit runtime used by the launcher"
                                  if staged else "runtime marker not found; inspect before removal"),
                          evidence=[f"staged runtime layout under {runtime}"]))
        for cache in self.shader_caches:
            if _kind(cache) != "missing":
                self.add(_marker(cache, f"shader-cache:{_key(cache)}", "DXMT shader cache",
                                 "DXMT_SHADER_CACHE from profile/record/override",
                                 "regenerable cache; may be shared by profiles"))

        active, error = _read_json(state / "active-profile.json")
        if error and error != "missing":
            self.note(f"active profile record is unreadable: {error}")
        if isinstance(active, dict):
            for field_name, label in (("env_script", "Generated env script"),
                                      ("cfg", "Game config written by config apply"),
                                      ("video_txt", "Video settings written by config apply")):
                value = active.get(field_name)
                if not isinstance(value, str) or not value:
                    continue
                path = Path(value).expanduser()
                if _kind(path) == "missing":
                    continue
                if _inside(path, state):
                    self.add(_marker(path, f"config-output:{_key(path)}", label,
                                     f"recorded in {state / 'active-profile.json'}",
                                     "generated inside the state directory"))
                else:
                    self.add(_retained(path, f"retained:{_key(path)}", label,
                                       "config artifact outside the state directory; "
                                       "manual cleanup only, never automatic removal",
                                       [f"recorded in {state / 'active-profile.json'}"]))

    def inspect_protected(self) -> None:
        targets: List[Tuple[str, Path, str]] = [
            ("Source checkout", repo_root(), "keep until the uninstall workflow is finished"),
            ("Steam root", self.steam, "native/Steam data; never removed by CS2Kit"),
        ]
        native = self.home / "Library" / "Application Support" / "Steam"
        if _key(native) != _key(self.steam):
            targets.append(("Native Steam root", native, "native Steam data; leave it alone"))
        for label, path, reason in targets:
            if _kind(path) == "missing":
                continue
            self.add(_retained(path, f"retained:{_key(path)}", label, reason,
                               ["protected by the uninstaller safety rules"]))

    def build(self) -> "Inventory":
        self.discover_prefixes()
        self.discover_shader_caches()
        unique_caches: List[Path] = []
        seen_caches: Set[str] = set()
        for cache in self.shader_caches:
            if _key(cache) not in seen_caches:
                seen_caches.add(_key(cache))
                unique_caches.append(cache)
        self.shader_caches = unique_caches
        self.inspect_launchers()
        for prefix in self.prefixes:
            self.inspect_prefix(prefix)
        self.inspect_engines()
        self.inspect_setup()
        self.inspect_state()
        self.inspect_protected()
        return self

    # --- output ------------------------------------------------------------
    def roots(self) -> Dict[str, Any]:
        return {
            "home": _norm(self.home),
            "setup_home": _norm(self.setup_home),
            "state_home": _norm(self.state_home),
            "library": _norm(self.library),
            "steam": _norm(self.steam),
            "prefixes": [_norm(p) for p in self.prefixes],
            "app_dests": [_norm(p) for p in self.app_dests],
            "engine_dests": [_norm(p) for p in self.engine_dests],
            "shader_caches": [_norm(p) for p in self.shader_caches],
            "source_checkout": _norm(repo_root()),
        }

    def environment_hints(self) -> Dict[str, str]:
        names = ("WINEPREFIX", "CS2KIT_HOME", "CS2KIT_SETUP_HOME", "CS2KIT_LIBRARY",
                 "CS2KIT_STEAM", "CS2KIT_REPO")
        return {name: os.environ[name] for name in names if name in os.environ}

    def as_dict(self) -> Dict[str, Any]:
        groups = {
            CANDIDATE: [i.as_dict() for i in self.items if i.proposal == CANDIDATE],
            RETAIN: [i.as_dict() for i in self.items if i.proposal == RETAIN],
            REVIEW: [i.as_dict() for i in self.items if i.proposal == REVIEW],
            REFUSED: [i.as_dict() for i in self.items if i.proposal == REFUSED],
            MISSING: [i.as_dict() for i in self.items if i.proposal == MISSING],
        }
        return {
            "command": "uninstall",
            "ok": True,
            "read_only": True,
            "apply_available": False,
            "complete": False,
            "roots": self.roots(),
            "environment_hints": self.environment_hints(),
            "groups": groups,
            "notes": self.notes,
            "counts": {name: len(items) for name, items in groups.items()},
        }


def inventory(args: Any) -> Inventory:
    return Inventory(args).build()


def _print_human(plan: Inventory, dry_run: bool = False) -> None:
    result = plan.as_dict()
    print("CS2Kit uninstall inventory (read-only; nothing was changed)")
    print(f"  setup home   {result['roots']['setup_home']}")
    print(f"  state home   {result['roots']['state_home']}")
    print(f"  prefixes     {', '.join(result['roots']['prefixes'])}")
    if dry_run:
        print("  --dry-run    explicitly requested; the plan is identical to the default")
    for name, title in (
            (CANDIDATE, "Removal candidates (NOT removed in this slice)"),
            (RETAIN, "Retained (games, userdata, shared data)"),
            (REVIEW, "Review before any removal"),
            (REFUSED, "Refused targets"),
            (MISSING, "Missing (nothing to do)")):
        items = result["groups"][name]
        print(f"\n{title} [{len(items)}]")
        for item in items:
            target = f" -> {item['target']}" if item.get("target") else ""
            print(f"  {item['id']}")
            print(f"    {item['path']}{target}")
            print(f"    {item['reason']}")
    print("\nDiscovery is incomplete by design: custom paths must be supplied explicitly.")
    print("Removal is not implemented; use docs/uninstall.md for the manual, recoverable procedure.")


def cmd_inventory(args: Any) -> int:
    if getattr(args, "apply", False):
        return emit_error(
            "uninstall --apply",
            "removal is not implemented in this discovery slice; nothing was changed",
            code=EXIT_USAGE, json_mode=bool(getattr(args, "json", False)))
    plan = inventory(args)
    if getattr(args, "json", False):
        print(json.dumps(plan.as_dict(), indent=2, sort_keys=True))
    else:
        _print_human(plan, dry_run=bool(getattr(args, "dry_run", False)))
    return EXIT_OK


def register(subparsers) -> None:
    parser = subparsers.add_parser(
        "uninstall", help="inventory what CS2Kit created (read-only)",
        description="Read-only discovery of launchers, prefixes, engines, archives, state "
                    "and retained game data. No writes, processes or network access. "
                    "Removal is not implemented in this slice.")
    parser.add_argument("--prefix", action="append",
                        help="prefix to inspect; repeat for multiple bottles "
                             "(default: WINEPREFIX or CS2KIT_SETUP_HOME/prefix)")
    parser.add_argument("--setup-home", help="downloads/DXMT/prefix root (default: ~/CS2)")
    parser.add_argument("--state-home", help="state root (default: CS2KIT_HOME or ~/.cs2kit)")
    parser.add_argument("--library", help="game library to mark as retained")
    parser.add_argument("--app-dest", action="append", help="custom launcher path; repeatable")
    parser.add_argument("--engine-dest", action="append",
                        help="custom engine install path; repeatable")
    parser.add_argument("--shader-cache", action="append",
                        help="custom DXMT shader cache; repeatable")
    parser.add_argument("--dry-run", action="store_true",
                        help="explicitly request the read-only plan (the default)")
    parser.add_argument("--apply", action="store_true",
                        help="reserved for removal; refused in this read-only slice")
    parser.add_argument("--json", action="store_true",
                        help="print one JSON object with the full inventory")
    parser.set_defaults(func=cmd_inventory, prefix=None, setup_home=None, state_home=None,
                        library=None, app_dest=None, engine_dest=None, shader_cache=None,
                        dry_run=False, apply=False, json=False)
