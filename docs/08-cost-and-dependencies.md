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

## The decision (locked)

**We ship Tier 1: Wine + DXMT + MSync — LGPL-2.1 throughout.** Users pay nothing, the project carries no Apple
licence obligations, and `CS2Kit` may be relicensed or monetised later without renegotiating anything.

Rejected: **CrossOver** (€74 per user — and the components that matter, DXMT and MSync, are free anyway) and
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

* **LGPL-2.1 imposes obligations**: ship the licence, provide the modified library source if you modify it, and keep
  relinking possible. Dynamic linking a shipped `.dll`/`.dylib` and shipping it unmodified is the easy path — do that.
* **Apple's GPTK use-grant grey zone** (§2A(i) "developing, testing, or evaluating") applies to T2 only. **T1 avoids
  the question entirely** — a further argument for DXMT.
* **None of this changes the Rosetta-27 clock (R-1).** Free or paid, the whole stack is x86-64 under Rosetta.
