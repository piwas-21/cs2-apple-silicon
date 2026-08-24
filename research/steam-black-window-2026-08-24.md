# Steam's window is black under Wine on Apple Silicon — measured 2026-08-24

**Status: UNRESOLVED.** This file records what was measured so nobody repeats it. Machine of record:
M2 Pro, macOS 26.5.2 (25F84), Wine 11.15, DXMT v0.80, Steam client build 1785799196.

## The symptom

The Windows Steam client installs and self-updates inside the bottle, its processes run (browser + renderer +
GPU + utility `steamwebhelper.exe`), the login window exists with the right title (`Aanmelden bij Steam`,
700×440) — and it paints **pure black**, confirmed both by the user's eyes and by
`screencapture -l <window-id>` (mean luminance **0.0/255**, 0 % non-black pixels).

## The control that makes this readable

`wine notepad` in the same bottle renders **perfectly** — mean luminance **243.5/255**, 99.9 % non-black.
So Wine's window painting, the Mac driver and the capture method are all fine. The fault is specific to
Steam's Chromium (CEF) layer. **CONFIRMED.**

## What was tried

| # | Configuration | GPU-process crashes | Window |
|---|---|---|---|
| A | Wine **staging** 11.15 + DXMT v0.80 | 9 per launch | black |
| B | Wine staging, DXMT removed (Wine's own d3d11/dxgi restored) | 9 per launch | black |
| C | + `-cef-disable-gpu -cef-disable-gpu-compositing -cef-in-process-gpu` | 9 | black |
| D | + `-cef-use-angle=swiftshader -cef-use-gl=swiftshader` | 9 | black |
| E | Wine staging, `wine explorer /desktop=` virtual desktop | 9 | black |
| F | Wine **devel** 11.15, DXMT removed | **0** | black |
| G | **Fresh prefix** + Wine devel + `-cef-disable-gpu` | **0** | black |
| H | + `HKCU\Software\Wine\Mac Driver` `OpenGLSurfaceMode` = `behind`, then `transparent` | 0 | black |
| I | + `-cef-use-angle=gl` | 0 | black |

## Two distinct faults, both identified

1. **Wine staging crashes Steam's GPU process.** `gpu_process_host.cc(1002): GPU process exited unexpectedly:
   exit_code=-2147483645` (0xC0000005, access violation), repeating until Chromium gives up; `WINEDEBUG=+seh`
   puts the fault in `handle_syscall_fault`, i.e. on the unix side. Wine **devel** 11.15 produces **zero** such
   crashes. **CONFIRMED — prefer devel over staging for this stack.**
2. **DXMT breaks ANGLE's D3D11 capability query.** With DXMT installed:
   `Renderer11::populateRenderer11DeviceCaps: Error querying driver version from DXGI Adapter`, then
   `eglCreateContext: Requested GLES version (3.0) is greater than max supported (2, 0)`. DXMT itself logs
   `D3D11Resource(tex2d): Unknown interface query` for the same reason. **CONFIRMED.**
   Consequence for the design: **DXMT must be scoped to `cs2.exe`, not to the whole bottle** — Steam's UI needs
   no Metal translation, only the game does. `profiles/bottle-recipe.yaml` already expresses per-executable
   overrides; this is what they are for.
3. Neither fault explains the black window on its own: **G** and **H** have zero crashes, no DXMT, a clean
   prefix and still paint black. **The root cause is still UNKNOWN.**

## What has NOT been tried (in priority order)

1. **A CrossOver-sourced Wine** (FOSS CrossOver 24+/25 built from
   <https://media.codeweavers.com/pub/crossover/source/>). This is what DXMT's own wiki recommends, and
   CrossOver/Kegworks users run the Steam client daily — the strongest available signal that the client's CEF
   works there. Cost: a multi-hour build, or a prebuilt engine from a third party.
2. A different Steam client channel (`-clientbeta`), or an older client build.
3. `winemac.drv` under a virtual desktop **with** `-cef-disable-gpu` (E and G were tested separately, not together).

## The route that does not need the UI at all

`steamcmd.exe` runs headless in the same bottle and is already installed and self-updated at
`~/CS2/prefix2/drive_c/steamcmd/steamcmd.exe`. With `+@sSteamCmdForcePlatformType windows` and
`+force_install_dir "S:\steamapps\common\Counter-Strike Global Offensive"` it can install appid 730 into the
existing library, reusing the 58 GB content depot (T-008) and never rendering a pixel. Login still requires the
account owner to type their password and Steam Guard code — **CS2Kit never wraps Steam authentication**, so this
is a command the user runs, not something the tool does.

Whether CS2 can then be launched and matchmade while the client's UI is black is **UNKNOWN** and is the next
thing to measure.
