"""T-011 benchmark protocol, automated as T-026 `cs2kit bench`.

Why this module exists: docs/07-benchmark-protocol.md argues that essentially every
published CS2-on-Mac FPS number is a rumour, because it omits the map and does not
control for shader compilation. Automating the protocol is the only way a
post-update regression is *detected* rather than felt, so everything here is keyed
by `probe.env_id()` plus the CS2 `buildid`: a number is only ever compared against
another number taken on the same machine, the same stack and the same game build.

Scope rule (docs/03-development-plan.md, Phase 4): CS2Kit measures, it does not
play. This module never launches the game and never needs sudo - it consumes
frametime logs the user produced by running the protocol, and stores the result.

The pure functions (`summarize`, `aggregate`, `compare`, the parsers) carry the
maths and are testable with no game, no bottle and no macOS present.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from cs2kit import probe
from cs2kit.util import (
    EXIT_NOT_READY,
    EXIT_OK,
    EXIT_REGRESSION,
    EXIT_USAGE,
    median,
    pct_delta,
    percentile,
    read_json,
    state_dir,
    which,
    write_json,
)

SCHEMA = 1

# --- the protocol, as constants so the CLI and the tests cannot drift from the doc
MAP_PRIMARY = {"name": "Ancient FPS Benchmark", "workshop_id": "3472126051", "weight": "heavy"}
MAP_SECONDARY = {"name": "Dust2 FPS Benchmark", "workshop_id": "3240880604", "weight": "light"}
WARMUP_RUNS = 3
MEASURED_RUNS = 5
DEFAULT_TOLERANCE_PCT = 5.0      # T-026 acceptance: reproduce the stored median within +-5 %
DEFAULT_HITCH_MS = 20.0
PROTOCOL_HITCH_MS = 50.0         # docs/07 reports "hitch count (frames > 50 ms)"

PROTOCOL_STEPS = (
    "1. Reboot. Nothing else running. Plugged in, unless this is explicitly a battery run.",
    "2. Subscribe to and load the {name} (workshop {workshop_id}).".format(**MAP_PRIMARY),
    "3. Complete {n} DISCARDED warm-up runs - they pay the shader-compilation cost.".format(n=WARMUP_RUNS),
    "4. Complete {n} MEASURED runs, saving one frametime log per run.".format(n=MEASURED_RUNS),
    "5. Report median avg FPS, median 1 % low, p99 frametime and hitch count. Never a maximum,",
    "   never a single run, and never against a number taken on the other map.",
    "6. Log powermetrics CPU/GPU power and memory pressure in parallel (needs your own sudo).",
)

FIXED_VARIABLES = (
    "macOS build", "chip / cores / GPU cores / RAM", "CS2 buildid", "runtime host + version",
    "graphics backend + version", "sync mode", "resolution", "upscaler", "in-game preset",
    "HiDPI state", "Steam overlay state", "power source", "Low Power Mode", "display refresh",
    "ambient temperature", "time since boot",
)

METRICS: Dict[str, bool] = {
    # metric -> higher_is_better
    "avg_fps": True,
    "low_1_pct_fps": True,
    "p99_frametime_ms": False,
    "hitch_count": False,
}
#: Only the two headline metrics decide the overall verdict. The frametime
#: percentile is a restatement of the 1 % low, and hitch counts are small
#: integers whose percentage deltas are meaningless near zero.
VERDICT_METRICS = ("avg_fps", "low_1_pct_fps")


class BenchError(ValueError):
    """A frametime log could not be understood, or a summary is impossible.

    Raised loudly rather than guessing: a silently mis-parsed log produces a
    plausible-looking FPS number that means nothing, which is exactly the failure
    docs/07-benchmark-protocol.md exists to prevent.
    """


# --- maths -------------------------------------------------------------------
def _round(value: float, digits: int = 4) -> float:
    """Round for storage. Benchmarks are compared with a +-5 % tolerance, so four
    decimals is far beyond the noise floor and keeps stored JSON diffable."""
    return float(round(float(value), digits))


def summarize(frametimes_ms: Sequence[float], hitch_ms: float = DEFAULT_HITCH_MS) -> Dict[str, Any]:
    """Reduce one run's frametimes to the five numbers docs/07 allows us to report.

    Definitions, spelled out because every one of them is somewhere reported wrongly:

    * ``avg_fps``   - frames divided by total elapsed time, NOT the mean of the
      per-frame FPS values. The mean of instantaneous FPS is dominated by the
      cheap frames and flatters a stuttering run.
    * ``low_1_pct_fps`` - the FPS of the 99th-percentile frametime, i.e. the pace
      during the worst 1 % of frames. (The other convention - the mean of the
      slowest 1 % of frames - is close but not identical; we state ours.)
    * ``p99_frametime_ms`` - the same percentile expressed as time.
    * ``hitch_count`` - frames slower than ``max(hitch_ms, 3 x median frametime)``.
      Two rules, because both failure modes matter: the fixed floor is the
      protocol's absolute "this was visible" threshold (pass ``hitch_ms=50`` to
      reproduce docs/07's "frames > 50 ms" exactly), while 3x the run's own median
      catches relative stutter on a machine fast enough that 20 ms never happens.
    * ``duration_s`` - the sum of the frametimes, not wall-clock time.

    Raises BenchError on an empty run or a non-positive/non-numeric frametime.
    """
    values: List[float] = []
    for raw in frametimes_ms:
        try:
            value = float(raw)
        except (TypeError, ValueError):
            raise BenchError("frametime %r is not a number" % (raw,))
        if not math.isfinite(value) or value <= 0:
            raise BenchError("frametime %r is not a positive duration in ms" % (raw,))
        values.append(value)
    if not values:
        raise BenchError("no frametimes: a run with zero frames cannot be summarised")

    total_ms = math.fsum(values)
    med = median(values)
    p99 = percentile(values, 99.0)
    threshold = max(float(hitch_ms), 3.0 * med)
    return {
        "avg_fps": _round(1000.0 * len(values) / total_ms),
        "low_1_pct_fps": _round(1000.0 / p99),
        "p99_frametime_ms": _round(p99),
        "hitch_count": sum(1 for v in values if v > threshold),
        "hitch_threshold_ms": _round(threshold),
        "median_frametime_ms": _round(med),
        "frames": len(values),
        "duration_s": _round(total_ms / 1000.0),
    }


def aggregate(runs: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Median of every metric across the measured runs, plus the run-to-run spread.

    docs/07: "Never report a maximum. Never report a single run." The median of the
    five measured runs is the reported number; ``spread_pct`` - the peak-to-peak
    range of avg FPS as a percentage of that median - is how a reader judges whether
    the machine was quiet enough for the number to mean anything. A spread wider
    than the T-026 +-5 % tolerance means the run conditions, not the stack, are what
    a later comparison will be measuring.
    """
    if not runs:
        raise BenchError("no measured runs to aggregate")
    for run in runs:
        missing = [m for m in METRICS if m not in run]
        if missing:
            raise BenchError("run is missing metrics: %s" % ", ".join(sorted(missing)))

    out: Dict[str, Any] = {}
    for metric in METRICS:
        out[metric] = _round(median(float(r[metric]) for r in runs))
    for extra in ("frames", "duration_s"):
        present = [float(r[extra]) for r in runs if extra in r]
        if present:
            out[extra] = _round(median(present))
    avg = [float(r["avg_fps"]) for r in runs]
    med_avg = median(avg)
    out["run_count"] = len(runs)
    out["spread_pct"] = _round((max(avg) - min(avg)) / med_avg * 100.0 if med_avg else 0.0)
    out["protocol_runs"] = MEASURED_RUNS
    return out


def compare(new: Dict[str, Any], baseline: Dict[str, Any],
            tol_pct: float = DEFAULT_TOLERANCE_PCT) -> Dict[str, Any]:
    """T-026: is this run the same as the stored one, to within `tol_pct` per cent?

    The boundary is inclusive: a delta of exactly -5.0 % against a 5 % tolerance is
    a PASS, -5.01 % is a REGRESSION. Deltas are rounded to six decimals first so
    that binary floating point cannot decide an acceptance test.

    The overall verdict is taken from VERDICT_METRICS only; each metric still
    carries its own verdict so a frametime-only regression is visible in the output.
    """
    tol = abs(float(tol_pct))
    metrics: Dict[str, Any] = {}
    for metric, higher_is_better in METRICS.items():
        if metric not in new or metric not in baseline:
            continue
        try:
            new_v, base_v = float(new[metric]), float(baseline[metric])
        except (TypeError, ValueError):
            continue
        delta = pct_delta(new_v, base_v)
        delta = _round(delta, 6) if math.isfinite(delta) else None
        if delta is None:
            # baseline was zero (typically hitch_count): fall back to a direct
            # comparison, since every percentage against zero is infinite.
            better = new_v < base_v if not higher_is_better else new_v > base_v
            worse = new_v > base_v if not higher_is_better else new_v < base_v
        else:
            signed = delta if higher_is_better else -delta
            better, worse = signed > tol, signed < -tol
        verdict = "REGRESSION" if worse else ("IMPROVED" if better else "PASS")
        metrics[metric] = {
            "new": _round(new_v),
            "baseline": _round(base_v),
            "delta_pct": delta,
            "higher_is_better": higher_is_better,
            "verdict": verdict,
        }

    considered = [m for m in VERDICT_METRICS if m in metrics]
    if not considered:
        raise BenchError("nothing comparable: need at least one of %s in both results"
                         % ", ".join(VERDICT_METRICS))
    regressed = [m for m in considered if metrics[m]["verdict"] == "REGRESSION"]
    improved = [m for m in considered if metrics[m]["verdict"] == "IMPROVED"]
    if regressed:
        verdict = "REGRESSION"
    elif improved:
        verdict = "IMPROVED"
    else:
        verdict = "PASS"
    return {
        "verdict": verdict,
        "tolerance_pct": _round(tol),
        "metrics": metrics,
        "regressed": regressed,
        "improved": improved,
        "decided_by": list(considered),
    }


# --- parsers -----------------------------------------------------------------
_COMMENT = re.compile(r"^\s*(?:#|//|;)")
_FRAMETIME_HEADER = re.compile(
    r"frame\s*_?\s*time|msbetween|ms_?between|\bms\b|millisec|\bdt\b|delta", re.I)
_FPS_HEADER = re.compile(r"\bfps\b|frames?\s*per\s*second", re.I)
_MS_INLINE = re.compile(r"([0-9]*\.?[0-9]+)\s*(?:ms\b|milliseconds?\b)", re.I)
_FPS_INLINE = re.compile(r"(?:([0-9]*\.?[0-9]+)\s*fps\b|\bfps[:= ]+\s*([0-9]*\.?[0-9]+))", re.I)
_NUMBER = re.compile(r"^[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$")

#: A parser that quietly drops most of the file is worse than one that refuses,
#: so a log is rejected once more than this fraction of its data lines are junk.
_MAX_JUNK_RATIO = 0.5


def _clean_lines(text: str) -> List[str]:
    return [ln for ln in (raw.rstrip("\r\n") for raw in text.splitlines())
            if ln.strip() and not _COMMENT.match(ln)]


def _is_number(token: str) -> bool:
    return bool(_NUMBER.match(token.strip().strip('"').strip("'")))


def _to_float(token: str) -> Optional[float]:
    token = token.strip().strip('"').strip("'")
    if not _is_number(token):
        return None
    try:
        return float(token)
    except ValueError:  # pragma: no cover - _NUMBER already guarantees this
        return None


def _split(line: str, delimiter: Optional[str]) -> List[str]:
    if delimiter is None:
        return line.split()
    return next(csv.reader(io.StringIO(line), delimiter=delimiter))


def _detect_delimiter(line: str) -> Optional[str]:
    for candidate in (",", "\t", ";"):
        if candidate in line:
            return candidate
    return None


def parse_csv(text: str) -> List[float]:
    """Frametimes from a columnar log: one bare column, or CSV with a header.

    Accepted shapes:
      * one column of numbers, no header (the simplest thing a user can produce);
      * any delimited file whose header names a frametime/ms column (PresentMon's
        ``MsBetweenPresents``, MangoHud's ``frametime``, our own exports);
      * the same with only an FPS column, which is converted to frametimes.

    Ambiguity is refused, not guessed: a headerless multi-column file raises
    BenchError rather than silently picking column 0.
    """
    lines = _clean_lines(text)
    if not lines:
        raise BenchError("empty frametime log")

    delimiter = _detect_delimiter(lines[0])
    first = _split(lines[0], delimiter)
    header = None if all(_is_number(f) for f in first if f.strip()) else first

    column, as_fps = 0, False
    if header is not None:
        index = next((i for i, name in enumerate(header) if _FRAMETIME_HEADER.search(name)), None)
        if index is None:
            index = next((i for i, name in enumerate(header) if _FPS_HEADER.search(name)), None)
            as_fps = index is not None
        if index is None:
            raise BenchError("no frametime or fps column in header: %s"
                             % ", ".join(n.strip() for n in header))
        column = index
        rows = lines[1:]
    else:
        if len([f for f in first if f.strip()]) != 1:
            raise BenchError("headerless log has %d columns; add a header naming the "
                             "frametime column so the right one is not guessed"
                             % len(first))
        rows = lines

    values: List[float] = []
    junk = 0
    for line in rows:
        fields = _split(line, delimiter)
        value = _to_float(fields[column]) if column < len(fields) else None
        if value is None or value <= 0 or not math.isfinite(value):
            junk += 1
            continue
        values.append(1000.0 / value if as_fps else value)

    if not values:
        raise BenchError("no usable numbers in the frametime log")
    if junk > _MAX_JUNK_RATIO * (junk + len(values)):
        raise BenchError("%d of %d data lines were unreadable; this does not look "
                         "like a frametime log" % (junk, junk + len(values)))
    return values


def _parse_inline(text: str) -> List[float]:
    """CS2 `cl_showfps`-style console spam: 'x fps  y ms', in either order."""
    lines = _clean_lines(text)
    values: List[float] = []
    junk = 0
    for line in lines:
        ms = _MS_INLINE.search(line)
        if ms:
            value = float(ms.group(1))
        else:
            fps = _FPS_INLINE.search(line)
            value = 1000.0 / float(fps.group(1) or fps.group(2)) if fps else 0.0
        if value > 0 and math.isfinite(value):
            values.append(value)
        else:
            junk += 1
    if not values:
        raise BenchError("no 'N ms' or 'N fps' readings found")
    if junk > _MAX_JUNK_RATIO * (junk + len(values)):
        raise BenchError("%d of %d lines carried no reading; this does not look "
                         "like a cl_showfps log" % (junk, junk + len(values)))
    return values


def parse_frametime_log(text: str) -> List[float]:
    """Permissive front door: columnar first, then cl_showfps-style console lines.

    Both parsers refuse a file that is mostly junk, so garbage in produces a
    BenchError naming both attempts rather than a fabricated benchmark result.
    """
    if not isinstance(text, str):
        raise BenchError("frametime log must be text, got %s" % type(text).__name__)
    try:
        return parse_csv(text)
    except BenchError as columnar:
        try:
            return _parse_inline(text)
        except BenchError as inline:
            raise BenchError("unrecognised frametime log (as columns: %s; as console "
                             "lines: %s)" % (columnar, inline))


def load_run(path: Path, hitch_ms: float = DEFAULT_HITCH_MS) -> Dict[str, Any]:
    """Read one frametime file and summarise it, tagging where it came from."""
    path = Path(path)
    try:
        text = path.read_text(errors="replace")
    except OSError as exc:
        raise BenchError("cannot read %s: %s" % (path, exc))
    run = summarize(parse_frametime_log(text), hitch_ms=hitch_ms)
    run["source"] = path.name
    return run


# --- storage -----------------------------------------------------------------
def bench_dir() -> Path:
    path = state_dir() / "bench"
    path.mkdir(parents=True, exist_ok=True)
    return path


def session_dir(env_id: str) -> Path:
    return bench_dir() / (env_id or "unknown")


def slug(text: str) -> str:
    """A filename-safe label. Benchmarks are compared by hand as often as by code,
    so the filename has to stay readable."""
    cleaned = re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")
    return cleaned[:48] or "session"


def session_id(label: str, when: Optional[float] = None) -> str:
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(when if when is not None else time.time()))
    return "%s-%s" % (stamp, slug(label))


def build_session(runs: Sequence[Dict[str, Any]], *, label: str = "session",
                  env: Optional[Dict[str, Any]] = None, warmups: int = 0,
                  map_info: Optional[Dict[str, Any]] = None,
                  notes: Sequence[str] = (), powermetrics: Optional[Dict[str, Any]] = None,
                  hitch_ms: float = DEFAULT_HITCH_MS,
                  when: Optional[float] = None) -> Dict[str, Any]:
    """Assemble the stored record. `env` is a probe.snapshot(); the env_id and the
    buildid are lifted out of it because those two are the comparison key."""
    env = env or {}
    stable = env.get("stable", {}) if isinstance(env, dict) else {}
    now = when if when is not None else time.time()
    session = {
        "schema": SCHEMA,
        "id": session_id(label, now),
        "label": label,
        "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "env_id": env.get("env_id") or "unknown",
        "buildid": stable.get("cs2_buildid"),
        "map": dict(map_info or MAP_PRIMARY),
        "hitch_ms": _round(hitch_ms),
        "warmup_runs": int(warmups),
        "runs": [dict(r) for r in runs],
        "aggregate": aggregate(runs),
        "powermetrics": powermetrics or powermetrics_status(),
        "notes": list(notes),
        "env": env,
        "protocol_ok": int(warmups) >= WARMUP_RUNS and len(runs) == MEASURED_RUNS,
    }
    return session


def save_session(session: Dict[str, Any]) -> Path:
    """Write a session, never over another one.

    Session ids are second-resolution timestamps, so importing two logs in the same
    second would otherwise silently overwrite the first - and a benchmark history
    that quietly loses entries is worse than no history."""
    directory = session_dir(session.get("env_id") or "unknown")
    base = session["id"]
    ident, suffix = base, 1
    while (directory / ("%s.json" % ident)).exists():
        suffix += 1
        ident = "%s-%d" % (base, suffix)
    session["id"] = ident
    return write_json(directory / ("%s.json" % ident), session)


def load_sessions(env_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Every stored session, oldest first. A session that will not parse is skipped
    rather than fatal: one corrupt file must not hide the rest of the history."""
    root = bench_dir()
    dirs = [session_dir(env_id)] if env_id else sorted(p for p in root.iterdir() if p.is_dir())
    out: List[Dict[str, Any]] = []
    for directory in dirs:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json")):
            data = read_json(path)
            if isinstance(data, dict) and data.get("id"):
                data.setdefault("path", str(path))
                out.append(data)
    out.sort(key=lambda s: (str(s.get("created") or ""), str(s.get("id"))))
    return out


def latest_session(env_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    sessions = load_sessions(env_id)
    return sessions[-1] if sessions else None


def find_session(ident: str, env_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Look a session up by full id or by unique prefix (ids start with a timestamp,
    so a prefix is how a human refers to 'the one from Tuesday')."""
    sessions = load_sessions(env_id)
    exact = [s for s in sessions if s.get("id") == ident]
    if exact:
        return exact[-1]
    prefixed = [s for s in sessions if str(s.get("id", "")).startswith(ident)]
    return prefixed[-1] if prefixed else None


def baseline_for(env_id: str, buildid: Optional[str] = None,
                 exclude_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """The most recent stored session that a new run may legitimately be compared
    against: same env_id, and same buildid when one is known. Comparing across a
    CS2 update or a stack change is exactly the mistake docs/07 forbids, so those
    sessions are not offered as a baseline at all."""
    candidates = [s for s in load_sessions(env_id) if s.get("id") != exclude_id]
    if buildid:
        candidates = [s for s in candidates if str(s.get("buildid") or "") == str(buildid)]
    return candidates[-1] if candidates else None


# --- environment -------------------------------------------------------------
def powermetrics_status() -> Dict[str, Any]:
    """docs/07 step 5 wants powermetrics logged in parallel. CS2Kit refuses to ask
    for sudo, so it records availability and tells the user the command; a missing
    or unprivileged powermetrics is a WARN note on the session, never a failure."""
    path = which("powermetrics")
    return {
        "available": bool(path),
        "path": path,
        "sampled": False,
        "note": ("run it yourself in parallel: sudo powermetrics --samplers cpu_power,gpu_power "
                 "-i 1000 | tee powermetrics.log" if path else
                 "powermetrics not found; CPU/GPU power will be missing from this session"),
    }


def _snapshot() -> Dict[str, Any]:
    """probe.snapshot() shells out to system_profiler and friends; a machine where
    one of those is missing must still be able to record a benchmark."""
    try:
        return probe.snapshot()
    except Exception as exc:  # pragma: no cover - defensive, probe swallows its own
        return {"stable": {}, "volatile": {"error": str(exc)}, "env_id": "unknown"}


def game_present() -> bool:
    try:
        return probe.cs2_exe() is not None
    except Exception:  # pragma: no cover - defensive
        return False


# --- rendering ---------------------------------------------------------------
def _emit(obj: Dict[str, Any]) -> None:
    print(json.dumps(obj, indent=2, sort_keys=True, default=str))


def format_aggregate(agg: Dict[str, Any]) -> str:
    return ("  avg FPS (median)      {avg_fps}\n"
            "  1 % low  (median)     {low}\n"
            "  p99 frametime         {p99} ms\n"
            "  hitch count (median)  {hitch}\n"
            "  runs                  {runs} (spread {spread} % of median avg FPS)"
            ).format(avg_fps=agg.get("avg_fps"), low=agg.get("low_1_pct_fps"),
                     p99=agg.get("p99_frametime_ms"), hitch=agg.get("hitch_count"),
                     runs=agg.get("run_count"), spread=agg.get("spread_pct"))


def format_session(session: Dict[str, Any]) -> str:
    head = ("session {id}\n  label       {label}\n  created     {created}\n"
            "  env_id      {env_id}\n  buildid     {buildid}\n  map         {map_name} ({map_id})\n"
            ).format(id=session.get("id"), label=session.get("label"),
                     created=session.get("created"), env_id=session.get("env_id"),
                     buildid=session.get("buildid"),
                     map_name=(session.get("map") or {}).get("name"),
                     map_id=(session.get("map") or {}).get("workshop_id"))
    body = format_aggregate(session.get("aggregate") or {})
    runs = "\n".join("    run %d  %s avg / %s low / %s ms p99 / %s hitches%s"
                     % (i, r.get("avg_fps"), r.get("low_1_pct_fps"), r.get("p99_frametime_ms"),
                        r.get("hitch_count"), "  <- %s" % r["source"] if r.get("source") else "")
                     for i, r in enumerate(session.get("runs") or [], 1))
    notes = "".join("\n  note: %s" % n for n in session.get("notes") or [])
    return head + body + "\n" + runs + notes


def format_comparison(result: Dict[str, Any]) -> str:
    lines = ["verdict: %s (tolerance +-%s %%)" % (result["verdict"], result["tolerance_pct"])]
    for metric, info in result["metrics"].items():
        delta = "n/a" if info["delta_pct"] is None else "%+.2f %%" % info["delta_pct"]
        lines.append("  %-18s %10s vs %-10s %10s  %s"
                     % (metric, info["new"], info["baseline"], delta, info["verdict"]))
    return "\n".join(lines)


# --- commands ----------------------------------------------------------------
def _collect_runs(paths: Sequence[str], hitch_ms: float) -> Tuple[List[Dict[str, Any]], List[str]]:
    runs, problems = [], []
    for raw in paths:
        try:
            runs.append(load_run(Path(raw), hitch_ms=hitch_ms))
        except BenchError as exc:
            problems.append("%s: %s" % (raw, exc))
    return runs, problems


def _protocol_notes(measured: int, warmups: int) -> List[str]:
    notes = []
    if warmups < WARMUP_RUNS:
        notes.append("only %d of %d warm-up runs declared; a cold shader cache invents a "
                     "1 %%-low problem (docs/07 trap 1)" % (warmups, WARMUP_RUNS))
    if measured != MEASURED_RUNS:
        notes.append("%d measured runs, protocol asks for %d; the median is weaker than it looks"
                     % (measured, MEASURED_RUNS))
    return notes


def cmd_run(args: argparse.Namespace) -> int:
    """`cs2kit bench run` - drive one protocol session (T-011) and store it (T-026)."""
    files = list(args.frametimes or [])
    protocol = [s for s in PROTOCOL_STEPS]
    power = powermetrics_status()

    if not args.json:
        print("CS2 benchmark protocol (docs/07-benchmark-protocol.md)")
        for step in protocol:
            print("  " + step)
        print("\nRecord every fixed variable: " + ", ".join(FIXED_VARIABLES) + ".")
        print("powermetrics: %s\n" % power["note"])

    present = game_present()
    if not present and not args.dry_run:
        message = ("CS2 is not installed where CS2Kit can see it (no game/bin/win64/cs2.exe "
                   "under the Steam root). Install it inside the bottle first, or re-run with "
                   "--dry-run to rehearse the protocol.")
        if args.json:
            _emit({"command": "bench run", "ok": False, "reason": "cs2-missing",
                   "detail": message, "protocol": protocol, "powermetrics": power})
        else:
            print(message, file=sys.stderr)
        return EXIT_NOT_READY

    if not files:
        message = ("Run the protocol, then pass one frametime log per measured run: "
                   "cs2kit bench run --frametimes run1.csv ... (%d files)." % MEASURED_RUNS)
        if args.dry_run:
            if args.json:
                _emit({"command": "bench run", "ok": True, "dry_run": True, "stored": False,
                       "game_present": present, "protocol": protocol, "powermetrics": power,
                       "fixed_variables": list(FIXED_VARIABLES), "next": message})
            else:
                print(message)
            return EXIT_OK
        if args.json:
            _emit({"command": "bench run", "ok": False, "reason": "no-frametimes",
                   "detail": message, "protocol": protocol})
        else:
            print(message, file=sys.stderr)
        return EXIT_USAGE

    runs, problems = _collect_runs(files, args.hitch_ms)
    if not runs:
        detail = "; ".join(problems) or "no runs parsed"
        if args.json:
            _emit({"command": "bench run", "ok": False, "reason": "unreadable", "detail": detail})
        else:
            print(detail, file=sys.stderr)
        return EXIT_USAGE

    notes = list(problems) + _protocol_notes(len(runs), args.warmups)
    if not power["available"]:
        notes.append("powermetrics unavailable: " + power["note"])
    session = build_session(runs, label=args.label, env=_snapshot(), warmups=args.warmups,
                            map_info=MAP_SECONDARY if args.map == "dust2" else MAP_PRIMARY,
                            notes=notes, powermetrics=power, hitch_ms=args.hitch_ms)
    if args.dry_run:
        path = None
    else:
        path = save_session(session)
    if args.json:
        _emit({"command": "bench run", "ok": True, "stored": path is not None,
               "path": str(path) if path else None, "session": session})
    else:
        print(format_session(session))
        print("\nstored: %s" % (path if path else "(dry run, nothing written)"))
    return EXIT_OK


def cmd_import(args: argparse.Namespace) -> int:
    """`cs2kit bench import` - turn logs you already have into a stored session."""
    runs, problems = _collect_runs(args.files, args.hitch_ms)
    if not runs:
        detail = "; ".join(problems) or "no files given"
        if args.json:
            _emit({"command": "bench import", "ok": False, "reason": "unreadable", "detail": detail})
        else:
            print(detail, file=sys.stderr)
        return EXIT_USAGE
    notes = list(problems) + _protocol_notes(len(runs), args.warmups)
    session = build_session(runs, label=args.label, env=_snapshot(), warmups=args.warmups,
                            map_info=MAP_SECONDARY if args.map == "dust2" else MAP_PRIMARY,
                            notes=notes, hitch_ms=args.hitch_ms)
    path = save_session(session)
    if args.json:
        _emit({"command": "bench import", "ok": True, "stored": True, "path": str(path),
               "session": session})
    else:
        print(format_session(session))
        print("\nstored: %s" % path)
    return EXIT_OK


def cmd_list(args: argparse.Namespace) -> int:
    sessions = load_sessions(args.env_id)
    rows = [{"id": s.get("id"), "created": s.get("created"), "label": s.get("label"),
             "env_id": s.get("env_id"), "buildid": s.get("buildid"),
             "avg_fps": (s.get("aggregate") or {}).get("avg_fps"),
             "low_1_pct_fps": (s.get("aggregate") or {}).get("low_1_pct_fps"),
             "run_count": (s.get("aggregate") or {}).get("run_count")} for s in sessions]
    if args.json:
        _emit({"command": "bench list", "count": len(rows), "sessions": rows})
        return EXIT_OK
    if not rows:
        print("no stored benchmark sessions (run: cs2kit bench run --help)")
        return EXIT_OK
    print("%-28s %-16s %-10s %8s %8s  %s" % ("id", "env_id", "buildid", "avg", "1% low", "label"))
    for row in rows:
        print("%-28s %-16s %-10s %8s %8s  %s"
              % (row["id"], row["env_id"], row["buildid"], row["avg_fps"],
                 row["low_1_pct_fps"], row["label"]))
    return EXIT_OK


def cmd_show(args: argparse.Namespace) -> int:
    session = find_session(args.id, args.env_id) if args.id else latest_session(args.env_id)
    if not session:
        detail = "no such session: %s" % args.id if args.id else "no stored benchmark sessions"
        if args.json:
            _emit({"command": "bench show", "ok": False, "detail": detail})
        else:
            print(detail, file=sys.stderr)
        return EXIT_NOT_READY
    if args.json:
        _emit({"command": "bench show", "ok": True, "session": session})
    else:
        print(format_session(session))
    return EXIT_OK


def cmd_compare(args: argparse.Namespace) -> int:
    """`cs2kit bench compare` - the T-026 acceptance test, as an exit code."""
    new = find_session(args.id, args.env_id) if args.id else latest_session(args.env_id)
    if not new:
        detail = "nothing to compare: %s" % (args.id or "no stored sessions")
        if args.json:
            _emit({"command": "bench compare", "ok": False, "detail": detail})
        else:
            print(detail, file=sys.stderr)
        return EXIT_NOT_READY
    if args.against:
        baseline = find_session(args.against, args.env_id)
    else:
        baseline = baseline_for(new.get("env_id") or "unknown", new.get("buildid"),
                                exclude_id=new.get("id"))
    if not baseline:
        detail = ("no comparable baseline: a baseline must share env_id %s and buildid %s "
                  "(record one with cs2kit bench run)"
                  % (new.get("env_id"), new.get("buildid")))
        if args.json:
            _emit({"command": "bench compare", "ok": False, "detail": detail,
                   "session": new.get("id")})
        else:
            print(detail, file=sys.stderr)
        return EXIT_NOT_READY

    result = compare(new.get("aggregate") or {}, baseline.get("aggregate") or {},
                     tol_pct=args.tolerance)
    result["session"] = new.get("id")
    result["baseline"] = baseline.get("id")
    cross_build = str(new.get("buildid") or "") != str(baseline.get("buildid") or "")
    if cross_build:
        result["warning"] = ("comparing across CS2 buildids (%s vs %s): the delta may be the "
                             "update, not the stack" % (new.get("buildid"), baseline.get("buildid")))
    code = EXIT_REGRESSION if result["verdict"] == "REGRESSION" else EXIT_OK
    if args.json:
        result["command"] = "bench compare"
        result["ok"] = code == EXIT_OK
        _emit(result)
    else:
        print("session  %s\nbaseline %s" % (result["session"], result["baseline"]))
        if cross_build:
            print("warning: %s" % result["warning"])
        print(format_comparison(result))
    return code


def cmd_bench(args: argparse.Namespace) -> int:
    """Bare `cs2kit bench`: say what the subcommands are, do nothing destructive."""
    print("cs2kit bench {run|import|list|show|compare} - see --help", file=sys.stderr)
    return EXIT_USAGE


# --- CLI wiring --------------------------------------------------------------
def register(subparsers) -> None:
    """Plug `bench` into the CS2Kit CLI (T-026)."""
    parser = subparsers.add_parser(
        "bench", help="run, store and compare CS2 benchmarks (T-011 / T-026)",
        description=("Automates the docs/07 benchmark protocol: %d warm-up runs, %d measured "
                     "runs on the %s (workshop %s), reported as median avg FPS, median 1 %% low, "
                     "p99 frametime and hitch count, keyed by environment and CS2 buildid."
                     % (WARMUP_RUNS, MEASURED_RUNS, MAP_PRIMARY["name"], MAP_PRIMARY["workshop_id"])))
    parser.set_defaults(func=cmd_bench)
    sub = parser.add_subparsers(dest="bench_cmd", metavar="{run,import,list,show,compare}")

    def _common(p, with_env: bool = True) -> None:
        p.add_argument("--json", action="store_true", help="print one JSON object to stdout")
        if with_env:
            p.add_argument("--env-id", dest="env_id", default=None,
                           help="restrict to one environment id (default: all)")

    run_p = sub.add_parser("run", help="drive a benchmark session and store the result",
                           description="Prints the protocol, then records the runs you measured.")
    run_p.add_argument("--frametimes", action="append", metavar="FILE",
                       help="one frametime log per measured run (repeatable)")
    run_p.add_argument("--warmups", type=int, default=WARMUP_RUNS,
                       help="warm-up runs completed and discarded (default %d)" % WARMUP_RUNS)
    run_p.add_argument("--label", default="run", help="short label for the session")
    run_p.add_argument("--map", choices=("ancient", "dust2"), default="ancient",
                       help="which benchmark map was used (never compare across maps)")
    run_p.add_argument("--hitch-ms", dest="hitch_ms", type=float, default=DEFAULT_HITCH_MS,
                       help="hitch floor in ms (%.0f reproduces docs/07's 'frames > 50 ms')"
                            % PROTOCOL_HITCH_MS)
    run_p.add_argument("--dry-run", action="store_true",
                       help="rehearse without a game present and without storing")
    _common(run_p, with_env=False)
    run_p.set_defaults(func=cmd_run)

    imp = sub.add_parser("import", help="build a session from frametime logs you already have")
    imp.add_argument("files", nargs="+", metavar="FILE")
    imp.add_argument("--label", default="import", help="short label for the session")
    imp.add_argument("--warmups", type=int, default=WARMUP_RUNS,
                     help="warm-up runs completed before these logs")
    imp.add_argument("--map", choices=("ancient", "dust2"), default="ancient")
    imp.add_argument("--hitch-ms", dest="hitch_ms", type=float, default=DEFAULT_HITCH_MS)
    _common(imp, with_env=False)
    imp.set_defaults(func=cmd_import)

    lst = sub.add_parser("list", help="list stored benchmark sessions")
    _common(lst)
    lst.set_defaults(func=cmd_list)

    show = sub.add_parser("show", help="show one session (default: the latest)")
    show.add_argument("id", nargs="?", default=None, help="session id or unique prefix")
    _common(show)
    show.set_defaults(func=cmd_show)

    cmp_p = sub.add_parser("compare", help="compare a session against its baseline (T-026)",
                           description="Exits %d when a headline metric moves outside the "
                                       "tolerance." % EXIT_REGRESSION)
    cmp_p.add_argument("id", nargs="?", default=None, help="session id (default: the latest)")
    cmp_p.add_argument("--against", default=None, help="baseline session id")
    cmp_p.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE_PCT,
                       help="percent tolerance (default %.1f, the T-026 acceptance)"
                            % DEFAULT_TOLERANCE_PCT)
    _common(cmp_p)
    cmp_p.set_defaults(func=cmd_compare)
