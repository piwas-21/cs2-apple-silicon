# Reference - first launch and the four known fixes (T-009)

**Status: T-009 ACHIEVED on the machine of record, 2026-08-24.** CS2 launches and draws through DXMT on Apple
Silicon. The record below is filled in with what was measured; anything still marked **UNRECORDED** was not
measured and must not be guessed.

Apply the four fixes **before** you start debugging anything. Each one is a documented, reproduced failure mode,
not a superstition; each is sourced below.

Acceptance (T-009): **the CS2 main menu renders and accepts mouse input.** — **MET.**

> **Fix 0, which outranks all four: be on the right engine.** On Gcenx Wine 11.15 nothing below matters — DXMT
> reports `Maximum supported feature level: D3D_FEATURE_LEVEL_11_1` and then fails with
> `err: Failed to create metal view, it seems like your Wine has no exported symbols needed by DXMT`. The engine of
> record is **Sikarugir Wine 10.0**; check it with
> `nm -g "$WINE_ROOT/lib/wine/x86_64-unix/winemac.so" | grep macdrv` before anything else
> ([../02-architecture.md](../02-architecture.md)).

---

## 0. Before the first launch

```bash
cs2kit doctor                 # must be free of FAILs
cs2kit verify --json          # T-021 baseline: game files as Steam validated them
```

If `cs2kit verify` has no baseline yet, take one immediately after Steam's own "Verify integrity of game files"
pass - that is the byte-identical reference the project enforces forever
([../06-legal-and-policy.md](../06-legal-and-policy.md), absolute rule 1).

## 1. Launch options

In the in-bottle Steam client: CS2 -> Properties -> Launch Options:

```
-novid -nojoy -console
```

* `-console` is what lets you *read* the renderer the game actually chose - see fix 4.
* **Not `-vulkan`.** The Windows build really does have a Vulkan renderer (CONFIRMED, Valve appinfo launch entry 6),
  but on Apple Silicon it routes through a DXVK-macOS fork frozen at 1.10.3 since 2023 and a MoltenVK with no
  geometry shaders. Two independent users report "won't launch" or "a frame per minute"
  (`research/performance-alternatives-findings.md` item 12). One confirmation run in T-012, then dropped.
* **Not `-d3d9ex`.** CS:GO-era flag; Source 2 has no D3D9 path (CONFIRMED, same file, item 13).
* **Not `-untrusted`.** Valve's 2020 Trusted Mode post says it may reduce your Trust score, and CS2's status is
  UNKNOWN (`research/steam-vac-findings.md`, Trusted Mode). Do not ship it by default.

## 2. Fix 1 - black screen on launch (audio plays, nothing renders)

Symptom: the game runs, you hear the menu, the window is black.

Fix, in order of cost:
1. Alt-tab away and back, or toggle fullscreen manually.
2. Permanent: set `setting.fullscreen` to `0` in `CS2Video.txt`. `cs2kit config apply <profile> --video` writes it
   to `<install>/game/csgo/cfg/CS2Video.txt`, which is the path CS2Kit uses.

CS2 can also keep per-account video settings under the Steam `userdata` tree. **Which file this bottle actually
reads is UNRECORDED** - confirm it on the first run and write the answer into the table below, because every later
reader will copy whichever path is recorded here.

Evidence: CONFIRMED, multiple independent reports - CodeWeavers forum thread "Black screen when I load CS2 (mac M1)"
and a video walkthrough, `research/performance-alternatives-findings.md` item 2.

## 3. Fix 2 - audio crackling, and audio dying after alt-tab

Set **`cs2.exe` to Windows 8** in the bottle:

```bash
WINEPREFIX="$HOME/CS2/prefix" winecfg      # Applications -> Add application -> cs2.exe -> Windows 8
```

The `cs2.exe` path inside the bottle is
`drive_c/Program Files (x86)/Steam/steamapps/common/Counter-Strike Global Offensive/game/bin/win64/cs2.exe`
(or the same tail under whichever library folder you added in T-007).

This is the **documented permanent fix** and it repairs microphone input as well as output. A second, weaker remedy
is Audio MIDI Setup -> output device -> Format -> 96,000 Hz. Evidence: CONFIRMED, CodeWeavers tip "Broken audio on
Mac" plus forum msg=290698, `research/performance-alternatives-findings.md` items 3 and 4.

This is a **bottle-level** setting, so it survives CS2 updates - unlike anything that would touch a game file, which
this project never does. `cs2kit doctor` re-checks it (the compat-mode check) and `cs2kit bottle repair` restores it
from the recipe.

## 4. Fix 3 - Retina off, render at 1920x1080 or lower

Native 3024x1964 costs roughly **4x**: a 96 GB M2 Max measured **23 FPS** at native Retina
([../07-benchmark-protocol.md](../07-benchmark-protocol.md), reference field; CONFIRMED). Turn Retina/HiDPI off in
the bottle and set the game to 1920x1080 or lower.

Verify it actually took effect. Benchmarking at the Retina backing-store resolution by accident is trap 2 of the
benchmark protocol, and it invents a performance problem that does not exist.

## 5. Fix 4 - confirm which renderer you are actually on

CS2 **silently falls back to DX11 when Vulkan initialisation fails** ([../07-benchmark-protocol.md](../07-benchmark-protocol.md),
trap 3). Read the console output - the launch option is not evidence. With DXMT installed and no `-vulkan`, DX11 via
DXMT is the intended and correct answer; the point of the check is that you *know*, rather than assume.

## 6. How to actually start it, and what to do when it will not restart

With the in-bottle client logged in and running, `cs2kit launch` is the supported way in: it checks the integrity
baseline, applies the profile environment and hands off to Steam with `-no-cef-sandbox`.

**`Steam.exe -applaunch 730` refuses to relaunch while the client still believes a session is running** — the state
you are in after killing CS2 between maps. Launching the executable directly always worked (MEASURED 2026-08-24):

```bash
cd "$WINEPREFIX/drive_c/Program Files (x86)/Steam/steamapps/common/Counter-Strike Global Offensive"
wine game/bin/win64/cs2.exe -novid -nojoy -console
```

That path skips the integrity guard, so run `cs2kit verify check` first.

## 7. Only then, debug

```bash
WINEDEBUG=+loaddll,+seh wine ...
```

Change one thing at a time and write each change into the deviations table below. If you change the bottle, express
the change in `profiles/bottle-recipe.yaml` afterwards so `cs2kit bottle create` reproduces it (T-025) - an
undocumented bottle is not reproducible, and reproducibility is the entire product.

## 8. Expect shader-compilation hitching on the first pass

The first pass over any map is dominated by shader compilation. It is inherent to D3D-to-Metal translation, and
1-2 matches on a map makes it "much smoother" (CONFIRMED, multiple independent reports,
`research/performance-alternatives-findings.md` item 1). Do not diagnose it as a stack fault, and never benchmark
it (trap 1). T-013 quantifies it.

---

---

## The record — machine of record, 2026-08-24

### Environment

| Field | Value |
|---|---|
| Date | **2026-08-24** |
| macOS / build | **26.5.2 (25F84)**, Apple M2 Pro, 32 GB ([target-machine.md](target-machine.md)) |
| Wine version | **`wine-10.0 (Sikarugir)`** — `WS12WineSikarugir10.0_6.tar.xz` ([toolchain.md](toolchain.md)) |
| DXMT version | **v0.80**, the builtin build; the loaded `d3d11.dll` hashes to DXMT's release binary (`7ca382af…`), not Wine's own (`e333b8c6…`) |
| CS2 `buildid` | **24828357** |
| Launch options actually used | `-novid -nojoy -console` (recipe default; the direct-launch runs used the same) |
| Steam client flags | `-no-cef-sandbox` — **mandatory**, see [../10-troubleshooting.md](../10-troubleshooting.md) entry 18 |

### Which fixes were needed

| Fix | Needed? | Notes / exact file path touched |
|---|---|---|
| 0 - the right engine | **YES, decisive** | Gcenx Wine 11.15 fails with `Failed to create metal view`; Sikarugir Wine 10.0 works. This is the whole of T-009's difficulty |
| 1 - `CS2Video.txt` `fullscreen = 0` | **no** | The menu and the video-settings screen rendered on the first launch without it. **Which copy CS2 reads under Wine is still UNRECORDED** — nobody had to find out |
| 2 - `cs2.exe` compat mode Windows 8 | **applied** | Pinned by `profiles/bottle-recipe.yaml` and placed by `cs2kit bottle create`, so it was in effect from the first launch. Whether audio *needs* it here is **UNRECORDED** — audio has not been assessed at all (T-016) |
| 3 - Retina off / 1920x1080 | **NOT applied** | The first session ran at the Retina backing resolution (**3024x1964** from a 1512x982-point window) at CS2's auto-selected **Low** preset. So the 117 fps sample was measured *with* the trap still in place, not after tuning |
| 4 - renderer confirmed from the console | **yes** | DXMT logged `Using feature level D3D_FEATURE_LEVEL_11_1` with **zero** `Failed to create metal view` errors; the loaded `d3d11.dll` is DXMT's, not Wine's |

### Errors, verbatim

| # | Stage | Error (verbatim) | Fix | Recipe change required? |
|---|---|---|---|---|
| 1 | launching `cs2.exe` on Gcenx Wine 11.15 (staging and devel) | `err: Failed to create metal view, it seems like your Wine has no exported symbols needed by DXMT` | change the engine to Sikarugir Wine 10.0 (`cs2kit engine install`), then re-run `cs2kit bottle create` so DXMT lands in the new engine | **yes** — `wine.root` now names the Sikarugir engine |
| 2 | starting the Steam client | `An unexpected error occurred while starting Steam (0x3008)` | `-no-cef-sandbox` (necessary on every engine); on FOSS CrossOver 24.0.7 it is **not sufficient** — that engine's client rejects its own helper's websocket | no — `cs2kit launch` passes the flag |
| 3 | first `wineserver` start on a bare engine | `Library not loaded: @rpath/libinotify.0.dylib` | stage the wrapper's `Contents/Frameworks/*.dylib` into `<engine>/lib/`; `cs2kit engine install` does it | no |
| 4 | every DXMT start | `info:  Failed to set Metal cache path, fallback to system default` | none needed — DXMT still initialises. Open lead for T-013; the missing-symbol hypothesis was tested and ruled out | no |

### Result

| Question | Answer |
|---|---|
| Main menu renders? | **YES** — the video-settings screen with live 3D previews drew at 3024x1964, mean luminance 98/255, 99.8 % non-black |
| Mouse input accepted? | **YES** — menus were navigated and a bot match started. Input *latency* is unmeasured (T-015) |
| Time from launch to menu (cold) | **~2 min 46 s** — `launch` 17:33:02Z to first rendered frame 17:35:48Z ([t010-dust2-log.jsonl](t010-dust2-log.jsonl)) |
| First-map hitching (subjective, cold) | **UNRECORDED** — no human sat through the cold pass; the automated monitor saw 0 frozen frames in 22 samples |
| Renderer reported by the console | **DX11 through DXMT v0.80**, `D3D_FEATURE_LEVEL_11_1` |
| Frame rate | **117 fps**, one sample, Dust2 bot match, auto-selected Low preset, 1512x982-point window. **Not a benchmark** — T-011 produces the number this project stands behind ([../07-benchmark-protocol.md](../07-benchmark-protocol.md)) |
| Measurement hazard found the same day | `screencapture -l` sampling every 20 s dropped the game from **72 fps to 3 fps**. Never sample frame rate by screenshot ([../07-benchmark-protocol.md](../07-benchmark-protocol.md)) |
| Audio | **UNRECORDED** — no automated signal exists and nobody has listened yet (T-016) |

### Acceptance (T-009)

* Main menu renders and accepts mouse input: **YES, 2026-08-24**, on Sikarugir Wine 10.0 + DXMT v0.80.
* Recorded by: the session logged in [../implementation-status.md](../implementation-status.md) - Date: **2026-08-24**

Next: **T-010 [GATE]** - bot match on Dust2, Mirage and Ancient, each played twice, 30 minutes continuous
([../03-development-plan.md](../03-development-plan.md)). One Dust2 pass is done: 10 minutes, 0 crashes,
0 frozen frames, RSS 0.7-1.4 GB. Five passes and a human ear remain.
