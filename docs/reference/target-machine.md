# Reference — target machine of record

Measured 2026-08-23 on the development Mac. All Phase 1–3 numbers in this repo refer to this machine unless stated.

| Property | Value |
|---|---|
| macOS | **26.5.2** (build 25F84) |
| Chip | **Apple M2 Pro** |
| CPU | 10 cores — **6 performance + 4 efficiency** |
| GPU | **16 cores**, Metal support: **Metal 4** |
| RAM | **32 GB** unified (34,359,738,368 B) |
| Display | Built-in Liquid Retina XDR, **3024 × 1964** Retina |
| Architecture | `arm64` |
| Rosetta 2 | **present and active** (`oahd` running; `/Library/Apple/usr/libexec/oah` incl. `RosettaLinux`) |
| Disk free at survey | **96 GiB** of 460 GiB — **insufficient**, see below |
| Steam.app | universal binary (`x86_64` + **`arm64` native**) |
| CrossOver / Whisky / Heroic / wine | **none installed** |

## The confirmed blocker on this machine (drives T-001) — updated 2026-08-23 18:10

macOS Steam **completed** the CS2 install. It is unplayable. This is the strongest possible confirmation of G-1,
observed at completion rather than inferred from a queue.

`appmanifest_730.acf`: `StateFlags 4` (installed) · `SizeOnDisk 66,024,731,334` · `BytesToDownload 0` ·
`buildid 24828357` · `LastPlayed` set (a launch was attempted).

| Depot | Installed? | Size | What it is |
|---|---|---|---|
| 2347770 | ✅ | 62,790,947,954 | OS-agnostic game content (maps, models, sounds) |
| 2347774 | ✅ | 1,142,056,124 | OS-agnostic content |
| 2347772 | ✅ | 9,276 | CS:GO-era macOS stub |
| 2347779 | ✅ | 2,091,728,725 | **Workshop Tools DLC** (`optionaldlc 2279721`) |
| 731 / 733 / 735 | ✅ | 8 B each | stubs |
| **2347771** | ❌ **ABSENT** | 4.99 GB dl | **`"cs2 windows"` — every `.exe` and `.dll` of the game** |

Verified missing on disk: `cs2.exe`, `engine2.dll`, `client.dll`, `server.dll`, `tier0.dll`, `schemasystem.dll`,
`rendersystemdx11.dll`, `rendersystemvulkan.dll`, `steam_api64.dll`.
The only 9 `.exe` files present are Workshop authoring tools from depot 2347779 — `resourcecompiler.exe`,
`vrad3.exe`, `source1import.exe`, `dmxconvert.exe`, `cs_mdl_import.exe`, `resourcecopy.exe`, `resourceinfo.exe`,
`csgocfg.exe`, `cs2_build_econ_items_workshop.exe`. **None of them is the game.**

**Two consequences.** (1) *Verify integrity of game files* **cannot fix this** — Steam considers the install
complete (`BytesToDownload 0`), and its macOS depot selection is what omits 2347771. (2) The 58 GB `csgo/` asset
tree is nevertheless **correct and reusable** by a Windows install, because depot 2347770 has no OS filter. That
turns the remaining work into a **4.99 GB** gap rather than a 72 GB re-download — see T-008 Option A2.

Free space: **90 GiB**.

## Disk budget for the real path

| Item | Size |
|---|---|
| CS2 Windows depots (2347770 + 2347771 + 2347774 + 2347777) download | ~60 GB |
| On disk after install | **~72 GB** |
| Bottle + Windows Steam client | ~2–4 GB |
| Shader caches, logs, benchmarks | ~2 GB |
| Working headroom (staging, updates) | ~20 GB |
| **Required free before starting Phase 1** | **~150 GiB** |
| Currently free | 96 GiB → **reclaim 60 GiB via T-001, then re-check** |

## Expected performance for this machine

Interpolating the reference field (`docs/07-benchmark-protocol.md`): **~100–125 avg FPS at 1080p medium** on the
Ancient benchmark — between the M1 Pro (~100) and the M4 Pro (122). The 32 GB of unified memory is comfortable
(CS2 alone ≈ 6.1 GB); **RAM is not this machine's constraint — backend choice, shader-cache warmth and resolution
are.** Note the actively-cooled MacBook **Pro** chassis matters: fanless M-series machines fall to 30–40 FPS under
sustained load.
