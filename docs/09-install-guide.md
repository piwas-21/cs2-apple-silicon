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

## What is measured, what is inferred, what is unknown

Honesty about provenance is the point of this project, so every claim below is tagged.

| Claim | Status |
|---|---|
| macOS Steam cannot produce a working CS2 - a "complete" 66 GB install has no `cs2.exe` | **MEASURED** on the machine of record, [reference/target-machine.md](reference/target-machine.md) |
| The 58 GB content depot 2347770 has no OS filter and is reusable by a Windows install | **MEASURED** (depot table, same file). Whether the in-bottle client actually reuses it is **UNKNOWN** - undocumented; the guide gives you the fallback |
| CS2 runs playably on Apple Silicon through Wine | **INFERRED** from other people's machines: a documented M5 Pro at 190 avg / 140 1 % low, an M1 Pro Wine player holding a 15,000 Premier rating ([07-benchmark-protocol.md](07-benchmark-protocol.md)) |
| ~100-125 avg FPS at 1080p medium on an M2 Pro | **INFERRED** by interpolation. Nobody has measured it yet - see [compatibility-matrix.md](compatibility-matrix.md), where every unmeasured cell says `not measured` |
| The black-screen, audio-crackle, Retina and `-vulkan` fixes in step 8 | **MEASURED by others**, CONFIRMED from multiple independent reports ([../research/performance-alternatives-findings.md](../research/performance-alternatives-findings.md)) |
| Wine 11.15 staging + DXMT v0.80 install cleanly from tarballs, and DXMT loads as a Wine **builtin** and initialises Metal | **MEASURED** on the machine of record 2026-08-24, with the exact commands and checksums in step 3 ([../research/wine-dxmt-install-findings-2026-08-24.md](../research/wine-dxmt-install-findings-2026-08-24.md)) |
| Whether DXMT renders CS2 *correctly* | **UNKNOWN.** Loading is not rendering. Nobody has run the game on this machine yet - step 9 is the gate |
| The Homebrew install route this guide used to print | **DEAD, MEASURED.** The cask was deleted 2026-04-16; the remaining Wine casks are disabled 2026-09-01 (same file; R-15/R-16 in [05-risk-register.md](05-risk-register.md)) |
| VAC's behaviour under Wine | **UNKNOWN.** Structural argument for low risk in [06-legal-and-policy.md](06-legal-and-policy.md) section 2; no Valve statement exists |
| How long this will keep working | **Through macOS 27**, then unknown. Apple retires general-purpose Rosetta 2 after macOS 27 and this whole stack is x86-64 ([rosetta-watch.md](rosetta-watch.md)) |

## Budget

| | |
|---|---|
| Money | **EUR 0.** Every component is free software. Do not buy CrossOver; do not buy Prime yet. |
| Time | ~2 hours of your attention, plus a 5-60 GB game download. The toolchain itself is a ~202 MB download and no admin password - everything lives under `~/CS2`. |
| Disk | **>= 85 GiB free** if you already have the macOS CS2 assets and the reuse route works; **~150 GiB** for a clean install ([reference/target-machine.md](reference/target-machine.md), disk budget). |
| Requirements | Apple Silicon (M1 or later), macOS 14 or later, a Steam account, the Steam Guard mobile authenticator. |

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

But the 58 GB of maps, models and sounds in depot **2347770 has no OS filter**, so a Windows install can use it. That
turns a 72 GB re-download into a **4.99 GB** gap. So:

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
plan for the clean route (~150 GiB, ~60 GB of downloading).

## Step 3 - Install the free stack: two tarballs, two checksums (30 min) - T-004

Four components, all free software: Rosetta 2, Wine, DXMT (DirectX 11 to Metal), MSync (synchronisation).

> **This guide used to say `brew install --cask gcenx/wine/wine-crossover`. Do not use it.** That cask was
> **deleted** from its tap on 2026-04-16, Homebrew now refuses third-party casks without `brew trust`, and the last
> version it shipped was **wine-8.0.1**, not the "11.x" we claimed. Homebrew's own `wine-stable` and `wine@staging`
> casks are **deprecated and will be disabled on 2026-09-01** for failing the macOS Gatekeeper check. All CONFIRMED
> on the machine of record, 2026-08-24
> ([../research/wine-dxmt-install-findings-2026-08-24.md](../research/wine-dxmt-install-findings-2026-08-24.md)).
> **No Homebrew route to Wine survives this month.** The tarballs below need no Homebrew, no admin password and no
> Gatekeeper argument, and they are pinned by checksum, so you get exactly the bytes this guide was written against.

```bash
# Rosetta 2 first: everything below Wine in this stack is x86-64 code.
softwareupdate --install-rosetta --agree-to-license

mkdir -p ~/CS2/downloads && cd ~/CS2/downloads

# Wine 11.15 staging - Gcenx, released 2026-08-08, 193561920 bytes (~185 MiB)
curl -fLO https://github.com/Gcenx/macOS_Wine_builds/releases/download/11.15/wine-staging-11.15-osx64.tar.xz

# DXMT v0.80 - the published "builtin" build, released 2026-04-23, 18681669 bytes (~18 MiB)
curl -fLO https://github.com/3Shain/DXMT/releases/download/v0.80/dxmt-v0.80-builtin.tar.gz
```

**Verify before you extract.** Run this and compare both lines by eye - if either differs, stop and re-download:

```bash
shasum -a 256 wine-staging-11.15-osx64.tar.xz dxmt-v0.80-builtin.tar.gz
```

```
a8c50d0e14fb7982a21506287e1e41e1990fe77c74fa2a32da7dbcf7b21de1e2  wine-staging-11.15-osx64.tar.xz
8f260e36b5739e68f3bad613381441385c4dc7b85b78ba8de653d5a6a264529d  dxmt-v0.80-builtin.tar.gz
```

Now extract, and put Wine on your `PATH`:

```bash
mkdir -p ~/CS2/wine ~/CS2/dxmt
tar -xJf wine-staging-11.15-osx64.tar.xz -C ~/CS2/wine   # -> ~/CS2/wine/Wine Staging.app
tar -xzf dxmt-v0.80-builtin.tar.gz       -C ~/CS2/dxmt   # -> ~/CS2/dxmt/v0.80 (the archive carries the version dir)

export WINE_ROOT="$HOME/CS2/wine/Wine Staging.app/Contents/Resources/wine"
export PATH="$WINE_ROOT/bin:$PATH"
wine --version
```

That last command must print:

```
wine-11.15 (Staging)
```

`$WINE_ROOT` is the **wine root** - the directory holding `bin/` and `lib/wine/`. Write it down; step 4 needs it,
because **DXMT installs into the Wine tree, not into your bottle**. Add both `export` lines to your shell profile if
you do not want to retype them.

Record the two URLs and the two checksums in [reference/toolchain.md](reference/toolchain.md). That file is the
reproducibility record: a stack you cannot reproduce cannot be debugged by anyone else.

Notes that save an hour:

* Wine 11 has **one `wine` binary**; there is no separate `wine64` any more. Guides that say `wine64` are older than
  Wine 11.
* **Do not copy the DXMT files by hand.** Which directory they belong in depends on how DXMT was built, and getting
  it wrong fails *silently* - the game runs, slowly, on the wrong graphics backend. `cs2kit bottle create` in step 4
  does it from the recipe.
* If you already installed a Wine cask, remove it before continuing - two Wines on `PATH` is a confusing afternoon.
* Gcenx's release page lists **GStreamer.framework** as a requirement (Wine's media backend). This guide does not
  install it: Wine 11.15, DXMT and the step-4 smoke test all ran without it on the machine of record, and CS2 plays
  no video once `-novid` is set. Whether anything later needs it is **UNKNOWN** - if audio or video misbehaves in a
  way [10-troubleshooting.md](10-troubleshooting.md) does not explain, install it and say so in an issue.
* **Use `curl`, not your browser.** A `curl` download carries no quarantine attribute (MEASURED: `xattr -p
  com.apple.quarantine` finds none), so Gatekeeper never gets involved. If you downloaded through a browser and Wine
  refuses to start, clear it once: `xattr -dr com.apple.quarantine ~/CS2/wine`.
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
* `info:  Failed to set Metal cache path…` is **DXMT's own log line**. Seeing it means DXMT ran its initialisation,
  which is what you are testing. It is a known open question (T-013), not a failure.
* The `err:rundll32 … Unable to find the entry point` line is **expected and required** - `NoSuchEntry` does not
  exist. The DLL had to load before it could fail.
* MoltenVK reporting **Metal Shading Language 3.1 / GPU Family Metal 3** means the Metal side came up.

MEASURED on the machine of record, 2026-08-24, on stock Wine 11.15 staging with no CrossOver anywhere
([../research/wine-dxmt-install-findings-2026-08-24.md](../research/wine-dxmt-install-findings-2026-08-24.md) §5).
**This proves DXMT loads and initialises Metal. It does not prove CS2 renders** - that is step 9, and it is still
the gate.

## Step 5 - Install the Windows Steam client inside the bottle (1-3 h) - T-007

**This is where most people lose time.** Have the Steam Guard mobile authenticator in your hand before you start.

CS2 is launched by Valve as `cs2.exe -steam` and needs Steamworks for matchmaking, Steam Datagram Relay, inventory and
the VAC session - so a **same-platform** (Windows) Steam client has to be running in the bottle. macOS Steam cannot
serve it. CONFIRMED from Valve's own app metadata
([../research/steam-vac-findings.md](../research/steam-vac-findings.md)).

```bash
cd ~/Downloads
curl -LO https://cdn.akamai.steamstatic.com/client/installer/SteamSetup.exe
shasum -a 256 SteamSetup.exe          # record it in docs/reference/toolchain.md
wine SteamSetup.exe
```

Accept the defaults, log in, **let the client finish self-updating**, and check that your library and friends list
load. Then:

1. Steam -> Settings -> **In Game** -> uncheck *Enable the Steam Overlay while in-game*. The overlay costs real
   frames (LIKELY, two sources).
2. Leave it **idling for 10 minutes**. If the client cannot idle without crashing, stop here and fix it - adding CS2
   on top of a broken Steam client makes diagnosis much harder.

Write down every error and its fix in [reference/steam-in-bottle.md](reference/steam-in-bottle.md). That file exists
because the next person should not have to rediscover them.

**CS2Kit never sees your Steam password.** You log into Valve's own client; automating or wrapping Steam
authentication is one of this project's absolute rules ([06-legal-and-policy.md](06-legal-and-policy.md)).

## Step 6 - Install CS2 and close the 4.99 GB gap (1 h + download) - T-008

Point the in-bottle Steam client at the macOS asset tree so it only has to fetch the missing Windows binaries:

```bash
ln -s "$HOME/Library/Application Support/Steam/steamapps" "$WINEPREFIX/dosdevices/s:"
```

In the in-bottle client: Steam -> Settings -> **Storage** -> Add Drive -> `S:`. Then install **Counter-Strike 2**
into that library folder.

* **If it downloads ~5 GB:** the reuse worked. This is the fast path.
* **If it insists on downloading ~60 GB:** let it, if you have the disk. Otherwise uninstall the macOS copy of CS2 to
  free 65 GB and install cleanly. **Timebox the reuse attempt to two hours** - cross-platform library reuse is
  undocumented (UNKNOWN), while the clean route always works.

When it finishes, three confirmations - in this order:

```bash
cs2kit doctor                     # 'CS2 (Windows build)' must be PASS, not FAIL
```

1. `cs2.exe` exists under `.../Counter-Strike Global Offensive/game/bin/win64/`. That single file is the entire point
   of this step: it is what the macOS install never had.
2. Run **Verify integrity of game files** once from the in-bottle client's CS2 properties.
3. Immediately record the hash baseline:

```bash
cs2kit verify baseline            # T-021: the byte-identical reference, taken right after Steam's verify
cs2kit verify check
```

From now on, CS2Kit refuses to launch if any guarded binary changes. That is deliberate: Valve's VAC FAQ names
*"modifications to a game's core executable files and dynamic link libraries"* as cheating, and this project's answer
is to make it mechanically impossible to do it by accident.

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

If it does not, go to [10-troubleshooting.md](10-troubleshooting.md) - it is keyed by symptom - and only then start
changing things one at a time with `WINEDEBUG=+loaddll,+seh`.

## Step 9 - Your bot match on Dust2 (20 min) - T-010

In CS2: **Play** -> **Practice** -> *Casual* / *Deathmatch* with bots -> **Dust2** -> Go.

Expect the first two or three minutes to hitch while shaders compile. That is inherent to translating DirectX to
Metal and it is CONFIRMED by multiple independent reports; the same map is *"much smoother"* after one or two
matches. **Play Dust2 twice.** The first pass is shader compilation, not performance - and it is exactly why
benchmarks in this project discard three warm-up runs
([07-benchmark-protocol.md](07-benchmark-protocol.md)).

**You are done when you have played 30 continuous minutes with no crash, no audio dropout and usable mouse input.**

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

## What this guide does not promise

* **No support from Valve.** CS2 has no macOS build; this configuration is outside anything Valve tests.
* **No guarantee about VAC.** The risk argument is structural and honest, and it is still an argument, not a policy.
* **No number until it is measured.** The compatibility matrix says `not measured` where nobody has measured, and it
  will keep saying that until somebody does.
* **A dated shelf life.** General-purpose Rosetta 2 is available **through macOS 27**; after that this stack has no
  successor we can build ([rosetta-watch.md](rosetta-watch.md)). Do not upgrade past macOS 27 on a machine you play
  on until that file says otherwise.

Full command reference: [cs2kit-spec.md](cs2kit-spec.md). The plan behind every step: [03-development-plan.md](03-development-plan.md).
