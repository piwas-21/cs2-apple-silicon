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


---

# UPDATE, later the same day: the root cause, measured

## `err: Failed to create metal view, it seems like your Wine has no exported symbols needed by DXMT`

CS2 itself printed it. Launching `cs2.exe` directly on **Gcenx Wine 11.15** (devel or staging), DXMT gets as far as
creating a device — `info: Maximum supported feature level: D3D_FEATURE_LEVEL_11_1` — and then **cannot create the
Metal view**, so nothing is ever presented. **CONFIRMED, and it reverses the earlier conclusion in
`research/wine-dxmt-install-findings-2026-08-24.md` §5.**

That earlier conclusion was drawn from a static symbol dump (`nm -m winemetal.so` shows no `winemac.drv` imports) and
it was **wrong**: DXMT resolves those entry points at runtime through Wine's unix-call interface, not as link-time
imports. A static dump cannot see it. **The DXMT wiki's requirement — a FOSS CrossOver Wine 24+, or a Wine patched
to export the `winemacdrv.h` API from `winemac.drv` — is real and still binding.**

Measured proof of the difference:

| Wine build | `nm -g winemac.so \| grep -c macdrv` | DXMT metal view | Steam CEF GPU process |
|---|---|---|---|
| Gcenx **staging** 11.15 | **0** | fails | crashes 9x per launch (0xC0000005) |
| Gcenx **devel** 11.15 | **0** | fails | no crashes |
| **Sikarugir CX 24.0.7** (Wine 9.0 base) | **1** (`_macdrv_functions`) | **no error** | no crashes |

This also explains the black Steam window: Steam's UI reaches D3D11 through ANGLE, ANGLE reaches DXMT, DXMT has no
Metal view, and the window presents nothing. The two symptoms had one cause.

## The Wine that works, and where it comes from

`WS12WineCX24.0.7_7.tar.xz` (172 MB, free) from
<https://github.com/Sikarugir-App/Engines/releases/tag/v1.0> —
sha256 `203f9e9fd6c2cc77e6525d798a434ced326145db34a356355e05659d3445fd1c`.
It is a **FOSS CrossOver 24.0.7** build; `wine --version` reports `wine-9.0 (SikarugirCX 24.0.7)`.

It needs the wrapper's dylibs beside the bundle (`@loader_path/../../`), otherwise `wineserver` dies with
`Library not loaded: @rpath/libinotify.0.dylib`. They come from
<https://github.com/Sikarugir-App/Wrapper/releases/tag/v1.0> (`Template-1.0.11.tar.xz`,
`Contents/Frameworks/*.dylib`). **CONFIRMED — this is a packaging dependency, not an optional extra.**

**Note the licence direction:** this project still redistributes nothing. Sikarugir's engine is a build of
CrossOver's published FOSS sources, which the user downloads themselves, exactly like the Gcenx tarball.

## State at the end of this session

* **T-008 DONE.** `cs2.exe` (2,967,704 bytes) and 123 files in `game/bin/win64`; `appmanifest_730.acf`
  `StateFlags 4`, `SizeOnDisk 71,644,882,396`. Installed head-lessly with `steamcmd` — the black UI never mattered.
  The 58 GB reuse did **not** happen: steamcmd re-downloaded ~71.7 GB, which is the fallback the plan allowed for.
* **T-021 DONE.** 137 guarded binaries baselined after steamcmd's own `validate` pass.
* **Wine of record changes to the CrossOver engine.** Gcenx Wine cannot run DXMT at all on this machine.
* **UNKNOWN, next to measure:** whether the Steam client's login window renders on the CX engine (it bootstraps
  with zero GPU-process crashes, but no window was observed within ~5 minutes, and the log shows
  `err:bcrypt:key_asymmetric_create no encryption support`, which may block the login handshake until the
  wrapper's crypto dylibs are wired correctly).


---

# The 0x3008 transport error — narrowed, 2026-08-24 (CrossOver engine)

**First, the good news, confirmed independently by the user and by the agent: on the FOSS CrossOver 24.0.7 engine
Steam's UI RENDERS.** A fully drawn Steam dialog (mean luminance 37.3/255, 90.6 % non-black pixels — against 0.0 on
every Gcenx run). The black-window failure is **solved by the engine change**, and the earlier "no window at all"
observations were an artefact of the agent's own process, not of the stack.

What remains is a different, smaller fault:

> **Onverwachte transportfout** — "An unexpected error occurred while starting Steam (**0x3008**)"

## The measurement that names it

`logs/transport_client.txt`, repeating **82 times** in one session:

```
WebUITransport: Websocket connection from: https://steamloopback.host
WebUITransport: Connection from: 127.0.0.1:64431
WebUITransport: TCP connection request
WebUITransport: Connection rejected
```

and in `logs/console_log.txt`:

```
src\steamUI\webuitransportcontroller.cpp (165) : Failed to reconnect to websocket: wine
```

So `steamwebhelper.exe` **successfully connects** to the client over loopback TCP, and **the client rejects it**.
This is not a rendering fault, not a GPU fault and not a socket-availability fault: the connection is made and then
refused at Steam's own layer. **CONFIRMED.**

## Hypotheses eliminated by experiment

| Hypothesis | Test | Result |
|---|---|---|
| DXMT breaks the client | `cs2kit bottle restore-wine`, relaunch | **0x3008 unchanged** — DXMT is innocent |
| CEF sandbox | `-no-cef-sandbox` (now always passed by `cs2kit launch`) | necessary but **not sufficient** |
| GPU/compositing | `-cef-disable-gpu` | unchanged |
| Corrupt web cache | deleted `htmlcache` + `appcache/httpcache` | unchanged |
| Stale helper processes | full `pkill` + `wineserver -k` before every launch | unchanged |

## Not yet tried

1. **The dialog's own third option — "(Valve only) Continue anyway".** One click; it may proceed to the login
   screen with a degraded UI. This is the cheapest untested action and it needs a human at the keyboard.
2. Building the bottle with **Sikarugir Creator** rather than by hand — the wrapper may configure something the
   hand-built prefix lacks.
3. A **newer CrossOver engine** (25.x). Sikarugir's public engine list stops at 24.0.7; the Kegworks tap now
   redirects to Sikarugir, so there is no newer free build to fetch today.
