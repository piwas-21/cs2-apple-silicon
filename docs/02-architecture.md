# 02 — Architecture

## The corrected stack

The prior analysis put **native macOS Steam** outside the bottle driving `steam://run/730`. That layer does not
exist for CS2 (see G-1). The Steam client must be **inside** the bottle, on the same platform as the game.

```
┌────────────────────────────────────────────────────────────────┐
│ cs2.exe  (x86-64 Windows, ~72 GB installed, VAC-protected)     │
│   launch: -novid -nojoy -console      (NOT -vulkan, see below) │
├────────────────────────────────────────────────────────────────┤
│ Windows Steam client  ← INSIDE the bottle. Installs, owns,     │
│   updates and launches CS2. Provides Steamworks, SDR relays,   │
│   matchmaking (usemms=1), friends, auth.  ⟵ THE CORRECTION     │
├────────────────────────────────────────────────────────────────┤
│ Wine 11.0  (CrossOver 26.3.0, or Gcenx GPTK / Sikarugir)       │
│   Win32 → macOS · MSync|ESync · per-exe compat (cs2.exe = Win8)│
├──────────────┬──────────────┬──────────────────────────────────┤
│ D3DMetal 3/4 │  DXMT 0.72   │  DXVK-macOS 1.10.3 (FROZEN 2023) │
│  DX11/12→    │  DX11→Metal  │   DX11→Vulkan→MoltenVK→Metal     │
│  Metal       │  open source │   no geometry shaders,           │
│  (Apple)     │              │   no VK_EXT_transform_feedback   │
│         └──── pick by MEASUREMENT, per machine (T-012) ────┘   │
├────────────────────────────────────────────────────────────────┤
│ Rosetta 2   x86-64 → ARM64   ⚠ general-purpose only THROUGH    │
│                               macOS 27  (project shelf life)   │
├────────────────────────────────────────────────────────────────┤
│ macOS 26.5.2 · Metal 4 · CoreAudio · IOKit HID · Network.fw    │
├────────────────────────────────────────────────────────────────┤
│ Apple M2 Pro · 6P+4E CPU · 16-core GPU · 32 GB unified         │
└────────────────────────────────────────────────────────────────┘

     CS2Kit  ──── observes and configures, never intercepts ────┘
     (doctor · bottle · config · bench · report)
```

## Layers we own vs. layers we consume

| Layer | Owner | Our involvement |
|---|---|---|
| CS2 | Valve | **Read-only. Byte-identical, forever.** Enforced by T-021. |
| Steam client | Valve | Install it, never wrap or automate its auth. |
| Wine | CodeWeavers / WineHQ | Configure via recipe; report bugs upstream; don't fork. |
| D3DMetal | Apple (closed) | Select and configure. Redistributable **non-commercially only**. |
| DXMT / DXVK / MoltenVK | OSS | Select and configure; upstream bug reports. |
| Rosetta 2 | Apple | Monitor the deprecation clock. Zero control. |
| **`CS2Kit`** | **us** | **~2 000 lines: recipe, doctor, bench, report.** |

That ratio *is* the strategy. The prior analysis reached the same conclusion — it just placed Steam on the wrong
side of the bottle wall.

## Why not the alternatives

| Rejected | Reason |
|---|---|
| Native macOS/Metal port of CS2 | Requires Valve. 0 % probability. |
| Boot Camp | **Does not exist on Apple Silicon** (Apple lists Intel Macs only). CONFIRMED. |
| Windows-on-ARM VM (Parallels/Fusion) | Adds a virtualization layer *and* Windows-on-ARM's own x86 translation on top of Rosetta; VM detection by anti-cheat is an added unknown. |
| `-vulkan` renderer | Real in the Windows build (Valve's own Workshop Tools launch entry passes `-vulkan`), but on Apple Silicon it lands on a 2023-frozen DXVK-macOS + a MoltenVK missing geometry shaders and transform feedback. CS2 silently falls back to DX11 on init failure — you can benchmark it believing you're on Vulkan. Test it in T-012, expect to reject it. |
| Patching CS2 binaries | Valve's VAC FAQ names modifying core executables/DLLs as cheating. The idea came from a mis-cited repo (G-2). |
| Cloud/streaming | **Not rejected** — it is the T-003 baseline this project must beat. |

## Data flow that must keep working

`Steam Guard auth → Steamworks init → SDR relay selection → matchmaking (usemms=1) → game server → VAC session
verification → voice (CoreAudio ↔ Wine) → HID raw input → Metal present`

Any one of these breaking is a *product* failure even at 200 FPS. Phase 3 tests them individually and in that order.
