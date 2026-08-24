# 08 — Cost and dependency model

**Short answer: no. CrossOver is a development convenience, not a shipped dependency, and end users need not pay
anything.** But that outcome has to be *engineered for* — it depends on which graphics backend wins T-012.

## Licence status of every component (verified 2026-08-23; DXMT corrected 2026-08-24)

| Component | Licence | Free to redistribute? | Commercial use? |
|---|---|---|---|
| **Wine** (**Sikarugir Engines**, `WS12WineSikarugir10.0_6`, wine-10.0) | LGPL-2.1 | ✅ | ✅ |
| **DXMT** (DX11→Metal, 3Shain/CodeWeavers, **v0.80** 2026-04-23) | **MIT** — and **LGPL from v0.81** | ✅ | ✅ |
| **MSync** (marzent/wine-msync) | **LGPL-2.1** | ✅ | ✅ |
| **DXVK-macOS** (Gcenx) | Zlib | ✅ | ✅ | 
| **MoltenVK** (Khronos) | Apache-2.0 | ✅ | ✅ |
| **D3DMetal** (Apple GPTK) | Apple SLA | ⚠️ **non-commercial only**, whole framework, Apple hardware only | ❌ |
| **CrossOver** (CodeWeavers) | €74 proprietary | ❌ | n/a |
| **CS2** | free-to-play | n/a | Prime $14.99 optional |
| Windows licence | **not required** — Wine is not Windows | — | — |

**The decisive finding: MSync and DXMT — the two components most people assume are CrossOver-exclusive — are both
free software.** CrossOver bundles them; it does not own them. Everything in the stack is free software **except
D3DMetal**, which is the one Apple-proprietary piece.

**DXMT licence correction (2026-08-24).** This table said LGPL-2.1. DXMT's own v0.80 release notes say: *"We are
changing the license of DXMT from MIT to LGPL. **v0.80 will be the last release distributed in MIT license.**"* The
version we ship instructions for is therefore **MIT**; v0.81 onward will be LGPL. MIT is more permissive, so no
conclusion below changes — but the claim was wrong and is corrected here and in
[06-legal-and-policy.md](06-legal-and-policy.md). CONFIRMED —
[../research/wine-dxmt-install-findings-2026-08-24.md](../research/wine-dxmt-install-findings-2026-08-24.md) §7.

## How the stack is actually obtained (measured 2026-08-24)

**We redistribute nothing but our own code.** The user downloads two tarballs and verifies two checksums; CS2Kit
places files the user already has. This is not a licensing pose — it is the install path, and it is the reason no
licence in the table above binds this project.

| Component | URL | Released | Bytes | SHA-256 |
|---|---|---|---|---|
| Sikarugir Wine 10.0 | `github.com/Sikarugir-App/Engines/releases/download/v1.0/WS12WineSikarugir10.0_6.tar.xz` | 2026-08-24 | 166 304 096 | `9da7ee0cbf386522f3a9906943726d9c3c125dbbd9ab120e3cde80e88d6091b2` |
| DXMT v0.80 builtin | `github.com/3Shain/DXMT/releases/download/v0.80/dxmt-v0.80-builtin.tar.gz` | 2026-04-23 | 18 681 669 | `8f260e36b5739e68f3bad613381441385c4dc7b85b78ba8de653d5a6a264529d` |

**Not Homebrew.** `gcenx/wine/wine-crossover` — the command this project used to print — was deleted from its tap on
2026-04-16 and had been shipping wine-8.0.1, not the 11.x we claimed; Homebrew now refuses third-party casks without
`brew trust`; and `wine-stable` / `wine@staging` are **disabled on 2026-09-01** for failing Gatekeeper (R-15 and
R-16 in [05-risk-register.md](05-risk-register.md)). A tarball has no package name to delete and no quarantine
attribute, and it can be pinned by checksum. All CONFIRMED —
[../research/wine-dxmt-install-findings-2026-08-24.md](../research/wine-dxmt-install-findings-2026-08-24.md).

**Total download for the toolchain: ~202 MB. Admin rights required: none.** Everything lives under `~/CS2`.

## The decision (locked)

**We ship Tier 1: Wine + DXMT + MSync — free software throughout (LGPL-2.1, MIT, LGPL-2.1), redistributed by
nobody but their own upstreams.** Users pay nothing, the project carries no Apple licence obligations, and `CS2Kit`
may be relicensed or monetised later without renegotiating anything.

Rejected: **CrossOver** (€74 per user — and the components that matter, DXMT and MSync, are free anyway; note that
CrossOver-sources *Wine* remains a documented **fallback**, not a purchase — see
[02-architecture.md](02-architecture.md)) and
**D3DMetal** (free to download, but redistributable only non-commercially, with a use grant worded for
"developing, testing, or evaluating"). D3DMetal survives only as a **user-installed local fallback** if T-012 shows
DXMT is inadequate on a given machine — we never ship it, so its licence never binds us.

**T-012 therefore confirms a decision rather than making one.** Run it on DXMT, record hitch counts as well as FPS,
and only reach for GPTK if the 1 % lows are unacceptable.

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

* **LGPL-2.1 imposes obligations** *on whoever redistributes*: ship the licence, provide the modified library source
  if you modify it, and keep relinking possible. **We redistribute nothing, so nothing attaches today.** If that ever
  changes, dynamic linking a shipped `.dll`/`.dylib` unmodified is the easy path — do that. DXMT v0.80's MIT terms
  are lighter still (attribution only), and DXMT v0.81+ moves to LGPL, so a future bundling decision must re-check
  the version it is bundling.
* **Apple's GPTK use-grant grey zone** (§2A(i) "developing, testing, or evaluating") applies to T2 only. **T1 avoids
  the question entirely** — a further argument for DXMT.
* **None of this changes the Rosetta-27 clock (R-1).** Free or paid, the whole stack is x86-64 under Rosetta.
