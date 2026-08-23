# 03 — Development plan

**34 tasks · 6 phases · ~7 calendar weeks of part-time work to a validated competitive setup, +4 weeks to a shippable `CS2Kit`.**

How to read a task: every task states **why it exists**, its **dependencies**, **concrete steps**, a **deliverable
artefact committed to this repo**, and a **binary acceptance test**. Nothing is "done" because it feels done.

Effort is in **focused hours** (h) or **days** (d, = 6 h). `[GATE]` tasks stop the project if they fail.

| Phase | Theme | Tasks | Effort | Gate |
|---|---|---|---|---|
| 0 | Decide and prepare — cheapest possible answers first | T-001…T-005 | ~1.5 d | T-003 |
| 1 | Get CS2 running at all | T-006…T-010 | ~2 d | T-010 |
| 2 | Measure, then tune (backend bake-off) | T-011…T-017 | ~3 d | — |
| 3 | Online, competitive, VAC | T-018…T-022 | ~2 d + soak | T-020 |
| 4 | Build `CS2Kit` (the only thing worth owning) | T-023…T-029 | ~8 d | — |
| 5 | Keep it alive | T-030…T-034 | ongoing | — |

---

# Phase 0 — Decide and prepare

*Goal: spend €0 and 1.5 days establishing that this project should exist, and clear the traps that will otherwise
waste a week.*

## T-001 · Deal with the 65 GB executable-less "installed" CS2 `[do this first]`
**Why:** as of 2026-08-23 18:10 the macOS Steam install **completed** — `StateFlags 4` (fully installed),
`SizeOnDisk 66,024,731,334`, `BytesToDownload 0`, and a `LastPlayed` timestamp. It is nonetheless **unplayable**:
`InstalledDepots` contains 2347770 / 2347772 / 2347774 / 2347779 and **not 2347771**, so there is no `cs2.exe`,
`engine2.dll`, `client.dll`, `tier0.dll` or `steam_api64.dll` anywhere on disk. The only 9 `.exe` files present
(`resourcecompiler`, `vrad3`, `source1import`, `dmxconvert`, `cs_mdl_import`, …) come from depot **2347779**, the
Workshop Tools DLC (`optionaldlc 2279721`) — authoring tools, not the game.
**This is worse than a stalled download: Steam believes the install is complete, so "Verify integrity of game files"
will not repair it.** Free space is 90 GiB and the correct in-bottle install needs ~72 GB — so this must be resolved
before Phase 1 either way. Prefer **Option A2 in T-008**, which reuses the 58 GB you already have.
**Depends:** —
**Steps**
1. Quit Steam completely (`osascript -e 'quit app "Steam"'`; confirm no `steam_osx` process).
2. Preserve the evidence: `cp "$STEAM/steamapps/appmanifest_730.acf" docs/reference/appmanifest_730.acf.before`.
3. **Decide between two routes — try A2 first (T-008):**
   * **Reuse route (preferred).** Keep the 58 GB `csgo/` asset tree; depot 2347770 is **OS-agnostic** and is exactly
     the same content the Windows install needs. Only the 4.99 GB executable depot is missing. Saves ~60 GB of
     download and fits in current free space. → T-008 Option A2.
   * **Clean route (fallback).** Uninstall CS2 from macOS Steam (or delete the `installdir` + `appmanifest_730.acf`),
     freeing ~65 GB → ~155 GiB free, then let the in-bottle Windows Steam download all ~72 GB from scratch.
4. Either way, resolve the `installdir` collision: macOS Steam and in-bottle Windows Steam both want
   `steamapps/common/Counter-Strike Global Offensive`. Do not let two clients manage the same folder unless you are
   deliberately doing A2. Note the leftover CS:GO-era `csgo/`, `platform/`, `installscript.vdf` in that folder too.
5. Set macOS Steam's CS2 to **"Only update this game when I launch it"** so it cannot re-queue the useless depots.
6. Re-run `scripts/preflight.sh`.
**Deliverable:** `docs/reference/appmanifest_730.acf.before` + the chosen route recorded.
**Acceptance:** either ≥ 150 GiB free (clean route), or the asset tree is preserved and the route is documented (A2).
**Effort:** 0.5 h · **Risk:** low.

## T-002 · Fix the project's legal frame before writing code
**Why:** the deliverable's licence model determines whether it may ship D3DMetal at all (gap G-4). Decide once, up front.
**Depends:** —
**Steps**
1. Read `docs/06-legal-and-policy.md` in full.
2. Choose and record a **binding** answer to: *is `CS2Kit` ever monetised?* If yes → it may **not** redistribute
   D3DMetal and must depend on the user's own CrossOver licence.
3. Choose the licence for this repo's own code (recommend **GPL-3.0** or **MIT**; note Wine is LGPL-2.1).
4. Write the "what this tool will never do" section: no game-file modification, no VAC interaction, no bundled Steam,
   no account automation.
**Deliverable:** `LICENSE`, and the *Distribution model* section of `docs/06-legal-and-policy.md` filled in.
**Acceptance:** a reader can answer "may this project ship `D3DMetal.framework`?" with yes/no and a licence clause reference.
**Effort:** 2 h · **Risk:** medium — the §2A(i) "developing, testing, or evaluating" wording is a genuine grey zone.

## T-003 · `[GATE]` Cheap-alternative bake-off — earn the right to build this
**Why:** CS2 is on **GeForce NOW** (NVIDIA catalogue: appid 730, `AVAILABLE`, `isFullyOptimized: true`), and Steam
Remote Play / Moonlight from any Windows box also work. If one of those hits your latency bar, the honest answer is
"don't build a bottle." The prior analysis relegated these to a NO-GO consolation prize; they must be measured **first**
because they cost hours, not weeks.
**Depends:** —
**Steps**
1. Run GFN CS2 on this Mac on your normal network. Measure with `cl_showfps 4` / `net_graph 1`: ping to the GFN
   region, `sv`/`var`, and subjective aim feel in an aim-training map. 30 minutes minimum.
2. Record your household round-trip to the nearest GFN datacentre (`ping`, `mtr`) — cloud adds ~15–40 ms of
   end-to-end latency on top of it, which is decisive for a tapping/counter-strafing game.
3. If a Windows PC is available, repeat with Sunshine + Moonlight on LAN (typically 5–10 ms added).
4. Score each path on: input feel, cost/month, setup hours, Premier eligibility (**UNKNOWN** for GFN — verify by
   attempting one competitive queue), and independence from Apple's Rosetta timeline.
**Deliverable:** `docs/reference/alternatives-scorecard.md` with your own numbers, not the internet's.
**Acceptance / GATE:** you can write one sentence: *"I am building a local bottle because <alternative> failed on
<measured criterion>."* If no alternative fails, **stop the project here** and document that outcome — it is a
successful result.
**Effort:** 3 h · **Risk:** low.

## T-004 · Choose the runtime host: CrossOver vs. DIY Wine+GPTK
**Why:** this decides the entire maintenance burden. There is no universally right answer; there is a right answer
for *this* project's licence model (T-002).
**Depends:** T-002
**Steps**
1. Build a comparison table:
   * **CrossOver 26.3.0** (€74, 14-day trial) = Wine 11.0 + D3DMetal 3.0 + DXMT 0.72 + vkd3d 1.18, MSync,
     GUI bottle management, CodeWeavers support, **CS2 rated "Runs Well"**, and a CS2-specific published tip.
   * **DIY**: Gcenx `brew install --cask game-porting-toolkit` (GPTK 3.0-3) or **Sikarugir** (ex-Kegworks) — free,
     scriptable, redistributable under the non-commercial GPTK terms, but you own every regression.
2. Note the dead ends so nobody revisits them: **Whisky is archived** (2025-05-11); **CXPatcher** is superseded by
   **Procyon**; **Boot Camp does not exist on Apple Silicon**.
3. Recommended: **start on the CrossOver trial** to get a known-good reference configuration fast, then reproduce it
   on the free stack in Phase 4 so `CS2Kit` has no paid dependency.
**Deliverable:** `docs/reference/runtime-decision.md` (decision + reasoning + fallback).
**Acceptance:** the chosen host is installed and `wine --version` (or CrossOver's bottled equivalent) reports a version.
**Effort:** 2 h · **Risk:** low.

## T-005 · Freeze the environment of record
**Why:** every future benchmark and bug report is meaningless without the exact stack it was produced on. Also
protects against "it broke and I don't know what changed."
**Depends:** T-004
**Steps**
1. Extend `scripts/preflight.sh` to emit a machine-readable snapshot: macOS build, chip, core split, GPU cores, RAM,
   free disk, Metal version, Rosetta present, runtime host + version, D3DMetal/DXMT/MoltenVK versions, CS2 buildid.
2. Commit the first snapshot as `docs/reference/env-snapshot-0.json`.
3. **Disable automatic macOS updates** for the duration. A macOS point release is an uncontrolled variable and, past
   macOS 27, an existential one (R-1).
**Deliverable:** `scripts/preflight.sh --json` + `env-snapshot-0.json`.
**Acceptance:** the snapshot regenerates identically twice in a row.
**Effort:** 3 h · **Risk:** low.

---

# Phase 1 — Get CS2 running at all

*Goal: `cs2.exe` reaches the main menu and a bot match, from a documented, reproducible procedure.*

## T-006 · Create the bottle
**Why:** the foundation. Getting Windows version, architecture and DLL policy right here prevents most Phase 2 mysteries.
**Depends:** T-004, T-001
**Steps**
1. Create a **64-bit** bottle, Windows 10 default.
2. Do **not** install a Windows Steam via winetricks recipes that bundle old runtimes; install nothing beyond what
   Steam's own installer requests.
3. Record every deviation from defaults in a config file that will later become the machine-readable bottle recipe.
4. Confirm the bottle's `C:` drive is **not** on a case-sensitive volume unless you have verified Steam tolerates it.
**Deliverable:** `profiles/bottle-recipe.yaml` (v0) — Windows version, arch, DLL overrides, env vars, graphics backend.
**Acceptance:** `winecfg` opens; `wine cmd` runs; the bottle path is recorded in the env snapshot.
**Effort:** 1 h · **Risk:** low.

## T-007 · Install the Windows Steam client inside the bottle
**Why:** this is the corrected architecture (gap G-1). CS2 launches with `-steam`, uses `usemms=1` matchmaking and
Steam Datagram Relay; **the game will not function without a running Steam client of the same platform.**
**Depends:** T-006
**Steps**
1. Download `SteamSetup.exe` from Valve and install it into the bottle.
2. Log in. Expect a **Steam Guard** prompt — have the mobile authenticator ready. This is a common first-run wall.
3. Verify: library loads, friends list appears, the client self-updates without crashing.
4. **Turn the Steam overlay OFF** globally for now (it measurably costs FPS; re-enable it deliberately in T-016).
5. Set the Steam library folder to a path with ≥ 80 GB free.
**Deliverable:** `docs/reference/steam-in-bottle.md` — the exact click path, plus every error hit and its fix.
**Acceptance:** the in-bottle Steam client shows your library and stays up for 10 minutes idle without crashing.
**Effort:** 3 h · **Risk:** medium — Steam-in-Wine login/self-update is a known friction point.

## T-008 · Install CS2 from inside the bottle
**Why:** only the in-bottle Windows client produces an install it can subsequently **own, verify and update**
(`steamcmd @sSteamCmdForcePlatformType windows` can fetch the bytes, but whether the resulting manifest is adopted by
the in-bottle client is **UNKNOWN** — do not build the plan on it).
**Depends:** T-007, T-001
**Option A2 (try first, timebox 2 h) — reuse the 58 GB of assets already on disk.**
The macOS install left depot **2347770** (62.8 GB staged, OS-agnostic content) and **2347774** complete and correct.
Only depot **2347771** (4.99 GB of `.exe`/`.dll`) is missing. Two ways to close that 5 GB gap:
  * point the in-bottle Windows Steam at the existing library folder (map a Wine drive to
    `~/Library/Application Support/Steam/steamapps`) and let it reconcile — ideally it fetches only the missing
    executable depot;
  * or `steamcmd +@sSteamCmdForcePlatformType windows +login <user> +app_update 730 validate` into that tree.
**Both have a real failure mode:** the Windows client may reject or fully re-validate a library populated by the
macOS client, and whether the in-bottle client subsequently *owns* the install for updates is **UNKNOWN**
(`research/steam-vac-findings.md` §2). Verify by launching the game and by forcing one update cycle. If either
fails, abandon A2, fall back to T-001's clean route, and record the result — it is publishable, nobody has documented it.

**Option A1 (fallback, known-good) — clean install inside the bottle. Steps:**
1. Install appid 730 from the in-bottle client. Budget **~60 GB download / ~72 GB on disk**.
2. Watch that depot **2347771** ("cs2 windows", `.+?\.(dll|exe)`, 4.99 GB) is included — it is the depot macOS Steam
   omitted. Confirm afterwards: `ls game/bin/win64/cs2.exe`.
3. Record the resulting `buildid` (public branch at time of writing: **24828357**, 2026-08-19) into the env snapshot.
4. Run *Verify integrity of game files* once and confirm 0 files re-acquired — this is your baseline proof the install
   is byte-identical to Valve's, which is the state VAC expects and which T-021 forbids you from ever leaving.
**Deliverable:** `docs/reference/install-log.md` incl. final `du -sh` and the buildid.
**Acceptance:** `cs2.exe` exists in `game/bin/win64/` **and** Steam's verify reports "all files successfully validated."
**Effort:** 1 h active + download time · **Risk:** medium (disk, download stalls).

## T-009 · First launch — apply the four known fixes before debugging anything
**Why:** four failure modes account for most first-launch reports; hitting them blind costs a day each.
**Depends:** T-008
**Steps**
1. Launch options, minimal and boring: `-novid -nojoy -console`. **Do not use `-vulkan`** (see T-012).
2. **Black screen at launch** → create `CS2Video.txt` with `fullscreen = 0` (windowed first, fullscreen later).
3. **Audio crackling** → set `cs2.exe` to **Windows 8** in the bottle's application-compatibility settings. This is
   the documented permanent fix, not a workaround.
4. **Stutter** → set Graphics = **D3DMetal**, Synchronization = **MSync** (CodeWeavers' own published CS2 tip). This
   is the baseline you must beat in T-012, not the final answer.
5. Turn **Retina/HiDPI off** in the bottle and set the game to **1920×1080** or lower. Native 3024×1964 costs ~4×
   (M2 Max @native Retina = 23 FPS).
6. If it still fails, capture `WINEDEBUG=+loaddll,+seh` output before changing anything else.
**Deliverable:** `docs/reference/first-launch.md` — what broke, what fixed it, in order.
**Acceptance:** the CS2 main menu renders and accepts mouse input.
**Effort:** 4 h · **Risk:** medium.

## T-010 · `[GATE]` Offline playable — bot match on three maps
**Why:** proves rendering, input, audio and the map/shader pipeline before any online variable is introduced.
**Depends:** T-009
**Steps**
1. Offline-with-bots on **Dust2, Mirage, Ancient** (Ancient is the heavy one — it is also the benchmark map in T-011).
2. Play each map through **twice** — the first pass is dominated by shader compilation and is not representative.
3. Check: mouse tracking feels linear, audio positional and clean, no crash across a full 30-minute session.
**Deliverable:** `docs/reference/phase1-signoff.md`.
**Acceptance / GATE:** 30 minutes of continuous bot play across 3 maps, no crash, no audio dropout, playable input.
Failure here means the stack is wrong — return to T-004 and switch runtime host before proceeding.
**Effort:** 2 h · **Risk:** low once T-009 passes.

---

# Phase 2 — Measure, then tune

*Goal: a defensible performance configuration for this machine, chosen by measurement rather than by forum consensus.*

## T-011 · Establish the benchmark protocol and take a baseline
**Why:** every published Mac CS2 FPS number is untrustworthy because the map isn't named and shader-compilation
warm-up isn't controlled. *Ancient* runs 25–30 % heavier than *Dust2* on identical hardware.
**Depends:** T-010
**Steps**
1. Implement `docs/07-benchmark-protocol.md`: fixed Workshop benchmark map (**Ancient FPS Benchmark 3472126051**;
   secondary: **Dust2 FPS Benchmark 3240880604**), 3 warm-up runs discarded, 5 measured runs, report
   **median avg FPS, median 1 % low, and the frametime p99** — never a single max.
2. Record avg / 1 % low / p99 frametime / CPU package power / GPU residency / memory pressure per run
   (`powermetrics`, `sudo powermetrics --samplers gpu_power,cpu_power` in a side terminal).
3. Baseline config = T-009 settings, 1080p, medium.
4. Sanity-check against the published field: M5 Pro 190/140 @1080p, M4 Pro 122 @1080p med, M4 Max 160–200 @1440p med,
   M1 Air 50 @1080p. An M2 Pro/32 GB should land **between the M1 Pro (~100) and the M4 Pro (~122)**. A wildly
   different number means the protocol is wrong, not the hardware.
**Deliverable:** `benchmarks/` CSV + `docs/reference/baseline.md`.
**Acceptance:** two independent baseline sessions on different days agree within **±5 %** on median avg FPS.
**Effort:** 6 h · **Risk:** medium — reproducibility is the hard part, not measurement.

## T-012 · Backend bake-off: D3DMetal vs DXMT vs DXVK vs `-vulkan`
**Why:** the single highest-leverage experiment in the project. Community data shows a **10× swing in both
directions** depending on machine (one M3: DXMT 120 vs D3DMetal 11; one M4 Max: the reverse). The prior analysis
assumed D3DMetal and skipped this.
**Depends:** T-011
**Steps**
1. Run the full T-011 protocol for each of: **D3DMetal 3.0**, **D3DMetal 4.0 beta** (via Procyon/GPTK 4 if available),
   **DXMT 0.72**, **DXVK-macOS 1.10.3**, and **CS2 `-vulkan`**.
2. Expect `-vulkan` to lose: on Apple Silicon it lands on a DXVK-macOS fork frozen at 1.10.3 and a MoltenVK with
   **no geometry shaders and no `VK_EXT_transform_feedback`**. CS2 falls back to DX11 if Vulkan init fails — check
   the console so you don't benchmark DX11 while believing you're on Vulkan.
3. Cross the winner with **MSync vs ESync**.
3b. **Record a licence column alongside FPS.** This experiment decides the project's distribution tier
   (`docs/08-cost-and-dependencies.md`): DXMT/MSync/Wine are **LGPL-2.1** → free stack, monetisable, no Apple
   entanglement; D3DMetal → free to users but binds the project to **non-commercial forever**. A backend 10 % slower
   but LGPL may be the correct product choice.
4. Record not just FPS but **hitch count** (frametime > 50 ms) — a backend that wins on average and loses on hitches
   loses outright for a tapping game.
**Deliverable:** `docs/reference/backend-bakeoff.md` — full table + a one-line verdict for this machine.
**Acceptance:** a ranked table with ≥ 5 runs per backend and an explicit winner justified by 1 % lows, not averages.
**Effort:** 1 d · **Risk:** low (worst case: the baseline stays).

## T-013 · Kill the shader-compilation stutter
**Why:** it is the dominant 1 %-low killer and it is a translation-layer artefact, not a GPU limit — i.e. it is
*addressable*, unlike raw throughput.
**Depends:** T-012
**Steps**
1. Quantify it: hitch count on **first** exposure to a map vs **third**.
2. Test whether the backend's shader cache persists across launches, where it lives, and what invalidates it
   (a CS2 update almost certainly does — feeds T-030).
3. Test a deliberate warm-up: load each map you play in offline mode after a CS2 update, before queueing.
4. Confirm `shaders_vulkan_*.vpk` presence/relevance for the chosen backend.
**Deliverable:** `docs/reference/shader-cache.md` incl. cache path and invalidation triggers.
**Acceptance:** on a warmed cache, first-minute hitch count drops **≥ 70 %** vs cold.
**Effort:** 4 h · **Risk:** medium.

## T-014 · Resolution, upscaling and the Retina tax
**Why:** the largest single performance lever on a Mac, and the most misunderstood.
**Depends:** T-012
**Steps**
1. Sweep 1280×960 stretched (the competitive default), 1600×900, 1920×1080, 2560×1440, native 3024×1964.
2. Cross with **FSR off / Quality / Balanced**.
3. Verify Retina/HiDPI is genuinely off in the bottle — a bottle silently rendering at backing-store resolution is
   the classic "why is my Mac slow" bug (M2 Max @native = 23 FPS).
4. Check external-monitor behaviour and refresh rate (**UNKNOWN** in published data — you will be generating it).
**Deliverable:** resolution/upscaler table in `docs/reference/baseline.md`.
**Acceptance:** a recommended resolution is chosen such that **1 % low ≥ 60 FPS** on Ancient.
**Effort:** 4 h · **Risk:** low.

## T-015 · Input path: raw mouse, polling, and latency
**Why:** for CS2 this outranks FPS, and **no ms-level input-latency measurement for CS2 under Wine on Apple Silicon
exists anywhere** (a genuine research gap this project can close).
**Depends:** T-012
**Steps**
1. Disable macOS pointer acceleration for the gaming mouse; verify CS2 `m_rawinput 1` actually takes effect in the bottle.
2. Set the mouse to its highest polling rate; confirm the bottle sees it.
3. Measure end-to-end latency: 240 fps phone camera on the screen, click-to-muzzle-flash frame counting, 20 trials,
   report median and spread. Compare against the **same measurement on a Windows PC or GFN** from T-003 — the number
   only means something as a delta.
4. Test USB, Bluetooth and dongle mice separately.
**Deliverable:** `docs/reference/input-latency.md` — the first public number of its kind, publish it.
**Acceptance:** ≥ 20 trials per configuration, median + IQR reported, method reproducible from the doc alone.
**Effort:** 6 h · **Risk:** medium (measurement rig fiddliness).

## T-016 · Audio and microphone
**Why:** a competitive setup without working comms is not a competitive setup; the prior analysis was right to
insist on this.
**Depends:** T-010
**Steps**
1. Confirm the **Windows 8 compat-mode** fix from T-009 holds under load.
2. Test: game audio, positional accuracy, voice out, mic in, push-to-talk, Steam's own mic test.
3. Test devices: built-in, USB headset, **AirPods (expect the worst)**, and hot-swapping mid-game.
4. Test the **alt-tab kills audio** regression explicitly, and whether the Steam overlay changes anything.
**Deliverable:** `docs/reference/audio-matrix.md`.
**Acceptance:** mic is audible to a second party in an actual match; no crackle across a 30-minute session.
**Effort:** 3 h · **Risk:** medium — AirPods/Bluetooth may simply not be viable; record that honestly.

## T-017 · Thermals and the 2-hour soak
**Why:** Mac gaming performance is a *sustained*-load question. A fanless M4 Air drops to 30–40 FPS; even a Pro chassis
throttles. Average FPS at minute 3 is marketing; minute 90 is the truth.
**Depends:** T-012
**Steps**
1. Two-hour continuous session logging FPS, frametime, CPU/GPU power, die temperature, memory pressure, swap.
2. Compare minute 5 vs minute 90 performance; on battery vs plugged in; **Low Power Mode on vs off**.
3. Log peak RSS of the whole stack (published figure: CS2 alone ≈ 6.1 GB; 32 GB should be ample — verify, don't assume).
**Deliverable:** `docs/reference/thermal-soak.md` with the time-series plot.
**Acceptance:** documented sustained-FPS figure and a stated "plugged in / on battery" recommendation.
**Effort:** 3 h (mostly unattended) · **Risk:** low.

---

# Phase 3 — Online, competitive, VAC

*Goal: answer the only question that actually matters, in the safest possible order.*

## T-018 · Account safety plan `[read before any online task]`
**Why:** risk is low but not zero, and it is asymmetric — a wrong step costs an account, not an afternoon.
**Depends:** T-010
**Steps**
1. Do **all** of Phase 3's first online steps on a **secondary, non-Prime account**.
2. **Do not buy Prime** (€13.29 / $14.99, **explicitly non-refundable**) until T-020 passes. The prior analysis had
   this ordering backwards.
3. Enforce the absolute rules from `docs/06-legal-and-policy.md`: no injected DLLs into `cs2.exe`, no game-file
   modification, no overlays beyond Steam's own, no macro software, no third-party "FPS boosters."
4. Keep Steam Guard on. Record which machine/IP the account is used from.
**Deliverable:** the *Account safety* section of `docs/06-legal-and-policy.md`, signed off.
**Acceptance:** a secondary account exists and is the only account used until T-020 passes.
**Effort:** 1 h · **Risk:** —

## T-019 · Casual online + community servers
**Why:** separates *networking* problems from *anti-cheat* problems. Doing them together makes both undebuggable.
**Depends:** T-018
**Steps**
1. Casual/Deathmatch on official servers; then a community server.
2. Watch `net_graph`: loss, choke, ping stability, and the known **`SteamNetworkingSockets` thread-starvation jitter**.
3. Test **Wi-Fi vs Ethernet**, and disable **AWDL** (AirDrop/Handoff/Sidecar) to test the documented Wi-Fi jitter source.
4. Test reconnect after a lid-close/sleep and after a network switch.
5. Confirm Steam friends, invites and lobby join work from inside the bottle.
**Deliverable:** `docs/reference/network-report.md`.
**Acceptance:** three consecutive full casual matches with **no disconnect** and ping variance within **±10 ms** of a
native macOS Steam ping to the same relay.
**Effort:** 4 h · **Risk:** medium.

## T-020 · `[GATE]` VAC-protected competitive validation
**Why:** **this is the project's actual success criterion.** Everything before it is instrumentation.
**Depends:** T-019
**Steps**
1. Queue **Competitive** on the secondary account. Complete a full match.
2. Watch specifically for: *"VAC unable to verify game session"* (note: this also occurs on plain Windows — one
   occurrence is not a verdict), mid-match kicks, "Untrusted" messaging, or any account warning.
3. Repeat for **5 matches across at least 3 separate days**, with a bottle restart and a Mac reboot in between.
4. If clean → buy Prime, migrate to the main account, run 5 **Premier** matches.
5. Log every anomaly with timestamp, buildid and env snapshot.
**Deliverable:** `docs/reference/vac-validation.md` — a dated log, not a conclusion.
**Acceptance / GATE:** **10 consecutive matches (5 Competitive + 5 Premier) with zero VAC/anti-cheat kicks and zero
account warnings.**
* **GO** → Phase 4.
* **CONDITIONAL GO** → matchmaking works but kicks recur → ship as "casual/practice only", never advertise
  competitive readiness.
* **NO-GO** → systematic kicks → stop; the honest answer is the T-003 alternatives. This is a **policy** wall, not an
  engineering one; do not attempt to engineer around it.
**Effort:** 6 h over ≥ 3 days · **Risk:** **the project's central unknown** — mitigated, not eliminated, by the fact
that CS2 ships a native Linux build with VAC, that Valve serves CS2 via GFN VMs, and that a documented M1 Pro
CrossOver player holds a 15,000 Premier CS Rating.

## T-021 · Codify "never modify game files" as an enforced invariant
**Why:** the prior analysis's patching strategy came from a mis-cited repo (gap G-2), and Valve's VAC FAQ names
*"modifications to a game's core executable files and dynamic link libraries"* as cheating. This is the one way to
turn a low risk into a ban.
**Depends:** T-020
**Steps**
1. Record SHA-256 for every file under `game/bin/win64/`.
2. Add a `CS2Kit doctor` check that recomputes them and **refuses to launch** on mismatch, telling the user to run
   Steam's verify.
3. Document the *legitimate* configuration surface: bottle settings, Wine DLL overrides (Wine's own DLLs only),
   environment variables, CS2 launch options, in-game console/`autoexec.cfg`. Nothing else.
**Deliverable:** `scripts/verify-game-integrity.sh` + a manifest of hashes.
**Acceptance:** the script detects a deliberately touched file in a scratch copy and exits non-zero.
**Effort:** 3 h · **Risk:** low.

## T-022 · Competitive-readiness sign-off
**Why:** converts scattered evidence into one publishable claim with its caveats attached.
**Depends:** T-020, T-015, T-016, T-017
**Steps** Assemble: sustained FPS, 1 % lows, input-latency delta vs. native, comms verdict, network stability, VAC log.
**Deliverable:** `docs/reference/competitive-readiness.md`.
**Acceptance:** a single honest paragraph a stranger can act on, with every number sourced to a task.
**Effort:** 2 h · **Risk:** low.

---

# Phase 4 — Build `CS2Kit`

*Goal: turn the validated procedure into software. Scope discipline is the whole game here — everything Phases 1–3
proved is knowledge; `CS2Kit` is just the automation of that knowledge.*

> **Scope rule:** `CS2Kit` **configures and diagnoses**. It never patches the game, never wraps Steam authentication,
> never implements graphics, and never touches VAC.

## T-023 · Specify `CS2Kit` v0.1 (CLI first, no GUI)
**Why:** a CLI is testable, scriptable and CI-able; a SwiftUI app is a distraction until the CLI's behaviour is
proven. The prior analysis started at "native SwiftUI launcher", which front-loads the least valuable part.
**Depends:** T-022
**Steps** Define commands: `cs2kit doctor` (env + integrity + config audit), `cs2kit bottle create|repair`,
`cs2kit config apply <profile>`, `cs2kit bench`, `cs2kit report` (redacted, shareable diagnostics bundle).
**Deliverable:** `docs/cs2kit-spec.md` with exact CLI surface, exit codes, and file layout.
**Acceptance:** every command maps to a Phase 1–3 procedure that is already documented and proven.
**Effort:** 4 h · **Risk:** low.

## T-024 · `cs2kit doctor`
**Why:** the highest-value 200 lines in the project — most user reports are environment problems, and `doctor` turns
a support thread into a paste.
**Depends:** T-023
**Steps** Check macOS version and the **Rosetta-27 horizon**, chip/RAM/GPU, **free disk ≥ 80 GB**, runtime host +
version, backend availability (D3DMetal / DXMT / DXVK), CS2 buildid, game-file integrity (T-021), bottle deviations
from the recipe, AWDL state, Low Power Mode, Retina/HiDPI state, Steam overlay state. Each check: PASS / WARN / FAIL
+ a one-line fix.
**Deliverable:** working `cs2kit doctor` + golden-output test.
**Acceptance:** on a deliberately broken bottle it identifies ≥ 5 seeded faults with correct remediation text.
**Effort:** 2 d · **Risk:** low.

## T-025 · Declarative bottle recipe + `bottle create`
**Why:** reproducibility. "It works on my Mac" must be a file, not a memory.
**Depends:** T-024
**Steps** Promote `profiles/bottle-recipe.yaml` to the source of truth (Windows version, per-exe compat mode,
DLL overrides, backend, sync mode, env vars, launch options, resolution, HiDPI). Implement create/apply/diff.
**Deliverable:** `cs2kit bottle create` reproducing the Phase 1 bottle from scratch.
**Acceptance:** a **fresh bottle built only from the recipe reaches the CS2 main menu with no manual step.**
**Effort:** 2 d · **Risk:** medium.

## T-026 · `cs2kit bench`
**Why:** makes T-011's protocol executable so that regressions after a CS2/macOS update are *detected*, not felt.
**Depends:** T-025, T-011
**Steps** Automate warm-up, runs, parsing, and a versioned results row keyed by env snapshot + CS2 buildid.
**Deliverable:** `cs2kit bench` + `benchmarks/results.csv` schema.
**Acceptance:** re-running on an unchanged machine reproduces the stored median within **±5 %**.
**Effort:** 1.5 d · **Risk:** medium.

## T-027 · Profiles that describe *situations*, not chip names
**Why:** the prior analysis proposed `m1.yaml … m5.yaml`. The measured variance is driven by **backend × chassis
(fanned vs fanless) × resolution × macOS build**, not by chip family — an M4 *Air* behaves like a weak machine and an
M3 with DXMT beats an M3 with D3DMetal by 10×.
**Depends:** T-026
**Steps** Ship 3 profiles: `competitive-lowest-latency`, `balanced-1080p`, `thermal-limited` (fanless/battery).
Each records *why* each value is set and which task measured it. Chip detection only selects a **starting point**;
`cs2kit bench` refines it.
**Deliverable:** `profiles/*.yaml` with provenance comments.
**Acceptance:** each profile's claimed numbers are reproducible via `cs2kit bench` on this machine.
**Effort:** 1 d · **Risk:** low.

## T-028 · `cs2kit report` — redacted diagnostics bundle
**Why:** enables community contribution of the data this ecosystem lacks (nobody publishes 1 % lows or latency).
**Depends:** T-024
**Steps** Bundle env snapshot + config + bench results + integrity result. **Redact** SteamID, account name, paths
containing the username, IPs, MAC addresses. Print exactly what will be shared before writing.
**Deliverable:** `cs2kit report` producing a shareable file.
**Acceptance:** a security review of a real bundle finds **zero** personal identifiers.
**Effort:** 1 d · **Risk:** medium (privacy defects are the embarrassing kind).

## T-029 · Documentation + honest positioning
**Why:** the project's credibility rests on not overclaiming, especially about VAC.
**Depends:** T-022…T-028
**Steps** Install guide, troubleshooting keyed to the 18 known failure modes, a compatibility matrix seeded with this
machine's data, and a plainly worded statement: *what is measured, what is inferred, what is unknown, and that
using a compatibility layer is at the user's own risk with no Valve endorsement.*
**Deliverable:** `docs/user-guide.md`, `docs/troubleshooting.md`, `docs/compatibility-matrix.md`.
**Acceptance:** a Mac-owning friend who has never used Wine reaches a bot match following the guide alone.
**Effort:** 1.5 d · **Risk:** low.

---

# Phase 5 — Keep it alive

*Goal: survive the two forces that kill projects like this — CS2 updates and Apple.*

## T-030 · CS2 update watch + post-update regression drill
**Why:** CS2 ships frequently; each build can invalidate the shader cache and can break the bottle. Whether any CS2
patch has ever broken a bottle is currently **UNKNOWN** — this task generates that data.
**Depends:** T-026
**Steps** Poll Valve's appinfo/news for `public` branch `buildid` changes; on change, run `cs2kit doctor` +
`cs2kit bench` + a 1-match smoke test, and append a row to the compatibility matrix.
**Deliverable:** `scripts/watch-cs2-build.sh` + a changelog of build → outcome.
**Acceptance:** a buildid change triggers the drill within 24 h and produces a matrix row.
**Effort:** 4 h · **Risk:** low.

## T-031 · Rosetta-27 exit plan `[strategic]`
**Why:** **the highest-severity risk in the register (R-1) and the only one with a date.** Apple states Rosetta is
available as a general-purpose translation tool **through macOS 27**, after which only *"a subset … aimed at
supporting older unmaintained gaming titles"* survives. This stack is x86-64 top to bottom.
**Depends:** —
**Steps**
1. Track quarterly: whether CS2 qualifies for the "older unmaintained gaming titles" carve-out (**it will not** — CS2
   is actively maintained, which is the uncomfortable reading); ARM64EC Wine + FEX progress against Apple Silicon's
   **16 KB page size**; whether Wine's 4 KB-page simulation ever moves beyond "simple applications"; any Apple
   statement extending Rosetta.
3. Pre-write the decommission notice and the migration recommendation (T-003 alternatives) so it can ship the day the
   news lands.
**Deliverable:** `docs/rosetta-watch.md`, reviewed quarterly with a dated entry each time.
**Acceptance:** a dated entry exists for the current quarter, every quarter.
**Effort:** 2 h/quarter · **Risk:** **critical, unavoidable, external.**

## T-032 · macOS release-candidate testing
**Why:** a macOS point release is an uncontrolled variable; test it on a spare volume before it lands on the machine
you play on.
**Depends:** T-024
**Steps** Install the macOS beta to a separate APFS volume, run `doctor` + `bench` + smoke test, publish the result
before the public release.
**Deliverable:** a compatibility-matrix row per macOS beta.
**Acceptance:** the matrix has a row for the current beta before its public release.
**Effort:** 3 h per release · **Risk:** low.

## T-033 · Community data intake
**Why:** the ecosystem's single biggest gap is measured data (1 % lows, latency, per-chip backend winners). Collect
`cs2kit report` bundles and publish the aggregate; this is the project's most durable contribution.
**Depends:** T-028
**Deliverable:** an aggregated public compatibility matrix.
**Acceptance:** ≥ 10 external bundles ingested, with M-series chip and backend coverage stated.
**Effort:** ongoing · **Risk:** low.

## T-034 · Quarterly upstream tracking
**Why:** every dependency is moving: CrossOver releases, D3DMetal 4.x, DXMT, MoltenVK (geometry shaders and
`VK_EXT_transform_feedback` are still missing — if either lands, revisit T-012), DXVK-macOS (**frozen at 1.10.3**;
if it ever un-freezes, revisit), Sikarugir/Procyon/Heroic.
**Depends:** —
**Deliverable:** a dated section in `docs/rosetta-watch.md` (rename to `docs/upstream-watch.md`).
**Acceptance:** one dated review per quarter.
**Effort:** 2 h/quarter · **Risk:** low.

---

## Critical path

```
T-001 ─┐
T-002 ─┼─> T-004 ─> T-005 ─> T-006 ─> T-007 ─> T-008 ─> T-009 ─> T-010[GATE]
T-003[GATE]                                                          │
                                                                     ▼
                                        T-011 ─> T-012 ─> T-013/14/15/16/17
                                                             │
                                                             ▼
                                          T-018 ─> T-019 ─> T-020[GATE] ─> T-021 ─> T-022
                                                                                      │
                                                                                      ▼
                                                                    T-023 ─> T-024 ─> T-025 ─> T-026 ─> T-027/28/29
                                                                                                          │
                                                                                                          ▼
                                                                                             T-030 … T-034 (forever)
```

**Three gates, in ascending order of consequence:** T-003 (should this exist at all?), T-010 (does it run?),
**T-020 (does it count?)**. T-031 runs in parallel from day one and can end the project from the outside at any time.
