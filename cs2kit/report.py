"""T-028 - a redacted, shareable diagnostic bundle.

Why the paranoia: T-028's acceptance test is "a security review of a real bundle
finds ZERO personal identifiers", and docs/05-risk-register.md rates this medium
risk because privacy defects are the embarrassing kind. A support bundle is worth
nothing if a user cannot paste it in public, so this module is written to
over-redact rather than to preserve detail: when a value is ambiguous, it goes.

Two rules follow from that:

1. Redaction is a *scrub of the assembled bundle*, not of each collector. Every
   collector may return whatever it likes - including data it did not expect to be
   personal - and it is still scrubbed on the way out.
2. `scan()` re-runs the detectors over the redacted text and `build_bundle()`
   refuses to claim success while it finds anything. The tests plant one of every
   identifier class and assert the scan comes back empty; that is the acceptance
   test, executed.

Scope rule (Phase 4): this module reads and writes local files only. It never
uploads anything - sharing is the user's deliberate act.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import socket
import sys
import tarfile
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from cs2kit import __version__, probe, yamlite
from cs2kit.util import EXIT_FAIL, EXIT_OK, EXIT_USAGE, profiles_dir, run, state_dir

SCHEMA = 1

REDACTED = "<redacted>"
PLACEHOLDERS = {
    "user": REDACTED,
    "email": "<email>",
    "ipv4": "<ip>",
    "ipv6": "<ip6>",
    "mac": "<mac>",
    "steamid64": "<steamid64>",
    "serial": "<serial>",
    "host": "<host>",
}

#: Loopback stays, because "did it bind to localhost?" is a real diagnostic and
#: 127.0.0.1 identifies nobody. Every other address - public *and* RFC1918 - goes:
#: a LAN address plus a timestamp is a fingerprint, and we are not in the business
#: of deciding which private ranges are safe.
KEEP_ADDRESSES = {"127.0.0.1", "::1", "0.0.0.0"}

# --- detectors ---------------------------------------------------------------
_RE_STEAMID64 = re.compile(r"(?<!\d)7656119\d{10}(?!\d)")
_RE_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
_RE_MAC = re.compile(r"(?<![0-9A-Za-z:-])(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}(?![0-9A-Za-z:-])")
_RE_IPV4 = re.compile(r"(?<![\w.])\d{1,3}(?:\.\d{1,3}){3}(?![\w.])")
_RE_IPV6 = re.compile(r"(?<![\w:.])(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}(?:%[0-9A-Za-z]+)?(?![\w:.])")
_RE_USERS_PATH = re.compile(r"(/(?:Users|home)/)([^/\s\"',;:)\]}]+)")
_RE_ACCOUNT_INLINE = re.compile(
    r"""(?ix)
    ( (?:account|persona|login|user|display|owner)[\s_-]*name    # the label
      (?: ["']?\s*[:=]\s*["']?                                  # json / ini / yaml
        | ["']?[ \t]+["']                                        # Valve KeyValues: "k"\t\t"v"
        ) )
    ( [^"'\s,;}\]]+ )                                            # the value
    """)
_RE_SERIAL_INLINE = re.compile(
    r"""(?ix)
    ( serial (?:[\s_-]*number)? [^\n:=]{0,16} (?:["']?\s*[:=]\s*|\t+) \s* ["']? )
    ( [A-Za-z0-9][A-Za-z0-9-]{5,} )
    """)

#: Dict keys whose *entire* value is personal whatever it looks like. Matched with
#: `search`, so "IOPlatformSerialNumber" and "steam_account_name" both hit.
_RE_SECRET_KEY = re.compile(
    r"""(?ix)
    (account[\s_-]*name | persona[\s_-]*name | display[\s_-]*name | real[\s_-]*name
     | full[\s_-]*name | user[\s_-]*name | \busername\b | \buser\b | logname | login
     | steam[\s_-]*id | steamid | \bfriend[\s_-]*code\b
     | e[\s_-]*mail | \bemail\b
     | serial | udid | \buuid\b | hardware[\s_-]*id
     | host[\s_-]*name | hostname | computer[\s_-]*name | machine[\s_-]*name
     | mac[\s_-]*addr | ether | \bbssid\b | \bssid\b
     | ip[\s_-]*addr | ipv4 | ipv6 | public[\s_-]*ip | \bwifi[\s_-]*network\b
     | \btoken\b | \bpassword\b | \bsecret\b | api[\s_-]*key)
    """)

_MIN_SECRET_LEN = 3


class RedactionError(RuntimeError):
    """The bundle still contains an identifier after redaction.

    This is a bug in this module, and it is raised rather than swallowed: shipping
    a bundle that failed its own scan would defeat the whole point of T-028.
    """


# --- local identity ----------------------------------------------------------
_SECRETS_CACHE: Optional[List[str]] = None


def _scutil(key: str) -> str:
    try:
        return run(["scutil", "--get", key], timeout=5).out.strip()
    except Exception:  # pragma: no cover - run() does not raise, this is belt-and-braces
        return ""


def local_secrets(refresh: bool = False) -> List[str]:
    """Literal strings that identify *this* machine and *this* person.

    Patterns cannot catch a name: "Mahmut's MacBook Pro" from `scutil --get
    ComputerName` matches no regex, so it is collected here and replaced literally,
    along with the hyphenated LocalHostName form macOS derives from it.
    """
    global _SECRETS_CACHE
    if _SECRETS_CACHE is not None and not refresh:
        return _SECRETS_CACHE
    raw: List[str] = []
    for value in (os.environ.get("USER"), os.environ.get("LOGNAME"),
                  os.environ.get("USERNAME")):
        if value:
            raw.append(value)
    try:
        raw.append(Path.home().name)
    except (OSError, RuntimeError):  # pragma: no cover - no home is exotic
        pass
    for key in ("ComputerName", "LocalHostName", "HostName"):
        value = _scutil(key)
        if value:
            raw.append(value)
    try:
        raw.append(socket.gethostname())
    except OSError:  # pragma: no cover
        pass
    _SECRETS_CACHE = _secret_variants(raw)
    return _SECRETS_CACHE


def _secret_variants(values: Iterable[str]) -> List[str]:
    """Each secret, plus the forms macOS derives from it, longest first.

    Longest first matters: replacing "Mahmuts-MacBook-Pro" before "Mahmut" leaves
    one placeholder instead of "<redacted>s-MacBook-Pro", which would leak the
    structure of the original."""
    forms = set()
    for value in values:
        value = (value or "").strip()
        if len(value) < _MIN_SECRET_LEN:
            continue
        hyphenated = value.replace(" ", "-")
        forms.update({value, hyphenated, re.sub(r"[^A-Za-z0-9-]", "", hyphenated)})
    out = set(forms)
    for form in forms:
        if not form.endswith(".local"):
            out.add(form + ".local")   # macOS mDNS name, derived from the same string
    return sorted((s for s in out if len(s) >= _MIN_SECRET_LEN), key=lambda s: (-len(s), s))


# --- string scrubbing --------------------------------------------------------
def _scrub_addresses(text: str) -> str:
    """IPs, validated with `ipaddress` rather than trusted to a regex.

    The naive IPv6 pattern also matches "12:30:45" out of a timestamp and every MAC
    address; parsing each candidate throws those out, so a bundle keeps its
    timestamps and still loses its addresses."""
    def _ip(match: "re.Match[str]", version: int) -> str:
        candidate = match.group(0)
        bare = candidate.split("%")[0]
        try:
            ipaddress.ip_address(bare)
        except ValueError:
            return candidate
        if bare in KEEP_ADDRESSES:
            return candidate
        return PLACEHOLDERS["ipv4"] if version == 4 else PLACEHOLDERS["ipv6"]

    text = _RE_MAC.sub(PLACEHOLDERS["mac"], text)
    text = _RE_IPV6.sub(lambda m: _ip(m, 6), text)
    text = _RE_IPV4.sub(lambda m: _ip(m, 4), text)
    return text


def scrub(text: str, secrets: Sequence[str] = ()) -> str:
    """Scrub one string. Order is deliberate: structured patterns first (an email
    would otherwise be half-eaten by the username rule), literals last."""
    if not text:
        return text
    text = _RE_EMAIL.sub(PLACEHOLDERS["email"], text)
    text = _scrub_addresses(text)
    text = _RE_STEAMID64.sub(PLACEHOLDERS["steamid64"], text)
    text = _RE_USERS_PATH.sub(
        lambda m: m.group(1) + (m.group(2) if m.group(2) == REDACTED else REDACTED), text)
    text = _RE_ACCOUNT_INLINE.sub(lambda m: m.group(1) + REDACTED, text)
    text = _RE_SERIAL_INLINE.sub(lambda m: m.group(1) + PLACEHOLDERS["serial"], text)
    for secret in secrets:
        text = re.sub(re.escape(secret), PLACEHOLDERS["host"], text, flags=re.IGNORECASE)
    return text


def redact(obj: Any, extra_secrets: Sequence[str] = ()) -> Any:
    """Recursively scrub a JSON-shaped object.

    Keys are scrubbed as well as values, because a path used as a dict key carries
    the username just as happily as one used as a value. A key that *names* a
    secret (`account_name`, `IOPlatformSerialNumber`, `hostname`, ...) has its
    whole value replaced, whatever the value's shape - that is how a SteamID stored
    as an int, or a serial that looks like a product code, is caught.
    """
    secrets = _secret_variants(list(extra_secrets)) + list(local_secrets())
    return _redact(obj, secrets)


def _redact(obj: Any, secrets: Sequence[str]) -> Any:
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for key, value in obj.items():
            new_key = scrub(key, secrets) if isinstance(key, str) else key
            if isinstance(key, str) and _RE_SECRET_KEY.search(key):
                out[new_key] = REDACTED if value not in (None, "", [], {}) else value
            else:
                out[new_key] = _redact(value, secrets)
        return out
    if isinstance(obj, (list, tuple)):
        return [_redact(v, secrets) for v in obj]
    if isinstance(obj, str):
        return scrub(obj, secrets)
    if isinstance(obj, bool) or obj is None:
        return obj
    if isinstance(obj, int):
        # a SteamID64 stored as a number is still a SteamID64
        return REDACTED if _RE_STEAMID64.fullmatch(str(obj)) else obj
    if isinstance(obj, float):
        return obj
    return scrub(str(obj), secrets)


# --- verification ------------------------------------------------------------
def scan(obj: Any, extra_secrets: Sequence[str] = ()) -> List[Dict[str, str]]:
    """Look for identifiers in an already-redacted object; empty list means clean.

    This is the T-028 acceptance test in code form, and it is run by build_bundle()
    before the bundle is written, not after.
    """
    text = obj if isinstance(obj, str) else json.dumps(obj, default=str)
    findings: List[Dict[str, str]] = []

    def note(kind: str, sample: str) -> None:
        findings.append({"kind": kind, "sample": sample[:80]})

    for match in _RE_STEAMID64.finditer(text):
        note("steamid64", match.group(0))
    for match in _RE_EMAIL.finditer(text):
        note("email", match.group(0))
    for match in _RE_MAC.finditer(text):
        note("mac", match.group(0))
    for regex, version in ((_RE_IPV4, 4), (_RE_IPV6, 6)):
        for match in regex.finditer(text):
            bare = match.group(0).split("%")[0]
            try:
                ipaddress.ip_address(bare)
            except ValueError:
                continue
            if bare not in KEEP_ADDRESSES:
                note("ipv%d" % version, match.group(0))
    for match in _RE_USERS_PATH.finditer(text):
        if match.group(2) != REDACTED:
            note("home_path", match.group(0))
    for secret in _secret_variants(list(extra_secrets)) + list(local_secrets()):
        if re.search(re.escape(secret), text, re.IGNORECASE):
            note("local_identifier", secret)
    return findings


# --- collection --------------------------------------------------------------
def _safe(label: str, fn, *args, **kwargs) -> Any:
    """Every collector is optional. A doctor signature change, a missing profile or
    a half-built bottle must degrade the bundle, never break `cs2kit report`."""
    try:
        return fn(*args, **kwargs)
    except Exception as exc:  # deliberately broad: this is the whole point
        return {"error": "%s: %s" % (type(exc).__name__, exc), "collector": label}


def _doctor_section() -> Any:
    """doctor is imported lazily and called defensively - T-024 owns its signature
    and is free to change it without breaking T-028."""
    try:
        from cs2kit import doctor  # noqa: WPS433 - optional dependency inside the same package
    except Exception as exc:
        return {"available": False, "error": "%s: %s" % (type(exc).__name__, exc)}
    result = _safe("doctor", getattr(doctor, "run_checks", lambda: None))
    return {"available": True, "result": _normalise(result)}


def _integrity_section() -> Any:
    """T-021's integrity guard, if that module exists yet. The first callable that
    answers wins; nothing here assumes a particular entry point."""
    try:
        from cs2kit import integrity  # noqa: WPS433
    except Exception as exc:
        return {"available": False, "error": "%s: %s" % (type(exc).__name__, exc)}
    for name in ("summary", "status", "verify", "run_checks", "check"):
        fn = getattr(integrity, name, None)
        if callable(fn):
            return {"available": True, "entry_point": name, "result": _normalise(_safe(name, fn))}
    return {"available": True, "entry_point": None,
            "result": {"error": "no recognised entry point in cs2kit.integrity"}}


def _bench_section() -> Any:
    try:
        from cs2kit import bench  # noqa: WPS433
    except Exception as exc:  # pragma: no cover - bench ships with the package
        return {"available": False, "error": "%s: %s" % (type(exc).__name__, exc)}
    session = _safe("bench", bench.latest_session)
    if isinstance(session, dict) and session.get("error"):
        return {"available": True, "session": None, "error": session["error"]}
    if not session:
        return {"available": True, "session": None,
                "note": "no stored benchmark session (run: cs2kit bench run)"}
    trimmed = {k: v for k, v in session.items() if k != "env"}
    return {"available": True, "session": trimmed}


def _recipe_section() -> Any:
    directory = profiles_dir()
    out: Dict[str, Any] = {"dir": str(directory), "profiles": [], "recipe": None}
    if not directory.is_dir():
        out["note"] = "no profiles/ directory in this checkout"
        return out
    for path in sorted(directory.glob("*.y*ml")):
        out["profiles"].append(path.name)
        if path.stem in ("bottle-recipe", "recipe"):
            out["recipe"] = _safe("recipe", yamlite.load_file, path)
    return out


def _normalise(value: Any) -> Any:
    """Turn whatever a collector returned into JSON-shaped data."""
    for attr in ("as_dict", "to_dict", "asdict"):
        method = getattr(value, attr, None)
        if callable(method):
            try:
                return method()
            except Exception:  # pragma: no cover - defensive
                break
    if isinstance(value, (list, tuple)):
        return [_normalise(v) for v in value]
    if isinstance(value, dict):
        return {k: _normalise(v) for k, v in value.items()}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def collect() -> Dict[str, Any]:
    """Assemble the raw, UNREDACTED bundle. Never write this to disk."""
    return {
        "schema": SCHEMA,
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tool": {
            "name": "cs2kit",
            "version": __version__,
            "python": sys.version.split()[0],
            "platform": sys.platform,
        },
        "env": _safe("env", probe.snapshot),
        "bottle": _safe("bottle", probe.bottle_state),
        "recipe": _safe("recipe", _recipe_section),
        "doctor": _doctor_section(),
        "bench": _bench_section(),
        "integrity": _integrity_section(),
    }


SECTION_DESCRIPTIONS = (
    ("tool", "CS2Kit and Python versions"),
    ("env", "machine snapshot: macOS build, chip, RAM, GPU, wine/DXMT versions, CS2 buildid"),
    ("bottle", "wine prefix state: recipe name and hash, DXMT presence (paths redacted)"),
    ("recipe", "the bottle recipe and profile names shipped in this checkout"),
    ("doctor", "PASS/WARN/FAIL result of every doctor check"),
    ("bench", "the latest stored benchmark session: medians, spread, hitch counts"),
    ("integrity", "T-021 game-file integrity summary (hashes, never file contents)"),
)

REDACTION_CLASSES = (
    "local username, in $USER and in every absolute path that contains it",
    "SteamID64 (17 digits beginning 7656119), in text and as a number",
    "Steam account, persona and login names",
    "email addresses",
    "IPv4 and IPv6 addresses, public and private alike (127.0.0.1 is kept)",
    "MAC addresses",
    "hardware serial numbers and UUIDs",
    "computer name, local hostname and DNS hostname",
    "any absolute path under the home directory",
)


# --- rendering ---------------------------------------------------------------
def render_markdown(bundle: Dict[str, Any]) -> str:
    """The human-readable half of the bundle - what a reviewer actually reads."""
    env = bundle.get("env") or {}
    stable = env.get("stable") or {} if isinstance(env, dict) else {}
    bench = (bundle.get("bench") or {}).get("session") or {}
    agg = bench.get("aggregate") or {}
    lines = [
        "# CS2Kit report",
        "",
        "Generated %s by cs2kit %s. Redacted for sharing: %s."
        % (bundle.get("generated"), (bundle.get("tool") or {}).get("version"),
           "; ".join(REDACTION_CLASSES)),
        "",
        "## Environment",
        "",
        "| key | value |",
        "| --- | --- |",
    ]
    for key in ("macos", "macos_build", "chip", "arch", "ram_gb", "gpu_cores", "metal",
                "resolution", "wine_version", "dxmt_version", "cs2_buildid", "recipe_name"):
        lines.append("| %s | %s |" % (key, stable.get(key, "-")))
    lines.append("| env_id | %s |" % (env.get("env_id", "-") if isinstance(env, dict) else "-"))

    lines += ["", "## Benchmark", ""]
    if agg:
        lines += ["| metric | value |", "| --- | --- |"]
        for key in ("avg_fps", "low_1_pct_fps", "p99_frametime_ms", "hitch_count",
                    "run_count", "spread_pct"):
            lines.append("| %s | %s |" % (key, agg.get(key, "-")))
        lines.append("")
        lines.append("Map: %s (workshop %s), buildid %s."
                     % ((bench.get("map") or {}).get("name"),
                        (bench.get("map") or {}).get("workshop_id"), bench.get("buildid")))
    else:
        lines.append("No stored benchmark session.")

    doctor = bundle.get("doctor") or {}
    lines += ["", "## Doctor", ""]
    checks = ((doctor.get("result") or {}).get("checks")
              if isinstance(doctor.get("result"), dict) else None)
    if checks:
        lines += ["| status | check | detail |", "| --- | --- | --- |"]
        for check in checks:
            lines.append("| %s | %s | %s |" % (check.get("status"), check.get("label"),
                                               str(check.get("detail", "")).replace("|", "/")))
    else:
        lines.append("Doctor output unavailable: %s"
                     % (doctor.get("error") or doctor.get("result") or "no checks"))

    lines += ["", "## Raw sections", "",
              "The machine-readable form of everything above is in `report.json`.", ""]
    for name, description in SECTION_DESCRIPTIONS:
        lines.append("* `%s` - %s" % (name, description))
    lines.append("")
    return "\n".join(lines)


def preview_lines(bundle: Dict[str, Any], files: Sequence[str] = ()) -> List[str]:
    """Exactly what will be shared, printed before anything is written (T-028)."""
    lines = ["This bundle will contain, and nothing else:"]
    for name, description in SECTION_DESCRIPTIONS:
        present = name in bundle and bundle.get(name) not in (None, {}, [])
        lines.append("  [%s] %-10s %s" % ("x" if present else " ", name, description))
    lines.append("")
    lines.append("Removed from every value, key and path before writing:")
    for item in REDACTION_CLASSES:
        lines.append("  - " + item)
    if files:
        lines.append("")
        lines.append("Files to write:")
        for path in files:
            lines.append("  " + str(path))
    return lines


# --- bundle ------------------------------------------------------------------
def build_bundle(dest_dir, bundle: Optional[Dict[str, Any]] = None,
                 extra_secrets: Sequence[str] = (), archive: bool = True,
                 name: str = "cs2kit-report", strict: bool = True) -> Dict[str, Any]:
    """Collect, redact, verify, then write report.json + report.md and a .tar.gz.

    The verification step is not optional decoration: `strict=True` raises
    RedactionError rather than write a bundle that its own scanner still finds
    identifiers in. T-028 promises zero, so zero is enforced here.
    """
    raw = collect() if bundle is None else bundle
    clean = redact(raw, extra_secrets=extra_secrets)
    findings = scan(clean, extra_secrets=extra_secrets)
    if findings and strict:
        raise RedactionError("redaction left %d identifier(s): %s"
                             % (len(findings), ", ".join(sorted({f["kind"] for f in findings}))))

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    dest = Path(dest_dir)
    out_dir = dest / ("%s-%s" % (name, stamp))
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "report.json"
    md_path = out_dir / "report.md"
    json_path.write_text(json.dumps(clean, indent=2, sort_keys=True, default=str) + "\n")
    md_path.write_text(render_markdown(clean))

    archive_path = None
    if archive:
        archive_path = dest / ("%s-%s.tar.gz" % (name, stamp))
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(str(out_dir), arcname=out_dir.name)
    return {
        "dir": str(out_dir),
        "json": str(json_path),
        "md": str(md_path),
        "archive": str(archive_path) if archive_path else None,
        "findings": findings,
        "clean": not findings,
        "bundle": clean,
    }


# --- command -----------------------------------------------------------------
def _interactive() -> bool:
    try:
        return bool(sys.stdin.isatty())
    except (ValueError, AttributeError):  # pragma: no cover - closed stdin
        return False


def _confirm(prompt: str) -> bool:
    try:
        answer = input(prompt)
    except (EOFError, KeyboardInterrupt):
        return False
    return answer.strip().lower() in ("y", "yes")


def cmd_report(args: argparse.Namespace) -> int:
    """`cs2kit report` - print what would be shared, then write it only on consent."""
    dest = Path(args.out) if args.out else state_dir() / "reports"
    raw = collect()
    clean = redact(raw, extra_secrets=args.secret or ())
    findings = scan(clean, extra_secrets=args.secret or ())
    preview = preview_lines(clean, files=[str(dest / "<stamp>/report.json"),
                                          str(dest / "<stamp>/report.md"),
                                          str(dest / "<stamp>.tar.gz")])

    if not args.json:
        print("\n".join(preview))
        print("")
        print(render_markdown(clean))

    if findings:
        detail = ("refusing to write: the redaction scan still found %d identifier(s): %s. "
                  "This is a CS2Kit bug - please report it with the kinds listed, not the values."
                  % (len(findings), ", ".join(sorted({f["kind"] for f in findings}))))
        if args.json:
            print(json.dumps({"command": "report", "ok": False, "written": False,
                              "reason": "redaction-incomplete", "detail": detail,
                              "findings": [f["kind"] for f in findings]},
                             indent=2, sort_keys=True))
        else:
            print(detail, file=sys.stderr)
        return EXIT_FAIL

    approved = bool(args.yes)
    if not approved:
        if _interactive():
            approved = _confirm("\nWrite and share this bundle? [y/N] ")
            if not approved:
                message = "aborted: nothing was written"
                print(json.dumps({"command": "report", "ok": True, "written": False,
                                  "reason": "declined", "detail": message},
                                 indent=2, sort_keys=True) if args.json else message)
                return EXIT_OK
        else:
            message = ("refusing to write a shareable bundle without confirmation: "
                       "re-run with --yes once you have read the preview above")
            if args.json:
                print(json.dumps({"command": "report", "ok": False, "written": False,
                                  "reason": "confirmation-required", "detail": message,
                                  "sections": [n for n, _ in SECTION_DESCRIPTIONS],
                                  "redacts": list(REDACTION_CLASSES)},
                                 indent=2, sort_keys=True))
            else:
                print(message, file=sys.stderr)
            return EXIT_USAGE

    result = build_bundle(dest, bundle=raw, extra_secrets=args.secret or (),
                          archive=not args.no_archive)
    if args.json:
        payload = {k: v for k, v in result.items() if k != "bundle"}
        payload.update({"command": "report", "ok": True, "written": True, "report": result["bundle"]})
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    else:
        print("\nwrote %s" % result["json"])
        print("wrote %s" % result["md"])
        if result["archive"]:
            print("wrote %s" % result["archive"])
    return EXIT_OK


def register(subparsers) -> None:
    """Plug `report` into the CS2Kit CLI (T-028)."""
    parser = subparsers.add_parser(
        "report", help="build a redacted, shareable diagnostic bundle (T-028)",
        description=("Collects environment, bottle, doctor, benchmark and integrity data, "
                     "strips every personal identifier, prints exactly what will be shared, "
                     "and writes report.json + report.md + a .tar.gz only after you agree."))
    parser.add_argument("--out", default=None, metavar="DIR",
                        help="where to write the bundle (default: <state>/reports)")
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    parser.add_argument("--secret", action="append", metavar="TEXT",
                        help="an extra literal string to scrub (repeatable)")
    parser.add_argument("--no-archive", dest="no_archive", action="store_true",
                        help="write the directory but not the .tar.gz")
    parser.add_argument("--json", action="store_true", help="print one JSON object to stdout")
    parser.set_defaults(func=cmd_report)
