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

## The disk trap found on this machine (drives T-001)

`~/Library/Application Support/Steam/steamapps/` contains:

* `appmanifest_730.acf` — *Counter-Strike 2*, `TargetBuildID 24828357`, `installdir "Counter-Strike Global Offensive"`,
  `BytesToDownload 54,888,337,776`, `BytesToStage 63,933,013,362`, **`BytesDownloaded 0`**, `StateFlags 1026`,
  `InstalledDepots {}` (empty).
* `downloading/730/` — **60 GB** on disk, containing `game/{bin,core,csgo,csgo_core,csgo_lv}`.
  `bin/` contains **only `win64/`** (no `linuxsteamrt64`, no `osx64`) and **0 `.dll`, 0 `.so`, 0 `.dylib` files** —
  directory skeletons pre-created from the manifest, no executables.
* `common/Counter-Strike Global Offensive/` — leftover CS:GO-era macOS install (`csgo/`, `platform/`,
  `installscript.vdf`, a `WINDOWSTEMPDIR_FONTCONFIG_CACHE`).

**Diagnosis.** `BytesToDownload` decomposes exactly as depot 2347770 (53,938,731,200) + 2347774 (949,604,816) +
2347772 macOS stub (1,696) + an 8-byte stub (64) = **54,888,337,776**. Depot **2347771** — `"cs2 windows"`, file
regex `.+?\.(dll|exe)`, 4.99 GB, i.e. **every executable in the game** — was **not queued**. `StateFlags 1026` =
`StateUpdateStarted(1024) | StateUpdateRequired(2)`, with no downloading/running bit: **queued and never scheduled.**

**Conclusion.** This download can never produce a runnable CS2. It is 60 GB of dead weight on a volume that needs
~72 GB free for the *correct* (in-bottle Windows) install. **Delete it first — T-001.**

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
