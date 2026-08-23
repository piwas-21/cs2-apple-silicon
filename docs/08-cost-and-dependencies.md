# 08 — Cost and dependency model

**Short answer: no. CrossOver is a development convenience, not a shipped dependency, and end users need not pay
anything.** But that outcome has to be *engineered for* — it depends on which graphics backend wins T-012.

## Licence status of every component (verified 2026-08-23)

| Component | Licence | Free to redistribute? | Commercial use? |
|---|---|---|---|
| **Wine** (Gcenx macOS builds, **11.15**, 2026-08-08) | LGPL-2.1 | ✅ | ✅ |
| **DXMT** (DX11→Metal, 3Shain/CodeWeavers, active 2026-08-21) | **LGPL-2.1** | ✅ | ✅ |
| **MSync** (marzent/wine-msync) | **LGPL-2.1** | ✅ | ✅ |
| **DXVK-macOS** (Gcenx) | Zlib | ✅ | ✅ | 
| **MoltenVK** (Khronos) | Apache-2.0 | ✅ | ✅ |
| **D3DMetal** (Apple GPTK) | Apple SLA | ⚠️ **non-commercial only**, whole framework, Apple hardware only | ❌ |
| **CrossOver** (CodeWeavers) | €74 proprietary | ❌ | n/a |
| **CS2** | free-to-play | n/a | Prime $14.99 optional |
| Windows licence | **not required** — Wine is not Windows | — | — |

**The decisive finding: MSync and DXMT — the two components most people assume are CrossOver-exclusive — are both
LGPL-2.1.** CrossOver bundles them; it does not own them. Everything in the stack is free software **except
D3DMetal**, which is the one Apple-proprietary piece.

## The three viable distribution tiers

| Tier | Stack | User pays | Project may monetise? | Risk |
|---|---|---|---|---|
| **T1 — fully free & unencumbered** ⭐ | Wine + **DXMT** + MSync (all LGPL/Zlib/Apache) | **€0** | ✅ yes | DXMT must perform well enough on the target machine |
| **T2 — free to user, non-commercial project** | Wine + **D3DMetal** + MSync | **€0** | ❌ never | Apple SLA §2A(iii) binds the project to non-commercial forever |
| **T3 — bring-your-own-CrossOver** | user's own CrossOver 26.3.0 | **€74** | ✅ | Best-supported config; but a paid wall for every user |

`CS2Kit` should **target T1, support T3, and treat T2 as the fallback.**

## Why T-012 is a licensing decision, not just a performance one

The backend bake-off decides which tier is available:

* If **DXMT wins** → T1. Zero cost to users, no Apple licence entanglement, the project may be monetised later,
  and `CS2Kit` can ship a complete working stack. Community data makes this plausible: on one M3/8 GB,
  **DXMT ≈ 120 FPS vs D3DMetal ≈ 11 FPS**. DXMT is also the actively developed one.
* If **D3DMetal wins decisively** → T2. Users still pay nothing (Apple's GPTK is a free download and §2C permits
  redistributing the framework whole), but the project is **permanently non-commercial**.
* If **neither is adequate** → T3, and the honest README line becomes "buy CrossOver."

So run T-012 with the licence column in the results table, not just FPS. A backend that is 10 % slower but LGPL may
be the correct product choice.

## What CrossOver is actually for here

A **paid reference implementation** for development only:
1. It is the configuration CodeWeavers rates **"Runs Well"** for CS2 — a known-good target to reproduce.
2. Its 14-day trial is free, and one seat covers the whole T-004→T-012 investigation.
3. If the free stack misbehaves, CrossOver isolates *"is this Wine, or is this my assembly of Wine?"* in minutes.

**T-004's exit condition should therefore be explicit: reproduce the CrossOver-verified configuration on the free
stack before Phase 4.** If that fails, `CS2Kit` degrades to T3 and must say so on the tin.

## What a user pays, end to end (T1 or T2)

| Item | Cost |
|---|---|
| macOS + Apple Silicon Mac | already owned |
| Wine + DXMT/D3DMetal + MSync + `CS2Kit` | **€0** |
| Counter-Strike 2 | **€0** (free-to-play) |
| Prime Status (only for Premier/Competitive) | $14.99 / €13.29, optional, **non-refundable** |
| Disk | ~72 GB |
| **Total to play** | **€0** |

## Caveats worth stating plainly

* **LGPL-2.1 imposes obligations**: ship the licence, provide the modified library source if you modify it, and keep
  relinking possible. Dynamic linking a shipped `.dll`/`.dylib` and shipping it unmodified is the easy path — do that.
* **Apple's GPTK use-grant grey zone** (§2A(i) "developing, testing, or evaluating") applies to T2 only. **T1 avoids
  the question entirely** — a further argument for DXMT.
* **None of this changes the Rosetta-27 clock (R-1).** Free or paid, the whole stack is x86-64 under Rosetta.
