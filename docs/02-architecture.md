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
│ Wine 11.x  (Gcenx macOS build, LGPL-2.1)                       │
│   Win32 → macOS · cs2.exe compat mode = Windows 8 (audio fix)  │
│   ├─ DXMT  0.72+  (LGPL-2.1)   DirectX 11 → Metal              │
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

## What we own vs. what we consume

| Layer | Owner | Licence | Our involvement |
|---|---|---|---|
| CS2 | Valve | proprietary | **Read-only, byte-identical forever.** Enforced by T-021. |
| Steam client | Valve | proprietary | Install it. Never wrap or automate its authentication. |
| Wine | WineHQ / Gcenx | LGPL-2.1 | Configure via recipe; report bugs upstream; don't fork. |
| DXMT | 3Shain / CodeWeavers | **LGPL-2.1** | **Our critical dependency.** Configure, track, upstream bugs. |
| MSync | marzent | LGPL-2.1 | Enable, configure. |
| Rosetta 2 | Apple | proprietary | Monitor the deprecation clock. Zero control. |
| **`CS2Kit`** | **us** | GPL-3.0 | **~2 000 lines: recipe, doctor, bench, report.** |

That ratio is the strategy: own as little as possible, and make what we own reproducible.

## Rejected options

| Rejected | Reason |
|---|---|
| Native macOS/Metal port | Requires Valve. Zero probability — no mention in Valve's own appid-730 news feed since the 2023 cancellation. |
| **CrossOver** (€74) | Works well and is CodeWeavers-supported, but it is a **paid** dependency for every user. DXMT and MSync — the parts that matter — are LGPL-2.1 and available without it. |
| **D3DMetal** (Apple GPTK) | Free to download, but redistributable **only non-commercially**, and its use grant is worded for "developing, testing, or evaluating". DXMT avoids the question. Kept as a **user-installed** fallback if T-012 demands it. |
| DXVK-macOS | Frozen at 1.10.3 since 2023 (upstream DXVK is 3.0.2). |
| `-vulkan` renderer | Real in the Windows build, but on Apple Silicon it routes through frozen DXVK-macOS + a MoltenVK with no geometry shaders or `VK_EXT_transform_feedback`. CS2 silently falls back to DX11 on init failure, so it is easy to benchmark it by mistake. One confirmation run in T-012, then dropped. |
| Boot Camp | **Does not exist on Apple Silicon.** CONFIRMED — Apple lists Intel Macs only. |
| Windows-on-ARM VM | Adds virtualization *and* Windows-on-ARM's own x86 translation on top; anti-cheat VM detection is an added unknown. |
| Patching CS2 binaries | Valve's VAC FAQ classes it as cheating. |
| Cloud gaming (GeForce NOW) | Not a build target — but it **is** the honest fallback if T-020 fails. |

## The path that must keep working

`Steam Guard auth → Steamworks init → SDR relay selection → matchmaking (usemms=1) → game server → VAC session
verification → voice (CoreAudio ↔ Wine) → HID raw input → DXMT → Metal present`

Any single break here is a product failure even at 200 FPS. Phase 3 tests these individually, in this order.
