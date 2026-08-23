# 03 — Development plan (final, ready to implement)

**Stack is decided. No comparisons, no trials, no paid software.**

```
cs2.exe (Windows x64)  →  Windows Steam client  →  Wine 11.15 staging (Gcenx tarball, LGPL-2.1)
                                                    + DXMT v0.80 (MIT, DX11→Metal)
                                                    + MSync (LGPL-2.1)
                                                    →  Rosetta 2  →  Metal 4  →  M2 Pro
```

Everything is free software. Nothing here costs money. `CS2Kit` may be licensed however we like.
**Both components are downloaded as signed-by-nobody tarballs and pinned by SHA-256 — no Homebrew** (T-004; the
cask route died on 2026-04-16 and Homebrew's own Wine casks are disabled on 2026-09-01,
[../research/wine-dxmt-install-findings-2026-08-24.md](../research/wine-dxmt-install-findings-2026-08-24.md)).

**Fallback, only if T-012 shows DXMT is unusable:** the user installs Apple's D3DMetal themselves. That is
`brew trust gcenx/wine && brew install --cask gcenx/wine/game-porting-toolkit` — the `brew trust` is not optional,
Homebrew refuses third-party casks by default as of 2026-08-24. We do not redistribute it, so the Apple licence
never binds this project.

---

## ⚡ Fast path — playing CS2 in ~2 days

Do these seven, in order, and stop. Everything after is measurement and productisation.

| # | Task | Time |
|---|---|---|
| 1 | **T-001** Free the disk / keep the 58 GB of assets | 30 min |
| 2 | **T-004** Install the free stack (two tarballs, two checksums) | 1 h |
| 3 | **T-006** Create the bottle | 1 h |
| 4 | **T-007** Windows Steam inside the bottle | 3 h |
| 5 | **T-008** CS2 via the 4.99 GB depot gap | 1 h + download |
| 6 | **T-009** First launch + the four known fixes | 4 h |
| 7 | **T-010** `[GATE]` Bot match on three maps | 2 h |

Then: Phase 2 tunes it (3 d), Phase 3 validates competitive play (2 d + soak), Phase 4 builds `CS2Kit` (8 d).

## Phase overview

| Phase | Theme | Tasks | Effort | Gate |
|---|---|---|---|---|
| 0 | Prepare | T-001, T-002, T-004, T-005 | 1 d | — |
| 1 | Get it running | T-006 … T-010 | 1 d + download | **T-010** |
| 2 | Measure and tune | T-011 … T-017 | 3 d | — |
| 3 | Online and competitive | T-018 … T-022 | 2 d + soak | **T-020** |
| 4 | Build `CS2Kit` | T-023 … T-029 | 8 d | — |
| 5 | Keep it alive | T-030 … T-034 | ongoing | — |

**Removed from scope** (deliberate decisions, not oversights): the cloud/streaming alternatives bake-off (old T-003 —
we are building regardless; GeForce NOW remains the honest fallback if T-020 fails), CrossOver evaluation, DXVK-macOS
(frozen at 1.10.3 since 2023), the `-vulkan` renderer (one confirmation run in T-012, then dropped), and any
per-chip profile matrix.

Effort is in focused hours (h) / days (d = 6 h). Every task states a **binary acceptance test**.

---

# Phase 0 — Prepare

## T-001 · Free the disk, keep the assets `[do this first]`
**Why:** macOS Steam reports CS2 as installed (`StateFlags 4`, 66 GB, `LastPlayed` set) but `InstalledDepots` omits
depot **2347771** — every `.exe`/`.dll`. Verified missing: `cs2.exe`, `engine2.dll`, `client.dll`, `tier0.dll`,
`steam_api64.dll`. The 9 `.exe` files present are Workshop Tools from depot 2347779. **Verify integrity cannot fix
this** — Steam thinks it is complete. But depot **2347770 (58 GB of maps/models/sounds) has no OS filter and is
exactly what the Windows install needs**, so we keep it and close a 4.99 GB gap instead of re-downloading 72 GB.
**Steps**
1. Quit Steam (`osascript -e 'quit app "Steam"'`; confirm no `steam_osx`).
2. `cp "$STEAM/steamapps/appmanifest_730.acf" docs/reference/appmanifest_730.acf.before`
3. **Do not uninstall CS2 yet.** Set it to "Only update this game when I launch it" so macOS Steam cannot re-queue
   the useless depots.
4. Delete the CS:GO-era leftovers in the same folder if present (`platform/`, `installscript.vdf`,
   `WINDOWSTEMPDIR_FONTCONFIG_CACHE`) — they are not part of CS2.
5. `bash scripts/preflight.sh`
**Acceptance:** ≥ 85 GiB free with the 58 GB `game/csgo/` tree intact.
**Effort:** 0.5 h · **Risk:** low.

## T-002 · Lock the project's licence and rules
**Why:** decided already — free stack, so no Apple entanglement. Write it down once so it is never re-litigated.
**Steps**
1. `LICENSE` = **GPL-3.0** for our own code (compatible with the LGPL-2.1 components we link against).
2. Record: we redistribute **no third-party binaries at all** — the user downloads Wine (LGPL-2.1) and DXMT
   (**MIT** through v0.80, LGPL from v0.81) from the URLs in T-004 and CS2Kit only places files they already have.
   If we ever do ship them, the LGPL rules apply: licence texts, unmodified, dynamically linked. We **never**
   redistribute D3DMetal; if a user wants it, they install GPTK themselves.
3. Write the absolute rules (see `docs/06-legal-and-policy.md`): never modify game files, never touch VAC, never wrap
   Steam authentication.
**Acceptance:** `LICENSE` exists; `docs/06` §Distribution model has one box ticked and no open questions.
**Effort:** 1 h · **Risk:** low.

## T-004 · Install the free stack — two tarballs, two checksums, no Homebrew
**Why:** this is the entire toolchain, and the version of this task we shipped **could not be executed**. It said
`brew install --cask --no-quarantine gcenx/wine/wine-crossover   # Wine 11.x`. That cask was **deleted from its tap
on 2026-04-16** (commit `f201026`), Homebrew now **refuses third-party casks** without `brew trust`, and the last
version it ever shipped was **wine-8.0.1**, not 11.x. Homebrew's own `wine-stable` (11.0_1) and `wine@staging`
(11.15) are **deprecated and disabled on 2026-09-01** for failing the Gatekeeper check. All CONFIRMED on the machine
of record 2026-08-24 — [../research/wine-dxmt-install-findings-2026-08-24.md](../research/wine-dxmt-install-findings-2026-08-24.md).
**No Homebrew route to Wine survives the month.** A tarball has no cask to delete, no tap to trust and no quarantine
attribute, and it can be pinned by checksum.

**Steps**
```bash
# 0. Rosetta 2 - the whole stack below is x86-64 (already present on this machine; verify)
softwareupdate --install-rosetta --agree-to-license

mkdir -p ~/CS2/downloads && cd ~/CS2/downloads

# 1. Wine 11.15 staging (Gcenx tarball, LGPL-2.1, released 2026-08-08, 193561920 bytes)
curl -fLO https://github.com/Gcenx/macOS_Wine_builds/releases/download/11.15/wine-staging-11.15-osx64.tar.xz

# 2. DXMT v0.80, the published *builtin* build (MIT, released 2026-04-23, 18681669 bytes)
curl -fLO https://github.com/3Shain/DXMT/releases/download/v0.80/dxmt-v0.80-builtin.tar.gz

# 3. Verify BEFORE extracting. Both lines must match exactly.
shasum -a 256 wine-staging-11.15-osx64.tar.xz dxmt-v0.80-builtin.tar.gz
# a8c50d0e14fb7982a21506287e1e41e1990fe77c74fa2a32da7dbcf7b21de1e2  wine-staging-11.15-osx64.tar.xz
# 8f260e36b5739e68f3bad613381441385c4dc7b85b78ba8de653d5a6a264529d  dxmt-v0.80-builtin.tar.gz

# 4. Extract. Wine lands as an .app bundle; the "wine root" is inside it.
mkdir -p ~/CS2/wine ~/CS2/dxmt
tar -xJf wine-staging-11.15-osx64.tar.xz -C ~/CS2/wine   # -> ~/CS2/wine/Wine Staging.app
tar -xzf dxmt-v0.80-builtin.tar.gz       -C ~/CS2/dxmt   # -> ~/CS2/dxmt/v0.80 (the archive carries the version dir)

export WINE_ROOT="$HOME/CS2/wine/Wine Staging.app/Contents/Resources/wine"
export PATH="$WINE_ROOT/bin:$PATH"
wine --version                                  # -> wine-11.15 (Staging)

# 5. This is T-006's command, run here so the acceptance test below has a prefix
#    to load DXMT into. The recipe knows the builtin layout; your fingers do not.
export WINEPREFIX="$HOME/CS2/prefix"
cs2kit bottle create --dxmt ~/CS2/dxmt/v0.80 --wine-root "$WINE_ROOT"
```
1. Verify `wine --version` prints **11.15 (Staging)**. Wine 11 has **one `wine` loader** — there is no `wine64`;
   guides that say `wine64` predate Wine 11.
2. **Do not place the DXMT files by hand.** The published archive is the `-Dwine_builtin_dll=true` build, so its
   DLLs go into the **Wine tree** (`$WINE_ROOT/lib/wine/…`), *not* the prefix, and the `d3d11`/`dxgi` overrides must
   stay **off** — DXMT's wiki, verbatim: *"Ensure these dlls are **NOT** set overrides `native,builtin`."* Getting
   this backwards fails **silently**: Wine hunts for a native DLL, finds none, and falls back to its own Direct3D.
   `cs2kit bottle create` (T-006) implements the correct layout from `dxmt.build` in the recipe.
3. Record every download URL + SHA-256 in `docs/reference/toolchain.md` so the stack is reproducible. The URLs and
   checksums above are the record as of 2026-08-24.
4. Do **not** install CrossOver, Whisky (archived 2025-05-11), Heroic or Porting Kit. They are not part of this plan.
5. **Fallback, not the path:** DXMT's wiki asks for a FOSS **CrossOver Wine 24+** built from source. That
   requirement was written against DXMT **v0.41**. On v0.80, `nm -m winemetal.so` shows **zero** symbols bound to
   `winemac.so` and one Wine import (`_NtSetEvent` from `ntdll.so`), and DXMT was measured initialising Metal under
   stock Wine 11.15. Build CrossOver sources only if a future DXMT re-introduces the dependency.

**Acceptance (binary, both halves — run after step 5):**
```bash
wine --version                                          # major version >= 11
WINEDEBUG=+loaddll,+dxmt wine rundll32 d3d11.dll,NoSuchEntry 2>&1 | grep -E 'd3d11.dll.*builtin'
```
The first must print ≥ 11. The second must show `Loaded L"C:\windows\system32\d3d11.dll" … builtin` — i.e. DXMT's
DLL, loaded as a Wine builtin, with no override set. `Failed to set Metal cache path, fallback to system default`
in the same output is DXMT's own log line and is expected here (it is a T-013 lead, not a failure).
**Effort:** 1 h · **Risk:** medium — this is the step CrossOver would have made trivial; budget debugging time here,
not later.

## T-005 · Freeze the environment of record
**Why:** every later benchmark is meaningless without the exact stack that produced it.
**Steps** Extend `scripts/preflight.sh --json` to capture: macOS build, chip, cores, GPU, RAM, free disk, Rosetta,
`wine --version`, DXMT version, CS2 `buildid`. Commit as `docs/reference/env-snapshot-0.json`. **Disable automatic
macOS updates** for the project's duration.
**Acceptance:** the snapshot regenerates identically twice.
**Effort:** 2 h · **Risk:** low.

---

# Phase 1 — Get it running

## T-006 · Create the bottle
**Steps**
1. `export WINEPREFIX="$HOME/CS2/prefix"` and build it from the recipe:
   `cs2kit bottle create --dxmt ~/CS2/dxmt/v0.80 --wine-root "$WINE_ROOT"` (64-bit; Windows 10). It is the same
   command as T-004 step 5 — running it twice is safe and is how you re-apply a corrected recipe.
2. **DXMT placement, per its wiki and per `dxmt.build: builtin` in the recipe:** `winemetal.so` →
   `<wine>/lib/wine/x86_64-unix/`; `d3d11.dll`, `dxgi.dll`, `d3d10core.dll`, `winemetal.dll` →
   `<wine>/lib/wine/x86_64-windows/`; `winemetal.dll` **also** → `<prefix>/drive_c/windows/system32/`.
   **Set no DLL overrides.** DXMT's wiki, verbatim: *"Ensure these dlls are **NOT** set overrides `native,builtin`."*
   Only the unpublished `-Dwine_builtin_dll=false` build goes into the prefix and needs
   `WINEDLLOVERRIDES="dxgi,d3d11,d3d10core=n,b;"` — that is `dxmt.build: prefix`, and it is not what upstream ships.
   *(The v0 recipe did the opposite of both and would have lost DXMT silently — corrected 2026-08-24,
   [../research/wine-dxmt-install-findings-2026-08-24.md](../research/wine-dxmt-install-findings-2026-08-24.md) §4.)*
3. Enable **MSync** (`WINEMSYNC=1`).
4. Record every deviation from defaults — this file becomes the machine-readable recipe in T-025.
**Deliverable:** `profiles/bottle-recipe.yaml` v1 (schema carries `wine.root` and `dxmt.build`).
**Acceptance:** `winecfg` opens; `wine cmd` runs; `cs2kit bottle diff` reports no drift; and
`WINEDEBUG=+loaddll wine rundll32 d3d11.dll,NoSuchEntry` shows `d3d11.dll … builtin` with **no** override in
`Software\Wine\DllOverrides`.
**Effort:** 1 h · **Risk:** medium.

## T-007 · Windows Steam inside the bottle
**Why:** CS2 launches with `-steam` and needs a **same-platform** Steam client for Steamworks, SDR relays and
matchmaking. macOS Steam cannot serve it.
**Steps**
1. `wine SteamSetup.exe`; log in (**have the Steam Guard mobile authenticator ready** — the usual first wall).
2. Let the client self-update fully; confirm library and friends load.
3. **Disable the Steam overlay** globally (it costs FPS; revisit in T-016).
4. Point the Steam library folder at the existing `steamapps` (see T-008).
**Deliverable:** `docs/reference/steam-in-bottle.md` — exact steps, every error and its fix.
**Acceptance:** the in-bottle client shows your library and idles 10 min without crashing.
**Effort:** 3 h · **Risk:** **the most likely place to lose a day.** If Steam will not run, that is a Wine/stack
problem — fix it here, not after CS2 is involved.

## T-008 · Install CS2 — close the 4.99 GB gap
**Steps**
1. Map a Wine drive to `~/Library/Application Support/Steam/steamapps` and add it as a Steam library folder in the
   in-bottle client.
2. Install appid 730. It should recognise depot 2347770 as present and fetch only **2347771** (~5 GB).
   * **If it insists on re-downloading everything** (~60 GB / 72 GB on disk): let it, if disk allows — else uninstall
     the macOS copy first to free 65 GB, then re-install cleanly. Timebox the reuse attempt to **2 h**.
3. Confirm `game/bin/win64/cs2.exe` exists — this is the whole point of the task.
4. Record the `buildid` (public: **24828357**).
5. Run *Verify integrity of game files* once. This is the byte-identical baseline T-021 enforces forever.
**Acceptance:** `cs2.exe` exists **and** Steam reports all files validated.
**Effort:** 1 h + download · **Risk:** medium — cross-platform library reuse is **undocumented**; the fallback always works.

## T-009 · First launch — apply the four known fixes before debugging
**Steps**
1. Launch options: `-novid -nojoy -console`. **Not** `-vulkan`.
2. **Black screen** → `CS2Video.txt` with `fullscreen = 0`.
3. **Audio crackling** → set `cs2.exe` to **Windows 8** (`winecfg` → Applications). Documented permanent fix.
4. **Retina off**, render at **1920×1080** or lower. Native 3024×1964 costs ~4× (an M2 Max drops to 23 FPS).
5. Only if it still fails: `WINEDEBUG=+loaddll,+seh` before changing anything else.
**Deliverable:** `docs/reference/first-launch.md`.
**Acceptance:** the CS2 main menu renders and accepts mouse input.
**Effort:** 4 h · **Risk:** medium.

## T-010 · `[GATE]` Offline playable
**Steps** Bot match on **Dust2, Mirage, Ancient**; play each **twice** (the first pass is shader compilation, not
representative); 30 min continuous.
**Acceptance / GATE:** 30 min across 3 maps, no crash, no audio dropout, playable input.
Failure = the free stack is not viable on this machine → the only remaining lever is the D3DMetal fallback (T-012).
**Effort:** 2 h · **Risk:** low once T-009 passes.

---

# Phase 2 — Measure and tune

## T-011 · Benchmark protocol + baseline
**Why:** published Mac FPS numbers are unusable — no named map, no shader warm-up. *Ancient* is 25–30 % heavier than *Dust2*.
**Steps** Implement `docs/07-benchmark-protocol.md`: **Ancient FPS Benchmark `3472126051`**, 3 discarded warm-ups,
5 measured runs, report **median avg, median 1 % low, p99 frametime, hitch count**. Log `powermetrics` alongside.
**Acceptance:** two baseline sessions on different days agree within **±5 %**.
**Expected for M2 Pro/32 GB:** ~100–125 avg @1080p medium. Far outside → the protocol or config is wrong.
**Effort:** 6 h · **Risk:** medium.

## T-012 · Confirm DXMT is the right backend
**Why:** DXMT is our stack; this proves it rather than assumes it. Community data shows a 10× swing both ways
(one M3: DXMT 120 vs D3DMetal 11; one M4 Max: the reverse). We need our machine's answer.
**Steps**
1. Full protocol on **DXMT** (primary), crossed with **MSync vs ESync**.
2. One confirmation run with **`-vulkan`** to document that it loses on Apple Silicon (DXVK-macOS is frozen at
   1.10.3; MoltenVK has no geometry shaders / transform feedback). **Check the console** — CS2 silently falls back
   to DX11 when Vulkan init fails, so you can benchmark DX11 believing otherwise. Then drop it.
3. **Only if DXMT's 1 % low is unacceptable:** install GPTK yourself and A/B D3DMetal. If D3DMetal wins decisively,
   record it as a *user-installed local fallback* — it does not change what we redistribute.
4. Score on **hitch count** as well as FPS. A backend that wins on average and loses on hitches loses outright.
**Acceptance:** a ranked table, ≥ 5 runs per configuration, with an explicit verdict for this machine.
**Effort:** 6 h · **Risk:** low.

## T-013 · Kill shader-compilation stutter
**Steps** Quantify hitch count on 1st vs 3rd exposure to a map; locate the DXMT shader cache; confirm it persists
across launches and find what invalidates it (a CS2 update almost certainly does → feeds T-030); define a post-update
warm-up drill.
**Acceptance:** warmed-cache first-minute hitch count **≥ 70 % lower** than cold.
**Effort:** 4 h · **Risk:** medium.

## T-014 · Resolution and upscaling
**Steps** Sweep 1280×960 stretched, 1600×900, 1920×1080, 2560×1440, native 3024×1964 × FSR off/Quality/Balanced.
Verify HiDPI is genuinely off. Document external-monitor behaviour (**no public data — we are generating it**).
**Acceptance:** a chosen resolution where **1 % low ≥ 60 FPS** on Ancient.
**Effort:** 4 h · **Risk:** low.

## T-015 · Input latency
**Why:** outranks FPS for CS2, and **no ms-level measurement of CS2 under Wine on Apple Silicon exists publicly.**
**Steps** Disable macOS pointer acceleration; verify `m_rawinput 1` takes effect; max polling rate; 240 fps camera,
click-to-muzzle-flash, **20 trials**, median + IQR; repeat USB / Bluetooth / dongle.
**Acceptance:** ≥ 20 trials per config, method reproducible from the doc alone. **Publish it.**
**Effort:** 6 h · **Risk:** medium.

## T-016 · Audio and microphone
**Steps** Confirm the Windows 8 fix holds under load; test game audio, positional accuracy, mic, push-to-talk,
Steam mic test; built-in / USB / AirPods; hot-swap; **alt-tab audio loss**; overlay on/off.
**Acceptance:** mic audible to a real teammate in a real match; no crackle over 30 min.
**Effort:** 3 h · **Risk:** medium — Bluetooth may simply not be viable; record that honestly.

## T-017 · Thermals and the 2-hour soak
**Why:** minute 5 is marketing, minute 90 is the truth.
**Steps** 2 h continuous session logging FPS, frametime, CPU/GPU power, temperature, memory pressure, peak RSS
(CS2 alone ≈ 6.1 GB); compare minute 5 vs 90; battery vs plugged; Low Power Mode on/off.
**Acceptance:** a published sustained-FPS figure and a power recommendation.
**Effort:** 3 h (mostly unattended) · **Risk:** low.

---

# Phase 3 — Online and competitive

## T-018 · Account safety `[read before any online task]`
**Steps** Use a **secondary, non-Prime** account for all first online testing. **Do not buy Prime**
(€13.29 / $14.99, **non-refundable**) until T-020 passes. No injected DLLs, no game-file modification, no macros,
no third-party overlays. Keep Steam Guard on.
**Acceptance:** a secondary account exists and is the only one used until T-020 passes.
**Effort:** 1 h.

## T-019 · Casual online + community servers
**Why:** separates *networking* faults from *anti-cheat* faults. Debugging them together is intractable.
**Steps** Casual/DM, then a community server. Watch `net_graph` for loss/choke and the known
**`SteamNetworkingSockets` thread-starvation jitter**. Wi-Fi vs Ethernet; **disable AWDL** (AirDrop/Handoff) and
quantify the difference. Reconnect after sleep and after a network switch. Friends/invites/lobbies from the bottle.
**Acceptance:** three consecutive casual matches, no disconnect, ping within **±10 ms** of native macOS Steam to the
same relay.
**Effort:** 4 h · **Risk:** medium.

## T-020 · `[GATE]` VAC-protected competitive validation
**Why:** **the project's actual success criterion.** Everything before it is instrumentation.
**Steps**
1. Competitive on the secondary account; complete full matches.
2. Watch for *"VAC unable to verify game session"* (**one occurrence is not a verdict — it happens on plain Windows
   too**), mid-match kicks, "Untrusted", account warnings.
3. **5 matches across ≥ 3 separate days**, with a bottle restart and a reboot in between.
4. If clean → buy Prime, move to the main account, run **5 Premier** matches.
5. Log every anomaly with timestamp, `buildid` and env snapshot.
**Acceptance / GATE:** **10 consecutive matches (5 Competitive + 5 Premier), zero anti-cheat kicks, zero warnings.**
* **GO** → Phase 4. * **CONDITIONAL** (kicks recur) → ship as practice/casual only, never claim competitive-ready.
* **NO-GO** (systematic kicks) → stop. That is a **policy** wall; do not engineer around it. GeForce NOW is then the
  honest recommendation for competitive play.
**Effort:** 6 h over ≥ 3 days · **Risk:** the central unknown — mitigated by CS2's native Linux build running VAC,
Valve serving CS2 through GFN VMs, and a documented M1 Pro Wine player holding a 15,000 Premier rating.

## T-021 · Enforce "never modify game files"
**Why:** Valve's VAC FAQ names *"modifications to a game's core executable files and dynamic link libraries"* as
cheating. This is the one action that turns a low risk into a real one.
**Steps** SHA-256 every file in `game/bin/win64/`; `cs2kit doctor` recomputes and **refuses to launch** on mismatch,
directing the user to Steam's verify. Document the legitimate surface: bottle settings, **Wine's own** DLL overrides,
env vars, launch options, `autoexec.cfg`. Nothing else.
**Acceptance:** the script exits non-zero on a deliberately touched file in a scratch copy.
**Effort:** 3 h.

## T-022 · Competitive-readiness sign-off
**Steps** Assemble sustained FPS, 1 % lows, input-latency delta, comms verdict, network stability, VAC log.
**Acceptance:** one honest paragraph a stranger can act on, every number sourced to a task.
**Effort:** 2 h.

---

# Phase 4 — Build `CS2Kit`

> **Scope rule:** `CS2Kit` **configures and diagnoses**. It never patches the game, never wraps Steam
> authentication, never implements graphics, never touches VAC.

## T-023 · Specify v0.1 (CLI only, no GUI)
CLI is testable and CI-able; a SwiftUI app is the least valuable part and comes last, if ever.
Commands: `doctor`, `bottle create|repair`, `config apply <profile>`, `bench`, `report`.
**Deliverable:** `docs/cs2kit-spec.md` — exact surface, exit codes, file layout.
**Acceptance:** every command maps to a Phase 1–3 procedure already proven.
**Effort:** 4 h.

## T-024 · `cs2kit doctor`
The highest-value code in the project — most user reports are environment problems.
Checks: macOS version + **Rosetta-27 horizon**, chip/RAM/GPU, **free disk ≥ 80 GB**, `wine`/DXMT versions, CS2
`buildid`, **game-file integrity** (T-021), bottle drift from the recipe, AWDL, Low Power Mode, HiDPI, overlay.
Each check → PASS/WARN/FAIL + a one-line fix.
**Acceptance:** finds ≥ 5 seeded faults on a deliberately broken bottle with correct remediation text.
**Effort:** 2 d.

## T-025 · Declarative recipe + `bottle create`
Promote `profiles/bottle-recipe.yaml` to source of truth (Windows version, per-exe compat mode, DLL overrides,
DXMT, MSync, env vars, launch options, resolution, HiDPI). Implement create / apply / diff.
**Acceptance:** **a fresh bottle built only from the recipe reaches the CS2 main menu with no manual step.**
**Effort:** 2 d · **Risk:** medium.

## T-026 · `cs2kit bench`
Automates T-011 so post-update regressions are *detected*, not felt. Results keyed by env snapshot + `buildid`.
**Acceptance:** re-run on an unchanged machine reproduces the stored median within **±5 %**.
**Effort:** 1.5 d.

## T-027 · Three situational profiles
Not per-chip files — the variance is **backend × chassis × resolution × macOS build**. Ship
`competitive-lowest-latency`, `balanced-1080p`, `thermal-limited` (fanless/battery), each with provenance comments
naming the task that measured it.
**Acceptance:** each profile's claimed numbers reproduce via `cs2kit bench`.
**Effort:** 1 d.

## T-028 · `cs2kit report`
Redacted, shareable bundle: env + config + bench + integrity. **Strip** SteamID, account name, usernames in paths,
IPs, MACs. Print exactly what will be shared before writing.
**Acceptance:** security review of a real bundle finds **zero** personal identifiers.
**Effort:** 1 d · **Risk:** medium — privacy defects are the embarrassing kind.

## T-029 · Documentation and honest positioning
Install guide, troubleshooting keyed to the known failure modes, compatibility matrix seeded with this machine, and a
plain statement of what is measured, what is inferred, what is unknown, and that this is unsupported by Valve.
**Acceptance:** a Mac-owning friend who has never used Wine reaches a bot match from the guide alone.
**Effort:** 1.5 d.

---

# Phase 5 — Keep it alive

## T-030 · CS2 update watch + regression drill
Poll Valve's appinfo for `public` `buildid` changes; on change run `doctor` + `bench` + a 1-match smoke test and
append a compatibility-matrix row. Whether a CS2 patch has ever broken a bottle is **UNKNOWN** — this generates that data.
**Acceptance:** a buildid change triggers the drill within 24 h. **Effort:** 4 h.

## T-031 · Rosetta-27 exit plan `[strategic, starts day one]`
**The highest-severity risk, and the only one with a date.** Apple: general-purpose Rosetta is available **through
macOS 27**, then only *"a subset … aimed at supporting older unmaintained gaming titles"* — and CS2 is actively
maintained, so it likely does **not** qualify. Our whole stack is x86-64. ARM64EC Wine + FEX is blocked by Apple
Silicon's **16 KB page size** (Wine needs 4 KB; Wine 11.0's simulation is "simple applications" only).
Track quarterly; pre-write the decommission notice and the migration recommendation.
**Acceptance:** a dated entry every quarter in `docs/rosetta-watch.md`. **Effort:** 2 h/quarter.

## T-032 · macOS beta testing
Install each macOS beta to a **separate APFS volume**; run `doctor` + `bench` + smoke test; publish before public release.
**Acceptance:** a matrix row per beta. **Effort:** 3 h per release.

## T-033 · Community data intake
Ingest `cs2kit report` bundles; publish the aggregate. The ecosystem has no 1 %-low or latency data — this is the
project's most durable contribution. **Acceptance:** ≥ 10 external bundles.

## T-034 · Quarterly upstream tracking
**DXMT** (our critical dependency — active; **MIT through v0.80, LGPL from v0.81**), Wine, MSync, MoltenVK (if geometry shaders or
`VK_EXT_transform_feedback` ever land, revisit T-012).
**Acceptance:** one dated review per quarter.

---

## Critical path

```
T-001 ─> T-004 ─> T-006 ─> T-007 ─> T-008 ─> T-009 ─> T-010[GATE]   ← playing, ~2 days
T-002 ─┘                                                  │
T-005 ─┘                                                  ▼
                              T-011 ─> T-012 ─> T-013/14/15/16/17    ← tuned, +3 days
                                                          │
                                                          ▼
                              T-018 ─> T-019 ─> T-020[GATE] ─> T-021 ─> T-022   ← validated
                                                          │
                                                          ▼
                              T-023 ─> T-024 ─> T-025 ─> T-026 ─> T-027/28/29   ← CS2Kit
                                                          │
                                                          ▼
                                            T-030 … T-034 (ongoing)
```

**Two gates: T-010 (does it run?) and T-020 (does it count?).** T-031 runs in parallel from day one and can end the
project from the outside.
