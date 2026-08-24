# 02 — Architecture

## The stack

Free software end to end. The Steam client runs **inside** the bottle — macOS Steam cannot install or launch CS2
(appid 730 is `oslist = "windows,linux"`; proven on this machine, see `docs/reference/target-machine.md`).

```
┌────────────────────────────────────────────────────────────────┐
│ cs2.exe  (x86-64 Windows, ~72 GB, VAC-protected)               │
│   launch: -novid -nojoy -console        (NOT -vulkan)          │
├────────────────────────────────────────────────────────────────┤
│ Windows Steam client — INSIDE the bottle.                      │
│   Installs, owns, updates and launches CS2. Steamworks, SDR    │
│   relays, matchmaking (usemms=1), friends, authentication.     │
├────────────────────────────────────────────────────────────────┤
│ Sikarugir Wine 10.0   (WS12WineSikarugir10.0_6, LGPL-2.1)      │
│   `wine-10.0 (Sikarugir)` · the ONLY engine of three measured  │
│   that renders Steam, passes its websocket check AND exports   │
│   the winemac.drv API DXMT needs · needs the wrapper dylibs    │
│   Win32 → macOS · cs2.exe compat mode = Windows 8 (audio fix)  │
│   ├─ DXMT  v0.80  (MIT)        DirectX 11 → Metal              │
│   │    builtin build: lives in lib/wine, NOT in the prefix,    │
│   │    and the d3d11/dxgi overrides stay OFF                   │
│   └─ MSync        (LGPL-2.1)   synchronisation                 │
├────────────────────────────────────────────────────────────────┤
│ Rosetta 2   x86-64 → ARM64                                     │
│   ⚠ general-purpose only THROUGH macOS 27 — project shelf life │
├────────────────────────────────────────────────────────────────┤
│ macOS 26.5.2 · Metal 4 · CoreAudio · IOKit HID · Network.fw    │
├────────────────────────────────────────────────────────────────┤
│ Apple M2 Pro · 6P+4E CPU · 16-core GPU · 32 GB unified         │
└────────────────────────────────────────────────────────────────┘

   CS2Kit ─── configures and observes. Never intercepts. ───┘
   (doctor · bottle · config · bench · report)
```

## The engine matrix — three free Wine builds, one that works

**This is the single most important decision in the architecture, and it is decided by measurement, not by
version number.** All three builds below are free software, all three install the same way, and two of them
cannot run CS2 at all. MEASURED on the machine of record 2026-08-24
([implementation-status.md](implementation-status.md),
[../research/steam-black-window-2026-08-24.md](../research/steam-black-window-2026-08-24.md)):

| Engine | `wine --version` | Steam UI | client↔helper transport | DXMT Metal view | Verdict |
|---|---|---|---|---|---|
| Gcenx Wine 11.15 staging | `wine-11.15 (Staging)` | **black**, 0.0/255 | OK | **fails** | unusable — *and* it crashes Steam's CEF GPU process 9× per launch (`0xC0000005`) |
| Gcenx Wine 11.15 devel | `wine-11.15 (Devel)` | **black**, 0.0/255 | OK | **fails** | unusable — no GPU-process crashes, still no Metal view |
| FOSS CrossOver 24.0.7 | `wine-9.0 (SikarugirCX 24.0.7)` | renders, 37.3/255 | **rejected — 0x3008**, 82× in one session | works | unusable — login is impossible |
| **Sikarugir Wine 10.0** | `wine-10.0 (Sikarugir)` | **renders** | **OK** | **works** | **the Wine of record** |

The one-line test that separates them, and the reason two of them fail:

```bash
nm -g "$WINE_ROOT/lib/wine/x86_64-unix/winemac.so" | grep macdrv    # must print _macdrv_functions
```

DXMT resolves Wine's `winemac.drv` entry points **at runtime, through Wine's unix-call interface** — not as
link-time imports. A build that hides those symbols gives DXMT a D3D11 device and then fails with
`err: Failed to create metal view, it seems like your Wine has no exported symbols needed by DXMT`. Steam's own UI
reaches D3D11 through ANGLE, so the same missing view is why Steam's window paints black on the Gcenx builds: **two
symptoms, one cause.** `cs2kit doctor` runs this check, and `cs2kit engine list` prints the table above with the
verdicts baked in.

The CrossOver 24.0.7 engine passes the Metal-view test and renders Steam, and still cannot be used: its Wine **9.0**
base makes `Steam.exe` reject `steamwebhelper.exe`'s own loopback websocket (`WebUITransport: Connection rejected`,
`Failed to reconnect to websocket: wine`), so the client dies on *"Unexpected transport error (0x3008)"* before the
login screen. That is a client-side rejection over a connection that succeeded — not a GPU, sandbox, cache or DXMT
fault; each of those was eliminated by experiment.

## How the stack is obtained — and why it is not Homebrew

**Two archives plus the wrapper dylibs, all checksummed, no package manager.** MEASURED and installed on the machine
of record 2026-08-24
([../research/wine-dxmt-install-findings-2026-08-24.md](../research/wine-dxmt-install-findings-2026-08-24.md),
[reference/toolchain.md](reference/toolchain.md)):

| Component | Source | Bytes | SHA-256 |
|---|---|---|---|
| **Sikarugir Wine 10.0** | `Sikarugir-App/Engines` v1.0 → `WS12WineSikarugir10.0_6.tar.xz` | 166 304 096 | `9da7ee0c…6091b2` |
| Wrapper dylibs (**required**) | `Sikarugir-App/Wrapper` v1.0 → `Template-1.0.11.tar.xz` | 84 533 420 | `9fa15479…6ccb8a` |
| DXMT **v0.80 builtin** | `3Shain/DXMT` → `dxmt-v0.80-builtin.tar.gz` | 18 681 669 | `8f260e36…64529d` |

The wrapper dylibs are a **packaging dependency, not an extra**: without `Contents/Frameworks/*.dylib` staged into
`<engine>/lib/`, `wineserver` aborts with `Library not loaded: @rpath/libinotify.0.dylib` and nothing starts.
`cs2kit engine install` fetches the engine, verifies its digest, extracts it and stages those dylibs in one step.

The Homebrew route this project originally specified is **gone**, in three ways, all CONFIRMED on 2026-08-24:
`gcenx/wine/wine-crossover` was **deleted from its tap on 2026-04-16** (and had been shipping **wine-8.0.1**, never
the "11.x" our own plan claimed); Homebrew now **refuses third-party casks by default** (`brew trust gcenx/wine`
required); and Homebrew's own `wine-stable` / `wine@staging` casks are **deprecated and will be disabled on
2026-09-01** for failing the Gatekeeper check (R-15, [05-risk-register.md](05-risk-register.md)). A tarball carries
no quarantine attribute, needs no admin rights, and can be pinned by checksum — which is why the install path is now
a `curl`, a `shasum` and a `tar`.

**Where DXMT goes is part of the architecture, not a detail.** The published release is the *builtin*
(`-Dwine_builtin_dll=true`) build: `winemetal.so`, `d3d11.dll`, `dxgi.dll` and `d3d10core.dll` belong in the **Wine
tree** (`<wine>/lib/wine/…`), `winemetal.dll` in the Wine tree *and* the prefix's `system32`, and the DXMT wiki says
verbatim *"Ensure these dlls are **NOT** set overrides `native,builtin`."* Setting the overrides makes Wine hunt for
a native DLL, fail to find one, and fall back to its own Direct3D — a silent loss of the entire graphics backend.
`profiles/bottle-recipe.yaml` encodes the choice as `dxmt.build: builtin|prefix` plus `wine.root`, so the layout and
the override rule cannot drift apart.

## What we own vs. what we consume

| Layer | Owner | Licence | Our involvement |
|---|---|---|---|
| CS2 | Valve | proprietary | **Read-only, byte-identical forever.** Enforced by T-021. |
| Steam client | Valve | proprietary | Install it. Never wrap or automate its authentication. |
| Wine | WineHQ / Sikarugir-App | LGPL-2.1 | Configure via recipe; report bugs upstream; don't fork. The user downloads the engine (`cs2kit engine install`). |
| Wine wrapper dylibs | Sikarugir-App (Wineskin lineage) | mixed FOSS | Stage them beside the engine, or `wineserver` will not start. Downloaded by the user. |
| DXMT | 3Shain / CodeWeavers | **MIT** (v0.80; **LGPL from v0.81**) | **Our critical dependency.** Configure, track, upstream bugs. The user downloads the tarball. |
| MSync | marzent | LGPL-2.1 | Enable, configure. |
| Rosetta 2 | Apple | proprietary | Monitor the deprecation clock. Zero control. |
| **`CS2Kit`** | **us** | GPL-3.0 | **~2 000 lines: recipe, doctor, bench, report.** |

That ratio is the strategy: own as little as possible, and make what we own reproducible.

## Rejected options

| Rejected | Reason |
|---|---|
| Native macOS/Metal port | Requires Valve. Zero probability — no mention in Valve's own appid-730 news feed since the 2023 cancellation. |
| **CrossOver** (€74) | Works well and is CodeWeavers-supported, but it is a **paid** dependency for every user. DXMT and MSync — the parts that matter — are free (MIT and LGPL-2.1) and available without it. |
| **Gcenx Wine 11.15** (staging or devel), the tarball this project shipped until 2026-08-24 | **REJECTED ON MEASUREMENT — it cannot run CS2.** It exports no `winemac.drv` symbols (`nm -g winemac.so \| grep -c macdrv` → **0**), so DXMT creates a D3D11 device at feature level 11_1 and then dies: *"Failed to create metal view, it seems like your Wine has no exported symbols needed by DXMT"*. Steam's own window paints **black** (0.0/255) for the same reason. The **staging** build additionally crashes Steam's CEF GPU process 9× per launch (`0xC0000005`); devel does not, and is still unusable. Nine configurations were tried before the cause was found — see [../research/steam-black-window-2026-08-24.md](../research/steam-black-window-2026-08-24.md). |
| **FOSS CrossOver 24.0.7** (`WS12WineCX24.0.7_7.tar.xz`, `wine-9.0 (SikarugirCX 24.0.7)`) | **REJECTED ON MEASUREMENT — login is impossible.** It is what DXMT's wiki asks for, it renders Steam's UI and it gives DXMT its Metal view. But its Wine **9.0** base makes `Steam.exe` reject `steamwebhelper.exe`'s loopback websocket — *"Unexpected transport error (0x3008)"*, `WebUITransport: Connection rejected` **82 times in one session**. DXMT, the CEF sandbox, GPU compositing, the web cache and stale helper processes were each eliminated by experiment. Kept in `cs2kit engine list` as a recorded dead end so nobody re-tries it. |
| **Building CrossOver Wine 24+ from `media.codeweavers.com/pub/crossover/source/`** | DXMT's wiki tells you to. Unnecessary — Sikarugir publishes a prebuilt engine that satisfies the same requirement, and the requirement itself is **real**: our earlier conclusion that DXMT v0.80 no longer needs the exported `winemac.drv` API was drawn from a static symbol dump (`nm -m winemetal.so` shows no link-time `winemac` imports) and was **wrong** — DXMT resolves those entry points at runtime. Building from source stays the escape hatch if the Sikarugir releases ever disappear. |
| **Any Homebrew cask** for Wine (`gcenx/wine/wine-crossover`, `wine-stable`, `wine@staging`) | `wine-crossover` was deleted from its tap on 2026-04-16 and had shipped **wine-8.0.1**; the two official casks are **disabled on 2026-09-01** for failing Gatekeeper; and third-party taps now need `brew trust`. Three failure modes, one of them dated. The tarball has none of them. CONFIRMED 2026-08-24. |
| **D3DMetal** (Apple GPTK) | Free to download, but redistributable **only non-commercially**, and its use grant is worded for "developing, testing, or evaluating". DXMT avoids the question. Kept as a **user-installed** fallback if T-012 demands it. |
| DXVK-macOS | Frozen at 1.10.3 since 2023 (upstream DXVK is 3.0.2). |
| `-vulkan` renderer | Real in the Windows build, but on Apple Silicon it routes through frozen DXVK-macOS + a MoltenVK with no geometry shaders or `VK_EXT_transform_feedback`. CS2 silently falls back to DX11 on init failure, so it is easy to benchmark it by mistake. One confirmation run in T-012, then dropped. |
| Boot Camp | **Does not exist on Apple Silicon.** CONFIRMED — Apple lists Intel Macs only. |
| Windows-on-ARM VM | Adds virtualization *and* Windows-on-ARM's own x86 translation on top; anti-cheat VM detection is an added unknown. |
| Patching CS2 binaries | Valve's VAC FAQ classes it as cheating. |
| Cloud gaming (GeForce NOW) | Not a build target — but it **is** the honest fallback if T-020 fails. |

Two of these are **fallbacks we keep warm**, not dead ends: building CrossOver-sources Wine ourselves (if the
Sikarugir releases vanish) and D3DMetal via the user's own GPTK (if T-012 says DXMT loses on this machine). Both are
user-installed; neither changes what this project distributes, which is **only its own code**.

## How the game and the client are actually started

Two rules that are architecture, not preference, both MEASURED on 2026-08-24
([implementation-status.md](implementation-status.md)):

* **The Steam client is always started with `-no-cef-sandbox`.** Under Wine the sandboxed Chromium helper cannot
  establish its transport, and the client aborts on 0x3008 before login. `cs2kit launch` passes the flag itself
  (`launch.STEAM_CLIENT_FLAGS`); it is a client flag, not a game launch option.
* **`Steam.exe -applaunch 730` is not reliable for repeated runs.** It refuses to relaunch while the client still
  believes a previous session is running — exactly the state after a hard kill. With the client logged in and
  running, launching `game/bin/win64/cs2.exe` directly always works, and that is what the soak and benchmark runs do.

The library is wired by **symlink**, not through Steam's UI: `<prefix>/drive_c/Program Files (x86)/Steam/steamapps`
points at the macOS Steam library. Adding a library folder in the client does **not** survive — Steam rewrites
`libraryfolders.vdf` on every start. `cs2kit bottle link-steamapps` makes the symlink.

## The path that must keep working

`Steam Guard auth → Steamworks init → SDR relay selection → matchmaking (usemms=1) → game server → VAC session
verification → voice (CoreAudio ↔ Wine) → HID raw input → DXMT → Metal present`

Any single break here is a product failure even at 200 FPS. Phase 3 tests these individually, in this order.
