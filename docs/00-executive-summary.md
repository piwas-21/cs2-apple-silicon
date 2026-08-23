# 00 — Executive summary

**Question:** can Counter-Strike 2 be made suitable for Apple Silicon MacBooks, and what should be built?

**Answer:** yes for *running* it — that is largely a solved problem in 2026 and the remaining work is integration,
measurement and maintenance. No for *porting* it — Valve dropped macOS on 2023-10-10 and a first-party Apple Silicon
build should be treated as **0 % probability** (no mention in Valve's own appid-730 news feed 2023-09 → 2026-01; the
only "active Mac depot" on SteamDB is CS:GO Legacy).

## The five facts that determine the design

1. **appid 730 is `oslist = "windows,linux"`.** macOS Steam cannot install or launch CS2. Anything that says
   "just use `steam://run/730`" is wrong. **The Windows Steam client must live inside the Wine bottle.** (CONFIRMED —
   Valve appinfo + storefront API + the stalled 60 GB download on this very Mac, explained byte-for-byte in G-1.)
2. **It already works well.** CodeWeavers rates CS2 **"Runs Well" (4/5)** on CrossOver 26.3.0 — the **#9 most-ranked
   app** in their entire database. Measured: M5 Pro **190 avg / 140 1%-low @1080p**; M4 Pro 122; M4 Max 160–200 @1440p;
   M1 Air 50. The M2 Pro/32 GB target should land ~100–125 @1080p medium.
3. **Anti-cheat is a manageable risk, not a wall.** CS2 ships a **native Linux build with VAC**, Valve serves CS2
   through GeForce NOW VMs, Valve's VAC FAQ says hardware/driver configuration does not trigger bans, and a documented
   M1 Pro CrossOver player holds a **15,000 Premier CS Rating**. No credible Wine-caused ban was found. **But Valve has
   never written a Wine policy** — that stays UNKNOWN and unfixable by engineering.
4. **The graphics backend is a per-machine measurement, not a constant.** D3DMetal vs DXMT vs DXVK swings **10× in
   both directions** across machines. Assuming D3DMetal is the 2024 answer.
5. **Rosetta 2 ends as a general-purpose tool after macOS 27** (Apple's own wording), and the whole stack is x86-64.
   The escape hatch (ARM64EC Wine + FEX) is blocked by Apple Silicon's 16 KB page size. **This project has a shelf life
   and must say so out loud.**

## What to build

Not a port, not an emulator, not a VM, not a Steam replacement, and — correcting the prior analysis — **not a
patcher**. Build **`CS2Kit`**: a CLI that creates a reproducible bottle from a declarative recipe, diagnoses the
environment, verifies game-file integrity (and refuses to run if files were modified), benchmarks to a protocol, and
produces a redacted shareable report. Everything else is documentation of measurements.

## Definition of success

> 10 consecutive VAC-protected matches (5 Competitive + 5 Premier) across ≥ 3 days with zero anti-cheat kicks and zero
> account warnings, at **1 % lows ≥ 60 FPS**, with working microphone comms, measured input latency published, and a
> fresh bottle reproducible from `profiles/bottle-recipe.yaml` with no manual step.

## Go / no-go

* **Do not start** until **T-003** proves GeForce NOW / Moonlight streaming fails *your measured* latency bar. CS2 is
  on GFN today, fully optimized, with zero engineering effort. Building a bottle when a cheaper path suffices is the
  most likely way to waste this project.
* **Stop at T-020** if competitive matches systematically kick you. That is a policy wall; do not engineer around it.
* **Plan the exit at T-031.** macOS 27 is the horizon, not a rumour.

## Effort

~1.5 days to decide · ~2 days to first bot match · ~3 days to a tuned configuration · ~2 days + soak to validate
competitive · ~8 days to ship `CS2Kit` v0.1 · then ongoing quarterly maintenance.
