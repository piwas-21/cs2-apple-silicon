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
│ Wine 11.15 staging  (Gcenx tarball, LGPL-2.1)                  │
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

## How the stack is obtained — and why it is not Homebrew

**Two tarballs, two checksums, no package manager.** MEASURED and installed on the machine of record 2026-08-24
([../research/wine-dxmt-install-findings-2026-08-24.md](../research/wine-dxmt-install-findings-2026-08-24.md)):

| Component | Source | Released | SHA-256 |
|---|---|---|---|
| Wine **11.15 staging** | `Gcenx/macOS_Wine_builds` → `wine-staging-11.15-osx64.tar.xz` | 2026-08-08 | `a8c50d0e…1de1e2` |
| DXMT **v0.80 builtin** | `3Shain/DXMT` → `dxmt-v0.80-builtin.tar.gz` | 2026-04-23 | `8f260e36…64529d` |

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
| Wine | WineHQ / Gcenx | LGPL-2.1 | Configure via recipe; report bugs upstream; don't fork. The user downloads the tarball. |
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
| **CrossOver-sources Wine 24+**, built from `media.codeweavers.com/pub/crossover/source/` | This is what DXMT's wiki tells you to build, because DXMT once needed `winemac.drv` symbols that stock Wine hides. **Not rejected — demoted to FALLBACK.** On v0.80 the requirement no longer binds: `nm -m winemetal.so` shows **zero** symbols bound to `winemac.so` and exactly one Wine import (`_NtSetEvent` from `ntdll.so`), and DXMT was measured loading as `builtin` under stock Wine 11.15 staging. Compiling Wine from source is an hour of toolchain work we do not ask a reader for; it stays documented as the escape hatch if a future DXMT re-introduces the dependency. MEASURED — [../research/wine-dxmt-install-findings-2026-08-24.md](../research/wine-dxmt-install-findings-2026-08-24.md) §5. |
| **Any Homebrew cask** for Wine (`gcenx/wine/wine-crossover`, `wine-stable`, `wine@staging`) | `wine-crossover` was deleted from its tap on 2026-04-16 and had shipped **wine-8.0.1**; the two official casks are **disabled on 2026-09-01** for failing Gatekeeper; and third-party taps now need `brew trust`. Three failure modes, one of them dated. The tarball has none of them. CONFIRMED 2026-08-24. |
| **D3DMetal** (Apple GPTK) | Free to download, but redistributable **only non-commercially**, and its use grant is worded for "developing, testing, or evaluating". DXMT avoids the question. Kept as a **user-installed** fallback if T-012 demands it. |
| DXVK-macOS | Frozen at 1.10.3 since 2023 (upstream DXVK is 3.0.2). |
| `-vulkan` renderer | Real in the Windows build, but on Apple Silicon it routes through frozen DXVK-macOS + a MoltenVK with no geometry shaders or `VK_EXT_transform_feedback`. CS2 silently falls back to DX11 on init failure, so it is easy to benchmark it by mistake. One confirmation run in T-012, then dropped. |
| Boot Camp | **Does not exist on Apple Silicon.** CONFIRMED — Apple lists Intel Macs only. |
| Windows-on-ARM VM | Adds virtualization *and* Windows-on-ARM's own x86 translation on top; anti-cheat VM detection is an added unknown. |
| Patching CS2 binaries | Valve's VAC FAQ classes it as cheating. |
| Cloud gaming (GeForce NOW) | Not a build target — but it **is** the honest fallback if T-020 fails. |

Two of these are **fallbacks we keep warm**, not dead ends: CrossOver-sources Wine (if DXMT ever needs the patched
`winemac.drv` again) and D3DMetal via the user's own GPTK (if T-012 says DXMT loses on this machine). Both are
user-installed; neither changes what this project distributes, which is **only its own code**.

## The path that must keep working

`Steam Guard auth → Steamworks init → SDR relay selection → matchmaking (usemms=1) → game server → VAC session
verification → voice (CoreAudio ↔ Wine) → HID raw input → DXMT → Metal present`

Any single break here is a product failure even at 200 FPS. Phase 3 tests these individually, in this order.
