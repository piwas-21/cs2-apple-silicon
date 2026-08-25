# 10 - Troubleshooting

Keyed by **symptom**. Every entry has the same five parts: what you see, why, a **one-command check**, the fix, and
where the evidence comes from. Nothing here is folklore - each entry cites a `docs/` or `research/` file, and each
carries a **CONFIRMED** (vendor or primary source), **LIKELY** (community, consistent) or **UNKNOWN** tag.

**Start here, always:**

```bash
cs2kit doctor          # most problems are environment problems; every line ends in one actionable fix
cs2kit doctor --json   # the same thing for an issue report
```

`cs2kit doctor` exits `1` if anything FAILs. Exit codes are documented in [cs2kit-spec.md](cli-reference.md).

| # | Symptom | Jump to |
|---|---|---|
| 1 | Black screen on launch, audio plays | [1](#1-black-screen-on-launch-audio-plays-nothing-renders) |
| 2 | Audio crackles, or dies after alt-tab | [2](#2-audio-crackles-distorts-or-dies-after-alt-tab) |
| 3 | Everything is smooth but the frame rate is terrible | [3](#3-frame-rate-is-terrible-and-the-machine-is-not-even-hot-retinahidpi) |
| 4 | `-vulkan` did nothing, or made it worse | [4](#4--vulkan-changes-nothing-or-makes-it-worse) |
| 5 | Stutters and freezes on a map you have not played | [5](#5-stutters-and-micro-freezes-on-a-map-you-have-not-played-before) |
| 6 | Steam in the bottle will not log in | [6](#6-steam-inside-the-bottle-will-not-log-in-steam-guard) |
| 7 | "VAC was unable to verify your game session" | [7](#7-vac-was-unable-to-verify-your-game-session) |
| 8 | Jitter, rubber-banding, `SteamNetworkingSockets` spam | [8](#8-jitter-rubber-banding-and-steamnetworkingsockets-lock-held-spam) |
| 9 | Nothing x86 runs / Rosetta | [9](#9-nothing-runs-at-all-rosetta-2) |
| 10 | Out of disk, or Steam stops mid-download | [10](#10-out-of-disk) |
| 11 | Game launches to a black window with software-slow rendering (DXMT) | [11](#11-dxmt-is-not-actually-in-use) |
| 12 | Steam says CS2 is installed but there is no `cs2.exe` | [12](#12-steam-says-cs2-is-installed-but-there-is-no-cs2exe) |
| 13 | `cs2kit launch` refuses to start the game | [13](#13-cs2kit-launch-refuses-integrity) |
| 14 | `brew`: "Cask 'wine-crossover' is unavailable" | [14](#14-brew-cask-wine-crossover-is-unavailable) |
| 15 | `brew`: "Refusing to load cask ... from untrusted tap" | [15](#15-brew-refusing-to-load-cask--from-untrusted-tap) |
| 16 | Your Wine cask is "deprecated ... disabled on 2026-09-01" | [16](#16-brew-says-your-wine-cask-is-deprecated-and-will-be-disabled-on-2026-09-01) |
| 17 | DXMT's DLLs load as `native` instead of `builtin` | [17](#17-dxmts-dlls-load-as-native-instead-of-builtin) |
| 18 | Steam dies with "Unexpected transport error (0x3008)" | [18](#18-steam-dies-on-startup-with-unexpected-transport-error-0x3008) |
| 19 | The game "does nothing" - empty log, no window | [19](#19-the-game-does-nothing--empty-log-no-window-exit-code-1) |
| 20 | "Failed to create metal view", or Steam's window is black | [20](#20-failed-to-create-metal-view-and-the-black-steam-window-are-one-fault) |
| 21 | `wineserver`: `Library not loaded: @rpath/libinotify.0.dylib` | [21](#21-wineserver-library-not-loaded-rpathlibinotify0dylib) |
| 22 | The game will not relaunch / Steam thinks it is already running | [22](#22-the-game-refuses-to-relaunch-steamexe--applaunch-730-does-nothing) |
| 23 | Steam forgets the library folder you added | [23](#23-steam-forgets-the-library-folder-and-offers-a-full-re-download) |

**The engine is the first thing to check.** Entries 18, 20 and 21 are all *"you are running a Wine build that cannot
do this"*, and one command tells you which build you have:

```bash
wine --version                                                       # must print: wine-10.0 (Sikarugir)
nm -g "$WINE_ROOT/lib/wine/x86_64-unix/winemac.so" | grep macdrv     # must print: _macdrv_functions
```

The three-engine table, with what each one fails at, is in [02-architecture.md](architecture.md) and in
`cs2kit engine list`.

---

## 1. Black screen on launch, audio plays, nothing renders

> **If it is the Steam client that is black, not the game, this is the wrong entry - go to
> [20](#20-failed-to-create-metal-view-and-the-black-steam-window-are-one-fault).** That is an engine fault,
> and no amount of fullscreen toggling fixes it.

**Cause.** A fullscreen-mode handover that the compatibility layer does not complete. Also reported as an
intermittent DXMT artefact at round start that "resolves once you can move".

**Check.**

```bash
cs2kit config show                # the profile's display block: width, height, fullscreen, hidpi
grep -ri "setting.fullscreen" "$HOME/Library/Application Support/Steam/steamapps/common/Counter-Strike Global Offensive/game/csgo/cfg"
```

**Fix.** Alt-tab away and back, or toggle fullscreen manually. Permanently: set `setting.fullscreen` to `0` in
`CS2Video.txt` - windowed / windowed-fullscreen is also the reported maximum-FPS mode on Apple Silicon.

```bash
cs2kit config apply balanced-1080p --video
```

That writes `CS2Video.txt` into `<install>/game/csgo/cfg/`. **Which copy CS2 actually reads under Wine is
UNCONFIRMED** - it may instead read the per-account copy under Steam's `userdata` tree. If the black screen
persists, point the tool at the other location and report which one worked:

```bash
cs2kit config apply balanced-1080p --video --video-path "<the path that worked>"
```

Record it in [reference/first-launch.md](reference/first-launch.md), where the path is **UNRECORDED** until somebody
confirms it on hardware.

**Evidence.** CONFIRMED, multiple independent reports (CodeWeavers forum thread *"Black screen when I load CS2
(mac M1)"*, plus a video walkthrough) - [../research/performance-alternatives-findings.md](../research/performance-alternatives-findings.md)
item 2; procedure in [reference/first-launch.md](reference/first-launch.md).

## 2. Audio crackles, distorts, or dies after alt-tab

**Cause.** CoreAudio behaviour under Wine with CS2's default Windows-version target. It affects **microphone input
as well as output**, which makes it look like two separate problems.

**Check.**

```bash
cs2kit bottle diff        # the recipe pins cs2.exe to Windows 8; drift shows up here
```

**Fix.** Set `cs2.exe` to **Windows 8** in the bottle - the documented permanent fix:

```bash
WINEPREFIX="$HOME/CS2/prefix" winecfg     # Applications -> Add application -> cs2.exe -> Windows 8
cs2kit bottle repair                      # or let the recipe re-apply it
```

The `cs2.exe` path inside the bottle ends
`.../Counter-Strike Global Offensive/game/bin/win64/cs2.exe`. A weaker second remedy is Audio MIDI Setup -> your
output device -> Format -> **96,000 Hz**.

Because this is a **bottle** setting rather than a game file, it survives CS2 updates. Bluetooth headsets are a
separate and unresolved question (T-016) - if crackle persists only on AirPods, test wired before you blame the
bottle.

**Evidence.** CONFIRMED - CodeWeavers tip *"Broken audio on Mac"* and forum msg=290698;
[../research/performance-alternatives-findings.md](../research/performance-alternatives-findings.md) items 3 and 4.

## 3. Frame rate is terrible and the machine is not even hot (Retina/HiDPI)

**Cause.** You are rendering at the Retina backing-store resolution. Native 3024x1964 costs roughly **4x**: a 96 GB
M2 Max measured **23 FPS** at native Retina. This is the most common self-inflicted performance problem on a Mac, and
it is invisible unless you look for it - the game reports the resolution it was asked for.

**Check.**

```bash
cs2kit doctor            # the 'HiDPI / Retina' check
```

**Fix.** Turn Retina/HiDPI off in the bottle and set the game to **1920x1080 or lower**. `cs2kit config apply
balanced-1080p` sets the intended resolution; verify in-game that it took effect rather than assuming.

**Evidence.** CONFIRMED - [07-benchmark-protocol.md](benchmarking.md) reference field and its trap 2;
[../research/performance-alternatives-findings.md](../research/performance-alternatives-findings.md) item 10.

## 4. `-vulkan` changes nothing, or makes it worse

**Cause.** The CS2 **Windows** build really does have a Vulkan renderer (CONFIRMED from Valve's own launch entries),
which is why guides recommend it. On Apple Silicon it routes through a DXVK-macOS fork frozen at 1.10.3 since 2023
and a MoltenVK with **no geometry shaders** and no `VK_EXT_transform_feedback`. Two independent users report the game
either will not launch or runs at "a frame per minute".

The trap: **CS2 silently falls back to DX11 when Vulkan initialisation fails.** You can benchmark DX11 for an hour
believing you are measuring Vulkan.

**Check.** Launch with `-console` and read which renderer the console reports. The launch option is not evidence.

**Fix.** Remove `-vulkan`. The intended path on this stack is **DX11 through DXMT**. Also remove `-d3d9ex` if a guide
gave it to you: it is a CS:GO-era flag and Source 2 has no D3D9 path.

**Evidence.** CONFIRMED (renderer exists) / flagged CONTRADICTION with AppleGamingWiki (community reports) -
[../research/steam-vac-findings.md](../research/steam-vac-findings.md) section 5 and
[../research/performance-alternatives-findings.md](../research/performance-alternatives-findings.md) items 12-13;
trap 3 in [07-benchmark-protocol.md](benchmarking.md).

## 5. Stutters and micro-freezes on a map you have not played before

**Cause.** Shader compilation. It is inherent to translating DirectX to Metal, it happens on the first one or two
passes over each map, and it is *not* a fault in your setup.

**Check.**

```bash
cs2kit bench compare      # hitch count is a first-class metric, not a footnote
```

**Fix.** Play the map once or twice; it becomes "much smoother" afterwards. Never benchmark a cold cache - the
protocol discards **three warm-up runs** before the five measured ones, precisely because a cold cache invents a
1 %-low problem that does not exist. After a CS2 update, expect the cache to be invalidated and re-warm before
judging performance (T-013, T-030).

**Evidence.** CONFIRMED, multiple independent reports -
[../research/performance-alternatives-findings.md](../research/performance-alternatives-findings.md) item 1;
trap 1 in [07-benchmark-protocol.md](benchmarking.md).

## 6. Steam inside the bottle will not log in (Steam Guard)

**Cause.** The Steam Guard mobile-authenticator prompt is the usual first wall, and a half-completed client
self-update produces errors that look like Wine faults but are not.

**Check.**

```bash
cs2kit doctor            # 'Bottle' and 'Wine' must be PASS before you blame Steam
```

**Fix.** **Log in with the QR code**, not with a password: the client's sign-in screen shows one, you scan it with
the Steam mobile app, and nothing has to be typed into a Wine window at all. That removes the keyboard-focus and
Steam-Guard-transcription problems together, and it is how the machine of record logged in (MEASURED 2026-08-24).
Let the client finish self-updating completely; then let it idle for 10 minutes before installing anything. If the
client cannot idle, the problem is the Wine stack, not CS2 - fix it here, before the game is involved.

If the login window never appears, or appears black, you are not looking at a Steam Guard problem: see entries
[18](#18-steam-dies-on-startup-with-unexpected-transport-error-0x3008) and
[20](#20-failed-to-create-metal-view-and-the-black-steam-window-are-one-fault).

**CS2Kit never wraps, replaces or automates Steam authentication** - you log into Valve's own client, every time.
That is an absolute rule, not an omission ([06-legal-and-policy.md](legal-and-vac.md)).

**Evidence.** Procedure and the errors-and-fixes table: [reference/steam-in-bottle.md](reference/steam-in-bottle.md);
risk R-11 in [05-risk-register.md](project/risk-register.md).

## 7. "VAC was unable to verify your game session"

**One occurrence is not a verdict.** This is a **kick, not a ban**, and it is an extremely common generic CS2 error
**on plain Windows too** - nine separate threads in Valve's own CS2 forum. Whether it fires *more* often under Wine
is **UNKNOWN**: no Wine-specific dataset exists.

**Check.**

```bash
cs2kit verify check      # are the guarded binaries still byte-identical to the Steam-validated baseline?
```

**Fix.** Restart the in-bottle Steam client, re-run *Verify integrity of game files*, log out and back in, re-queue.
If it recurs across several sessions, log each occurrence with a timestamp, the CS2 `buildid` and
`cs2kit doctor --json`, and treat it as a T-020 finding rather than a configuration problem.

**Never** respond by installing anything that patches, injects into or hooks CS2. Valve's VAC FAQ names
*"modifications to a game's core executable files and dynamic link libraries"* as cheating - that is the one action
that converts a low risk into a real one. VAC bans are permanent and non-appealable (CONFIRMED).

**Evidence.** CONFIRMED (the error is generic and common) / UNKNOWN (Wine-specific rate) -
[../research/steam-vac-findings.md](../research/steam-vac-findings.md), *Named failure modes*;
policy in [06-legal-and-policy.md](legal-and-vac.md) section 2.

## 8. Jitter, rubber-banding, and `SteamNetworkingSockets lock held` spam

**Cause.** Two distinct things that look identical in a match:

* **AWDL** (AirDrop/Handoff) raising Wi-Fi jitter while you play. LIKELY - single community report, plausible
  mechanism.
* **`SteamNetworkingSockets lock held for N ms (Performance warning) ... symptom of general performance problem such
  as thread starvation`** spamming the console. Reported by several users as *"removes a lot of precision from the
  game"* - it is net jitter, not just log noise. **Fix UNKNOWN.**

**Check.**

```bash
cs2kit doctor            # the 'AWDL (AirDrop/Handoff)' check
ifconfig awdl0
```

**Fix.** `sudo ifconfig awdl0 down` before an online session (it comes back up after a reboot or when you use
AirDrop). Prefer Ethernet over Wi-Fi. Compare your ping to the same relay from native macOS Steam - the T-019
acceptance is within **+/-10 ms**. If the lock-held spam persists on a quiet network, record it: no fix is known and
the data is worth having.

**Evidence.** CONFIRMED (reported), UNKNOWN (fix) -
[../research/performance-alternatives-findings.md](../research/performance-alternatives-findings.md) items 5 and 6;
risk R-12 in [05-risk-register.md](project/risk-register.md).

## 9. Nothing runs at all (Rosetta 2)

**Cause.** Wine's macOS build is compiled x86-64 (`--enable-archs=i386,x86_64`), so **the entire stack - Wine, the
Windows Steam client and `cs2.exe` - runs under Rosetta 2**. Without Rosetta, nothing starts.

**Check.**

```bash
cs2kit doctor            # the 'Rosetta 2' and 'Rosetta horizon' checks
pgrep -q oahd && echo active
```

**Fix.**

```bash
softwareupdate --install-rosetta --agree-to-license
```

**If `cs2kit doctor` reports the Rosetta *horizon* as WARN or FAIL, that is not a bug you can fix.** Apple states
general-purpose Rosetta is *"available through macOS 27"*, after which only *"a subset ... aimed at supporting older
unmaintained gaming titles"* remains - and CS2 is actively maintained, so it probably does not qualify. Do not
upgrade past macOS 27 on a machine you play on. The full position, the ARM64EC/FEX blocker and the migration
recommendation: [rosetta-watch.md](project/rosetta-watch.md).

**Evidence.** CONFIRMED, Apple primary - [../research/tooling-licensing-findings.md](../research/tooling-licensing-findings.md)
sections 6 and 7; risk R-1 in [05-risk-register.md](project/risk-register.md).

## 10. Out of disk

**Cause.** The Windows CS2 install is ~60 GB downloaded and **~72 GB on disk**, plus the bottle and the Steam client
(~2-4 GB) and shader caches and logs (~2 GB). A dead macOS-Steam download of CS2 can be sitting on 60 GB of your disk
doing nothing.

**Check.**

```bash
bash scripts/preflight.sh          # grades free space and finds the dead download
cs2kit doctor                      # 'Free disk' check; the floor is 80 GiB
```

**Fix.** Delete `~/Library/Application Support/Steam/steamapps/downloading/730` if it exists. Keep the 58 GB content
depot 2347770 - it has no OS filter and a Windows install can reuse it, which is what turns 72 GB into a 4.99 GB gap
(T-001/T-008). If you still cannot reach 85 GiB free, uninstall the macOS copy of CS2 entirely and install cleanly
into the bottle.

**Evidence.** MEASURED on the machine of record - [reference/target-machine.md](reference/target-machine.md), disk
budget; risk R-6 (*"already occurring"*) in [05-risk-register.md](project/risk-register.md).

## 11. DXMT is not actually in use

**Cause.** DXMT's files are not where the build you downloaded expects them, so Wine is falling back to its own
Direct3D path. Symptoms range from a black window to a technically-running game that is far slower than the reference
field would predict. The published release is the **builtin** build, and its files go into the **Wine tree**, not into
your bottle:

| File | `dxmt.build: builtin` (what upstream ships) |
|---|---|
| `winemetal.so` | `<wine>/lib/wine/x86_64-unix/` |
| `d3d11.dll`, `dxgi.dll`, `d3d10core.dll`, `winemetal.dll` | `<wine>/lib/wine/x86_64-windows/` |
| `winemetal.dll` (again) | `<prefix>/drive_c/windows/system32/` |
| DLL overrides | **none** - see entry 17 |

A second, quieter cause: `cs2kit` could not find the **wine root** (the directory holding `bin/` and `lib/wine/`), so
there was nowhere to put them. `cs2kit doctor` reports that as a `Wine tree` WARN.

A third: **you changed engines.** DXMT's DLLs live inside the *engine*, not inside the prefix, so a freshly
installed engine has no DXMT in it until you re-run `cs2kit bottle create --wine-root <the new engine>`.

**Check.**

```bash
cs2kit doctor            # the 'DXMT' and 'Wine tree' checks
cs2kit bottle diff       # drift between profiles/bottle-recipe.yaml and the prefix
WINEDEBUG=+loaddll,+dxmt wine rundll32 d3d11.dll,NoSuchEntry
```

The last command is the direct answer: `d3d11.dll`, `DXGI.DLL` and `winemetal.dll` must all load, all tagged
**`builtin`**, followed by DXMT's own `info:` line. The `err:rundll32 ... Unable to find the entry point` at the end
is expected - see step 4 of [09-install-guide.md](install.md).

**Fix.**

```bash
cs2kit bottle repair                                                       # re-apply the recipe
cs2kit bottle create --dxmt ~/CS2/dxmt/v0.80 --wine-root "$WINE_ROOT"      # or a fresh bottle
```

Record the DXMT release you used in [reference/toolchain.md](reference/toolchain.md) - a benchmark whose graphics
backend version is unrecorded cannot be compared with anything.

**Evidence.** The layout and the "no overrides" rule are CONFIRMED from DXMT's own installation guide and were
verified on the machine of record 2026-08-24 -
[../research/wine-dxmt-install-findings-2026-08-24.md](../research/wine-dxmt-install-findings-2026-08-24.md) §4.
DXMT is the project's chosen backend and its critical dependency ([02-architecture.md](architecture.md));
community data shows 10x swings between backends across machines, which is why T-012 measures rather than assumes
(risk R-5, [05-risk-register.md](project/risk-register.md)).

## 12. Steam says CS2 is installed but there is no `cs2.exe`

**Cause.** You installed CS2 with **macOS** Steam. Appid 730 is `oslist = "windows,linux"`, and macOS Steam's depot
selection omits depot **2347771** - which contains every `.exe` and `.dll` of the game. On the machine of record it
produced a "complete" **66 GB** install (`StateFlags 4`, `BytesToDownload 0`) with no `cs2.exe`, no `engine2.dll`, no
`client.dll`, no `steam_api64.dll`. The only nine `.exe` files present were Workshop authoring tools from a different
depot.

**Verify integrity of game files cannot fix this.** Steam believes the install is complete.

**Check.**

```bash
cs2kit doctor            # 'CS2 (Windows build)' -> FAIL, naming depot 2347771
```

**Fix.** Install CS2 from the **Windows Steam client inside the bottle** (step 6 of
[09-install-guide.md](install.md)). Keep the macOS content depot 2347770 - the in-bottle client may be able
to reuse it and fetch only the missing ~4.99 GB.

**Evidence.** MEASURED, with byte counts and the full depot table -
[reference/target-machine.md](reference/target-machine.md); mechanism CONFIRMED in
[../research/steam-vac-findings.md](../research/steam-vac-findings.md) section 1.

## 13. `cs2kit launch` refuses: integrity

**Cause.** A file under `game/bin/win64/` no longer matches the SHA-256 baseline recorded after Steam's own verify
pass. `cs2kit launch` exits with the integrity code rather than starting the game.

The overwhelmingly likely explanation is a **legitimate CS2 update**. The dangerous one is that something modified a
game binary - which Valve's VAC FAQ classes as cheating.

**Check.**

```bash
cs2kit verify check --json      # which files differ, and how
cs2kit doctor                   # the buildid check tells you whether the game updated
```

**Fix.** If the `buildid` changed, the game updated: run *Verify integrity of game files* in the in-bottle Steam
client, then re-baseline and re-warm the shader cache.

```bash
cs2kit verify baseline
```

If the `buildid` did **not** change, do not re-baseline. Find out what wrote to that directory, remove it, and let
Steam restore the original files before you play online again.

**Evidence.** T-021 and absolute rule 1 - [06-legal-and-policy.md](legal-and-vac.md); post-update drill in
[03-development-plan.md](project/development-plan.md) T-030.

## 14. `brew`: "Cask 'wine-crossover' is unavailable"

```
Warning: Cask 'wine-crossover' is unavailable: '/opt/homebrew/Library/Taps/gcenx/homebrew-wine/Casks/wine-crossover.rb' does not exist.
Error: No casks found for wine-crossover.
```

**Cause.** The cask was **deleted from its tap on 2026-04-16** (commit `f201026`, "Delete Casks/wine-crossover.rb").
Only `game-porting-toolkit` remains in that tap. You are almost certainly reading an old copy of this guide, an old
blog post, or the tap's **own README** - which still advertises the cask four months after deleting it. A README is
not a package index.

**Check.**

```bash
ls /opt/homebrew/Library/Taps/gcenx/homebrew-wine/Casks/     # only game-porting-toolkit.rb
git -C /opt/homebrew/Library/Taps/gcenx/homebrew-wine log --oneline -3
```

**Fix.** Stop using Homebrew for Wine. Use the tarball in step 3 of
[09-install-guide.md](install.md) - two `curl`s, two checksums, one `tar`. There is nothing to salvage
here: even when the cask existed it shipped **wine-8.0.1** (crossover-sources-23.7.1), not the "Wine 11.x" our own
plan claimed. If you did install it before it disappeared, you were running a Wine three major versions behind this
guide.

**Evidence.** CONFIRMED on the machine of record 2026-08-24, from the tap's own git history -
[../research/wine-dxmt-install-findings-2026-08-24.md](../research/wine-dxmt-install-findings-2026-08-24.md) §1;
risk R-16 in [05-risk-register.md](project/risk-register.md).

## 15. `brew`: "Refusing to load cask ... from untrusted tap"

```
Error: Refusing to load cask gcenx/wine/game-porting-toolkit from untrusted tap gcenx/wine.
Run `brew trust --cask gcenx/wine/game-porting-toolkit` or `brew trust gcenx/wine` to trust it.
```

**Cause.** Homebrew now refuses casks from third-party taps until you explicitly trust the tap. Nothing is broken and
nothing has been removed - it is a deliberate supply-chain gate, and it is why guides written before it landed stop
working at their first command.

**Check.**

```bash
brew info --cask gcenx/wine/game-porting-toolkit    # reproduces the message without installing anything
```

**Fix.** For **Wine: do not**. This guide does not use a cask for Wine at all (entry 14). For **Apple's Game Porting
Toolkit**, which is only relevant as the T-012 fallback and only if measurement demands it:

```bash
brew trust gcenx/wine
brew install --cask gcenx/wine/game-porting-toolkit
```

Trusting a tap means you accept whatever that tap's maintainer publishes, now and later. Read it as the security
decision it is; this project does not need you to make it.

**Evidence.** CONFIRMED, reproduced 2026-08-24 -
[../research/wine-dxmt-install-findings-2026-08-24.md](../research/wine-dxmt-install-findings-2026-08-24.md) §1d.

## 16. `brew` says your Wine cask is "deprecated" and will be "disabled on 2026-09-01"

```
==> wine@staging (WineHQ-staging): 11.15
Deprecated because it does not pass the macOS Gatekeeper check! It will be disabled on 2026-09-01.
```

**Cause.** Both official WineHQ macOS casks - `wine-stable` (11.0_1) and `wine@staging` (11.15) - are deprecated for
failing Homebrew's Gatekeeper/notarisation check, and **both are disabled on 2026-09-01**. The Wine *software* is
fine; the *delivery mechanism* is what expires. After that date `brew install --cask wine-stable` will refuse to run.

**Check.**

```bash
brew info --cask wine-stable | head -4
brew info --cask wine@staging | head -4
wine --version                 # which Wine is actually on your PATH right now?
```

**Fix.** Move to the tarball (step 3 of [09-install-guide.md](install.md)). It is the **same upstream** -
Gcenx builds the official WineHQ macOS packages - delivered as an archive rather than a cask, so there is no
Gatekeeper check to fail, no admin password, and a SHA-256 you can pin. Then remove the cask so you do not end up
with two Wines on `PATH`:

```bash
brew uninstall --cask wine-stable        # or wine@staging, whichever you installed
cs2kit engine install                    # the engine that can actually run CS2
wine --version                           # must now print wine-10.0 (Sikarugir)
```

**A WineHQ/Gcenx build is not a substitute here.** Its delivery is not the only problem: it exports no
`winemac.drv` symbols, so it cannot run this stack at all (entry
[20](#20-failed-to-create-metal-view-and-the-black-steam-window-are-one-fault)).

**Evidence.** CONFIRMED, both `brew info` outputs read on the machine of record 2026-08-24 -
[../research/wine-dxmt-install-findings-2026-08-24.md](../research/wine-dxmt-install-findings-2026-08-24.md) §2;
risk **R-15** in [05-risk-register.md](project/risk-register.md), the second dated risk in this project after Rosetta-27.

## 17. DXMT's DLLs load as `native` instead of `builtin`

**Cause.** **You set DLL overrides you should not have set.** Almost every DXVK/DXMT guide on the internet tells you
to set `d3d11`, `dxgi` and `d3d10core` to `native,builtin` - and for the *published* DXMT release that is exactly
wrong. The release is the `-Dwine_builtin_dll=true` ("builtin") build: its DLLs are Wine **builtins** living in the
Wine tree. Marking them `native` tells Wine to prefer a native DLL, and what happens next depends on what is lying
around in your `system32`:

* nothing there → Wine falls back to **its own Direct3D**, and you lose DXMT entirely, silently;
* an old hand-copied DXMT DLL there → Wine loads **that** one, so you are running whatever version you copied months
  ago rather than the one you just installed.

Either way the game usually still starts, which is what makes this expensive: the frame rate is wrong and nothing
says why.

**Check.**

```bash
WINEDEBUG=+loaddll,+dxmt wine rundll32 d3d11.dll,NoSuchEntry
```

Every `d3d11.dll` / `DXGI.DLL` / `winemetal.dll` line must end in **`builtin`**. If any says `native`, this is your
entry. Also look for DXMT's own `info:` line - if it is absent, DXMT never initialised.

```bash
cs2kit bottle diff       # the recipe pins 'no overrides' for dxmt.build: builtin
```

**Fix.** Remove the overrides and let the recipe re-apply the correct state:

```bash
cs2kit bottle repair
WINEPREFIX="$HOME/CS2/prefix" winecfg    # Libraries tab: remove d3d11, dxgi, d3d10core if present
unset WINEDLLOVERRIDES                   # and delete it from any launch script or shell profile
```

Then delete any hand-copied `d3d11.dll`, `dxgi.dll` or `d3d10core.dll` from
`$WINEPREFIX/drive_c/windows/system32/`. `winemetal.dll` is the **one** DXMT DLL that legitimately belongs there -
leave it. (Stray native copies are inert while no override names them, but they become live the moment somebody sets
an override "to be safe", so remove them.)

**The one case where overrides are correct** is a `-Dwine_builtin_dll=false` build, which upstream does not publish.
That is `dxmt.build: prefix` in `profiles/bottle-recipe.yaml`, and it needs
`WINEDLLOVERRIDES="dxgi,d3d11,d3d10core=n,b;"`. If you did not build DXMT yourself, this is not you.

**Evidence.** CONFIRMED - DXMT's installation guide states verbatim *"Ensure these dlls are **NOT** set overrides
`native,builtin`"*, and the `builtin` load was measured with no overrides set on the machine of record 2026-08-24 -
[../research/wine-dxmt-install-findings-2026-08-24.md](../research/wine-dxmt-install-findings-2026-08-24.md) §4-§5.
This project's own v0 recipe had it backwards; entry 11 is the same fault seen from the performance side.

## 18. Steam dies on startup with "Unexpected transport error (0x3008)"

**Symptom.** The Steam client window renders (so this is not the black-window failure), and immediately shows
*"An unexpected error occurred while starting Steam (0x3008)"* with four options: restart Steam, restart
steamwebhelper, continue anyway, quit. **Measured 2026-08-24 on FOSS CrossOver 24.0.7.**

**Cause.** 0x3008 is a transport failure between `Steam.exe` and its Chromium helper, `steamwebhelper.exe`.
There are **three** causes, and they are not equally cheap to fix:

1. **The CEF sandbox.** Under Wine the sandboxed helper cannot establish the channel. Fix: `-no-cef-sandbox`, always.
2. **A stale `steamwebhelper.exe`** left over from a previous launch. Fix: kill it before starting.
3. **The engine.** On **FOSS CrossOver 24.0.7** the helper *connects* over loopback TCP and the client
   **rejects it** - `WebUITransport: Connection rejected`, logged **82 times in one session**, with
   `src\steamUI\webuitransportcontroller.cpp (165) : Failed to reconnect to websocket: wine`. That is not a
   sandbox, GPU, cache or DXMT fault - each of those was eliminated by experiment - it is that engine's Wine 9.0
   base. **No flag fixes it. Change the engine.**

**One-command check.**

```bash
pgrep -f "Steam.exe|steamwebhelper" | wc -l      # must be 0 before a clean start
```

**Fix.** Always start the client with `-no-cef-sandbox`, from a clean process table:

```bash
pkill -f steamwebhelper; pkill -f "Steam.exe"; wineserver -k
cd "$WINEPREFIX/drive_c/Program Files (x86)/Steam" && wine Steam.exe -no-cef-sandbox
```

`cs2kit launch` passes `-no-cef-sandbox` automatically (`launch.STEAM_CLIENT_FLAGS`) — it is a client flag, not a
game launch option, and it is not optional. If the dialog still appears, pick **Restart steamwebhelper** once; if
it recurs, delete the helper's cache: `rm -rf "$WINEPREFIX/drive_c/users/$USER/AppData/Local/Steam/htmlcache"`.

**If it still recurs, check the engine** — this is cause 3, and it is the whole reason FOSS CrossOver 24.0.7 was
rejected:

```bash
wine --version          # wine-9.0 (SikarugirCX 24.0.7) -> this is your problem
cs2kit engine install   # sikarugir-10; then re-run `cs2kit bottle create` to put DXMT in the new engine
```

**Evidence.** [../research/steam-black-window-2026-08-24.md](../research/steam-black-window-2026-08-24.md),
*"The 0x3008 transport error — narrowed"*; the engine matrix in [02-architecture.md](architecture.md).


---

## 19. The game "does nothing" — empty log, no window, exit code 1

**Symptom.** `wine cs2.exe` returns immediately. No window, and the log file it was redirected to is
**zero bytes**. Steam is running and logged in; nothing else looks wrong. **Measured 2026-08-24.**

**Cause.** A `wineserver` already owns the prefix and was started **without** `WINEMSYNC=1`, while the new
process is started **with** it. The one error line only appears if you run in the foreground:

```
err:msync:msync_init Failed to open msync shared memory file; make sure no stale
wineserver instances are running without WINEMSYNC.
```

The usual way in: the Steam client was started from one shell (no `WINEMSYNC`) and the game from another
(profile sourced, so `WINEMSYNC=1`). The first process to touch the prefix decides for everyone.

**One-command check.**

```bash
cs2kit doctor | grep -i "Running wineserver"
```

`doctor` reads the running `wineserver`'s own environment and FAILs when it disagrees with the recipe.

**Fix.** Kill the server, then start *everything* — client and game — with the same setting:

```bash
wineserver -k
source ~/.cs2kit/env/balanced-1080p.sh     # exports WINEMSYNC=1
cd "$WINEPREFIX/drive_c/Program Files (x86)/Steam" && wine Steam.exe -no-cef-sandbox -silent
```

The generated launcher app does this for you: `cs2kit app create` bakes the profile's environment into the
bundle, so the client and the game always agree.


---

## 20. "Failed to create metal view", and the black Steam window, are one fault

**Symptom, one or both of:**

```
err: Failed to create metal view, it seems like your Wine has no exported symbols needed by DXMT
```

...printed by CS2 itself, right after DXMT reports `info: Maximum supported feature level: D3D_FEATURE_LEVEL_11_1`;
and/or **the Steam client's window renders pure black** (mean luminance 0.0/255, 0 % non-black pixels) while
`wine notepad` in the same bottle renders perfectly (243.5/255). **MEASURED 2026-08-24 on Gcenx Wine 11.15, both
staging and devel.**

**Cause. You are on a Wine build that hides the `winemac.drv` API.** DXMT needs those entry points to create the
Metal view it presents into, and it resolves them **at runtime** through Wine's unix-call interface. It gets a D3D11
device, reports feature level 11_1, and then has nowhere to draw. Steam's own UI reaches D3D11 through ANGLE, so it
loses its surface for exactly the same reason - **two symptoms, one cause**, which is why nine configurations of
GPU flags, virtual desktops, fresh prefixes and `OpenGLSurfaceMode` settings changed nothing.

A static symbol dump (`nm -m winemetal.so`) shows **no** `winemac` imports and is **misleading** — that dump is how
this project talked itself into the wrong engine in the first place.

**One-command check.**

```bash
nm -g "$WINE_ROOT/lib/wine/x86_64-unix/winemac.so" | grep macdrv     # must print _macdrv_functions
```

| Engine | count | result |
|---|---|---|
| Gcenx staging 11.15 | **0** | no Metal view; black Steam window; CEF GPU process crashes 9x per launch |
| Gcenx devel 11.15 | **0** | no Metal view; black Steam window; no crashes |
| Sikarugir Wine 10.0 | **1** (`_macdrv_functions`) | works |

`cs2kit doctor` runs the same check as `winemac.drv exports`.

**Fix.** Install the engine that exports them, then re-place DXMT into it (the DLLs live in the *engine*, so a new
engine starts without them):

```bash
cs2kit engine install                                                # sikarugir-10
export WINE_ROOT="$HOME/.cs2kit/engines/sikarugir-10/wswine.bundle"
export PATH="$WINE_ROOT/bin:$PATH"
cs2kit bottle create --dxmt ~/CS2/dxmt/v0.80 --wine-root "$WINE_ROOT"
cs2kit doctor
```

Do **not** spend time on `-cef-disable-gpu`, `-cef-use-angle=swiftshader`, `wine explorer /desktop=`, a fresh
prefix, or the Mac driver's `OpenGLSurfaceMode` registry values. All nine were tried, in every combination that
mattered, and all nine left the window black.

**Evidence.** CONFIRMED, with the full experiment table -
[../research/steam-black-window-2026-08-24.md](../research/steam-black-window-2026-08-24.md); engine matrix in
[02-architecture.md](architecture.md) and in `cs2kit engine list`.

## 21. `wineserver`: `Library not loaded: @rpath/libinotify.0.dylib`

**Symptom.** Nothing starts. `wine --version` may work, but the first command that needs a server aborts with a
dyld error naming `@rpath/libinotify.0.dylib` (or another `lib*.dylib`).

**Cause.** The Sikarugir/CrossOver engines link against wrapper dylibs that are **not inside the engine archive**.
They ship in the wrapper template, and the engine resolves `@rpath` to its own `lib/` directory. This is a
**packaging dependency, not an optional extra**. CONFIRMED 2026-08-24.

**One-command check.**

```bash
ls "$WINE_ROOT/lib" | grep -c dylib      # 0 means they were never staged
```

**Fix.**

```bash
cs2kit engine install       # fetches Template-1.0.11.tar.xz and stages Contents/Frameworks/*.dylib for you
```

By hand: download
`https://github.com/Sikarugir-App/Wrapper/releases/download/v1.0/Template-1.0.11.tar.xz`, extract it, and copy
`Template-1.0.11.app/Contents/Frameworks/*.dylib` into `$WINE_ROOT/lib/`.

**Evidence.** [../research/steam-black-window-2026-08-24.md](../research/steam-black-window-2026-08-24.md),
*"The Wine that works, and where it comes from"*; [reference/toolchain.md](reference/toolchain.md).

## 22. The game refuses to relaunch (`Steam.exe -applaunch 730` does nothing)

**Symptom.** CS2 ran, you killed it (or it crashed), and now nothing happens when you launch it again. The client
looks fine. No error dialog, no log.

**Cause.** The client still believes the previous CS2 session is running, and refuses to start a second one. This is
the normal state after a hard kill between maps - which is exactly what a repeated benchmark or soak run does.
MEASURED 2026-08-24.

**One-command check.**

```bash
pgrep -f "cs2.exe" | wc -l        # 0 processes and still no launch = this entry
```

**Fix.** With the client **logged in and running**, start the executable directly. This always worked on the machine
of record:

```bash
cd "$WINEPREFIX/drive_c/Program Files (x86)/Steam/steamapps/common/Counter-Strike Global Offensive"
wine game/bin/win64/cs2.exe -novid -nojoy -console
```

You are bypassing `cs2kit launch`, so you are also bypassing its integrity guard - run `cs2kit verify check` first,
every time. If you would rather not remember that, `cs2kit app create` writes a launcher that verifies and then
launches.

**Evidence.** [implementation-status.md](project/measured-results.md), T-010 first pass.

## 23. Steam forgets the library folder, and offers a full re-download

**Symptom.** You added the macOS Steam library through Settings -> Storage -> Add Drive inside the bottle. It worked.
You restarted the client and CS2 is "not installed" again, with a ~72 GB download waiting.

**Cause.** **Steam rewrites `libraryfolders.vdf` on every start**, and a library folder that points outside its own
idea of the filesystem does not survive that rewrite. MEASURED 2026-08-24.

**One-command check.**

```bash
ls -l "$WINEPREFIX/drive_c/Program Files (x86)/Steam/steamapps"    # must be a symlink, not a directory
```

**Fix.** Use a symlink instead of a library folder. Steam cannot rewrite the filesystem:

```bash
cs2kit bottle link-steamapps      # steamapps -> ~/Library/Application Support/Steam/steamapps
```

If the client *still* offers a fresh download, its manifest is nested where the client cannot see it (this happens
after a `steamcmd` install with `+force_install_dir`). Promote `appmanifest_730.acf` to the library root with
`InstalledDepots` listing 2347770 / 2347771 / 2347774, and keep the macOS-era manifest as a `.bak`. That is a file
move, not a download.

**Evidence.** [implementation-status.md](project/measured-results.md), *"Reusing the existing install — no second
download"*; step 6 of [09-install-guide.md](install.md).

---

## Known defects with no fix

Recorded so that you do not spend an evening on them. All are cosmetic or upstream.

| Symptom | Status | Evidence |
|---|---|---|
| Custom weapon skins show an empty box in the inventory | CONFIRMED (reported), no fix | research item 7 |
| Stickers cannot be dragged to a custom position | CONFIRMED (reported), no fix | research item 7 |
| Leaf/foliage flickering | LIKELY, long-standing | research item 8 |
| Changing Display Mode in-game causes UI bugs | LIKELY - leave it windowed / windowed-fullscreen | research item 11 |
| Whether a CS2 update has ever broken a working bottle | **UNKNOWN** - no source found either way; T-030 generates this data | research item 15 |
| `info:  Failed to set Metal cache path, fallback to system default` on every DXMT start | **CONFIRMED it happens, UNKNOWN why** - it is a DXMT log line, not an error, and DXMT still initialises. The obvious explanation (a missing weak-linked Metal symbol) was tested and **ruled out**: `MTLSetShaderCachePath` is present on this macOS, in both architectures. It matters because T-013's whole subject is where the shader cache lives. Not a fix you are missing. | [../research/wine-dxmt-install-findings-2026-08-24.md](../research/wine-dxmt-install-findings-2026-08-24.md) §6 |
| External-monitor behaviour | **UNKNOWN** - no CS2-specific report exists; T-014 generates it | research item 16 |

Items are in [../research/performance-alternatives-findings.md](../research/performance-alternatives-findings.md),
section 2.

## Reporting a problem

```bash
cs2kit report            # redacted: no SteamID, no account name, no usernames in paths, no IPs, no MACs
```

`cs2kit report` prints exactly what it will share before it writes anything. Attach the bundle, say which step of
[09-install-guide.md](install.md) you were on, and paste `cs2kit doctor --json`. A bundle also feeds the
community dataset (T-033) - what is stripped and where to send it is in
[12-maintenance.md](project/maintenance.md) - which is the one thing this ecosystem has never had.


---

## 24. macOS Steam deleted your Windows CS2 install

**Symptom.** CS2 stops launching. `game/bin/win64/cs2.exe` is **gone**, `appmanifest_730.acf` shows
`StateFlags 6` (update required) and a **new buildid**, `SizeOnDisk` has dropped, and
`steamapps/downloading` is filling with gigabytes. **Measured 2026-08-25: 14 GB downloaded over a working
install, `cs2.exe` deleted.**

**Cause.** The bottle and macOS Steam were sharing one Steam library. macOS Steam sees appid 730 in *its*
library, decides the copy is not the macOS build, and "updates" it — which means deleting the Windows
binaries and downloading the macOS depots over them. **Nothing unusual triggers it.** In our case a
`Counter-Strike 2.url` shortcut on the Desktop, created from Steam's own UI, was double-clicked: macOS
routes `steam://rungameid/730` to **macOS Steam**, not to the bottle, and the update starts immediately.

**Prevention — the game must live in a library macOS Steam does not know about.**

```bash
cs2kit bottle migrate            # moves the install to ~/CS2/library (instant: same-volume rename)
cs2kit bottle link-steamapps     # points the bottle at it
cs2kit doctor                    # "Steam library conflict" must not appear
```

`cs2kit setup` does this for you, and `cs2kit bottle link-steamapps` now **refuses** to share the macOS
library unless you pass `--allow-macos-library`.

**Also.**

* **Delete any `.url` shortcut** Steam put on your Desktop, and launch with the **CS2Kit**
  app instead. A `steam://` link always goes to macOS Steam.
* **Quit macOS Steam** while you play — `doctor` warns when it is running. Two clients on one account
  fight over the same downloads.

**Recovery if it already happened.** The content depot survives (that is ~58 GB of maps, models and
sounds), so only the Windows code has to come back: migrate the remains into the bottle-only library, then
install CS2 from the **in-bottle** Steam client — it will verify what is there and fetch only the missing
Windows depot rather than the whole 70 GB.


---

## 25. The launcher app says "cs2.exe not found", or Steam never appears

**Two different faults produced this, and both are fixed in the tool. If you built the app before
2026-08-25, regenerate it: `cs2kit app create`.**

### a. A path baked in at build time

The old launcher wrote the game directory into the app when it was created. Move the game to another
Steam library — which `cs2kit bottle migrate` deliberately does — and the app kept pointing at the old
place: *"cs2.exe not found at …/Library/Application Support/Steam/steamapps/common/…"*.

The app now runs `cs2kit play`, which resolves the bottle, the engine and the game **at launch** and
searches every library it knows: the bottle-only one first, then whatever the bottle's `steamapps` points
at, then the macOS one.

### b. Orphaned Steam helpers block a new client

Symptom: the app reports its problem, Steam never opens, and nothing is obviously wrong. The client had
started, **logged in, and exited immediately**.

Cause: `steamservice.exe` processes left over from earlier runs. Four of them were alive here. They also
break naive process checks — `pgrep -f steam` matches them, so the tool believed Steam was already
running.

```bash
pgrep -ifl "steam.exe" | grep -v steamservice     # is the CLIENT actually up?
```

`cs2kit play` now kills orphaned `steamservice.exe` / `steamwebhelper.exe` before starting the client,
and only counts the real client as "running".

### c. You cannot find the app in Finder

macOS has **two** Applications folders: `/Applications` (what Finder's sidebar shows) and
`~/Applications` (your home folder — Spotlight finds it, Finder's sidebar does not). Early versions
installed into the home one, so the app looked missing. `cs2kit app create` now installs into
`/Applications` when it is writable, with an icon, and falls back to `~/Applications` otherwise.


---

## 26. The launcher app will not open, or opens and nothing happens

Four separate faults produced this over one afternoon. All are fixed; if your app predates
2026-08-25, regenerate it with `cs2kit app create`.

| symptom | cause | fix |
|---|---|---|
| `open` fails, `_LSOpenURLsWithCompletionHandler() failed … error -1712` | the bundle's executable was a **shell script**. LaunchServices waits for it to register as an application and times out | the app is now a compiled **AppleScript applet** — a real application bundle |
| the app runs, Steam never appears | AppleScript's `do shell script` **reaps whatever it starts**, even with `nohup … &`. Steam logged in and vanished the moment the applet returned | `cs2kit play --detach` double-forks and `setsid`s first, so it is reparented to launchd |
| the app reports its message but never starts Steam | `pgrep -f steam.exe` matches **any command line** mentioning it — including the shell that is about to launch Steam. CS2Kit believed Steam was already running | process detection is now `pgrep -ix steam.exe`, an exact **process name** match |
| the app is nowhere in Finder | it was installed into `~/Applications`, which Finder's sidebar does not show (Spotlight does) | it installs into **`/Applications`** when writable, named **CS2Kit.app**, with an icon |

**Check it yourself:**

```bash
open -a CS2Kit ; echo "rc=$?"     # must be 0
pgrep -ix steam.exe                # the client, not steamservice/steamwebhelper
tail -5 ~/CS2/cs2kit-app.log       # what the launcher actually did
```

A parenthesised bundle name (`Counter-Strike 2 (CS2Kit).app`) also refused to launch on this machine
after being replaced in place, while the same bundle named `CS2Kit.app` opened fine — most likely a stale
LaunchServices registration. The generated app is called **CS2Kit.app** for that reason. If you ever hit
it, `lsregister -f /Applications/YourApp.app` re-registers a bundle.
