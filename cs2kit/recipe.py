"""T-025 - the declarative bottle recipe is the source of truth.

A bottle that was hand-tuned is a bottle nobody can rebuild. Everything that
deviates from Wine's defaults lives in `profiles/bottle-recipe.yaml`, and
`cs2kit bottle create` must be able to reach the CS2 main menu from that file
alone, with no manual step.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from cs2kit import yamlite
from cs2kit.util import profiles_dir

SCHEMA_VERSION = 1
FORBIDDEN_LAUNCH_OPTIONS = {
    # Lands on a DXVK-macOS fork frozen at 1.10.3 (2023) and a MoltenVK with no
    # geometry shaders. CS2 then falls back to DX11 *silently*, so a -vulkan run
    # can look fine while measuring something else entirely. See docs/02.
    "-vulkan",
}


class RecipeError(ValueError):
    pass


@dataclass
class Recipe:
    name: str
    data: Dict[str, Any] = field(default_factory=dict)
    source: Optional[str] = None

    # --- typed accessors ----------------------------------------------------
    @property
    def wine(self) -> Dict[str, Any]:
        return self.data.get("wine") or {}

    @property
    def windows_version(self) -> str:
        return self.wine.get("windows_version") or "win10"

    @property
    def dll_overrides(self) -> Dict[str, str]:
        return dict(self.wine.get("dll_overrides") or {})

    @property
    def app_defaults(self) -> Dict[str, Dict[str, Any]]:
        """Per-executable overrides, e.g. cs2.exe pinned to Windows 8 for the
        documented permanent audio-crackle fix (T-009 step 3)."""
        return dict(self.wine.get("app_defaults") or {})

    @property
    def env(self) -> Dict[str, str]:
        return {k: str(v) for k, v in (self.data.get("env") or {}).items()}

    @property
    def dxmt(self) -> Dict[str, Any]:
        return self.data.get("dxmt") or {}

    @property
    def dxmt_files(self) -> List[str]:
        return list(self.dxmt.get("files") or [])

    @property
    def dxmt_build(self) -> str:
        """`builtin` (the published release: DLLs live in the Wine tree and the
        overrides must stay off) or `prefix` (DLLs in system32, overrides on)."""
        return str(self.dxmt.get("build") or "builtin")

    @property
    def dxmt_prefix_files(self) -> List[str]:
        """Files that belong in the prefix's system32 even for a builtin build -
        `winemetal.dll` is the one DXMT's wiki names explicitly."""
        return list(self.dxmt.get("prefix_files") or [])

    @property
    def wine_root(self) -> Optional[str]:
        return self.wine.get("root") or None

    @property
    def launch_options(self) -> List[str]:
        return [str(x) for x in (self.data.get("game") or {}).get("launch_options") or []]

    @property
    def display(self) -> Dict[str, Any]:
        return self.data.get("display") or {}

    def hash(self) -> str:
        blob = yamlite.dumps(self.data).encode()
        return hashlib.sha256(blob).hexdigest()[:16]

    def dumps(self) -> str:
        return yamlite.dumps(self.data)

    # --- validation ---------------------------------------------------------
    @property
    def kind(self) -> str:
        """`bottle` (a full prefix recipe) or `profile` (a tuning overlay, T-027)."""
        return str(self.data.get("kind") or "bottle")

    def validate(self) -> List[str]:
        problems: List[str] = []
        if int(self.data.get("schema") or 0) != SCHEMA_VERSION:
            problems.append(f"schema must be {SCHEMA_VERSION}, got {self.data.get('schema')!r}")
        if not self.data.get("name"):
            problems.append("name is required")
        if self.kind not in ("bottle", "profile"):
            problems.append(f"kind must be 'bottle' or 'profile', got {self.kind!r}")
        if self.kind == "profile":
            problems.extend(self._validate_common())
            if not self.data.get("provenance"):
                problems.append("a profile must carry provenance naming the task that measured it (T-027)")
            return problems
        problems.extend(self._validate_dxmt())
        problems.extend(self._validate_common())
        return problems

    def _validate_dxmt(self) -> List[str]:
        """The override rule is decided by which DXMT build you have, and getting
        it backwards fails silently - Wine simply loads something else.

        builtin (the published `-builtin.tar.gz`): the DLLs are installed as Wine
        builtins, and DXMT's wiki says verbatim "Ensure these dlls are NOT set
        overrides native,builtin".
        prefix (`-Dwine_builtin_dll=false`): the DLLs sit in the prefix's system32
        and only load if d3d11/dxgi/d3d10core are overridden native."""
        problems: List[str] = []
        build = self.dxmt_build
        if build not in ("builtin", "prefix"):
            return [f"dxmt.build must be 'builtin' or 'prefix', got {build!r}"]
        graphics = ("d3d11", "dxgi", "d3d10core")
        if build == "builtin":
            wrong = sorted(d for d in graphics if "native" in self.dll_overrides.get(d, ""))
            if wrong:
                problems.append(
                    f"dxmt.build is 'builtin' but {', '.join(wrong)} is overridden to native - "
                    "the builtin build must NOT be overridden or Wine silently loads something else")
            if "n,b" in (self.env.get("WINEDLLOVERRIDES") or ""):
                problems.append("env.WINEDLLOVERRIDES sets n,b, which contradicts dxmt.build: builtin")
        else:
            for dll in ("d3d11", "dxgi"):
                if "native" not in self.dll_overrides.get(dll, ""):
                    problems.append(f"dxmt.build is 'prefix', so wine.dll_overrides.{dll} must start "
                                    "with 'native' or DXMT never loads")
        return problems

    def _validate_common(self) -> List[str]:
        """Rules that hold for a bottle recipe and a tuning profile alike."""
        problems: List[str] = []
        for opt in self.launch_options:
            if opt in FORBIDDEN_LAUNCH_OPTIONS:
                problems.append(f"launch option {opt} is forbidden by docs/02-architecture.md")
        env = self.env
        if env.get("WINEMSYNC") not in ("1", "0", None) :
            problems.append("env.WINEMSYNC must be 0 or 1")
        if env.get("WINEMSYNC") == "1" and env.get("WINEESYNC") == "1":
            problems.append("WINEMSYNC and WINEESYNC are mutually exclusive - pick one (T-012)")
        if self.display.get("hidpi") is True:
            problems.append("display.hidpi must be false - Retina costs roughly 4x (T-009 step 4)")
        return problems

    def require_valid(self) -> "Recipe":
        problems = self.validate()
        if problems:
            raise RecipeError(f"{self.source or self.name}: " + "; ".join(problems))
        return self

    # --- comparison ---------------------------------------------------------
    def flatten(self) -> Dict[str, Any]:
        return _flatten(self.data)

    def diff(self, other: "Recipe") -> Dict[str, Any]:
        mine, theirs = self.flatten(), other.flatten()
        keys = sorted(set(mine) | set(theirs))
        return {k: {"expected": mine.get(k), "actual": theirs.get(k)}
                for k in keys if mine.get(k) != theirs.get(k)}


def _flatten(obj: Any, prefix: str = "") -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            out.update(_flatten(value, f"{prefix}.{key}" if prefix else str(key)))
    elif isinstance(obj, list):
        out[prefix] = list(obj)
    else:
        out[prefix] = obj
    return out


def loads(text: str, source: Optional[str] = None) -> Recipe:
    data = yamlite.loads(text)
    if not isinstance(data, dict):
        raise RecipeError(f"{source or 'recipe'}: expected a mapping at the top level")
    return Recipe(name=str(data.get("name") or "unnamed"), data=data, source=source)


def load(path: Path) -> Recipe:
    path = Path(path)
    try:
        text = path.read_text()
    except OSError as exc:
        raise RecipeError(f"cannot read {path}: {exc}") from exc
    return loads(text, source=str(path))


def default_path() -> Path:
    return profiles_dir() / "bottle-recipe.yaml"


def load_default() -> Recipe:
    return load(default_path())


def resolve(name_or_path: Optional[str]) -> Recipe:
    """Accept a profile name (`balanced-1080p`), a bare filename or a path."""
    if not name_or_path:
        return load_default()
    path = Path(name_or_path)
    if path.exists():
        return load(path)
    for candidate in (profiles_dir() / f"{name_or_path}.yaml", profiles_dir() / name_or_path):
        if candidate.exists():
            return load(candidate)
    available = ", ".join(sorted(p.stem for p in profiles_dir().glob("*.yaml"))) or "none"
    raise RecipeError(f"unknown profile {name_or_path!r} (available: {available})")


def list_profiles() -> List[Path]:
    return sorted(profiles_dir().glob("*.yaml"))
