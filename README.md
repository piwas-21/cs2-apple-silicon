
# CS2 on Apple Silicon

[![ci](https://github.com/piwas-21/cs2-apple-silicon/actions/workflows/ci.yml/badge.svg)](https://github.com/piwas-21/cs2-apple-silicon/actions/workflows/ci.yml)
[![licence: GPL-3.0](https://img.shields.io/badge/licence-GPL--3.0-blue.svg)](LICENSE)

**Counter-Strike 2 running on an Apple Silicon Mac, on a stack that costs nothing.**
Plus `CS2Kit` — a small CLI that makes the setup reproducible, diagnosable and measurable.

```
cs2.exe (Windows x64)
   └─ Windows Steam client          ← runs inside the bottle; macOS Steam cannot serve CS2
        └─ Sikarugir Wine 10.0      LGPL-2.1
             ├─ DXMT v0.80          MIT — Direct3D 11 → Metal
             └─ MSync               LGPL-2.1 — synchronisation
                  └─ Rosetta 2 → Metal 3 → Apple Silicon
```

CS2 has **no macOS build and never will** — Valve dropped it in 2023 and appid 730 is `oslist =
"windows,linux"`. So this is not a port; it is a Windows-bottle integration problem, solved end to end and
written down.

## Status — measured, on one machine

Machine of record: **MacBook Pro M2 Pro, 32 GB, macOS 26.5.2 (25F84)**.

| | |
|---|---|
| Game runs and renders through DXMT | **yes** — `D3D_FEATURE_LEVEL_11_1` |
| 48-minute bot-match gate, 3 maps × 2 passes | **passed** — 0 crashes, 0 frozen frames |
| Frame rate (benchmark map, 1000-frame window, auto-Low) | **127.9 fps**, worst frame 13.43 ms |
| Audio | works (user-attested) |
| Competitive / VAC validation | **not started** — see [Honest limits](#honest-limits) |

## Quickstart

```bash
git clone https://github.com/piwas-21/cs2-apple-silicon.git
cd cs2-apple-silicon

bash scripts/preflight.sh          # grade the machine; finds the disk trap first
./bin/cs2kit engine list           # which Wine build works, and why the others do not
./bin/cs2kit engine install        # download + verify + stage the engine
./bin/cs2kit bottle create --dxmt <extracted DXMT release>
./bin/cs2kit doctor                # 18 checks, one fix line each
```

Then follow **[docs/install.md](docs/install.md)** from step 5 (Steam, login, CS2), and finish with:

```bash
./bin/cs2kit app create            # a double-clickable launcher — no terminal to play
```

`bin/cs2kit` runs from a checkout with the **system `python3`**: no pip, no venv, no dependencies.

## What `CS2Kit` does

```
cs2kit engine list | install        the one Wine build that runs CS2, checksummed
cs2kit doctor                       machine + bottle + game;each check ends in one action
cs2kit env --save <file>            freeze the environment every benchmark is keyed to
cs2kit bottle create|diff|repair    build the prefix from profiles/bottle-recipe.yaml
cs2kit bottle link-steamapps        reuse an existing CS2 install — no re-download
cs2kit bottle restore-wine          undo DXMT, to A/B whether it is the problem
cs2kit config list|apply <profile>  env vars, launch options, cvars
cs2kit verify baseline|check        SHA-256 guard on game/bin/win64
cs2kit launch                       integrity-guarded start
cs2kit app create                   the double-clickable launcher
cs2kit bench run|compare            the benchmark protocol, and regression detection
cs2kit report                       a redacted bundle you can share
cs2kit watch check|drill            CS2 buildid watch + the update drill
```

**Scope rule:** CS2Kit *configures and diagnoses*. It never patches the game, never wraps Steam
authentication, never implements graphics, never touches VAC.

## The engine matrix — the thing that cost us a day

Three free Wine builds were measured. **Only one does all three jobs.**

| engine | Steam UI | client↔helper transport | DXMT Metal view |
|---|---|---|---|
| Gcenx Wine 11.15 (staging/devel) | black | OK | **fails** — no `winemac.drv` exports |
| FOSS CrossOver 24.0.7 | renders | **rejected — 0x3008** | works |
| **Sikarugir Wine 10.0** | **renders** | **OK** | **works** |

`cs2kit doctor` checks this directly (`Wine exports DXMT's API`), so nobody has to rediscover it.
Full detail: [docs/architecture.md](docs/architecture.md).

## Documentation

| For | Read |
|---|---|
| Installing from zero | [docs/install.md](docs/install.md) |
| Something is broken | [docs/troubleshooting.md](docs/troubleshooting.md) — 23 entries, each with a one-command check |
| Every command and exit code | [docs/cli-reference.md](docs/cli-reference.md) |
| Why this stack, and what was rejected | [docs/architecture.md](docs/architecture.md) |
| Licences, VAC policy, the absolute rules | [docs/legal-and-vac.md](docs/legal-and-vac.md) |
| Producing an FPS number that means something | [docs/benchmarking.md](docs/benchmarking.md) |
| Exact versions and checksums | [docs/reference/toolchain.md](docs/reference/toolchain.md) |
| What has actually been measured | [docs/project/measured-results.md](docs/project/measured-results.md) |
| Per-machine results | [docs/compatibility-matrix.md](docs/compatibility-matrix.md) |

Project-internal planning, risks and maintenance cadence live in [docs/project/](docs/project/); the
URL-cited evidence behind every claim lives in [research/](research/).

## Honest limits

* **One machine.** Everything here was measured on a single M2 Pro. Your mileage is literally unknown.
* **Competitive play is unvalidated.** T-020 — ten VAC-protected matches across three days — has **not**
  been run. Until it has, treat this as **practice and offline only**. There is no evidence of a
  legitimate player being VAC-banned for a compatibility layer, and Valve has published no policy either
  way. See [docs/legal-and-vac.md](docs/legal-and-vac.md).
* **The numbers are preliminary.** One benchmark run, not the 3-warm-up + 5-measured protocol, and no
  1 % lows. Untuned: auto-Low at the Retina backing resolution.
* **Rosetta 2 ends after macOS 27.** This entire stack is x86-64. That is a dated, unavoidable risk —
  [docs/project/rosetta-watch.md](docs/project/rosetta-watch.md).
* **Unsupported by Valve, Apple and CodeWeavers.** Nobody owes you a fix.

## Disclosure

> CS2 has no macOS build. This tool configures a Windows compatibility environment on your Mac. It does not
> modify Counter-Strike 2 and does not interact with Valve Anti-Cheat. It is not endorsed by Valve, Apple or
> CodeWeavers, and is **not supported by Valve**. Use is at your own risk. We have found no evidence of bans
> caused by compatibility layers, but Valve has published no policy on the matter.

## Contributing and licence

Tests: `uv run pytest` (209 tests, Python 3.9 and 3.13, macOS and Linux). Start with
[CONTRIBUTING.md](CONTRIBUTING.md).

Our code is **GPL-3.0** ([LICENSE](LICENSE)). We redistribute nothing: Wine and MSync are LGPL-2.1, DXMT is
MIT through v0.80, and the user downloads both. Apple's D3DMetal is deliberately not used.
