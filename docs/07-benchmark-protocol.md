# 07 — Benchmark protocol

**Why this document exists:** essentially every published CS2-on-Mac FPS number is unusable, because it omits the
benchmark map and does not control for shader compilation. *Ancient* runs **25–30 % heavier than *Dust2*** on identical
hardware, and the first pass over any map is dominated by shader-compile hitches. A number without this protocol is a
rumour.

## Fixed variables (record every one, every run)
macOS build · chip / core split / GPU cores / RAM · CS2 `buildid` · runtime host + version · graphics backend +
version · sync mode · resolution · upscaler · in-game preset · HiDPI state · Steam overlay state · power source ·
Low Power Mode · display refresh · ambient temp (roughly) · time since boot.

## Procedure
1. Reboot. Nothing else running. Plugged in unless the run is explicitly a battery run.
2. Load the benchmark map and complete **3 discarded warm-up runs** (shader compilation).
3. Complete **5 measured runs**.
4. Report **median avg FPS**, **median 1 % low**, **p99 frametime**, and **hitch count (frames > 50 ms)**.
   Never report a maximum. Never report a single run.
5. Log `powermetrics` CPU/GPU power and memory pressure in parallel.

## Maps
* **Primary: Ancient FPS Benchmark — Workshop `3472126051`** (heavy; the honest number).
* **Secondary: Dust2 FPS Benchmark — Workshop `3240880604`** (light; comparable to most online claims).
* Never compare a number from one map against a number from the other.

## Reference field (for sanity-checking your result, not for bragging)

| Machine | RAM | Stack | Setting | Avg | 1 % low |
|---|---|---|---|---|---|
| M5 Pro MBP | 48 GB | CrossOver preview + GPTK 4.0b2, D3DMetal+MSync | 1080p med-low, FSR Q, Ancient | 190 | 140 |
| M5 Pro MBP | 48 GB | same | 1440p, FSR Q, Ancient | 145 | 110 |
| M4 Pro MBP | 24 GB | CrossOver + GPTK 3b, D3DMetal+MSync | 1080p med, no upscale, Ancient | 122 | — |
| M4 Pro MBP | 24 GB | same | 1080p med, FSR Q, **Dust2** | 160 | — |
| M4 Max MBP | — | CrossOver + CXPatcher, D3DMetal | 1440p high, Mirage DM | 100–140 | — |
| M3 Pro | — | DXMT | — | ~120 sustained | — |
| M1 Pro | 16 GB | DXMT | — | ~100 | — |
| M1 Air | 8 GB | — | 1080p | 50 | — |
| **M2 Max** | 96 GB | — | **native Retina 3024×1964** | **23** | — |
| M4 **Air** | 16 GB | — | — | 30–40 (thermal) | — |

**Expected for the M2 Pro / 32 GB target: ~100–125 avg @1080p medium.** A number far outside that means the protocol
or the configuration is wrong — investigate before celebrating or despairing.

## Three traps this protocol exists to prevent
1. **Benchmarking a cold shader cache** → invents a 1 %-low problem that warm-up would remove.
2. **Benchmarking at Retina backing-store resolution by accident** → ~4× cost (M2 Max: 23 FPS).
3. **Benchmarking DX11 while believing you're on Vulkan** → CS2 falls back to DX11 when Vulkan init fails. Check the
   console output, not the launch option.

## Input latency (T-015) — separate protocol
240 fps camera on the display; count frames from mouse-button depression to muzzle flash; 20 trials; report median and
IQR. **The number is only meaningful as a delta** against the same rig measured on native Windows or GFN. No such
measurement for CS2 under Wine on Apple Silicon exists publicly — this is the project's most citable contribution.
