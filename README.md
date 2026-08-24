# cs2-apple-silicon

Run **Counter-Strike 2** on an **Apple Silicon MacBook**, using **only free software**, and build `CS2Kit` — a small
CLI that makes the setup reproducible, diagnosable and measurable.

**Status: it runs.** On 2026-08-24 CS2 launched, rendered through DXMT and played a bot match on Dust2 on the
machine of record — on **Sikarugir Wine 10.0**, which is the only engine of the three we measured that works
([docs/implementation-status.md](docs/implementation-status.md)). Competitive validation (T-020) is still open.
**Cost to us and to every future user: €0.**
**Machine of record:** MacBook Pro **M2 Pro, 32 GB, macOS 26.5.2**, 16-core GPU, Metal 4.

---

## The stack (decided — no alternatives to evaluate)

```
cs2.exe (Windows x64)
   └─ Windows Steam client        ← runs INSIDE the bottle; macOS Steam cannot serve CS2
        └─ Sikarugir Wine 10.0  (WS12WineSikarugir10.0_6.tar.xz, LGPL-2.1)
             ├─ DXMT   v0.80 (MIT; LGPL from v0.81)  DirectX 11 → Metal
             └─ MSync  (LGPL-2.1)  synchronisation
                  └─ Rosetta 2 → Metal 4 → Apple M2 Pro
```

**The engine is not interchangeable.** Three free Wine builds were measured on the machine of record on 2026-08-24
and **only one runs CS2**:

| Engine | Steam UI | Steam client↔helper transport | DXMT Metal view | Verdict |
|---|---|---|---|---|
| Gcenx Wine 11.15 staging/devel | **black** (0.0/255 luminance) | OK | **fails** — *"Failed to create metal view"* | unusable |
| FOSS CrossOver 24.0.7 (Wine 9.0 base) | renders | **rejected — 0x3008**, 82 times in one session | works | unusable |
| **Sikarugir Wine 10.0** | **renders** | **OK** | **works** (`_macdrv_functions` exported) | **the Wine of record** |

Evidence: [docs/implementation-status.md](docs/implementation-status.md) and
[research/steam-black-window-2026-08-24.md](research/steam-black-window-2026-08-24.md).
Every component is free software. `CS2Kit` redistributes **none** of it — `cs2kit engine install` fetches the
engine from its upstream release and verifies its SHA-256 ([docs/reference/toolchain.md](docs/reference/toolchain.md)),
so no licence follows our code at all. **Homebrew is not the route:** the cask the plan used to name was deleted
upstream on 2026-04-16, and Homebrew's own Wine casks are disabled on 2026-09-01 for failing Gatekeeper.
Apple's proprietary **D3DMetal is deliberately excluded**; if T-012 ever shows DXMT is inadequate on some machine,
the user installs GPTK themselves — we never redistribute it.

## The one-paragraph verdict

CS2 has **no macOS build and never will** (Valve dropped it 2023-10-10; appid 730 is `oslist = "windows,linux"`).
So this is not a port, it is a **Windows-bottle integration problem** — and other people have already shown it works:
a documented M5 Pro run hits **190 avg / 140 1%-low at 1080p**, and an M1 Pro player holds a **15,000 Premier CS
Rating** through Wine. There is no evidence of a legitimate player ever being VAC-banned for using a compatibility
layer. **The value here is not "make it run" — it is making it reproducible, measured, legal and maintainable.**
The one thing we cannot engineer around: **Apple retires general-purpose Rosetta 2 after macOS 27**, and this entire
stack is x86-64.

## Hard rules

| Never | Why |
|---|---|
| Use macOS Steam to install CS2 | It **cannot**. Proven on this machine — a "complete" 66 GB install with no `cs2.exe`. See [target-machine.md](docs/reference/target-machine.md). |
| Modify `cs2.exe` or any Valve DLL | Valve's VAC FAQ names modifying core executables/DLLs as cheating. Enforced by a hash guard (T-021). |
| Use `-vulkan` | On Apple Silicon it lands on a DXVK fork frozen since 2023 and a MoltenVK with no geometry shaders. One confirmation run, then dropped. |
| Redistribute D3DMetal | Apple's licence permits it only non-commercially. We avoid the question entirely by shipping DXMT. |
| Buy Prime before T-020 passes | €13.29 / $14.99 and **non-refundable**. |

## Start here

```bash
bash scripts/preflight.sh          # grades the machine, finds the disk trap
./bin/cs2kit doctor                # the same grade, plus the bottle, the game and the integrity guard
```

`bin/cs2kit` runs from a checkout with the **system `python3`** — no `pip`, no venv, no dependencies.
On a bare machine the FAILs it prints are exactly the three things Phase 0–1 exists to fix: no Wine, no bottle,
no `cs2.exe`. Its `winemac.drv exports` check is the one that would have saved us a day — it fails any engine that
cannot give DXMT a Metal view.

**T-010 gate: PASSED** on the machine of record — 6 passes across Dust2, Mirage and Ancient, 48 minutes of bot
play, **0 crashes, 0 frozen frames**, 101–130 fps median (indicative, auto-Low; see the caveats in
[docs/07-benchmark-protocol.md](docs/07-benchmark-protocol.md)). Audio is still unassessed.

What is actually built and what still needs hardware time is spelled out task by task in
[docs/implementation-status.md](docs/implementation-status.md). **One indicative FPS sample exists** (117 fps,
Dust2 bot match, CS2's auto-selected Low preset, 2026-08-24) and it is a single reading, not a benchmark — the
T-011 protocol produces the number this project will stand behind. **No latency and no VAC number is recorded
anywhere in this repo, because none has been measured.**

Then read [docs/00-executive-summary.md](docs/00-executive-summary.md) and work
[docs/03-development-plan.md](docs/03-development-plan.md) from **T-001**.
The **⚡ Fast path** at the top of that file is seven tasks to a playable game in ~2 days.

## CS2Kit

```
cs2kit doctor                       grade machine + bottle + game; one fix line per fault    T-024
cs2kit engine list | install        fetch the one Wine build measured to run CS2             T-004
cs2kit env --save <file>            freeze the environment of record                        T-005
cs2kit bottle create --dxmt <dir>   build the prefix from profiles/bottle-recipe.yaml        T-006/T-025
cs2kit bottle link-steamapps        reuse an existing CS2 install, no second download        T-008
cs2kit bottle diff | repair         report and undo drift from the recipe                    T-025
cs2kit config list | apply <name>   situational profiles (env, launch options, cvars)        T-027
cs2kit verify baseline | check      SHA-256 guard on game/bin/win64                          T-021
cs2kit launch                       integrity-guarded start via the in-bottle Steam client   T-021
cs2kit app create                   a double-clickable launcher: verify, then launch         T-007/T-029
cs2kit bench run | compare          the T-011 protocol, and regression detection             T-011/T-026
cs2kit report                       a redacted bundle you can share                          T-028
cs2kit watch check | drill          CS2 buildid watch + the regression drill                 T-030
```

**Scope rule:** CS2Kit *configures and diagnoses*. It never patches the game, never wraps Steam
authentication, never implements graphics, never touches VAC.

Full surface: [docs/cs2kit-spec.md](docs/cs2kit-spec.md). Install from zero:
[docs/09-install-guide.md](docs/09-install-guide.md). When it breaks:
[docs/10-troubleshooting.md](docs/10-troubleshooting.md). Contributing:
[CONTRIBUTING.md](CONTRIBUTING.md). Licence: **GPL-3.0** ([LICENSE](LICENSE)). We redistribute nothing:
Wine and MSync are LGPL-2.1, DXMT is **MIT through v0.80** (LGPL from v0.81), and the user downloads both.

## Disclosure

> CS2 has no macOS build. This tool configures a Windows compatibility environment on your Mac. It does not modify
> Counter-Strike 2 and does not interact with Valve Anti-Cheat. It is not endorsed by Valve, Apple or CodeWeavers, and
> is **not supported by Valve**. Use is at your own risk. We have found no evidence of bans caused by compatibility
> layers, but Valve has published no policy on the matter.

## Repo map

```
docs/
  00-executive-summary.md      verdict, success criteria, go/no-go
  01-gap-analysis.md           9 corrections to the prior analysis this supersedes
  02-architecture.md           the stack, and why each rejected option was rejected
  03-development-plan.md       ← THE PLAN. Fast path + 33 tasks + acceptance criteria
  04-test-matrix.md            the regression suite a CS2 update must survive
  05-risk-register.md          scored risks + the Rosetta-27 exit plan
  06-legal-and-policy.md       licences, VAC policy, absolute rules
  07-benchmark-protocol.md     how to produce an FPS number that means something
  08-cost-and-dependencies.md  every component's licence; why users pay nothing
  09-install-guide.md          bare Mac to a bot match, copy-pasteable
  10-troubleshooting.md        every known failure mode, keyed to a cs2kit command
  11-validation-log.md         the Phase 3 online + anti-cheat record (empty until someone plays)
  12-maintenance.md            Phase 5 cadence: update drill, macOS betas, bundles, upstreams
  implementation-status.md     every one of the 34 tasks: shipped, tooled, or waiting on hardware
  cs2kit-spec.md               the CLI surface, exit codes, file layout
  compatibility-matrix.md      measured rows, one per machine/buildid
  rosetta-watch.md             the quarterly R-1 log and the decommission notice
  reference/                   target-machine.md, toolchain checksums, env-snapshot-0.json
research/                      URL-cited primary-source findings + the prior analysis
scripts/preflight.sh           machine grader (run this first)
cs2kit/                        the CLI (stdlib only, Python 3.9+)
LICENSE                        GPL-3.0 for our own code
CONTRIBUTING.md                how to run the tests and add a doctor check
.github/workflows/ci.yml       tests on py3.9+3.13 x macOS+Linux, stdlib-only guard, docs links
profiles/                      bottle-recipe.yaml + the three situational profiles
tests/                         pytest suite: `uv run pytest`
```

Every claim in `docs/` traces to a URL-cited entry in `research/`, tagged **CONFIRMED** (vendor/primary),
**LIKELY** (community), or **UNKNOWN** (not verified).
