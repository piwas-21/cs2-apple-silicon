# Implementation status — every task in the plan, and what exists for it

`docs/03-development-plan.md` has 34 tasks. Roughly half are **software** (they can be finished on any machine and
are finished here), and half are **procedures on real hardware** (they require a Steam login, a 5 GB download, hours
of play, a 240 fps camera or three separate days of competitive matches). Software tasks are **SHIPPED**. Hardware
tasks are **TOOLED**: the command, the recipe or the template that executes them exists, is tested, and produces the
artefact the task's acceptance test asks for — the only missing input is the machine time.

Nothing in this table is marked done because it was attempted. **TOOLED means the code exists; it does not mean the
number exists.** No FPS figure, no latency figure and no VAC verdict is recorded anywhere in this repo, because none
has been measured.

| Task | Status | Artefact |
|---|---|---|
| T-001 free the disk, keep the assets | **TOOLED** | `scripts/preflight.sh`, `cs2kit doctor` (disk, depot 2347770/2347771, the macOS-Steam trap), `docs/reference/appmanifest_730.acf.before` |
| T-002 licence and rules | **SHIPPED** | `LICENSE` (GPL-3.0, verbatim), `docs/06-legal-and-policy.md` §Distribution model — one box ticked, no open question |
| T-004 install the free stack | **TOOLED** | `docs/reference/toolchain.md` (URL + SHA-256 template), `cs2kit doctor` wine/DXMT checks |
| T-005 freeze the environment | **SHIPPED** | `cs2kit env --save`, `docs/reference/env-snapshot-0.json` (regenerates identically: `env_id 9dfc995799409cc9`) |
| T-006 create the bottle | **SHIPPED** | `profiles/bottle-recipe.yaml`, `cs2kit bottle create` |
| T-007 Windows Steam in the bottle | **TOOLED** | `docs/reference/steam-in-bottle.md`, `cs2kit launch` (finds and runs the in-bottle client) |
| T-008 install CS2, close the depot gap | **TOOLED** | `docs/09-install-guide.md` step 6, `cs2kit doctor` depot checks |
| T-009 first launch + the four fixes | **SHIPPED** as configuration | recipe pins `cs2.exe` to Windows 8; `cs2kit config apply --video` writes `CS2Video.txt`; HiDPI check; `-vulkan` refused |
| T-010 `[GATE]` offline playable | **HUMAN** | `docs/09-install-guide.md` step 10 (three maps, twice each, 30 min) |
| T-011 benchmark protocol + baseline | **SHIPPED** as tooling | `cs2kit bench run/import`, `docs/07-benchmark-protocol.md` |
| T-012 confirm DXMT | **TOOLED** | `cs2kit bench compare` across configurations; hitch count is a first-class metric |
| T-013 shader stutter | **TOOLED** | hitch count + `bench compare` cold vs warm |
| T-014 resolution and upscaling | **TOOLED** | one profile per resolution; `bench compare` |
| T-015 input latency | **HUMAN** | `docs/07-benchmark-protocol.md`; needs a 240 fps camera and 20 trials |
| T-016 audio and microphone | **HUMAN** | `docs/10-troubleshooting.md` audio entries; needs a real teammate |
| T-017 thermals, 2-hour soak | **TOOLED** | `bench run --label soak`, `powermetrics` availability recorded |
| T-018 account safety | **SHIPPED** as policy | `docs/11-validation-log.md` checklist |
| T-019 casual + community servers | **HUMAN** | `docs/11-validation-log.md` networking checklist |
| T-020 `[GATE]` VAC-protected competitive | **HUMAN** | `docs/11-validation-log.md` match log + GO/CONDITIONAL/NO-GO block. **Unresolved: this is the project's actual success criterion.** |
| T-021 never modify game files | **SHIPPED** | `cs2kit verify baseline/check`, `cs2kit launch` refuses on mismatch (exit 4) |
| T-022 competitive sign-off | **TOOLED** | `docs/11-validation-log.md` sign-off template, every slot named to the task that fills it |
| T-023 specify v0.1 | **SHIPPED** | `docs/cs2kit-spec.md` |
| T-024 `cs2kit doctor` | **SHIPPED** | 18 checks, each with one fix line; seeded-fault tests |
| T-025 declarative recipe | **SHIPPED** | `cs2kit bottle create/diff/repair`; drift is a doctor check |
| T-026 `cs2kit bench` | **SHIPPED** | ±5 % tolerance, keyed by `env_id` + `buildid` |
| T-027 three profiles | **SHIPPED** | `profiles/{competitive-lowest-latency,balanced-1080p,thermal-limited}.yaml`, provenance enforced by the validator |
| T-028 `cs2kit report` | **SHIPPED** | redact → re-scan → refuse to write on any finding; verified on a real bundle |
| T-029 documentation | **SHIPPED** | `docs/09-install-guide.md`, `docs/10-troubleshooting.md`, `docs/compatibility-matrix.md` |
| T-030 update watch + drill | **SHIPPED** | `cs2kit watch check/record/drill`, appends a matrix row |
| T-031 Rosetta-27 exit plan | **SHIPPED** | `docs/rosetta-watch.md` (first dated entry, decommission notice pre-written), doctor grades the horizon |
| T-032 macOS beta testing | **TOOLED** | `docs/12-maintenance.md`, matrix row shape |
| T-033 community intake | **TOOLED** | `cs2kit report` bundles, intake procedure in `docs/12-maintenance.md` |
| T-034 quarterly upstream tracking | **TOOLED** | `docs/12-maintenance.md` review table + the MoltenVK trigger that re-opens T-012 |

## What would change these

* Every **TOOLED** row becomes **DONE** by running the named command on hardware and committing the artefact it
  writes — a checksum, a matrix row, a bench session, a dated log entry.
* **T-010** and **T-020** are the two gates. Until T-020 is filled in, this project claims *nothing* about
  competitive play, and `docs/11-validation-log.md` says so in the same words.
* The one thing no amount of work here can change: **Rosetta 2's macOS 27 horizon** (`docs/rosetta-watch.md`).

## Verifying this repo on your own machine

```bash
uv run pytest            # the whole suite
./bin/cs2kit doctor      # the machine, the bottle, the game
./bin/cs2kit report      # a redacted bundle you can share
```
