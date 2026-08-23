# 10 - Troubleshooting

Keyed by **symptom**. Every entry has the same five parts: what you see, why, a **one-command check**, the fix, and
where the evidence comes from. Nothing here is folklore - each entry cites a `docs/` or `research/` file, and each
carries a **CONFIRMED** (vendor or primary source), **LIKELY** (community, consistent) or **UNKNOWN** tag.

**Start here, always:**

```bash
cs2kit doctor          # most problems are environment problems; every line ends in one actionable fix
cs2kit doctor --json   # the same thing for an issue report
```

`cs2kit doctor` exits `1` if anything FAILs. Exit codes are documented in [cs2kit-spec.md](cs2kit-spec.md).

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

---

## 1. Black screen on launch, audio plays, nothing renders

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

**Evidence.** CONFIRMED - [07-benchmark-protocol.md](07-benchmark-protocol.md) reference field and its trap 2;
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
trap 3 in [07-benchmark-protocol.md](07-benchmark-protocol.md).

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
trap 1 in [07-benchmark-protocol.md](07-benchmark-protocol.md).

## 6. Steam inside the bottle will not log in (Steam Guard)

**Cause.** The Steam Guard mobile-authenticator prompt is the usual first wall, and a half-completed client
self-update produces errors that look like Wine faults but are not.

**Check.**

```bash
cs2kit doctor            # 'Bottle' and 'Wine' must be PASS before you blame Steam
```

**Fix.** Have the mobile authenticator ready **before** you run `wine SteamSetup.exe`; let the client finish
self-updating completely; then let it idle for 10 minutes before installing anything. If the client cannot idle, the
problem is the Wine stack, not CS2 - fix it here, before the game is involved.

**CS2Kit never wraps, replaces or automates Steam authentication** - you log into Valve's own client, every time.
That is an absolute rule, not an omission ([06-legal-and-policy.md](06-legal-and-policy.md)).

**Evidence.** Procedure and the errors-and-fixes table: [reference/steam-in-bottle.md](reference/steam-in-bottle.md);
risk R-11 in [05-risk-register.md](05-risk-register.md).

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
policy in [06-legal-and-policy.md](06-legal-and-policy.md) section 2.

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
risk R-12 in [05-risk-register.md](05-risk-register.md).

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
recommendation: [rosetta-watch.md](rosetta-watch.md).

**Evidence.** CONFIRMED, Apple primary - [../research/tooling-licensing-findings.md](../research/tooling-licensing-findings.md)
sections 6 and 7; risk R-1 in [05-risk-register.md](05-risk-register.md).

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
budget; risk R-6 (*"already occurring"*) in [05-risk-register.md](05-risk-register.md).

## 11. DXMT is not actually in use

**Cause.** The `d3d11`/`dxgi` DLL overrides are missing from the prefix, or the DXMT DLLs were never copied into it,
so you are falling back to Wine's own Direct3D path. Symptoms range from a black window to a technically-running game
that is far slower than the reference field would predict.

**Check.**

```bash
cs2kit doctor            # the 'DXMT' check
cs2kit bottle diff       # drift between profiles/bottle-recipe.yaml and the prefix
```

**Fix.**

```bash
cs2kit bottle repair                                  # re-apply the recipe
cs2kit bottle create --dxmt /path/to/extracted-dxmt   # or install DXMT into a fresh bottle
```

Record the DXMT release you used in [reference/toolchain.md](reference/toolchain.md) - a benchmark whose graphics
backend version is unrecorded cannot be compared with anything.

**Evidence.** DXMT is the project's chosen backend and its critical dependency
([02-architecture.md](02-architecture.md)); community data shows 10x swings between backends across machines, which
is why T-012 measures rather than assumes (risk R-5, [05-risk-register.md](05-risk-register.md)).

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
[09-install-guide.md](09-install-guide.md)). Keep the macOS content depot 2347770 - the in-bottle client may be able
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

**Evidence.** T-021 and absolute rule 1 - [06-legal-and-policy.md](06-legal-and-policy.md); post-update drill in
[03-development-plan.md](03-development-plan.md) T-030.

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
| External-monitor behaviour | **UNKNOWN** - no CS2-specific report exists; T-014 generates it | research item 16 |

Items are in [../research/performance-alternatives-findings.md](../research/performance-alternatives-findings.md),
section 2.

## Reporting a problem

```bash
cs2kit report            # redacted: no SteamID, no account name, no usernames in paths, no IPs, no MACs
```

`cs2kit report` prints exactly what it will share before it writes anything. Attach the bundle, say which step of
[09-install-guide.md](09-install-guide.md) you were on, and paste `cs2kit doctor --json`. A bundle also feeds the
community dataset (T-033) - what is stripped and where to send it is in
[12-maintenance.md](12-maintenance.md) - which is the one thing this ecosystem has never had.
