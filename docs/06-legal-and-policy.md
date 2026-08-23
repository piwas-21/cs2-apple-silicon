# 06 — Legal, licensing and anti-cheat policy

> Not legal advice. Every quoted term is reproduced from the source cited in `research/`.

## 1. Apple Game Porting Toolkit / `D3DMetal.framework`

From the *Apple Inc. Software License Agreement for Game Porting Toolkit* (text extracted from the licence PDF
shipped with GPTK 3.0):

* **§2A(iii)** — you may *"distribute the Apple Software solely for non-commercial purposes and in accordance with
  this Agreement, including Section 2C."*
* **§2C** — *"The Apple Software is provided as part of a bundle and its components may not be separated … **Notwithstanding
  the foregoing, the Framework in its entirety or any part of the Redistributables may be distributed separately from
  the Apple Software.** For clarity, all distribution … [is] subject to the non-commercial restriction in Section 2(A)(iii)."*
* **§2B/§2C** — Apple-branded hardware only. **§2D** — no reverse engineering. **§5** — automatic termination on breach.

**Therefore, contradicting the common claim that GPTK is evaluation-only:** an **open-source, non-commercial**
`CS2Kit` **may** redistribute `D3DMetal.framework` **in its entirety** (not split up), for use on Apple hardware.
Gcenx already does this via `brew install --cask game-porting-toolkit`; Sikarugir and Procyon likewise.

**The genuine grey zone:** the §2A(i) **use** grant is worded *"for the sole purpose of developing, testing, or
evaluating video games for use on Apple-branded products."* A tool whose purpose is *playing a shipped game* sits
outside that wording even though the **distribution** grant in §2A(iii) is broader. **CLOSED by the decision below:**
we ship no Apple software, so this project never reaches the question. It is recorded only so that a future proposal
to bundle D3DMetal re-opens it deliberately, with counsel, rather than by accident.

### Distribution model — DECIDED (T-002)
- [x] **Tier 1: we redistribute nothing but our own GPL-3.0 code.** The user downloads Wine (**LGPL-2.1**) and DXMT
      (**MIT** — see below) themselves from the pinned URLs in [09-install-guide.md](09-install-guide.md); CS2Kit
      only places files the user already has. **We do NOT bundle D3DMetal**, so §2A(iii) and the §2A(i) use-grant
      grey zone below **do not apply to this project**. Users who want D3DMetal install Apple's GPTK themselves.
      Should we ever bundle an LGPL library, the obligations attach then: ship the licence text, keep it unmodified
      and dynamically linked.
- [ ] ~~Non-commercial, open source, bundling D3DMetal.~~ **Not taken.** Never monetised — no paid tier, no donations tied to
      binaries, no sponsored builds. (This is why CodeWeavers needs a *separate bilateral agreement* with Apple to
      ship D3DMetal in the €74 CrossOver.)

**Standing rule (not an option to pick):** should any commercial element ever appear, it must **not** bundle
D3DMetal — it depends on the user's own CrossOver licence or on DXMT/DXVK instead. Tier 1 above already satisfies
this, and `CS2Kit` is GPL-3.0, so the rule binds every downstream fork too.

Wine itself is **LGPL-2.1** and freely redistributable (Apple's GPTK Wine half is CrossOver 22.1.1 sources).
**DXMT / DXVK / MoltenVK** are open source — no equivalent restriction.

### DXMT's licence — corrected 2026-08-24
Earlier drafts of this file and of [08-cost-and-dependencies.md](08-cost-and-dependencies.md) called DXMT
**LGPL-2.1**. That is **wrong**. DXMT's own v0.80 release notes say, verbatim:

> *"We are changing the license of DXMT from MIT to LGPL. **v0.80 will be the last release distributed in MIT
> license.**"*

So the release this project ships instructions for — **v0.80** — is **MIT**; **v0.81 onward will be LGPL**.
CONFIRMED from the release notes, fetched 2026-08-24
([../research/wine-dxmt-install-findings-2026-08-24.md](../research/wine-dxmt-install-findings-2026-08-24.md) §7).

**The conclusion does not move.** MIT is strictly more permissive than LGPL-2.1 — attribution, no copyleft, no
relinking obligation — so nothing that was permitted becomes forbidden. And it is moot in practice: **we redistribute
no third-party binaries at all.** When DXMT flips to LGPL at v0.81 it will still be the user's download, not ours.

## 2. Valve, VAC and this project

**What Valve says.** The VAC FAQ describes VAC as signature-based and states that **hardware configurations and
drivers do not trigger bans**. It explicitly names as cheating: *"modifications to a game's core executable files and
dynamic link libraries."* **Valve has published no policy on Wine/Proton and VAC on macOS** — this is **UNKNOWN** and
cannot be resolved by engineering.

**Why the risk is nonetheless low (inference from confirmed facts):**
CS2 ships a **native Linux build with VAC enabled** and is Steam-Deck-"Playable" → VAC does not require Windows kernel
primitives. Valve serves CS2 through **GeForce NOW cloud VMs**. No credible report of a Wine-caused CS2 ban was
found, and a documented M1 Pro CrossOver player holds a **15,000 Premier CS Rating**.

### Absolute rules for this project
1. **Never modify, patch, inject into, or hook `cs2.exe` or any Valve DLL.** Enforced mechanically by T-021's hash
   guard, which refuses to launch on mismatch. This is the one action that converts a low risk into a real one — and
   it is exactly the strategy the prior analysis inherited from a mis-cited repository (G-2).
2. **Never interfere with, disable, spoof or study VAC.** Out of scope, permanently.
3. **Never wrap, replace or automate Steam authentication.** The user logs into Valve's own client.
4. Configuration is limited to: bottle settings, **Wine's own** DLL overrides, environment variables, CS2 launch
   options, and in-game console/`autoexec.cfg`. Nothing else.
5. Ship no cheat-adjacent capability: no overlays beyond Steam's, no macros, no memory reading, no input automation.

### Account safety (T-018)
* Use a **secondary, non-Prime** account for all first online testing.
* **Prime is €13.29 / $14.99 and explicitly non-refundable** — buy it only *after* T-020 passes on the secondary
  account. (The prior analysis's ordering would have you validate competitive play before establishing this.)
* Keep Steam Guard enabled.

## 3. User-facing disclosure (required in the README of any release)

> CS2 has no macOS build. This tool configures a Windows compatibility environment on your Mac. It does not modify
> Counter-Strike 2 and does not interact with Valve Anti-Cheat. It is not endorsed by Valve, Apple or CodeWeavers, and
> is **not supported by Valve**. Use is at your own risk. We have found no evidence of bans caused by compatibility
> layers, but Valve has published no policy on the matter.

## 4. Trademarks
"Counter-Strike", "Steam", "Valve" are Valve's; "Apple", "Metal", "macOS" are Apple's; "CrossOver" is CodeWeavers'.
Use nominatively only. Do not name the project in a way that implies endorsement.
