# 09 - Install guide: from a bare Mac to a bot match on Dust2

**Who this is for:** someone with an Apple Silicon Mac who has never used Wine and wants to shoot a bot on Dust2.
Follow the steps in order and paste the commands as written. Everything is free software; the total cost is EUR 0
([08-cost-and-dependencies.md](08-cost-and-dependencies.md)).

**Read this box before you start.**

> Counter-Strike 2 has **no macOS build** - Valve dropped it on 2023-10-10, and appid 730 is
> `oslist = "windows,linux"` (CONFIRMED, [../research/steam-vac-findings.md](../research/steam-vac-findings.md)).
> This guide does not port CS2. It builds a **Windows compatibility environment** (Wine) on your Mac and installs the
> ordinary Windows CS2 into it. Nothing here modifies Counter-Strike 2, and nothing here interacts with Valve
> Anti-Cheat.
>
> **This is not supported by Valve, Apple or CodeWeavers, and it can stop working with any update.** We have found no
> evidence of a legitimate player being banned for using a compatibility layer, but **Valve has published no policy on
> Wine and VAC** - that is genuinely UNKNOWN and cannot be resolved by engineering
> ([06-legal-and-policy.md](06-legal-and-policy.md)). Use a **secondary Steam account** for your first sessions and do
> not buy Prime until you know the setup works.

## The one thing that will waste your day if you skip it: the engine

**Three free Wine builds were measured on the machine of record on 2026-08-24. Only one runs CS2.** They all install
the same way and they all look equally plausible on a release page. Two of them cannot get you past the Steam login
screen, and neither failure names itself.

| Engine | Steam UI | Steam client <-> helper transport | DXMT Metal view | Verdict |
|---|---|---|---|---|
| Gcenx Wine 11.15 **staging** | **black**, 0.0/255 luminance | OK | **fails** | **do not use** - also crashes Steam's CEF GPU process 9x per launch (`0xC0000005`) |
| Gcenx Wine 11.15 **devel** | **black**, 0.0/255 | OK | **fails** | **do not use** - no crashes, still no Metal view |
| FOSS CrossOver 24.0.7 (`wine-9.0`) | renders | **rejected - 0x3008**, 82x in one session | works | **do not use** - login is impossible |
| **Sikarugir Wine 10.0** (`wine-10.0 (Sikarugir)`) | **renders** | **OK** | **works** | **use this one** |

The Gcenx builds fail because they export none of the `winemac.drv` API that DXMT needs, so CS2 prints
`err: Failed to create metal view, it seems like your Wine has no exported symbols needed by DXMT` - and Steam's own
window, which reaches D3D11 through ANGLE, paints black for the same reason. **Two symptoms, one cause.**
`cs2kit engine install` fetches the right one, and `cs2kit engine list` prints this table with the verdicts baked
in. MEASURED - [02-architecture.md](02-architecture.md),
[../research/steam-black-window-2026-08-24.md](../research/steam-black-window-2026-08-24.md).

## What is measured, what is inferred, what is unknown

Honesty about provenance is the point of this project, so every claim below is tagged.

| Claim | Status |
|---|---|
| macOS Steam cannot produce a working CS2 - a "complete" 66 GB install has no `cs2.exe` | **MEASURED** on the machine of record, [reference/target-machine.md](reference/target-machine.md) |
| **CS2 launches, renders through DXMT and plays a bot match** on Sikarugir Wine 10.0 | **MEASURED** 2026-08-24, M2 Pro / macOS 26.5.2: 10 minutes on Dust2, 0 crashes, 0 frozen frames in 22 samples ([implementation-status.md](implementation-status.md), [reference/t010-dust2-log.jsonl](reference/t010-dust2-log.jsonl)) |
| Gcenx Wine 11.15 and FOSS CrossOver 24.0.7 **cannot** run this stack | **MEASURED**, with the log lines, in [../research/steam-black-window-2026-08-24.md](../research/steam-black-window-2026-08-24.md) |
| **117 fps** in a Dust2 bot match at CS2's auto-selected Low preset, window 1512x982 points | **MEASURED once, 2026-08-24 - a single indicative sample, not a benchmark.** The number this project will stand behind comes from the T-011 protocol ([07-benchmark-protocol.md](07-benchmark-protocol.md)), which discards three warm-up runs and reports 1 % lows |
| The 58 GB content depot 2347770 has no OS filter and is reusable by a Windows install | **MEASURED** (depot table, [reference/target-machine.md](reference/target-machine.md)). On this machine `steamcmd` re-downloaded anyway; the finished install was then **reused with no second download** by symlinking the bottle's `steamapps` |
| Adding the macOS library as a Steam *library folder* survives a client restart | **FALSE, MEASURED.** Steam rewrites `libraryfolders.vdf` on every start. The symlink survives; the library folder does not |
| Playing CS2 online, competitively, without incident | **UNKNOWN.** T-020 is the project's real gate and it is empty - [11-validation-log.md](11-validation-log.md) |
| The black-screen, audio-crackle, Retina and `-vulkan` fixes in step 8 | **MEASURED by others**, CONFIRMED from multiple independent reports ([../research/performance-alternatives-findings.md](../research/performance-alternatives-findings.md)) |
| The Homebrew install route this guide used to print | **DEAD, MEASURED.** The cask was deleted 2026-04-16; the remaining Wine casks are disabled 2026-09-01 ([../research/wine-dxmt-install-findings-2026-08-24.md](../research/wine-dxmt-install-findings-2026-08-24.md); R-15/R-16 in [05-risk-register.md](05-risk-register.md)) |
| VAC's behaviour under Wine | **UNKNOWN.** Structural argument for low risk in [06-legal-and-policy.md](06-legal-and-policy.md) section 2; no Valve statement exists |
| How long this will keep working | **Through macOS 27**, then unknown. Apple retires general-purpose Rosetta 2 after macOS 27 and this whole stack is x86-64 ([rosetta-watch.md](rosetta-watch.md)) |

## Budget

| | |
|---|---|
| Money | **EUR 0.** Every component is free software. Do not buy CrossOver; do not buy Prime yet. |
| Time | ~2 hours of your attention, plus a 5-72 GB game download. The toolchain itself is a ~270 MB download and no admin password - everything lives under `~/CS2` and `~/.cs2kit`. |
| Disk | **>= 85 GiB free** if you already have the macOS CS2 assets and the reuse route works; **~150 GiB** for a clean install ([reference/target-machine.md](reference/target-machine.md), disk budget). |
| Requirements | Apple Silicon (M1 or later), macOS 14 or later, a Steam account, the Steam mobile app (for the QR login). |

A **fanless** Mac (Air) will work but throttles to roughly 30-40 FPS under sustained load - CONFIRMED datapoint in
[07-benchmark-protocol.md](07-benchmark-protocol.md). An actively-cooled MacBook Pro is the machine of record.

---

## Step 1 - Grade your machine (5 min)

```bash
git clone https://github.com/mahmutkaya/cs2-apple-silicon.git
cd cs2-apple-silicon
bash scripts/preflight.sh
```

This prints a `PASS`/`WARN`/`FAIL` line per item and exits non-zero if something blocks you. Fix every **FAIL**
before continuing; a `WARN` is a note, not a stop.

Two `FAIL`s have to be dealt with here:

* **`Rosetta 2 not installed`** - `softwareupdate --install-rosetta --agree-to-license`. Everything below Wine in
  this stack is x86-64 code, so without Rosetta nothing runs at all
  ([reference/toolchain.md](reference/toolchain.md)).
* **`Free space`** - go to step 2.

Put CS2Kit on your `PATH` for the rest of the guide (it needs no installation - it is standard-library Python and
runs from the checkout with the `python3` that macOS already ships):

```bash
export PATH="$PWD/bin:$PATH"
cs2kit --version
```

## Step 2 - Free the disk, and keep the 58 GB of assets (30 min) - T-001

**Do not "just uninstall CS2" yet.** On the machine of record, macOS Steam had downloaded 66 GB and marked CS2
installed - while omitting depot **2347771**, which contains *every* `.exe` and `.dll`, `cs2.exe` included. Steam's
*Verify integrity of game files* cannot fix that: as far as Steam is concerned the install is complete
(`BytesToDownload 0`). **MEASURED** - [reference/target-machine.md](reference/target-machine.md).

But the 58 GB of maps, models and sounds in depot **2347770 has no OS filter**, so a Windows install can use it. So:

```bash
osascript -e 'quit app "Steam"'          # 1. quit Steam completely
pgrep steam_osx || echo "steam is down"

STEAM="$HOME/Library/Application Support/Steam"
cp "$STEAM/steamapps/appmanifest_730.acf" /tmp/appmanifest_730.acf.before   # 2. keep a copy

du -sh "$STEAM/steamapps/downloading/730" 2>/dev/null                       # 3. dead download?
rm -rf "$STEAM/steamapps/downloading/730"                                   #    delete it if present
```

In the macOS Steam client, set CS2 to **"Only update this game when I launch it"** so it cannot re-queue the useless
macOS depots behind your back.

Then re-run `bash scripts/preflight.sh` and confirm **>= 85 GiB free** with the `steamapps/common/Counter-Strike
Global Offensive/game/csgo/` tree still present. If you cannot reach 85 GiB, uninstall the macOS CS2 copy entirely and
plan for the clean route (~150 GiB, ~72 GB of downloading).

## Step 3 - Install the free stack: the engine, then DXMT (30 min) - T-004

Four components, all free software: Rosetta 2, Wine (the **Sikarugir 10.0** engine), DXMT (DirectX 11 to Metal) and
MSync (synchronisation).

> **This guide used to say Gcenx Wine 11.15 staging, and before that
> `brew install --cask gcenx/wine/wine-crossover`. Do not use either.** The Gcenx build **cannot run CS2** on this
> stack - it exports no `winemac.drv` symbols, DXMT never gets a Metal view, and Steam's window is black. The cask
> was **deleted** from its tap on 2026-04-16 and last shipped **wine-8.0.1**; Homebrew's own `wine-stable` and
> `wine@staging` casks are **disabled on 2026-09-01** for failing the macOS Gatekeeper check. All CONFIRMED on the
> machine of record 2026-08-24.

```bash
# Rosetta 2 first: everything below Wine in this stack is x86-64 code.
softwareupdate --install-rosetta --agree-to-license

# The engine. This downloads it, checks its SHA-256, extracts it, and stages the
# wrapper dylibs it links against - without those, wineserver will not even start.
cs2kit engine list                     # the three measured engines and why two of them fail
cs2kit engine install                  # defaults to sikarugir-10, the only one that works

export WINE_ROOT="$HOME/.cs2kit/engines/sikarugir-10/wswine.bundle"
export PATH="$WINE_ROOT/bin:$PATH"
wine --version
```

That last command must print exactly:

```
wine-10.0 (Sikarugir)
```

**Now check the engine can do the one job the others could not.** This is a five-second command and it is the
difference between a working afternoon and a wasted one:

```bash
nm -g "$WINE_ROOT/lib/wine/x86_64-unix/winemac.so" | grep macdrv
```

It must print a line ending in **`_macdrv_functions`**. If it prints nothing, you are on an engine that cannot give
DXMT a Metal view: go back and install `sikarugir-10`. (`cs2kit doctor` runs this check too, as
`winemac.drv exports`.)

<details>
<summary><b>What <code>cs2kit engine install</code> actually does</b> - the manual equivalent, if you would rather see every byte</summary>

```bash
mkdir -p ~/CS2/downloads && cd ~/CS2/downloads

# 1. The engine - Sikarugir Wine 10.0, 166304096 bytes (~159 MiB)
curl -fLO https://github.com/Sikarugir-App/Engines/releases/download/v1.0/WS12WineSikarugir10.0_6.tar.xz

# 2. The wrapper, for its dylibs only - Template 1.0.11, 84533420 bytes (~81 MiB)
curl -fLO https://github.com/Sikarugir-App/Wrapper/releases/download/v1.0/Template-1.0.11.tar.xz

# 3. Verify BEFORE extracting. Both lines must match exactly.
shasum -a 256 WS12WineSikarugir10.0_6.tar.xz Template-1.0.11.tar.xz
# 9da7ee0cbf386522f3a9906943726d9c3c125dbbd9ab120e3cde80e88d6091b2  WS12WineSikarugir10.0_6.tar.xz
# 9fa15479e7ff6abd99c1d07be285fb95f41fc6991586502427152b1f7d6ccb8a  Template-1.0.11.tar.xz

# 4. Extract. The engine archive carries its own wswine.bundle/ directory.
mkdir -p ~/CS2/engine && tar -xJf WS12WineSikarugir10.0_6.tar.xz -C ~/CS2/engine
tar -xJf Template-1.0.11.tar.xz -C ~/CS2/engine

# 5. Stage the wrapper's dylibs beside the engine. Without this step wineserver
#    aborts with: Library not loaded: @rpath/libinotify.0.dylib
cp ~/CS2/engine/Template-1.0.11.app/Contents/Frameworks/*.dylib ~/CS2/engine/wswine.bundle/lib/

export WINE_ROOT="$HOME/CS2/engine/wswine.bundle"
```

The dylibs are a **packaging dependency, not an optional extra** - MEASURED
([../research/steam-black-window-2026-08-24.md](../research/steam-black-window-2026-08-24.md)). The engine is a
build of CodeWeavers' published FOSS sources plus WineHQ's; this project redistributes none of it, which is why
you fetch it yourself.
</details>

Then DXMT - one tarball, one checksum:

```bash
mkdir -p ~/CS2/downloads && cd ~/CS2/downloads

# DXMT v0.80 - the published "builtin" build, released 2026-04-23, 18681669 bytes (~18 MiB)
curl -fLO https://github.com/3Shain/DXMT/releases/download/v0.80/dxmt-v0.80-builtin.tar.gz
shasum -a 256 dxmt-v0.80-builtin.tar.gz
```

```
8f260e36b5739e68f3bad613381441385c4dc7b85b78ba8de653d5a6a264529d  dxmt-v0.80-builtin.tar.gz
```

```bash
mkdir -p ~/CS2/dxmt
tar -xzf dxmt-v0.80-builtin.tar.gz -C ~/CS2/dxmt   # -> ~/CS2/dxmt/v0.80 (the archive carries the version dir)
```

`$WINE_ROOT` is the **wine root** - the directory holding `bin/` and `lib/wine/`. Write it down; step 4 needs it,
because **DXMT installs into the Wine tree, not into your bottle**. Add both `export` lines to your shell profile if
you do not want to retype them.

Record the URLs and the checksums you saw in [reference/toolchain.md](reference/toolchain.md). That file is the
reproducibility record: a stack you cannot reproduce cannot be debugged by anyone else.

Notes that save an hour:

* Wine 10 has **one `wine` binary**; there is no separate `wine64` any more. Guides that say `wine64` are older than
  Wine 11.
* **Do not copy the DXMT files by hand.** Which directory they belong in depends on how DXMT was built, and getting
  it wrong fails *silently* - the game runs, slowly, on the wrong graphics backend. `cs2kit bottle create` in step 4
  does it from the recipe.
* **If you change engines later, re-run `cs2kit bottle create`.** DXMT's DLLs live inside the engine, so a new
  engine is a DXMT-less engine until the recipe is applied to it.
* If you already installed a Wine cask, remove it before continuing - two Wines on `PATH` is a confusing afternoon.
* **Use `curl`, not your browser.** A `curl` download carries no quarantine attribute (MEASURED: `xattr -p
  com.apple.quarantine` finds none), so Gatekeeper never gets involved. If you downloaded through a browser and Wine
  refuses to start, clear it once: `xattr -dr com.apple.quarantine ~/.cs2kit/engines`.
* Do **not** install CrossOver (EUR 74), Whisky (archived by its author on 2025-05-11), Heroic or Porting Kit. They
  are different ways to run the same Wine and they are not what this guide configures
  ([02-architecture.md](02-architecture.md)).
* Do **not** install Apple's Game Porting Toolkit / D3DMetal. This project configures DXMT instead, which keeps the
  licensing clean ([06-legal-and-policy.md](06-legal-and-policy.md)). It stays available as a fallback you install
  yourself if measurement ever demands it - and note that it now needs `brew trust gcenx/wine` first.

## Step 4 - Create the bottle (15 min) - T-006 / T-025

A "bottle" (Wine calls it a prefix) is a directory that looks like a Windows C: drive. CS2Kit builds it from a
declarative recipe, `profiles/bottle-recipe.yaml`, so that the result is reproducible rather than remembered.

```bash
export WINEPREFIX="$HOME/CS2/prefix"
cs2kit bottle create --dxmt ~/CS2/dxmt/v0.80 --wine-root "$WINE_ROOT"
cs2kit bottle diff                  # must report no drift from the recipe
```

`bottle create` initialises a 64-bit Windows 10 prefix, places DXMT, and enables MSync. Anything you later change by
hand belongs **in the recipe**, or the next machine cannot reproduce it: `cs2kit bottle diff` tells you what has
drifted and `cs2kit bottle repair` puts it back.

**Why `--wine-root` is not optional-looking cruft.** DXMT's published release is the *builtin*
(`-Dwine_builtin_dll=true`) build, so its files go into the **Wine tree**, not into your bottle:

| File | Goes to |
|---|---|
| `winemetal.so` | `$WINE_ROOT/lib/wine/x86_64-unix/` |
| `d3d11.dll`, `dxgi.dll`, `d3d10core.dll`, `winemetal.dll` | `$WINE_ROOT/lib/wine/x86_64-windows/` |
| `winemetal.dll` (again) | `$WINEPREFIX/drive_c/windows/system32/` |

and **no DLL overrides are set at all.** DXMT's own installation guide says it verbatim: *"Ensure these dlls are
**NOT** set overrides `native,builtin`."* If you set `d3d11`/`dxgi` to `native`, Wine goes looking for a *native*
DLL, does not find one, and quietly falls back to its own Direct3D - you lose DXMT and nothing tells you. (Only an
unpublished `-Dwine_builtin_dll=false` build goes into the prefix and needs the overrides; that is `dxmt.build:
prefix` in the recipe, and it is not what you downloaded.)

### Prove DXMT is live - before Steam exists

You do not have to wait for a game to find out whether the graphics backend works. Ask Wine to load `d3d11.dll` and
deliberately fail to find an entry point: the load happens first, and the trace names which implementation won.

```bash
WINEDEBUG=+loaddll,+dxmt wine rundll32 d3d11.dll,NoSuchEntry
```

Among the output you must see all three of these, every one tagged **`builtin`**:

```
	Metal Shading Language 3.1
		GPU Family Metal 3
00d4:trace:loaddll:build_module Loaded L"C:\windows\system32\winemetal.dll" at 00006FFFFE850000: builtin
00d4:trace:loaddll:build_module Loaded L"C:\windows\system32\DXGI.DLL" at 00006FFFFE090000: builtin
00d4:trace:loaddll:build_module Loaded L"C:\windows\system32\d3d11.dll" at 00006FFFFE200000: builtin
info:  Failed to set Metal cache path, fallback to system default
00d4:err:rundll32:wWinMain Unable to find the entry point L"NoSuchEntry" in L"d3d11.dll"
```

Reading it:

* **`builtin` on all three lines** is the whole point. `native` means you have overrides set that you should not -
  see [10-troubleshooting.md](10-troubleshooting.md) entry 17.
* `info:  Failed to set Metal cache path...` is **DXMT's own log line**. Seeing it means DXMT ran its initialisation,
  which is what you are testing. It is a known open question (T-013), not a failure.
* The `err:rundll32 ... Unable to find the entry point` line is **expected and required** - `NoSuchEntry` does not
  exist. The DLL had to load before it could fail.
* MoltenVK reporting **Metal Shading Language 3.1 / GPU Family Metal 3** means the Metal side came up.

**This proves DXMT loads and initialises Metal. It does not prove it can present a frame** - that needs the engine's
`winemac.drv` exports, which is the `nm -g` check in step 3. Both were MEASURED on the machine of record 2026-08-24
([../research/wine-dxmt-install-findings-2026-08-24.md](../research/wine-dxmt-install-findings-2026-08-24.md) section 5,
[../research/steam-black-window-2026-08-24.md](../research/steam-black-window-2026-08-24.md)).

## Step 5 - Install the Windows Steam client inside the bottle (1-3 h) - T-007

**This is where most people lose time**, and it is where two of the three engines fail outright. Have your phone
with the Steam mobile app in your hand.

CS2 is launched by Valve as `cs2.exe -steam` and needs Steamworks for matchmaking, Steam Datagram Relay, inventory and
the VAC session - so a **same-platform** (Windows) Steam client has to be running in the bottle. macOS Steam cannot
serve it. CONFIRMED from Valve's own app metadata
([../research/steam-vac-findings.md](../research/steam-vac-findings.md)).

```bash
cd ~/CS2/downloads
curl -fLO https://cdn.akamai.steamstatic.com/client/installer/SteamSetup.exe
shasum -a 256 SteamSetup.exe          # record it in docs/reference/toolchain.md
wine SteamSetup.exe /S                # /S = silent; the interactive installer works too
```

**Always start the client with `-no-cef-sandbox`.** This is not a tuning flag: with the Chromium sandbox on, the
helper process cannot establish its transport under Wine and the client dies on *"Unexpected transport error
(0x3008)"* before you ever see a login screen. MEASURED, and `cs2kit launch` passes it for you.

```bash
cs2kit app create                     # a double-clickable .app: verify the game files, then launch
open ~/Applications/CS2.app           # or wherever `app create` reported it wrote
```

**Start it from your own desktop session, not from a terminal in a background/agent context.** On this machine every
"no window appeared" observation turned out to be an artefact of the process that launched Wine, not of the stack -
which cost hours. The `.app` from `cs2kit app create` exists precisely so the client runs in your Aqua login session.

<details>
<summary><b>The manual equivalent</b>, if you want to drive the client by hand</summary>

```bash
pkill -f steamwebhelper; pkill -f "Steam.exe"; wineserver -k      # always start from a clean process table
cd "$WINEPREFIX/drive_c/Program Files (x86)/Steam"
wine Steam.exe -no-cef-sandbox
```
</details>

**Log in with the QR code.** The client shows one on its sign-in screen; scan it with the Steam mobile app and
confirm. No password is typed into anything, no Steam Guard code has to be transcribed, and the whole
keyboard-focus problem disappears. **CS2Kit never sees your Steam password** - automating or wrapping Steam
authentication is one of this project's absolute rules ([06-legal-and-policy.md](06-legal-and-policy.md)).

Then:

1. Steam -> Settings -> **In Game** -> uncheck *Enable the Steam Overlay while in-game*. The overlay costs real
   frames (LIKELY, two sources).
2. Leave it **idling for 10 minutes**. If the client cannot idle without crashing, stop here and fix it - adding CS2
   on top of a broken Steam client makes diagnosis much harder.

Write down every error and its fix in [reference/steam-in-bottle.md](reference/steam-in-bottle.md). That file exists
because the next person should not have to rediscover them.

## Step 6 - Install CS2, or reuse the copy you already have (1 h + download) - T-008

### 6a. If you already have CS2 on this Mac: reuse it, do not download it again

Point the bottle's own Steam library at the macOS one with a **symlink**:

```bash
cs2kit bottle link-steamapps          # <prefix>/drive_c/Program Files (x86)/Steam/steamapps -> the macOS library
```

Restart the in-bottle client. CS2 should appear as **installed**.

> **Do not do this through Steam's UI.** Adding a Library Folder in Settings -> Storage looks like it works and then
> silently reverts: **Steam rewrites `libraryfolders.vdf` on every start.** MEASURED 2026-08-24. The symlink
> survives; the library folder does not.

<details>
<summary><b>What <code>cs2kit bottle link-steamapps</code> does</b>, and the manifest fix-up you may also need</summary>

```bash
ln -s "$HOME/Library/Application Support/Steam/steamapps" \
      "$WINEPREFIX/drive_c/Program Files (x86)/Steam/steamapps"
```

If the client still offers a full fresh download, its manifest is in the wrong place - this happens when `steamcmd`
installed the game with `+force_install_dir` into a nested directory. Promote the manifest to the library root
(`appmanifest_730.acf`, with `InstalledDepots` listing 2347770 / 2347771 / 2347774) and keep the old macOS-era
manifest as a `.bak` next to it. That is a file move, not a download.
</details>

### 6b. If you do not have it, or the reuse fails: install it

From the in-bottle client, install **Counter-Strike 2** into that library.

* **If it downloads ~5 GB:** the reuse worked - depot 2347770 was recognised. This is the fast path.
* **If it insists on downloading ~72 GB:** let it, if you have the disk. Otherwise uninstall the macOS copy of CS2 to
  free 65 GB and install cleanly. **Timebox the reuse attempt to two hours** - cross-platform library reuse is
  undocumented (UNKNOWN), while the clean route always works.
* **If the client's UI is fighting you, `steamcmd` needs no UI at all.** It runs headless in the same bottle with
  `+@sSteamCmdForcePlatformType windows` and installs appid 730 without rendering a pixel. That is how CS2 got onto
  the machine of record while the Steam window was still black. You type your own credentials into Valve's tool;
  CS2Kit is not involved.

When it finishes, three confirmations - in this order:

```bash
cs2kit doctor                     # 'CS2 (Windows build)' must be PASS, not FAIL
```

1. `cs2.exe` exists under `.../Counter-Strike Global Offensive/game/bin/win64/`. That single file is the entire point
   of this step: it is what the macOS install never had. (For reference, on 2026-08-24 it was **2 967 704 bytes**,
   one of **123** files in that directory.)
2. Run **Verify integrity of game files** once from the in-bottle client's CS2 properties.
3. Immediately record the hash baseline:

```bash
cs2kit verify baseline            # T-021: the byte-identical reference, taken right after Steam's verify
cs2kit verify check
```

From now on, CS2Kit refuses to launch if any guarded binary changes. That is deliberate: Valve's VAC FAQ names
*"modifications to a game's core executable files and dynamic link libraries"* as cheating, and this project's answer
is to make it mechanically impossible to do it by accident. On the machine of record that baseline covers
**137 guarded binaries**.

## Step 7 - Apply a profile (2 min) - T-027

```bash
cs2kit config list
cs2kit config apply balanced-1080p
```

This writes an environment script, a launch-options line and an `autoexec`-style cfg - **nothing inside the game's
binary directory**. `balanced-1080p` is the sensible default; `competitive-lowest-latency` and `thermal-limited`
(fanless machines and battery) are the other two.

## Step 8 - First launch, with the four known fixes applied first (1 h) - T-009

Apply all four **before** you start debugging anything. Each is a documented, independently reproduced failure mode.
Details, sources and the file paths: [reference/first-launch.md](reference/first-launch.md).

1. **Launch options** (CS2 -> Properties -> Launch Options in the in-bottle client):

   ```
   -novid -nojoy -console
   ```

   **Not `-vulkan`.** It exists in the Windows build, but on Apple Silicon it lands on a DXVK fork frozen since 2023
   and a MoltenVK without geometry shaders; two independent users report "won't launch" or "a frame per minute".
   Worse, **CS2 silently falls back to DX11 when Vulkan initialisation fails**, so you can benchmark DX11 while
   believing you are on Vulkan. Not `-d3d9ex` either - it is a CS:GO-era flag that does nothing in Source 2.

2. **Black screen** (you hear the menu, you see nothing): alt-tab away and back, or set `setting.fullscreen` to `0`
   in `CS2Video.txt`:

   ```bash
   cs2kit config apply balanced-1080p --video    # writes <install>/game/csgo/cfg/CS2Video.txt
   ```

   If it is the **whole Steam client** that is black rather than the game, this fix is not your problem: you are on
   the wrong engine (step 3).

3. **Audio crackling, or audio dying after alt-tab**: set `cs2.exe` to **Windows 8** compatibility mode. This is the
   documented permanent fix and it repairs the microphone too.

   ```bash
   WINEPREFIX="$HOME/CS2/prefix" winecfg     # Applications -> Add application -> cs2.exe -> Windows 8
   ```

4. **Retina off, render at 1920x1080 or lower.** Native 3024x1964 costs roughly **4x**: a 96 GB M2 Max measured
   **23 FPS** at native Retina. This is the single most common self-inflicted performance problem on a Mac.

Then launch:

```bash
cs2kit launch                     # verifies the hash guard, sets the environment, hands off to Steam
```

**Acceptance for this step:** the CS2 main menu renders and responds to your mouse.

> **When a relaunch refuses:** `Steam.exe -applaunch 730` will not start the game while the client still believes the
> previous session is running - exactly the state you are in after killing CS2 between maps. With the client logged
> in and running, launch the executable directly instead; that always worked on the machine of record:
> ```bash
> cd "$WINEPREFIX/drive_c/Program Files (x86)/Steam/steamapps/common/Counter-Strike Global Offensive"
> wine game/bin/win64/cs2.exe -novid -nojoy -console
> ```
> Run `cs2kit verify check` first if you skip `cs2kit launch`, because you are also skipping its integrity guard.

If it still does not start, go to [10-troubleshooting.md](10-troubleshooting.md) - it is keyed by symptom - and only
then start changing things one at a time with `WINEDEBUG=+loaddll,+seh`.

## Step 9 - Your bot match on Dust2 (20 min) - T-010

In CS2: **Play** -> **Practice** -> *Casual* / *Deathmatch* with bots -> **Dust2** -> Go.

Expect the first two or three minutes to hitch while shaders compile. That is inherent to translating DirectX to
Metal and it is CONFIRMED by multiple independent reports; the same map is *"much smoother"* after one or two
matches. **Play Dust2 twice.** The first pass is shader compilation, not performance - and it is exactly why
benchmarks in this project discard three warm-up runs
([07-benchmark-protocol.md](07-benchmark-protocol.md)).

Two things that make a bot match behave like a soak test rather than a ten-minute demo (both learned the hard way on
2026-08-24):

* Set `mp_match_end_restart 1` (or a long `mp_maxrounds`) and re-assert `bot_quota` each round. Otherwise the match
  simply ends, the server returns to team selection, and it **looks** like a freeze when it is not.
* Send `jointeam 2` from the console after the map loads. Launch options do not join a team, and a spectator camera
  is not what you are trying to measure.

**You are done when you have played 30 continuous minutes with no crash, no audio dropout and usable mouse input.**

For reference, the first pass on the machine of record: 10 minutes, **0 crashes**, **0 frozen frames across 22
samples**, 0.7-1.4 GB resident, and a single indicative **117 fps** reading at CS2's auto-selected Low preset in a
1512x982-point window. **That is one sample, not a benchmark** - `cs2kit bench run` and
[07-benchmark-protocol.md](07-benchmark-protocol.md) exist because a single number proves nothing.

Then, before you go online:

```bash
cs2kit doctor                     # should be free of FAILs now
cs2kit report                     # a redacted bundle: no SteamID, no account name, no IPs
```

## Step 10 - Before you play online

* Use a **secondary, non-Prime account** for your first online sessions
  ([06-legal-and-policy.md](06-legal-and-policy.md), Account safety).
* **Prime is EUR 13.29 / USD 14.99 and explicitly non-refundable.** Do not buy it until your setup has survived
  several complete matches.
* Disable AirDrop/Handoff (AWDL) during a match - it adds Wi-Fi jitter (LIKELY). `cs2kit doctor` warns when `awdl0`
  is up.
* *"VAC was unable to verify your game session"* is a **kick, not a ban**, and it happens on plain Windows too. One
  occurrence is not a verdict; restart Steam and re-queue.
* Never install anything that injects into, overlays or patches CS2. That is the one action that turns a low risk
  into a real one.
* Log what happens. The online and anti-cheat record lives in [11-validation-log.md](11-validation-log.md); it is
  empty until somebody plays, and one honest row there is worth more than any claim in this guide.

## When something breaks

1. `cs2kit doctor` - most problems are environment problems and it names the fix on one line.
2. [10-troubleshooting.md](10-troubleshooting.md) - keyed by symptom, with the one-command check for each.
3. `cs2kit report` - a redacted bundle you can paste into an issue without leaking your SteamID or your username.

The three failures that cost this project the most time, and where they are answered:

| What you see | Entry |
|---|---|
| `Failed to create metal view ... no exported symbols needed by DXMT` | [10-troubleshooting.md](10-troubleshooting.md) entry 19 - wrong engine |
| Steam's window is **black** but `wine notepad` renders fine | [10-troubleshooting.md](10-troubleshooting.md) entry 19 - the same cause |
| *"Unexpected transport error (0x3008)"* | [10-troubleshooting.md](10-troubleshooting.md) entry 18 - `-no-cef-sandbox`, then the engine |

## What this guide does not promise

* **No support from Valve.** CS2 has no macOS build; this configuration is outside anything Valve tests.
* **No guarantee about VAC.** The risk argument is structural and honest, and it is still an argument, not a policy.
* **No number until it is measured.** The compatibility matrix says `not measured` where nobody has measured, and it
  will keep saying that until somebody does. The 117 fps above is one sample from one session on one machine.
* **A dated shelf life.** General-purpose Rosetta 2 is available **through macOS 27**; after that this stack has no
  successor we can build ([rosetta-watch.md](rosetta-watch.md)). Do not upgrade past macOS 27 on a machine you play
  on until that file says otherwise.

Full command reference: [cs2kit-spec.md](cs2kit-spec.md). The plan behind every step: [03-development-plan.md](03-development-plan.md).
