# 01 — Gap analysis: this plan vs. the prior analysis document

Compared against `research/prior-analysis-2026-08-23.md`.

The prior document is **directionally correct** — its central thesis ("don't port CS2, make the Windows CS2
environment behave correctly on macOS, reuse Wine + D3DMetal, keep Steam intact") is the right thesis and this plan
keeps it. What it lacks is verification. It reasons from plausible architecture rather than from Valve's own
metadata, Apple's licence text, and measured results, and that produces **one plan-breaking error, one false citation,
and seven material omissions**.

## Severity legend
🔴 plan-breaking · 🟠 material · 🟡 refinement

---

### 🔴 G-1 — "Use native macOS Steam and `steam://run/730`" cannot work

**Prior doc, §9:** *"Do not replace Steam… The launcher should ultimately execute the normal Steam launch flow:
`CS2-Mac → Steam.app → steam://run/730`."* It lists this as "a major design principle."

**Reality (CONFIRMED):** appid 730 is `common.oslist = "windows,linux"`; the storefront API returns
`platforms.mac = false`; the store page has only `win` and `linux` system-requirement tabs. **There is no macOS
executable in any CS2 depot.** macOS Steam can never launch it.

**Proven on the target machine.** This Mac has an `appmanifest_730.acf` and 60 GB in `steamapps/downloading/730`.
Byte arithmetic against Valve's depot table shows exactly what macOS Steam queued:

| Depot | OS filter | Contents | Download bytes |
|---|---|---|---|
| 2347770 | *(all)* | game content, vpk/assets | 53,938,731,200 |
| 2347774 | *(all)* | content | 949,604,816 |
| 2347772 | macos | CS:GO-era stub | 1,696 |
| *(stub)* | — | — | 64 |
| **sum** | | | **54,888,337,776** = the manifest's `BytesToDownload` exactly |
| **2347771** | **windows** | **`.+?\.(dll\|exe)` — every executable** | **NOT QUEUED (4.99 GB)** |

macOS Steam queued the OS-agnostic asset depots plus a 1.7 KB macOS stub and **omitted the depot that contains
`cs2.exe`**. Completing that download would yield 63.9 GB of assets and zero executables. `StateFlags 1026` =
`StateUpdateStarted|StateUpdateRequired` with no running/downloading bit — queued, never scheduled. It is not a
network problem and cannot be fixed by "verify files."

**Correction:** the **Windows Steam client must run inside the bottle**, and it must be the thing that installs,
owns, updates and launches CS2. This is not a detail — it inverts the prior doc's stated design principle, changes
the launcher's job from "shell out to Steam.app" to "manage a Windows Steam install", and adds the whole
Steam-in-Wine failure surface (login, Steam Guard, overlay, self-update) to the plan. → tasks **T-004 … T-008**.

---

### 🔴 G-2 — The one CS2-specific citation is the wrong game

**Prior doc, §16 + Sources:** cites `github.com/alien-agent/cs2-macos-patcher` as *"a current GitHub project [that]
demonstrates CS2-specific patching of a Windows game running under CrossOver on Apple Silicon"* and builds the
strategic recommendation *"small compatibility fixes can be layered on top of an existing runtime"* on top of it.

**Reality (CONFIRMED):** in that repository **"CS2" means *Cities: Skylines II***. It IL-patches
`Colossal.IO.dll` / `Game.dll` / `PDX.SDK.dll` under `Cities2_Data/Managed`. It has nothing to do with
Counter-Strike 2.

**Why this matters beyond a bad footnote:** the prior doc's §6 "CS2-specific compatibility layer" and §16 strategy
are the only justification for a *patching* posture — and patching is precisely the activity Valve's VAC FAQ
describes as cheating (*"modifications to a game's core executable files and dynamic link libraries"*). The false
citation pointed the plan at its single most dangerous workstream. **Delete the patching strategy entirely.** The
legitimate substitutes are bottle configuration, DLL overrides of *Wine's own* libraries, environment variables and
CS2 console/launch options — all of which leave Valve's files byte-identical. → **T-021**, `docs/06-legal-and-policy.md`.

---

### 🟠 G-3 — "The graphics problem is largely solved by D3DMetal" is a 2024 answer

**Prior doc, §3.2 / §17 / §27:** treats D3DMetal as *the* graphics component and says a custom DirectX
implementation is unnecessary because "D3DMetal already solves the core problem."

**Reality (2026):** there are now **three** competing DX11 backends on macOS and the winner is machine-dependent.

| Backend | Path | Status 2026-08 | Evidence |
|---|---|---|---|
| **D3DMetal 3.0 / 4.0b2** | DX11/12 → Metal | Apple, closed source, in CrossOver 26.3.0 & GPTK 3.0 | CodeWeavers' own CS2 tip: *Graphics = D3DMetal, Sync = MSync* |
| **DXMT 0.72** | DX11 → Metal | open source, shipped in CrossOver 26.3.0 | On one M3/8 GB: **DXMT ≈120 FPS vs D3DMetal ≈11 FPS**. On an M4 Max, D3DMetal won and DXMT stuttered. |
| **DXVK-macOS 1.10.3** | DX11 → Vulkan → MoltenVK → Metal | **frozen since 2023**; upstream DXVK is 3.0.2 | same M3: 120 → 30 FPS decay |

**Correction:** backend selection is an **experiment with a measured outcome per machine**, not an architectural
constant. The plan makes it a first-class benchmarked decision (**T-012**) instead of a given.

---

### 🟠 G-4 — The licensing question is absent, and the common answer to it is wrong

The prior doc has no legal section. It proposes shipping a launcher that "configures D3DMetal" without asking
whether D3DMetal may be redistributed.

**Reality (CONFIRMED, licence text extracted):** Apple's *Software License Agreement for Game Porting Toolkit*
**§2A(iii)** grants the right to *"distribute the Apple Software solely for non-commercial purposes"*, and **§2C**
states *"the Framework in its entirety or any part of the Redistributables may be distributed separately from the
Apple Software"* — subject to the non-commercial restriction, Apple-branded hardware only, and no reverse
engineering. Gcenx ships exactly this via `brew install --cask game-porting-toolkit`.

This **contradicts the widely repeated claim** that GPTK is evaluation-only and can never be redistributed. But it
also imposes a hard constraint the prior doc never states: **the moment this project is monetised, the right
evaporates** (which is why CodeWeavers needs its own bilateral agreement with Apple to ship D3DMetal in the €74
CrossOver). A residual grey zone remains: the §2A(i) *use* grant is worded "developing, testing, or evaluating video
games", which is not literally "playing a shipped game." → `docs/06-legal-and-policy.md`, **T-002**.

---

### 🟠 G-5 — VAC is rated "Critical / Unknown"; the evidence supports "Medium / manageable"

**Prior doc, §7/§8/§23:** makes VAC the project's central uncertainty, rates it **Critical / Unknown**, and defines
project success as Level 3 VAC-protected competitive play, warning that Valve may require Windows kernel
functionality Wine cannot reproduce.

**Reality:** the structural argument runs the other way. **CS2 ships a native Linux build with VAC enabled** and is
Steam-Deck-"Playable" — VAC demonstrably does not require Windows kernel primitives. Valve itself serves CS2 through
GeForce NOW cloud VMs. Valve's VAC FAQ states hardware configurations and drivers do not trigger bans. No credible
report of a Wine-caused CS2 ban was found, and a documented M1 Pro CrossOver player maintains a **15,000 Premier CS
Rating**.

**Correction:** VAC is **Medium**, and the honest residual risks are *operational*, not existential — the
"VAC unable to verify game session" kick (which also happens on plain Windows) and Valve's total lack of a written
Wine policy (**UNKNOWN**, and unfixable by engineering). The correct posture is: never touch game files, use a
throwaway non-Prime account until Phase 3 passes, buy Prime (€13.29, **non-refundable**) only afterwards. The prior
doc's ordering would have you validate competitive play *before* establishing that ordering. → **T-018 … T-020**.

---

### 🟠 G-6 — Rosetta 2 is a dated deadline, not a vague "sustainability" note

**Prior doc, §14:** *"Apple has also been changing the long-term Rosetta strategy, so the project's sustainability
across future macOS releases needs monitoring."*

**Reality (CONFIRMED, Apple's own wording):** Rosetta is available as a general-purpose translation tool
**through macOS 27**, after which only *"a subset … aimed at supporting older unmaintained gaming titles"* remains.
The entire stack — Wine, the Windows Steam client, `cs2.exe` — is x86-64 under Rosetta. The obvious escape route,
**ARM64EC Wine + FEX**, is blocked by Apple Silicon's **16 KB page size** (Wine needs 4 KB; Wine 11.0's 4 KB
simulation is documented as "simple applications" only).

**Correction:** this is the project's **highest-severity long-term risk** and it has a date. It gets a monitored
trigger and a written exit plan, not a footnote. → `docs/05-risk-register.md` R-1, **T-031**.

---

### 🟡 G-7 — No measured baseline; the performance targets are invented

The prior doc sets targets (60 / 90–120 / 120+ FPS) with no reference to any published measurement, and cites one
2024 CodeWeavers blog figure (M1 Pro ≈ 40 FPS) that 2026 data has long overtaken.

**2026 measurements now available:** M5 Pro 48 GB, GPTK 4.0b2, D3DMetal+MSync, *Ancient* benchmark → **190 avg /
140 1%-low @1080p**, 145/110 @1440p · M4 Pro 24 GB → 122 @1080p medium · M4 Max → 160–200 @1440p medium ·
M1 Air 8 GB → 50 @1080p · **M2 Max 96 GB at native Retina 3024×1964 → 23** · MacBook **Air** M4 16 GB → 30–40
(thermal, fanless).

Two things follow that the prior doc misses: **Retina resolution is a ~4× tax** (it identifies this qualitatively in
§13 but doesn't quantify it), and **averages are meaningless without a named benchmark map** — *Ancient* runs
25–30 % heavier than *Dust2* on identical hardware. → `docs/07-benchmark-protocol.md`, **T-011**.

---

### 🟡 G-8 — The known-bug catalogue is missing

The prior doc lists *categories* to test (audio, input, networking). It does not list the **specific, already-solved
failures** every CS2-on-Mac user hits, so the plan would rediscover them:

* **Audio crackling** → set `cs2.exe` to **Windows 8** in the bottle's Wine configuration (permanent fix).
* **Black screen at launch** → `CS2Video.txt` with `fullscreen = 0`.
* **Shader-compilation stutter on first exposure to each map** — the dominant 1%-low killer; benchmarks are invalid
  until the map has been played through twice.
* **Alt-tab kills audio**; **Steam overlay costs FPS**; **`SteamNetworkingSockets` thread starvation → net jitter**;
  **AWDL (AirDrop/Handoff) jitter on Wi-Fi**.

→ folded into **T-009**, **T-013**, **T-015**, `docs/04-test-matrix.md`.

---

### 🟡 G-9 — Tooling status is stale, and alternatives are dismissed too early

* **Whisky** — archived 2025-05-11 (author cited burnout and "Whisky harms Wine on Mac", not legal pressure). Not in
  the prior doc at all, but it is the tool most guides still point at. Successor: **Sikarugir** (the renamed
  Kegworks). **CXPatcher** is being replaced by **Procyon**.
* **Boot Camp on Apple Silicon: impossible** (CONFIRMED, Apple lists Intel Macs only) — worth stating so nobody
  proposes it.
* **CS2 *is* on GeForce NOW** (NVIDIA's own catalogue JSON: appid 730, `AVAILABLE`, `isFullyOptimized: true`).
  The prior doc mentions cloud gaming only as a NO-GO consolation prize. It is in fact a legitimate, zero-engineering
  competitive path and must be benchmarked **against** the bottle, not after it. → **T-003**, **T-030**.

---

## What the prior document got right (kept verbatim in spirit)

1. Don't port CS2; don't write a Windows compatibility layer; don't build an emulator or a VM. ✅
2. Don't touch VAC. ✅ (strengthened: don't touch game files either)
3. Treat online/competitive as a first-class requirement, not a final feature. ✅
4. Judge on frametime and input latency, not average FPS. ✅
5. Render below native Retina resolution. ✅ (now quantified: ~4× cost)
6. Data-driven configuration profiles, thin CS2-specific layer, diagnostics + compatibility report. ✅
7. Its risk-register *shape* is good — the scores needed evidence, not replacement.
