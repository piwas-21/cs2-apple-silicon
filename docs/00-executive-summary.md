# 00 — Executive summary

**Goal:** play Counter-Strike 2 on an Apple Silicon MacBook using only free software, and ship `CS2Kit` so anyone
else can reproduce it.

## The decision

| | |
|---|---|
| **Stack** | Wine **11.15 staging** (Gcenx tarball) + **DXMT v0.80** + **MSync** — Wine/MSync LGPL-2.1, DXMT MIT through v0.80 (LGPL after). Installed and proven on the machine of record 2026-08-24; **not** via Homebrew (that cask was deleted upstream) |
| **Cost to us** | €0 |
| **Cost to every future user** | **€0** (CS2 is free-to-play; Prime is optional at $14.99) |
| **Excluded** | CrossOver (€74), D3DMetal (non-commercial licence), DXVK-macOS (frozen 2023), `-vulkan`, VMs, Boot Camp |
| **Time to a playable game** | **~2 days** (7 tasks — the ⚡ Fast path) |
| **Time to a validated competitive setup** | ~7 days |
| **Time to `CS2Kit` v0.1** | +8 days |

## The five facts that produced it

1. **appid 730 is `oslist = "windows,linux"`.** macOS Steam cannot install or launch CS2. **Proven here:** this Mac
   has a "complete" 66 GB CS2 install (`StateFlags 4`, `LastPlayed` set) with **no `cs2.exe`** — `InstalledDepots`
   omits depot **2347771**, which holds every `.exe`/`.dll`. *Verify integrity cannot fix it.* The Windows Steam
   client must run **inside** the bottle.
2. **The 58 GB already on disk is reusable.** Depot 2347770 has no OS filter, so the gap is **4.99 GB, not 72 GB**.
3. **It already works well.** CodeWeavers rates CS2 **"Runs Well" (4/5)**; measured M5 Pro **190 avg / 140 1%-low**
   @1080p, M4 Pro 122, M1 Air 50. Expect **~100–125** on this M2 Pro at 1080p medium.
4. **The whole toolchain is free software.** DXMT and MSync — assumed by most to be CrossOver-exclusive — are both
   free software (Wine/MSync **LGPL-2.1**, DXMT **MIT** through v0.80), and we redistribute none of it — the user
   fetches it. Only Apple's D3DMetal is encumbered, and we simply don't use it.
5. **Anti-cheat risk is Medium, not existential.** CS2 ships a **native Linux build with VAC**; Valve serves CS2
   through GeForce NOW VMs; Valve's VAC FAQ says hardware/driver configuration doesn't trigger bans; an M1 Pro Wine
   player holds a **15,000 Premier CS Rating**. No credible Wine-caused ban found. **But Valve has never published a
   Wine policy** — that stays UNKNOWN and cannot be fixed by engineering.

## What we build

Not a port, not an emulator, not a VM, not a Steam replacement, and **not a patcher**. Just **`CS2Kit`**: a CLI that
builds a reproducible bottle from a declarative recipe, diagnoses the environment, verifies game-file integrity
(refusing to launch if Valve's files were touched), benchmarks to a protocol, and emits a redacted shareable report.
Roughly 2 000 lines. Everything else in this repo is documented measurement.

## Definition of success

> 10 consecutive VAC-protected matches (5 Competitive + 5 Premier) across ≥ 3 days, **zero** anti-cheat kicks and
> **zero** account warnings, at **1 % lows ≥ 60 FPS**, with working microphone comms, published input-latency
> numbers, and a fresh bottle reproducible from `profiles/bottle-recipe.yaml` with **no manual step**.

## The two gates

* **T-010 — does it run?** 30 minutes of bot play across three maps without a crash. Failure means the free stack
  isn't viable on this machine and the only remaining lever is a user-installed D3DMetal.
* **T-020 — does it count?** The competitive/VAC validation. If matches are systematically kicked, **stop** — that is
  a policy wall, not an engineering one, and GeForce NOW becomes the honest recommendation.

## The risk we cannot engineer around

Apple retires general-purpose **Rosetta 2 after macOS 27**, keeping only *"a subset … aimed at supporting older
unmaintained gaming titles"* — and CS2 is actively maintained, so it likely doesn't qualify. This entire stack is
x86-64. The escape route (ARM64EC Wine + FEX) is blocked by Apple Silicon's 16 KB page size. **The project has a
shelf life and says so out loud** (T-031, R-1).

## Honest unknowns going in

Cross-platform Steam library reuse (T-008) is **undocumented** — timeboxed to 2 h with a known-good fallback.
Whether a CS2 update has ever broken a bottle is **UNKNOWN**. No ms-level input-latency measurement for CS2 under
Wine on Apple Silicon exists publicly — T-015 will be the first.
