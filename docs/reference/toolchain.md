# T-004 — Toolchain of record

Everything here was **downloaded, checksummed and installed on the machine of record on 2026-08-24**.
Nothing in this file is a plan: if a value is here, it was measured on that machine. Reproduce the stack by
running the commands in order — no Homebrew, no admin rights, no paid software.

**Why not Homebrew:** the plan's original command, `brew install --cask gcenx/wine/wine-crossover`, no longer
exists (the cask was deleted from the tap on **2026-04-16**, and it had shipped Wine **8.0.1**, not 11.x).
Homebrew's own `wine-stable` / `wine@staging` casks are **deprecated for failing the macOS Gatekeeper check and are
disabled on 2026-09-01**. A tarball has neither problem. See
[research/wine-dxmt-install-findings-2026-08-24.md](../../research/wine-dxmt-install-findings-2026-08-24.md).

**Why not the WineHQ/Gcenx tarball either:** it cannot run this stack. Gcenx Wine 11.15 exports no `winemac.drv`
symbols, so DXMT cannot create a Metal view — CS2 prints *"Failed to create metal view, it seems like your Wine has
no exported symbols needed by DXMT"* and Steam's own window renders black. MEASURED, with the experiment table, in
[research/steam-black-window-2026-08-24.md](../../research/steam-black-window-2026-08-24.md).

## Components

| Component | Version | Licence | Size | Source |
|---|---|---|---|---|
| Wine — **the one that works** | **Sikarugir Wine 10.0** (`wine-10.0 (Sikarugir)`) | LGPL-2.1 | 166 304 096 B (159 MiB) | [Sikarugir-App/Engines v1.0](https://github.com/Sikarugir-App/Engines/releases/tag/v1.0), `WS12WineSikarugir10.0_6.tar.xz` — listed in the project's own [EngineList.txt](https://raw.githubusercontent.com/Sikarugir-App/Engines/main/EngineList.txt) |
| Wine wrapper dylibs (**required** by the engine) | Template 1.0.11 | mixed FOSS | 84 533 420 B (81 MiB) | [Sikarugir-App/Wrapper v1.0](https://github.com/Sikarugir-App/Wrapper/releases/tag/v1.0) — `Contents/Frameworks/*.dylib` staged into `<engine>/lib/`, or `wineserver` dies on `libinotify.0.dylib` |
| DXMT (builtin build) | **v0.80** | **MIT** (v0.81+ will be LGPL) | 18 681 669 B (18 MiB) | [3Shain/DXMT v0.80](https://github.com/3Shain/DXMT/releases/tag/v0.80), released 2026-04-23 |
| Windows Steam client | build **1785799196** | proprietary (Valve) | 2 380 800 B installer | `https://cdn.akamai.steamstatic.com/client/installer/SteamSetup.exe` |
| MSync | in-tree | LGPL-2.1 | — | Wine build above (`WINEMSYNC=1`) |
| Rosetta 2 | system | Apple | — | `softwareupdate --install-rosetta --agree-to-license` |

### Rejected engines — kept here so nobody re-tries them

| Engine | Version | Size | Why it is not the engine of record |
|---|---|---|---|
| FOSS CrossOver 24.0.7 | `wine-9.0 (SikarugirCX 24.0.7)` | 172 348 356 B | Renders Steam and gives DXMT its Metal view, but its Wine 9.0 base makes the client **reject the helper's loopback websocket** — *"Unexpected transport error (0x3008)"*, 82 rejections in one session. Login is impossible. `WS12WineCX24.0.7_7.tar.xz`, sha256 `203f9e9fd6c2cc77e6525d798a434ced326145db34a356355e05659d3445fd1c` |
| Gcenx Wine 11.15 staging | `wine-11.15 (Staging)` | 193 561 920 B | **No `winemac.drv` exports** → no Metal view → CS2 fails and Steam's window is black. Also crashes Steam's CEF GPU process 9x per launch (`0xC0000005`). `wine-staging-11.15-osx64.tar.xz`, sha256 `a8c50d0e14fb7982a21506287e1e41e1990fe77c74fa2a32da7dbcf7b21de1e2` |
| Gcenx Wine 11.15 devel | `wine-11.15 (Devel)` | 191 398 232 B | Same missing exports; no GPU-process crashes. Still cannot render a frame |

`cs2kit engine list` prints this table from the same data, so the CLI and this file cannot drift apart.

## Checksums (SHA-256, verified on download with `shasum -a 256`)

```
9da7ee0cbf386522f3a9906943726d9c3c125dbbd9ab120e3cde80e88d6091b2  WS12WineSikarugir10.0_6.tar.xz
9fa15479e7ff6abd99c1d07be285fb95f41fc6991586502427152b1f7d6ccb8a  Template-1.0.11.tar.xz
8f260e36b5739e68f3bad613381441385c4dc7b85b78ba8de653d5a6a264529d  dxmt-v0.80-builtin.tar.gz
7d3654531c32d941b8cae81c4137fc542172bfa9635f169cb392f245a0a12bcb  SteamSetup.exe
```

Rejected builds, for completeness:

```
203f9e9fd6c2cc77e6525d798a434ced326145db34a356355e05659d3445fd1c  WS12WineCX24.0.7_7.tar.xz
a8c50d0e14fb7982a21506287e1e41e1990fe77c74fa2a32da7dbcf7b21de1e2  wine-staging-11.15-osx64.tar.xz
```

`SteamSetup.exe` is a moving target — Valve replaces it in place. The digest above is what that URL served on
2026-08-24; a different digest is not a fault, it is a newer installer.

## Reproduce it

```bash
# 1. The engine: download, verify, extract, and stage the wrapper dylibs beside it.
cs2kit engine list                                  # the three engines and the measured verdicts
cs2kit engine install                               # defaults to sikarugir-10

export WINE_ROOT="$HOME/.cs2kit/engines/sikarugir-10/wswine.bundle"
export PATH="$WINE_ROOT/bin:$PATH"
wine --version                                      # -> wine-10.0 (Sikarugir)

# 2. The check that decides whether this engine can run CS2 at all.
nm -g "$WINE_ROOT/lib/wine/x86_64-unix/winemac.so" | grep macdrv    # -> ..._macdrv_functions

# 3. DXMT.
mkdir -p ~/CS2/downloads && cd ~/CS2/downloads
curl -fL -O https://github.com/3Shain/DXMT/releases/download/v0.80/dxmt-v0.80-builtin.tar.gz
shasum -a 256 -c <<'SUMS'
8f260e36b5739e68f3bad613381441385c4dc7b85b78ba8de653d5a6a264529d  dxmt-v0.80-builtin.tar.gz
SUMS
mkdir -p ~/CS2/dxmt
tar -xzf dxmt-v0.80-builtin.tar.gz -C ~/CS2/dxmt

# 4. The bottle. Places DXMT into the WINE TREE, sets no d3d11/dxgi overrides.
export WINEPREFIX="$HOME/CS2/prefix"
cs2kit bottle create --dxmt ~/CS2/dxmt/v0.80 --wine-root "$WINE_ROOT"
cs2kit doctor                                       # DXMT and 'winemac.drv exports' must read PASS
```

<details>
<summary><b>Without <code>cs2kit engine install</code></b> — the same thing by hand</summary>

```bash
mkdir -p ~/CS2/downloads && cd ~/CS2/downloads
curl -fL -O https://github.com/Sikarugir-App/Engines/releases/download/v1.0/WS12WineSikarugir10.0_6.tar.xz
curl -fL -O https://github.com/Sikarugir-App/Wrapper/releases/download/v1.0/Template-1.0.11.tar.xz
shasum -a 256 -c <<'SUMS'
9da7ee0cbf386522f3a9906943726d9c3c125dbbd9ab120e3cde80e88d6091b2  WS12WineSikarugir10.0_6.tar.xz
9fa15479e7ff6abd99c1d07be285fb95f41fc6991586502427152b1f7d6ccb8a  Template-1.0.11.tar.xz
SUMS

mkdir -p ~/CS2/engine
tar -xJf WS12WineSikarugir10.0_6.tar.xz -C ~/CS2/engine     # -> ~/CS2/engine/wswine.bundle
tar -xJf Template-1.0.11.tar.xz          -C ~/CS2/engine     # -> ~/CS2/engine/Template-1.0.11.app
cp ~/CS2/engine/Template-1.0.11.app/Contents/Frameworks/*.dylib ~/CS2/engine/wswine.bundle/lib/

export WINE_ROOT="$HOME/CS2/engine/wswine.bundle"
```
</details>

## Installed layout (what `cs2kit bottle create` actually did)

`dxmt.build: builtin` in `profiles/bottle-recipe.yaml` means the DLLs belong to **Wine**, not to the prefix, and
the `d3d11`/`dxgi` overrides must stay **off** — DXMT's wiki: *"Ensure these dlls are **NOT** set overrides
`native,builtin`."*

```
$WINE_ROOT/                                  wine-10.0 (Sikarugir)
  bin/wine
  lib/*.dylib                                the wrapper's dylibs; without them wineserver aborts
  lib/wine/x86_64-unix/winemac.so            exports _macdrv_functions  <- the reason this engine works
  lib/wine/x86_64-unix/winemetal.so          DXMT's Metal backend (unix side)
  lib/wine/x86_64-windows/{d3d11,dxgi,d3d10core,winemetal}.dll
  lib/wine/i386-windows/{d3d11,dxgi,d3d10core,winemetal}.dll     for the 32-bit Steam client
$WINEPREFIX/
  drive_c/windows/system32/winemetal.dll     the one file that belongs in both places
  drive_c/Program Files (x86)/Steam/steamapps -> ~/Library/Application Support/Steam/steamapps
  .cs2kit/state.json                         recipe name + hash + wine root, written by cs2kit
```

**The DXMT DLLs live in the engine, not in the prefix.** Installing a new engine therefore removes DXMT from your
path; re-run `cs2kit bottle create --wine-root <the new engine>` after every engine change.

## Proof DXMT is live (before any game exists)

```bash
WINEDEBUG=+loaddll,+dxmt wine rundll32 d3d11.dll,NoSuchEntry
```

Measured output on 2026-08-24 (M2 Pro, macOS 26.5.2 build 25F84):

```
Loaded L"C:\\windows\\system32\\winemetal.dll" ... builtin
Loaded L"C:\\windows\\system32\\DXGI.DLL"      ... builtin
Loaded L"C:\\windows\\system32\\d3d11.dll"     ... builtin
info:  Failed to set Metal cache path, fallback to system default     <- DXMT's own log line
[mvk-info] ... Metal Shading Language 3.1 ... GPU Family Metal 3
```

* **CONFIRMED:** DXMT v0.80 loads and initialises Metal as a Wine **builtin**, with no DLL overrides set.
* **CONFIRMED, and it corrects an earlier reading of this same evidence:** loading is not presenting. DXMT resolves
  Wine's `winemac.drv` API **at runtime** through the unix-call interface, so `nm -m winemetal.so` showing no
  `winemac` imports proves nothing — the requirement in DXMT's wiki (a Wine that exports the `winemacdrv.h` API) is
  **real and binding**. That mistake cost this project a day; the `nm -g … | grep macdrv` check in step 2 is what
  catches it, and `cs2kit doctor` runs it.
* **CONFIRMED on 2026-08-24:** CS2 renders through this stack — DXMT at `D3D_FEATURE_LEVEL_11_1`, zero metal-view
  errors, a played bot match on Dust2 ([../implementation-status.md](../implementation-status.md)).
* **Lead for T-013:** DXMT could not set its Metal shader-cache path and fell back to the system default.

## Environment of record

`docs/reference/env-snapshot-0.json`, regenerated with `cs2kit env --save`. The `stable` half is what every
benchmark is keyed by; re-run it after any toolchain change — **including an engine change.**

## Rejected, and why

| Route | Why not |
|---|---|
| **Gcenx / WineHQ macOS tarballs** (11.15 staging or devel) | No `winemac.drv` exports → DXMT cannot create a Metal view → CS2 fails and Steam's window is black. MEASURED |
| **FOSS CrossOver 24.0.7** (`WS12WineCX24.0.7_7.tar.xz`) | Renders Steam and runs DXMT, but the client rejects its own helper's websocket (0x3008) on its Wine 9.0 base. MEASURED |
| `brew install --cask gcenx/wine/wine-crossover` | **Deleted from the tap 2026-04-16**; last shipped Wine 8.0.1 |
| `brew install --cask wine-stable` / `wine@staging` | Deprecated for failing Gatekeeper; **disabled 2026-09-01** |
| Building FOSS CrossOver Wine 24+ from CodeWeavers sources | The DXMT wiki's recommendation, and the requirement it states is real — but Sikarugir publishes a prebuilt engine that satisfies it. Keep as the fallback if those releases disappear |
| Apple's D3DMetal / GPTK | Deliberately excluded — we redistribute nothing of Apple's ([docs/06](../06-legal-and-policy.md)) |
| Whisky, Porting Kit, CrossOver | Not part of this plan ([docs/02](../02-architecture.md)) |
