# CS2Kit specification (v0.1) - T-023

The exact command-line surface, exit codes, file layout and JSON schemas of `cs2kit`. **This document describes the
code that is in the repository**; where a section and the code disagree, the code is right and this file is a bug.
Every command below was read off `cs2kit <command> --help` in this checkout.

## Scope rule

> **CS2Kit configures and diagnoses. It never patches the game, never wraps Steam authentication, never implements
> graphics, never touches VAC.** ([03-development-plan.md](03-development-plan.md), Phase 4)

That is a boundary, not a slogan, and it is what each half of the tool is allowed to do:

| CS2Kit does | CS2Kit never does |
|---|---|
| Create and repair a Wine prefix from a declarative recipe | Write anything under `game/bin/win64/` |
| Set Wine's own DLL overrides and per-executable compatibility modes | Inject or hook a DLL into `cs2.exe` |
| Write environment scripts, launch options, an `autoexec`-style cfg, `CS2Video.txt` | Read or write CS2's process memory |
| SHA-256 the shipped Windows binaries and refuse to launch on a mismatch | Modify, patch or "fix" a game file |
| Hand off to the **user's own** in-bottle Windows Steam client | Store, type, automate or proxy Steam credentials |
| Record and compare benchmarks; redact and package diagnostics | Interfere with, disable, spoof or study VAC |

Valve's VAC FAQ names *"modifications to a game's core executable files and dynamic link libraries"* as cheating.
That is the single action that would turn this project's low risk into a real one, so `cs2kit verify` (T-021) makes
it mechanically visible and `cs2kit launch` refuses to start the game when it happens
([06-legal-and-policy.md](06-legal-and-policy.md)).

## Standard library only

`cs2kit/*` imports nothing outside the Python 3.9 standard library, and `bin/cs2kit` runs the package from a
checkout with `/usr/bin/python3`:

```bash
PYTHONPATH="$PWD" /usr/bin/python3 -c "import cs2kit.cli"     # enforced in CI
```

The reason is operational, not aesthetic. The user of this tool is someone whose game does not start; requiring them
to fix a Python environment first would put a second broken system between them and a diagnosis. macOS ships Python
3.9, so 3.9 is the floor. Where a dependency would have been convenient the project wrote a small stdlib answer
instead: `cs2kit/yamlite.py` (the YAML subset the recipes use) and `probe.parse_acf()` (Valve's KeyValues format).
`pytest` is a `dev` dependency group and never leaks into `cs2kit/`.

## Invocation

```
cs2kit [--version] <command> [<args>]
```

Commands are plugins: each module exposes `register(subparsers)` and sets `func`, an `argparse.Namespace -> int`
callable. A module that fails to import degrades to a stub command that explains itself, so one broken plugin cannot
take the CLI down - which matters when the CLI is what you are using to diagnose a broken machine.

| Command | Task | Purpose |
|---|---|---|
| [`doctor`](#cs2kit-doctor) | T-024 | Grade the machine, the toolchain, the bottle and the game |
| [`env`](#cs2kit-env) | T-005 | Print or freeze the environment snapshot |
| [`bottle`](#cs2kit-bottle) | T-006 / T-025 | Create, diff and repair the Wine prefix from the recipe |
| [`config`](#cs2kit-config) | T-027 | List, show, apply and diff situational profiles |
| [`verify`](#cs2kit-verify) | T-021 | Record and enforce the game-file hash baseline |
| [`launch`](#cs2kit-launch) | T-021 | Integrity-guarded hand-off to the in-bottle Steam client |
| [`bench`](#cs2kit-bench) | T-011 / T-026 | Run, store and compare benchmarks |
| [`report`](#cs2kit-report) | T-028 | Build a redacted, shareable diagnostic bundle |
| [`watch`](#cs2kit-watch) | T-030 | Detect CS2 `buildid` changes and print the regression drill |

**Every command that prints results supports `--json` and prints a single JSON object to stdout.** The two
exceptions are deliberate: `cs2kit env` always emits JSON (that is its whole output), and `cs2kit verify baseline`
prints a human confirmation of a write it just performed. Human progress text and errors go to stderr where a
command distinguishes them; JSON goes to stdout.

Errors have one shape across the CLI (`util.emit_error`): under `--json` a failure prints
`{"command": "<command>", "ok": false, "detail": "<one line>"}` and returns a non-zero code; without `--json` it
prints `cs2kit: <one line>`. A script should branch on the **exit code** first and read `detail` for the reason.

## Exit codes

Defined once in `cs2kit/util.py` and stable across commands.

| Code | Name | Meaning |
|---|---|---|
| 0 | `EXIT_OK` | Success, or "checked and nothing is wrong". |
| 1 | `EXIT_FAIL` | A check FAILed, or the operation did not achieve its goal. |
| 2 | `EXIT_USAGE` | Bad invocation: no subcommand, unreadable input, refusal to act without consent. |
| 3 | `EXIT_NOT_READY` | A prerequisite is missing - no Wine, no bottle, no CS2, no baseline, no stored session. |
| 4 | `EXIT_INTEGRITY` | **T-021**: guarded game files differ from the validated baseline. |
| 5 | `EXIT_REGRESSION` | A benchmark moved outside tolerance, or the CS2 `buildid` changed (`watch check --exit-on-change`). |

Exit code 3 is distinct from 1 on purpose: "not set up yet" is a normal state on a new machine, while "set up and
wrong" is not. Scripts should treat 3 as "do the previous step", 4 as "stop and re-verify through Steam", and 5 as
"investigate before publishing a number".

## File layout

### State directory - `~/.cs2kit` (override with `CS2KIT_HOME`)

```
~/.cs2kit/
  active-profile.json          the profile cs2kit config apply last wrote, with its hash
  env/<profile>.sh             a sourceable environment script per applied profile
  integrity/<buildid>.json     T-021 SHA-256 baseline of game/bin/win64, keyed by CS2 buildid
  bench/<env_id>/<id>.json     one stored benchmark session per file
  watch.json                   the last recorded CS2 buildid (T-030)
  reports/                     default output of cs2kit report (bundle dir + .tar.gz)
```

### Repository - profiles and documents (override the root with `CS2KIT_REPO`)

```
profiles/
  bottle-recipe.yaml           kind: bottle   - the source of truth for the prefix (T-025)
  balanced-1080p.yaml          kind: profile  - the default situational profile (T-027)
  competitive-lowest-latency.yaml
  thermal-limited.yaml
docs/compatibility-matrix.md   cs2kit watch drill appends a row here
```

### Inside the bottle

```
$WINEPREFIX/.cs2kit/state.json  what cs2kit bottle create installed: recipe name and hash,
                                DXMT release and files, env, launch options, timestamp
```

### Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `CS2KIT_HOME` | `~/.cs2kit` | State directory. |
| `CS2KIT_REPO` | the checkout | Where `profiles/` and `docs/` are found. |
| `CS2KIT_STEAM` | `~/Library/Application Support/Steam` | Steam root that `probe` reads `appmanifest_730.acf` from. |
| `WINEPREFIX` | `~/CS2/prefix` | The bottle. |
| `NO_COLOR` / `CS2KIT_NO_COLOR` | unset | Disable ANSI colour. |

---

# Commands

## `cs2kit doctor`

```
cs2kit doctor [--json] [--strict] [--verbose]
```

Runs every check in triage order - hardware, toolchain, game, environment - and prints one line each, ending in a
single actionable fix. `--strict` treats `WARN` as failure; `--verbose` shows `SKIP` checks.

**Exit:** `1` if any check is `FAIL` (or, with `--strict`, `WARN`); `0` otherwise.

**Checks** (id -> what it enforces):

| id | Checks | Task |
|---|---|---|
| `arch` | `arm64` | T-001 |
| `ram` | >= 16 GB (WARN below) | T-017 |
| `chassis` | fanless machines warn about sustained throttling | T-017 |
| `rosetta` | `oahd` is running | T-004 |
| `rosetta-horizon` | macOS <= 27; WARN on 27, FAIL beyond ([rosetta-watch.md](rosetta-watch.md)) | T-031 |
| `disk` | >= 80 GiB free | T-001 |
| `wine` | installed, major >= 11 | T-004 |
| `bottle` | the prefix exists | T-006 |
| `bottle-recipe` | `profiles/bottle-recipe.yaml` loads | T-025 |
| `bottle-drift` | registry values, DXMT and recipe hash match the recipe | T-025 |
| `dxmt` | `d3d11.dll` / `dxgi.dll` present in the prefix | T-004 |
| `sync` | MSync enabled, and not both MSync and ESync | T-012 |
| `cs2` | `game/bin/win64/cs2.exe` exists (names depot 2347771 when it does not) | T-008 |
| `depot-content` | the reusable 58 GB content depot 2347770 is present | T-001 |
| `buildid` | CS2 `buildid` is readable | T-030 |
| `game-file-integrity` | guarded binaries match the baseline | T-021 |
| `low-power` | Low Power Mode off | T-011 |
| `awdl` | `awdl0` down during play | T-019 |
| `hidpi` | not rendering at Retina backing-store resolution | T-009 |
| `profile` | a profile is applied and still matches its file | T-027 |
| `macos-steam` | warns about a macOS Steam CS2 install that can never produce `cs2.exe` | T-001 |

**`--json`:**

```json
{
  "env": { "stable": {...}, "volatile": {...}, "env_id": "0123456789abcdef" },
  "checks": [
    {"id": "disk", "label": "Free disk", "status": "PASS", "detail": "112 GiB", "fix": "", "task": "T-001"}
  ],
  "summary": {"PASS": 14, "WARN": 3, "FAIL": 0, "SKIP": 0}
}
```

`status` is one of `PASS`, `WARN`, `FAIL`, `SKIP`. `fix` is empty when there is nothing to do.

## `cs2kit env`

```
cs2kit env [--save FILE]
```

Prints `probe.snapshot()` as JSON, or writes it to `FILE` (T-005 commits
`docs/reference/env-snapshot-0.json`). The snapshot has two halves, and the split is what makes benchmarks
comparable:

* **`stable`** - identity: `macos`, `macos_build`, `macos_major`, `chip`, `arch`, `p_cores`, `e_cores`,
  `gpu_cores`, `metal`, `ram_gb`, `resolution`, `wine_version`, `dxmt_version`, `cs2_buildid`, `recipe_name`,
  `recipe_hash`.
* **`volatile`** - conditions: `captured_at`, `free_gib`, `rosetta`, `low_power_mode`, `awdl_up`, `wine_path`,
  `prefix`, `prefix_exists`, `dxmt_installed`, `cs2_exe`, `installed_depots`, `steam_root`.
* **`env_id`** - the first 16 hex characters of the SHA-256 of the `stable` half.

**A benchmark is only ever compared with another benchmark of the same `env_id` and `buildid`.** Adding a volatile
fact to `stable` silently invalidates every stored result, which is why the halves are separate and documented.

**Exit:** always `0`.

## `cs2kit bottle`

```
cs2kit bottle create  [--recipe R] [--prefix P] [--dxmt DIR] [--dry-run] [--json]
cs2kit bottle diff    [--recipe R] [--prefix P] [--dry-run] [--json]
cs2kit bottle repair  [--recipe R] [--prefix P] [--dry-run] [--json]
```

Bare `cs2kit bottle` runs `diff`. The recipe (`profiles/bottle-recipe.yaml`) is the source of truth: `create` runs
`wineboot --init`, applies the recipe's registry values (Windows version, per-executable compatibility modes, DLL
overrides), copies the DXMT DLLs from `--dxmt`, and writes `$WINEPREFIX/.cs2kit/state.json`. `diff` reports registry
drift; `repair` re-applies it. `--dry-run` logs the Wine calls without running them.

**Exit:** `0`; `1` from `diff` when there is drift; `3` when Wine is missing, the recipe is invalid, or the prefix
is not a Wine prefix.

**`--json`:**

```json
// create / repair
{"prefix": "...", "state": {"recipe_name": "cs2-default", "recipe_hash": "...", "dxmt_version": "...",
                            "dxmt_files": [...], "created": "...", "env": {...}, "launch_options": [...]},
 "commands": [["wineboot", "--init"]], "dxmt_copied": ["d3d11.dll"], "dry_run": false}
// diff
{"prefix": "...", "recipe": "cs2-default",
 "drift": {"Wine\\Version": {"expected": "win10", "actual": "win7"}}}
```

## `cs2kit config`

```
cs2kit config list  [--json]
cs2kit config show  [profile] [--json]
cs2kit config apply <profile> [--no-cfg] [--video] [--video-path FILE] [--dry-run] [--json]
cs2kit config diff  [profile] [--json]
```

Bare `cs2kit config` runs `list`. Three profiles ship - `balanced-1080p`, `competitive-lowest-latency`,
`thermal-limited` - and deliberately not one per chip: the variance that matters is
backend x chassis x resolution x macOS build (T-027).

`apply` writes **only** what CS2Kit is entitled to write:

| Written | Where |
|---|---|
| environment script | `~/.cs2kit/env/<profile>.sh` (source it, or use `cs2kit launch`) |
| game cfg | `<install>/game/csgo/cfg/cs2kit.cfg` - suppress with `--no-cfg`; load it with `exec cs2kit` |
| `CS2Video.txt` | only with `--video` - the T-009 black-screen workaround; `--video-path FILE` writes it elsewhere |
| applied record | `~/.cs2kit/active-profile.json` |

Launch options are **printed for you to paste** into Steam's Launch Options box. CS2Kit does not edit Valve's client
configuration.

**Where CS2 reads `CS2Video.txt` from under Wine is UNCONFIRMED.** `--video` writes the install-tree copy and says
so; CS2 may instead read a per-account copy under Steam's `userdata` tree. `--video-path FILE` writes it wherever
you confirm it belongs - and when you do confirm it, record which one worked in
[reference/first-launch.md](reference/first-launch.md), where the path is currently **UNRECORDED**.

**Exit:** `0`; `3` when the profile does not exist or fails validation.

**`--json`** (`apply`): `{"record": {"name", "hash", "source", "applied", "env_script", "cfg", "video_txt",
"launch_options", "env"}, "written": [paths], "dry_run": bool, "cfg_dir": path|null}`.

## `cs2kit verify`

```
cs2kit verify baseline [--root DIR]
cs2kit verify check    [--root DIR] [--json] [--strict]
```

Bare `cs2kit verify` runs `check`. `baseline` SHA-256s every `.exe`, `.dll`, `.sys`, `.so` and `.dylib` under
`game/bin/win64/` and stores the result as `~/.cs2kit/integrity/<buildid>.json`. **Run it once, immediately after
Steam's own *Verify integrity of game files*** - that pass is what makes the baseline authoritative. It refuses to
store an empty baseline.

`check` re-hashes and compares. A `buildid` change is reported as a legitimate game update rather than as tampering;
what is guarded is *unexplained* change.

**Exit:** `0` clean; `3` when CS2 is not installed or no baseline exists; **`4`** on a mismatch; `1` for `WARN`
under `--strict`.

**`--json`** (`check`):

```json
{"status": "PASS", "changed": [], "missing": [], "added": [], "checked": 41,
 "buildid": "24828357", "baseline_buildid": "24828357", "message": "...", "clean": true}
```

## `cs2kit launch`

```
cs2kit launch [--profile P] [--prefix P] [--print-only] [--force] [--timeout S] [--json] [extra ...]
```

Verifies the T-021 guard, applies the profile environment, and runs the **in-bottle Windows Steam client** with
CS2's app id - exactly as the user would by hand. It injects nothing, patches nothing, and never sees a password.
`extra` arguments are passed through as CS2 launch options. `--print-only` prints the environment and the command
and stops.

`--force` launches despite an integrity `FAIL`. It exists so the tool cannot become the thing standing between you
and your own machine; using it after an unexplained change is a bad idea, and the refusal text says so.

**Exit:** `0`; **`4`** on an integrity `FAIL` without `--force`; `3` when the prefix or the in-bottle Steam client
is missing; otherwise Steam's own exit code.

**`--json`:** `{"command": [...], "env": {...}, "integrity": {<verify check object>}}`.

## `cs2kit bench`

```
cs2kit bench run     [--frametimes FILE ...] [--warmups N] [--label L] [--map {ancient,dust2}]
                     [--hitch-ms MS] [--dry-run] [--json]
cs2kit bench import  FILE... [--label L] [--warmups N] [--map {ancient,dust2}] [--hitch-ms MS] [--json]
cs2kit bench list    [--env-id ID] [--json]
cs2kit bench show    [id] [--env-id ID] [--json]
cs2kit bench compare [id] [--against ID] [--tolerance PCT] [--env-id ID] [--json]
```

Automates [07-benchmark-protocol.md](07-benchmark-protocol.md): **3 discarded warm-up runs, 5 measured runs**, on the
**Ancient FPS Benchmark (workshop `3472126051`)** by default, with Dust2 (`3240880604`) as the explicitly
non-comparable secondary. CS2Kit **measures, it does not play**: `bench run` prints the protocol and then consumes
the frametime logs you produced, so nothing here launches the game or needs `sudo`.

Reported metrics, defined precisely because each is commonly reported wrongly:

| Metric | Definition | Better |
|---|---|---|
| `avg_fps` | frames / total elapsed time - **not** the mean of per-frame FPS, which flatters a stuttering run | higher |
| `low_1_pct_fps` | the FPS of the 99th-percentile frametime | higher |
| `p99_frametime_ms` | the same percentile as a time | lower |
| `hitch_count` | frames slower than `max(--hitch-ms, 3 x median frametime)`; pass `--hitch-ms 50` to reproduce docs/07's "frames > 50 ms" exactly | lower |

Only `avg_fps` and `low_1_pct_fps` decide the overall verdict. Sessions are stored under
`~/.cs2kit/bench/<env_id>/<id>.json` and carry `protocol_ok` (3 warm-ups and 5 measured runs) plus `spread_pct`, the
peak-to-peak range of avg FPS - if the spread is wider than the tolerance, the run conditions rather than the stack
are what a later comparison measures.

`compare` is the **T-026 acceptance test as an exit code**: default tolerance **+/-5 %**, inclusive at the boundary.
A baseline must share the same `env_id` **and** `buildid`; comparing across buildids is allowed with `--against` but
carries a warning in the output.

**Exit:** `0`; `2` from bare `cs2kit bench` or unreadable logs; `3` when CS2 is absent (`run` without `--dry-run`) or
no session or baseline exists; **`5`** when `compare` finds a regression.

**`--json`:** every subcommand emits `{"command": "bench <sub>", "ok": bool, ...}`. `compare` adds
`{"verdict": "PASS|REGRESSION|IMPROVED", "metrics": {"avg_fps": {"new", "baseline", "delta_pct",
"higher_is_better", "verdict"}, ...}, "session": id, "baseline": id}`.

## `cs2kit report`

```
cs2kit report [--out DIR] [--yes] [--secret TEXT] [--no-archive] [--json]
```

Collects tool versions, the environment snapshot, bottle state, the recipe and profile names, every doctor result,
the latest benchmark session and the integrity summary; **redacts every personal identifier**; prints exactly what
will be shared; and writes `report.json`, `report.md` and a `.tar.gz` **only after you agree**. `--yes` skips the
prompt; in a non-interactive shell without `--yes` it refuses (exit `2`) rather than writing silently.

Redacted classes (T-028's acceptance is *zero* personal identifiers, so redaction is verified by re-scanning the
redacted bundle and refusing to write while anything is still found):

* local username, in `$USER` and in every `/Users/<name>/` path, and any absolute path under `$HOME`
* SteamID64, Steam account/persona/login names, email addresses
* IPv4 and IPv6 addresses (`127.0.0.1` is kept), MAC addresses
* hardware serial numbers and UUIDs, computer/local/DNS hostnames

`--secret TEXT` adds a literal string to scrub. **The bundle is never uploaded** - sharing is your deliberate act.

**Exit:** `0`; `2` when confirmation is required and absent; `1` if the redaction self-scan still finds an
identifier (a CS2Kit bug - report the *kinds*, never the values).

## `cs2kit watch`

```
cs2kit watch check  [--timeout S] [--offline] [--exit-on-change] [--json]
cs2kit watch record [--buildid N] [--json]
cs2kit watch drill  [--buildid N] [--verdict V] [--matrix FILE] [--no-matrix] [--record] [--json]
```

T-030: notice every CS2 `buildid` change and run the same drill each time, because *whether a CS2 patch has ever
broken a Wine bottle is currently UNKNOWN* and this is how that becomes data.

`check` compares the recorded buildid against Valve's `public` branch using **exactly one optional, unauthenticated
GET** with a hard timeout, no retries and no telemetry. Offline, DNS failure or a changed mirror shape all degrade to
`status: "unknown"` and a warning - never a false "unchanged" (which would suppress the drill) and never a false
"changed" (which would cry wolf nightly). `--exit-on-change` returns `5`, which is what makes it usable from cron or
a LaunchAgent.

`drill` **prints** the eight-step drill (doctor, bottle repair if needed, main menu, `bench run`, `bench compare`,
a one-match smoke test, `watch record`, file the row) and appends one row to
[compatibility-matrix.md](compatibility-matrix.md). It prints rather than executes, because `doctor` and `bench`
have their own exit codes and the smoke test needs a human at the mouse.

The matrix row is a stable contract - eight columns, appended at the end of the file, `?` for any value that is not
known:

```
| date | buildid | macOS | wine | dxmt | avg fps | 1% low | verdict |
```

`--verdict` takes `PASS`, `DEGRADED` or `BROKEN`. `avg fps` and `1% low` come from the latest stored bench session
for that environment, so a drill run before any benchmark honestly reports `?`.

**Exit:** `0`; `5` from `check --exit-on-change` when the buildid changed; `3` from `record` when there is no
buildid to record.

---

## What v0.1 deliberately does not include

| Not included | Why |
|---|---|
| A GUI | A CLI is testable and CI-able; a SwiftUI app is the least valuable part and comes last, if ever (T-023). |
| Downloading or installing CS2 | Valve's client owns the install. CS2Kit points Steam at a library folder; it never fetches depots. |
| Any Steam login handling | Absolute rule 3 ([06-legal-and-policy.md](06-legal-and-policy.md)). |
| Anything that reads or writes the game's memory or binaries | Absolute rule 1; enforced by `verify` and `launch`. |
| Shipping D3DMetal | Never redistributed; a user-installed local fallback only ([06-legal-and-policy.md](06-legal-and-policy.md), section 1). |
| Uploading reports anywhere | `report` writes local files; sharing is the user's act (T-028). |
| Per-chip profiles | Three situational profiles instead; the variance is not the model name on the lid (T-027). |

## Related documents

* [09-install-guide.md](09-install-guide.md) - the ordered procedure these commands automate.
* [10-troubleshooting.md](10-troubleshooting.md) - symptom-keyed, using these commands as the checks.
* [07-benchmark-protocol.md](07-benchmark-protocol.md) - the protocol `bench` implements.
* [06-legal-and-policy.md](06-legal-and-policy.md) - the rules the scope section enforces.
* [11-validation-log.md](11-validation-log.md) - the Phase 3 online and anti-cheat record these commands feed.
* [12-maintenance.md](12-maintenance.md) - the Phase 5 cadence for `watch`, `bench` and `report`.
* [../CONTRIBUTING.md](../CONTRIBUTING.md) - how to add a check or a command without breaking the contracts above.
