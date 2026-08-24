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


---

## Session update — 2026-08-24, end of day

**T-004 corrected, T-006 / T-008 / T-021 DONE on the machine of record.**

| Task | Status | Evidence |
|---|---|---|
| T-004 toolchain | **DONE** | FOSS CrossOver 24.0.7 Wine + DXMT v0.80, both checksummed in `reference/toolchain.md`. Gcenx's Wine was tried first and **cannot run DXMT** (`Failed to create metal view`) |
| T-006 bottle | **DONE** | built by `cs2kit bottle create --dxmt`, zero drift, DXMT placed in the Wine tree, Wine originals backed up |
| T-008 CS2 install | **DONE** | `cs2.exe` 2,967,704 bytes, 123 files in `game/bin/win64`, `StateFlags 4`, 71.6 GB — installed head-lessly with `steamcmd`, so the broken Steam UI never blocked it |
| T-021 integrity | **DONE** | 137 guarded binaries baselined after steamcmd's `validate` |
| T-009 first launch | **BLOCKED** | the Steam client must be logged in once, and its window has not been seen to render |

**The blocker, stated precisely:** CS2 launches, DXMT initialises at feature level 11_1, and the game then waits for
a logged-in Steam client. Logging in needs the client's Chromium UI once. On Gcenx Wine that window drew black —
now explained by the missing Metal view. On the CrossOver engine **no window was observed at all**, but every
observation was made from an agent-spawned process, which may not hold a proper Aqua GUI session. **The one
observation that has never been made is a human looking at the Steam client running on the CrossOver engine.**
That is the next measurement, and it is cheap.

A Sikarugir wrapper has been assembled at `~/Applications/Sikarugir/CS2.app` (Template 1.0.11 + the CX 24.0.7
engine, prefix created) precisely so that launch happens in the user's own GUI session rather than the agent's.


---

## 2026-08-24, evening — **T-007 and T-009 achieved: CS2 runs and renders.**

The Windows Steam client logs in, and **Counter-Strike 2 launches and draws through DXMT on Apple Silicon**:
the video-settings screen with its live 3D previews rendered at 3024×1964, mean luminance 98/255, 99.8 % non-black.
DXMT logged `Using feature level D3D_FEATURE_LEVEL_11_1` with **zero** "Failed to create metal view" errors, and the
loaded `d3d11.dll` hashes to DXMT v0.80's release binary (`7ca382af…`), not Wine's own (`e333b8c6…`).

### The engine matrix — three builds, only one works

| Engine | Steam UI | client↔helper transport | DXMT Metal view | Verdict |
|---|---|---|---|---|
| Gcenx Wine 11.15 (staging/devel) | **black** (0.0/255) | OK | **fails** | unusable |
| FOSS CrossOver 24.0.7 (Wine 9.0 base) | renders | **rejected — 0x3008** | works | unusable |
| **Sikarugir Wine 10.0** | **renders** | **OK** | **works** | **the Wine of record** |

### Reusing the existing install — no second download

`steamcmd` had installed CS2 into the macOS Steam library with its own nested manifest, which the in-bottle client
could not see: it offered a fresh 66.85 GB download instead. Two file-level steps fixed it, with no re-download:

1. Promote steamcmd's manifest to the library root (`appmanifest_730.acf`, `InstalledDepots` 2347770 / 2347771 /
   2347774) — the macOS-era manifest it replaced is kept at `~/CS2/appmanifest_730.macos-era.acf.bak`.
2. Point the bottle's own library at it: `drive_c/Program Files (x86)/Steam/steamapps` → symlink →
   `~/Library/Application Support/Steam/steamapps`. Adding it as a *library folder* does **not** survive — Steam
   rewrites `libraryfolders.vdf` on every start; the symlink does.

`cs2kit launch` then reported `[PASS] 137 guarded files match the baseline` and started the game.


---

## T-010, first pass on Dust2 — 2026-08-24 evening (partial: 1 of 6 passes)

Ten minutes of continuous bot play on `de_dust2`, sampled every 30 s by `~/CS2/t010_monitor.py`.

| metric | result |
|---|---|
| crashes | **0** |
| frozen frames (identical downsampled pixels between samples) | **0 / 22 samples** |
| luminance range | 32 – 144 / 255 (scene advancing throughout) |
| resident memory | 700 – 1393 MB (well under the 6.1 GB the plan expects) |
| audio | **not assessed** — no automated signal; T-016 needs ears |

**"It looked stuck" was the match ending, not a hang.** After the round limit the server returned to the
team-selection screen with `0 Spelers - 0 Bots`, which looks frozen but is not: two captures six seconds apart
differ, so the frame is still advancing. Two procedure fixes for the next run:

1. Bots do not survive the match end. Set `mp_match_end_restart 1` (or a long `mp_maxrounds`) and re-assert
   `bot_quota` per round, otherwise a "30 minute" soak silently becomes a ten-minute one.
2. Launch args do not auto-join a team — send `jointeam 2` (or `mp_humanteam`) after the map loads, or the run
   measures a spectator camera rather than gameplay.

**Also learned:** `Steam.exe -applaunch 730` refuses to relaunch while the client still believes the previous
session is running, which is exactly the state after a hard kill between maps. Launching `game/bin/win64/cs2.exe`
directly, with the client logged in and running, is the reliable way to drive repeated runs.

**Remaining for the gate:** the second Dust2 pass, then Mirage and Ancient twice each, plus a human ear on audio.
