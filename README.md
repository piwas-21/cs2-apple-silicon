# cs2-apple-silicon

A verification-first engineering plan for running **Counter-Strike 2** on **Apple Silicon MacBooks**, and for
building `CS2Kit` — a thin, open-source, non-commercial bottle-manager + diagnostics layer on top of Wine + Apple's
D3DMetal / DXMT.

Status: **planning complete, implementation not started.**
Target machine of record: **MacBook Pro M2 Pro, 32 GB, macOS 26.5.2 (25F84), 16-core GPU, Metal 4.**

---

## The one-paragraph verdict

CS2 has **no macOS build and never will** (Valve dropped it 2023-10-10; appid 730 `oslist = "windows,linux"`).
Running it on an M-series Mac is therefore not a "port" problem, it is a **Windows-bottle integration problem**, and
that problem is already largely solved by other people: CodeWeavers rates CS2 **"Runs Well" (4/5) on CrossOver 26.3.0**,
and a documented M5 Pro run hits **190 avg / 140 1%-low at 1080p**. There is no evidence of a legitimate player ever
being VAC-banned for using Wine, and at least one M1 Pro player holds a **15,000 Premier CS Rating** through CrossOver.
**So the engineering risk is low and the value of this project is not "make it run" — it is "make it reproducible,
measured, legal, and maintainable."** The two real threats are (1) Apple retiring **Rosetta 2 after macOS 27**, which
deletes the foundation of the whole stack, and (2) every CS2 update potentially breaking the bottle.

## What this repo says you should NOT do

| Don't | Why |
|---|---|
| Use native macOS Steam + `steam://run/730` | macOS Steam **cannot install CS2**. Proven on this machine — see [target-machine.md](docs/reference/target-machine.md). |
| Patch/modify `cs2.exe` or any game DLL | Valve's VAC FAQ names *"modifications to a game's core executable files and dynamic link libraries"* as cheating. This is the one action that turns a low ban risk into a real one. |
| Assume D3DMetal is the best backend | On one M3, **DXMT ≈ 120 FPS vs D3DMetal ≈ 11 FPS**. On an M4 Max the ordering reverses. Backend choice is a **per-machine measurement**, not a constant. |
| Use `-vulkan` | The CS2 Windows build does have a Vulkan renderer, but on Apple Silicon it routes through a DXVK-macOS fork frozen at 1.10.3 and a MoltenVK with no geometry shaders / transform feedback. Benchmark it, expect to reject it. |
| Ship this commercially | Apple's GPTK licence permits redistributing `D3DMetal.framework` **only for non-commercial purposes**. Money changes the legal answer. |
| Write per-chip `m1.yaml … m5.yaml` profiles up front | The variance that matters is **backend × macOS version × CS2 build**, not chip family. |

## Repo map

```
docs/
  00-executive-summary.md    verdict, go/no-go, what success means
  01-gap-analysis.md         diff vs. the prior analysis document — 9 material corrections
  02-architecture.md         the real stack, with the layer the prior doc got wrong
  03-development-plan.md     ← THE PLAN. 6 phases, 34 numbered tasks, acceptance criteria
  04-test-matrix.md          the regression suite a CS2 update must be run against
  05-risk-register.md        scored risks + the Rosetta-27 exit plan
  06-legal-and-policy.md     GPTK licence, VAC policy, what is and isn't allowed
  07-benchmark-protocol.md   how to produce an FPS number that means something
  08-cost-and-dependencies.md  licence tiers: why users pay nothing, and what that costs us
  reference/target-machine.md  measured state of this Mac, incl. the 60 GB stuck download
research/
  steam-vac-findings.md              primary-source research (Steam appinfo, Steamworks, VAC)
  tooling-licensing-findings.md      CrossOver / GPTK licence / MoltenVK / Rosetta timeline
  performance-alternatives-findings.md  ~25-row FPS table, 18-item bug table, alternatives
  prior-analysis-2026-08-23.md       the earlier document this plan supersedes
scripts/
  preflight.sh               run this first; it grades the machine and finds the disk trap
```

## Start here

1. `bash scripts/preflight.sh`
2. Read [docs/00-executive-summary.md](docs/00-executive-summary.md)
3. Work [docs/03-development-plan.md](docs/03-development-plan.md) from **T-001**.

Every factual claim in `docs/` is traceable to a URL-cited entry in `research/`.
Claims are tagged **CONFIRMED** (vendor/primary), **LIKELY** (community/secondary), **UNKNOWN** (not verified).
