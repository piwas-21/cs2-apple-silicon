# Contributing to CS2Kit

CS2Kit configures, diagnoses and measures a Counter-Strike 2 Wine bottle on Apple Silicon. It **never patches the
game, never wraps Steam authentication, never implements graphics and never touches VAC**
([docs/03-development-plan.md](docs/03-development-plan.md), Phase 4 scope rule). Every rule below exists because
breaking it would either endanger a user's Steam account or quietly destroy the project's one real asset: that its
numbers and procedures can be reproduced.

Work is tracked as tasks `T-001` .. `T-034` in [docs/03-development-plan.md](docs/03-development-plan.md). A change
that does not serve a task probably belongs in an issue first.

---

## Running the tests

```bash
uv run pytest                       # the whole suite
uv run pytest tests/test_docs.py    # the docs link invariant on its own
uv run pytest -k doctor -x          # one area, stop at the first failure
```

Tests must be **offline, deterministic and hermetic**. Two fixtures in [tests/conftest.py](tests/conftest.py) exist
so that no test ever touches your real machine:

* `sandbox` - redirects `CS2KIT_HOME`, `CS2KIT_STEAM`, `CS2KIT_REPO` and `WINEPREFIX` into a `tmp_path`, and disables
  colour. **Use it in every test that resolves a path.**
* `cs2_tree` - builds a realistic installed-CS2 tree inside the sandbox (`buildid 24828357`, a `game/bin/win64`
  binary set, an `appmanifest_730.acf`).

Never call `wine`, `brew`, `system_profiler` or the network from a test. Probe functions take injectable paths and
`cs2kit.util.run()` returns a `Proc` rather than raising, precisely so that a fake is a one-line monkeypatch.

## Rule 1 - standard library only

`cs2kit/*` imports **nothing that is not in the Python 3.9 standard library**. No PyYAML, no `requests`, no `rich`.

The reason is concrete: a new user's first command must work on a stock Mac with nothing installed.
[bin/cs2kit](bin/cs2kit) runs the package straight out of a checkout with `/usr/bin/python3` - no pip, no venv, no
sudo. Someone whose bottle is broken must not have to fix a Python environment first.

Prove it before you open a PR - CI runs exactly this on Linux and macOS:

```bash
PYTHONPATH="$PWD" /usr/bin/python3 -c "import cs2kit.cli"
PYTHONPATH="$PWD" /usr/bin/python3 -m cs2kit doctor
```

The floor is **Python 3.9** because that is what macOS ships. No `match`, no `X | Y` type unions at runtime, no
`dict | dict`; use `typing.Optional` / `typing.Dict` and keep `from __future__ import annotations` at the top of
every module.

Where a dependency would have been convenient, the project already has a small stdlib answer:
[cs2kit/yamlite.py](cs2kit/yamlite.py) parses the YAML subset the recipe needs, and
[cs2kit/probe.py](cs2kit/probe.py) parses Valve's KeyValues/ACF format. Extend those rather than adding a package.

Test-time dependencies are different: `pytest` lives in the `dev` dependency group in
[pyproject.toml](pyproject.toml) and never leaks into `cs2kit/`.

## Rule 2 - never modify game files

Valve's VAC FAQ names *"modifications to a game's core executable files and dynamic link libraries"* as cheating
([docs/06-legal-and-policy.md](docs/06-legal-and-policy.md)). This is the single action that would convert a low ban
risk into a real one, so it is enforced mechanically by the T-021 hash guard in
[cs2kit/integrity.py](cs2kit/integrity.py): CS2Kit records a SHA-256 baseline of `game/bin/win64/` after Steam's own
verify pass and refuses to launch when a guarded file differs.

**The legitimate configuration surface is exactly this, and nothing else:**

| Allowed | Not allowed |
|---|---|
| Bottle settings (Windows version, per-exe compat mode) | Writing, patching or replacing anything under `game/bin/win64/` |
| **Wine's own** DLL overrides | Injecting or hooking a DLL into `cs2.exe` |
| Environment variables (`WINEMSYNC`, `DXMT_*`, ...) | Automating, wrapping or storing Steam credentials |
| CS2 launch options | Reading or writing CS2's process memory |
| `autoexec.cfg` / console cvars, `CS2Video.txt` | Interfering with, disabling, spoofing or studying VAC |
| Reading `appmanifest_730.acf` and file hashes | Macros, input automation, overlays beyond Steam's own |

A pull request that adds a capability in the right-hand column will be rejected on principle, regardless of how well
it is written. If you are unsure which column your change is in, it is in the right-hand one - ask first.

## Rule 3 - never invent a number

Every factual claim in `docs/` must trace to a file in `docs/` or `research/` and carry a **CONFIRMED** (vendor or
primary source), **LIKELY** (community) or **UNKNOWN** (not verified) tag. Benchmarks follow
[docs/07-benchmark-protocol.md](docs/07-benchmark-protocol.md) - median of 5 measured runs after 3 discarded
warm-ups, reported as median avg **and** median 1 % low. Never a maximum, never a single run.

Unmeasured cells say `not measured` (compatibility matrix) or **UNRECORDED** (the `docs/reference/` templates).
A fabricated checksum or FPS figure is worse than a missing one: it makes an unreproducible result look
reproducible.

## How to add a doctor check

`cs2kit doctor` (T-024) is the highest-value code in the project, because most user reports are environment
problems. A check is a `Check` dataclass from [cs2kit/util.py](cs2kit/util.py):

```python
Check(id, label, status, detail, fix, task)
```

1. **Pick the group.** [cs2kit/doctor.py](cs2kit/doctor.py) runs four groups in triage order - hardware
   (`_hw_checks`), toolchain (`_toolchain_checks`), game (`_game_checks`), environment (`_environment_checks`).
   Put the check where a human would look for it, and keep the order: eligible machine, then toolchain, then bottle,
   then game, then a quiet environment to measure in.
2. **Read from the snapshot, not from the system.** The group functions receive `probe.snapshot()` and read
   `snap["stable"]` (identity - what a benchmark is comparable within) or `snap["volatile"]` (free disk, power state,
   time). If your check needs a new fact, add it to [cs2kit/probe.py](cs2kit/probe.py) in the correct half. Putting a
   volatile fact in `stable` changes `env_id` and silently invalidates every stored benchmark.
3. **Choose the status honestly.** `FAIL` = CS2 will not work until this is fixed. `WARN` = it works but a measurement
   or a match will suffer. `SKIP` = not applicable here (hidden unless `--verbose`). `PASS` otherwise. `FAIL` sets
   exit code 1; with `--strict`, `WARN` does too.
4. **Write one actionable `fix` line.** A command the user can paste, not a diagnosis they must interpret. Never a
   paragraph. Compare `softwareupdate --install-rosetta --agree-to-license` with "Rosetta is missing".
5. **Name the task.** `task="T-019"` tells the user which document explains the check.
6. **Test it against the sandbox** with a passing case and a failing case, and assert on the `Check.status` and
   `Check.id` rather than on printed text - `--json` output is a contract, formatting is not.
7. **Document it** in [docs/cs2kit-spec.md](docs/cs2kit-spec.md) and, if it corresponds to a known failure mode,
   in [docs/10-troubleshooting.md](docs/10-troubleshooting.md).

A check that cannot state its remediation in one line is usually two checks.

## Adding a command

Command modules are plugins. Each exposes exactly:

```python
def register(subparsers) -> None:
    p = subparsers.add_parser("name", help="...", description="...")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.set_defaults(func=cmd_name)      # func(args) -> int exit code
```

`func` returns an exit code from [cs2kit/util.py](cs2kit/util.py) (`EXIT_OK`, `EXIT_FAIL`, `EXIT_USAGE`,
`EXIT_NOT_READY`, `EXIT_INTEGRITY`, `EXIT_REGRESSION`) - it never calls `sys.exit()` and never raises for an
expected condition. **Any command that prints results must support `--json` and print a single JSON object to
stdout**; the exit codes and the JSON shapes are a stable contract documented in
[docs/cs2kit-spec.md](docs/cs2kit-spec.md). Update that document in the same PR.

## Style

* `from __future__ import annotations`, dataclasses, type hints.
* Docstrings explain **why**, and name the task: *"T-021 - enforce 'never modify game files'."* The what is readable
  from the code; the why is not.
* Plain prose. No emoji beyond the existing table conventions, no marketing, no exclamation marks.
* Tables over paragraphs when the content is a matrix.
* Machine-readable output goes to stdout; human progress and warnings go to stderr.

## Before you open a pull request

```bash
uv run pytest
PYTHONPATH="$PWD" /usr/bin/python3 -c "import cs2kit.cli"
bash -n scripts/*.sh
```

Then fill in [.github/PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md) - it asks for the task number, the
evidence and the risk. CI runs the same four checks on Linux and macOS with Python 3.9 and 3.13.

## Licence

CS2Kit is **GPL-3.0-or-later** ([LICENSE](LICENSE)). By contributing you agree your contribution is licensed under
it. We link against LGPL-2.1 components (Wine, DXMT, MSync) and keep them unmodified and dynamically linked; we
**never** redistribute Apple's D3DMetal ([docs/06-legal-and-policy.md](docs/06-legal-and-policy.md)).
