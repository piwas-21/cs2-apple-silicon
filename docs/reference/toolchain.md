# T-004 — Toolchain of record

Everything here was **downloaded, checksummed and installed on the machine of record on 2026-08-24**.
Nothing in this file is a plan: if a value is here, it was measured on that machine. Reproduce the stack by
running the commands in order — no Homebrew, no admin rights, no paid software.

**Why not Homebrew:** the plan's original command, `brew install --cask gcenx/wine/wine-crossover`, no longer
exists (the cask was deleted from the tap on **2026-04-16**, and it had shipped Wine **8.0.1**, not 11.x).
Homebrew's own `wine-stable` / `wine@staging` casks are **deprecated for failing the macOS Gatekeeper check and are
disabled on 2026-09-01**. A tarball has neither problem. See
[research/wine-dxmt-install-findings-2026-08-24.md](../../research/wine-dxmt-install-findings-2026-08-24.md).

## Components

| Component | Version | Licence | Size | Source |
|---|---|---|---|---|
| Wine (staging, macOS build) | **11.15** | LGPL-2.1 | 185 MB | [Gcenx/macOS_Wine_builds 11.15](https://github.com/Gcenx/macOS_Wine_builds/releases/tag/11.15), released 2026-08-08 |
| DXMT (builtin build) | **v0.80** | **MIT** (v0.81+ will be LGPL) | 18 MB | [3Shain/DXMT v0.80](https://github.com/3Shain/DXMT/releases/tag/v0.80), released 2026-04-23 |
| MSync | in-tree | LGPL-2.1 | — | Wine build above (`WINEMSYNC=1`) |
| Rosetta 2 | system | Apple | — | `softwareupdate --install-rosetta --agree-to-license` |

## Checksums (SHA-256, verified on download)

```
a8c50d0e14fb7982a21506287e1e41e1990fe77c74fa2a32da7dbcf7b21de1e2  wine-staging-11.15-osx64.tar.xz
8f260e36b5739e68f3bad613381441385c4dc7b85b78ba8de653d5a6a264529d  dxmt-v0.80-builtin.tar.gz
```

## Reproduce it

```bash
mkdir -p ~/CS2/downloads && cd ~/CS2/downloads
curl -fL -O https://github.com/Gcenx/macOS_Wine_builds/releases/download/11.15/wine-staging-11.15-osx64.tar.xz
curl -fL -O https://github.com/3Shain/DXMT/releases/download/v0.80/dxmt-v0.80-builtin.tar.gz
shasum -a 256 -c <<'SUMS'
a8c50d0e14fb7982a21506287e1e41e1990fe77c74fa2a32da7dbcf7b21de1e2  wine-staging-11.15-osx64.tar.xz
8f260e36b5739e68f3bad613381441385c4dc7b85b78ba8de653d5a6a264529d  dxmt-v0.80-builtin.tar.gz
SUMS

mkdir -p ~/CS2/wine ~/CS2/dxmt
tar -xJf wine-staging-11.15-osx64.tar.xz -C ~/CS2/wine
tar -xzf dxmt-v0.80-builtin.tar.gz      -C ~/CS2/dxmt

export PATH="$HOME/CS2/wine/Wine Staging.app/Contents/Resources/wine/bin:$PATH"
export WINEPREFIX="$HOME/CS2/prefix"
wine --version                                  # -> wine-11.15 (Staging)

cs2kit bottle create --dxmt ~/CS2/dxmt/v0.80    # wineboot, registry, DXMT placement
cs2kit doctor                                   # DXMT must read PASS
```

## Installed layout (what `cs2kit bottle create` actually did)

`dxmt.build: builtin` in `profiles/bottle-recipe.yaml` means the DLLs belong to **Wine**, not to the prefix, and
the `d3d11`/`dxgi` overrides must stay **off** — DXMT's wiki: *"Ensure these dlls are **NOT** set overrides
`native,builtin`."*

```
~/CS2/wine/Wine Staging.app/Contents/Resources/wine/
  bin/wine                                   wine-11.15 (Staging)
  lib/wine/x86_64-unix/winemetal.so          DXMT's Metal backend (unix side)
  lib/wine/x86_64-windows/{d3d11,dxgi,d3d10core,winemetal,nvapi64,nvngx}.dll
  lib/wine/i386-windows/{d3d11,dxgi,d3d10core,winemetal}.dll     for the 32-bit Steam client
~/CS2/prefix/
  drive_c/windows/system32/winemetal.dll     the one file that belongs in both places
  .cs2kit/state.json                         recipe name + hash + wine root, written by cs2kit
```

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

* **CONFIRMED:** DXMT v0.80 loads and initialises Metal under **stock** Wine 11.15 staging — no CrossOver build
  needed. DXMT's wiki still says a FOSS CrossOver Wine 24+ is required; that requirement is pinned to the v0.41
  header, and `nm -m winemetal.so` shows v0.80 imports **no** `winemac.drv` symbols, only `NtSetEvent` from `ntdll`.
* **UNKNOWN:** whether CS2 renders correctly through it. No game is installed yet (T-008).
* **Lead for T-013:** DXMT could not set its Metal shader-cache path and fell back to the system default.

## Environment of record

`docs/reference/env-snapshot-0.json`, regenerated with `cs2kit env --save`. The `stable` half is what every
benchmark is keyed by; re-run it after any toolchain change.

## Rejected, and why

| Route | Why not |
|---|---|
| `brew install --cask gcenx/wine/wine-crossover` | **Deleted from the tap 2026-04-16**; last shipped Wine 8.0.1 |
| `brew install --cask wine-stable` / `wine@staging` | Deprecated for failing Gatekeeper; **disabled 2026-09-01** |
| Building FOSS CrossOver Wine 24+ from CodeWeavers sources | The DXMT wiki's recommendation; unnecessary for v0.80 (measured above). Keep as the fallback if a future DXMT re-introduces the `winemac.drv` symbol requirement |
| Apple's D3DMetal / GPTK | Deliberately excluded — we redistribute nothing of Apple's ([docs/06](../06-legal-and-policy.md)) |
| Whisky, Porting Kit, CrossOver | Not part of this plan ([docs/02](../02-architecture.md)) |
