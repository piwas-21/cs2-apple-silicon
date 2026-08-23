# Reference - first launch and the four known fixes (T-009)

**Status: TEMPLATE.** Apply the four fixes **before** you start debugging anything. Each one is a documented,
reproduced failure mode, not a superstition; each is sourced below. Every machine-specific output in the
"to be filled in on first run" block is **UNRECORDED** until a human runs this.

Acceptance (T-009): **the CS2 main menu renders and accepts mouse input.**

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

## 6. Only then, debug

```bash
WINEDEBUG=+loaddll,+seh wine ...
```

Change one thing at a time and write each change into the deviations table below. If you change the bottle, express
the change in `profiles/bottle-recipe.yaml` afterwards so `cs2kit bottle create` reproduces it (T-025) - an
undocumented bottle is not reproducible, and reproducibility is the entire product.

## 7. Expect shader-compilation hitching on the first pass

The first pass over any map is dominated by shader compilation. It is inherent to D3D-to-Metal translation, and
1-2 matches on a map makes it "much smoother" (CONFIRMED, multiple independent reports,
`research/performance-alternatives-findings.md` item 1). Do not diagnose it as a stack fault, and never benchmark
it (trap 1). T-013 quantifies it.

---

## To be filled in on first run

### Environment

| Field | Value |
|---|---|
| Date | UNRECORDED |
| macOS / build | UNRECORDED |
| Wine version | UNRECORDED |
| DXMT version | UNRECORDED |
| CS2 `buildid` | UNRECORDED |
| Launch options actually used | UNRECORDED |

### Which fixes were needed

| Fix | Needed? | Notes / exact file path touched |
|---|---|---|
| 1 - `CS2Video.txt` `fullscreen = 0` | UNRECORDED | UNRECORDED |
| 2 - `cs2.exe` compat mode Windows 8 | UNRECORDED | UNRECORDED |
| 3 - Retina off / 1920x1080 | UNRECORDED | UNRECORDED |
| 4 - renderer confirmed from the console | UNRECORDED | UNRECORDED |

### Errors, verbatim

| # | Stage | Error (verbatim) | Fix | Recipe change required? |
|---|---|---|---|---|
| 1 | UNRECORDED | UNRECORDED | UNRECORDED | UNRECORDED |

### Result

| Question | Answer |
|---|---|
| Main menu renders? | UNRECORDED |
| Mouse input accepted? | UNRECORDED |
| Time from launch to menu (cold) | UNRECORDED |
| First-map hitching (subjective, cold) | UNRECORDED |
| Renderer reported by the console | UNRECORDED |

### Acceptance (T-009)

* Main menu renders and accepts mouse input: **UNRECORDED**
* Recorded by: UNRECORDED - Date: UNRECORDED

Next: **T-010 [GATE]** - bot match on Dust2, Mirage and Ancient, each played twice, 30 minutes continuous
([../03-development-plan.md](../03-development-plan.md)).
