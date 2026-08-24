# Reference - Windows Steam inside the bottle (T-007)

**Status: T-007 ACHIEVED on the machine of record, 2026-08-24.** The Windows Steam client renders, logs in and
serves CS2 — **on Sikarugir Wine 10.0 only**. T-007 is, per the plan, *"the most likely place to lose a day"*, and
it is where two of the three engines we measured fail outright. The record at the bottom is filled in with what was
measured; anything still marked **UNRECORDED** was not measured and must not be guessed.

> **Before anything else: the engine decides this task.** Gcenx Wine 11.15 renders Steam's window **black**
> (0.0/255) because DXMT cannot create a Metal view on it. FOSS CrossOver 24.0.7 renders the UI and then dies on
> *"Unexpected transport error (0x3008)"* because its Wine 9.0 base rejects the client's own helper websocket.
> **Sikarugir Wine 10.0 does both jobs.** Table and evidence: [../02-architecture.md](../architecture.md);
> `cs2kit engine list` prints the same verdicts.

## Why the Steam client must run inside the bottle

CS2 is launched by Valve's own launch entry `game\bin\win64\cs2.exe -steam`, and appid 730's configuration uses
Steamworks throughout: `usemms = 1` (matchmaking), `sdr-groups` (Steam Datagram Relay), Steam Inventory, and the
"Valve Anti-Cheat enabled" category. **No Steam client process in the bottle means no login, no matchmaking, no
inventory and no VAC session** - CONFIRMED from Valve's appinfo, `research/steam-vac-findings.md` section 2
("Does CS2 need the Steam client running at all? - YES").

macOS Steam cannot serve CS2 at all: appid 730 is `oslist = "windows,linux"`, and on this machine a "complete"
66 GB macOS install contains no `cs2.exe` ([target-machine.md](target-machine.md)). That is the whole reason this
task exists.

**Rule 3 of the project applies to every line below: never wrap, replace or automate Steam authentication**
([../06-legal-and-policy.md](../legal-and-vac.md)). You type your password into Valve's own client. CS2Kit
never sees it, never stores it, and has no code path that touches it.

---

## Procedure

### 1. Preconditions

```bash
cs2kit doctor            # wine, bottle, DXMT, disk must not be FAIL
export WINEPREFIX="$HOME/CS2/prefix"
```

The bottle must already exist (T-006 / `cs2kit bottle create`). Do not create it by hand here.

### 2. Have the Steam mobile app in your hand

You will log in by **scanning a QR code**, not by typing a password (step 4). Keep Steam Guard **enabled** -
([../06-legal-and-policy.md](../legal-and-vac.md), Account safety).

### 3. Install the Windows Steam client

```bash
curl -fLO https://cdn.akamai.steamstatic.com/client/installer/SteamSetup.exe
shasum -a 256 SteamSetup.exe        # record it in reference/toolchain.md
wine SteamSetup.exe /S              # /S = silent; the interactive installer works too
```

Then start it — **always with `-no-cef-sandbox`**, and always from a clean process table:

```bash
pkill -f steamwebhelper; pkill -f "Steam.exe"; wineserver -k
cd "$WINEPREFIX/drive_c/Program Files (x86)/Steam" && wine Steam.exe -no-cef-sandbox
```

Without that flag the client aborts on 0x3008 before the login screen. It is a **client** flag, not a game launch
option. `cs2kit launch` passes it for you, and `cs2kit app create` bakes it into a double-clickable `.app`.

**Start it from your own desktop login session.** Every "no window appeared" observation on this machine turned out
to be an artefact of the process that launched Wine — a background/agent shell is not an Aqua GUI session — and
that cost hours. The `.app` exists for exactly this reason.

Let the client **self-update completely** before doing anything else; a half-updated client produces errors that
look like Wine faults and are not.

### 4. Log in with the QR code, and let the library load

The sign-in screen shows a QR code. Scan it with the Steam mobile app and approve. **No password is typed into any
Wine window**, no Steam Guard code has to be transcribed, and the keyboard-focus problems disappear with it.
MEASURED 2026-08-24 — this is how the machine of record logged in.

Confirm: library list populates, friends list connects, the client idles **10 minutes without crashing**. That idle
is the acceptance test for T-007 - if the client cannot idle, CS2 will not help you diagnose it.

### 5. Disable the Steam overlay (globally)

Steam -> Settings -> In Game -> uncheck **Enable the Steam Overlay while in-game**. Disabling the overlay (plus
GPU-accelerated rendering and hardware video decoding in the client) is reported to take an M3/8 GB machine from
"max 80 / min 55" to "constant 120 / min 75" - LIKELY, two sources, `research/performance-alternatives-findings.md`
item 9. Revisit under measurement in T-016.

### 6. Point Steam at the existing asset tree — with a symlink, not a library folder

This is what avoids a second 72 GB download (T-008):

```bash
cs2kit bottle link-steamapps
```

It replaces the bottle's own `drive_c/Program Files (x86)/Steam/steamapps` with a symlink to
`~/Library/Application Support/Steam/steamapps` (the original is kept beside it). Restart the client; CS2 shows as
installed.

> **Adding it as a Library Folder does not survive.** Steam -> Settings -> Storage -> Add Drive appears to work and
> is gone after the next start: **Steam rewrites `libraryfolders.vdf` on every launch.** MEASURED 2026-08-24. The
> symlink survives because Steam cannot rewrite the filesystem.

If the client still offers a full download, the manifest is in the wrong place — promote `appmanifest_730.acf` to
the library root with `InstalledDepots` 2347770 / 2347771 / 2347774 (see
[../10-troubleshooting.md](../troubleshooting.md) entry 23).

**Timebox the reuse attempt to 2 hours** (T-008 step 2). If the in-bottle client insists on re-downloading
everything and the disk cannot hold both copies, uninstall the macOS copy first and install cleanly. The fallback
always works; the reuse route is *undocumented* and is the risk you are timeboxing.

### 7. Run it in your GUI session

```bash
cs2kit app create        # writes a double-clickable .app: verify the game files, then launch
```

---

## Known failure modes

| Symptom | Cause | Action |
|---|---|---|
| The client's window is **black** (0.0/255) while `wine notepad` renders fine | the engine exports no `winemac.drv` symbols, so DXMT has no Metal view and ANGLE has no surface | change the engine — `cs2kit engine install`; [../10-troubleshooting.md](../troubleshooting.md) entry 20 |
| *"An unexpected error occurred while starting Steam (0x3008)"* | the CEF sandbox, a stale helper, **or** a Wine 9.0-based engine whose client rejects its own helper websocket | `-no-cef-sandbox` + clean process table; if it persists, the engine — entry 18 |
| `wineserver` aborts: `Library not loaded: @rpath/libinotify.0.dylib` | the wrapper dylibs were never staged beside the engine | `cs2kit engine install`; entry 21 |
| Client installs, then crashes on first run | usually an incomplete self-update, occasionally a missing DLL override | let it finish updating; `WINEDEBUG=+loaddll` and read the log before changing the bottle |
| No window appears at all, no error | the client was started from a non-GUI (background/agent) process | start it from your own desktop session, e.g. the `.app` from `cs2kit app create` |
| CS2 shows as "not installed" after a restart | Steam rewrote `libraryfolders.vdf` | use the symlink, not a library folder — `cs2kit bottle link-steamapps`; entry 23 |
| Library empty after login | account/region issue in Valve's client, not Wine | log out and back in inside the bottle |

If Steam will not run at all, **that is a Wine/stack problem - fix it here, not after CS2 is involved** (T-007 risk note).

---

---

## The record — machine of record, 2026-08-24

### Environment

| Field | Value |
|---|---|
| Date | **2026-08-24** |
| Wine version | **`wine-10.0 (Sikarugir)`** (`WS12WineSikarugir10.0_6.tar.xz`, sha256 `9da7ee0c…6091b2`) |
| `WINEPREFIX` | `~/CS2/prefix` on a stock install; the session of record used a per-engine prefix while comparing engines |
| `SteamSetup.exe` SHA-256 | `7d3654531c32d941b8cae81c4137fc542172bfa9635f169cb392f245a0a12bcb` (2 380 800 bytes, downloaded 2026-08-24) |
| In-bottle Steam client build | **1785799196** |
| Login method | **QR code**, scanned with the Steam mobile app. No password was typed into a Wine window |
| Mandatory client flag | `-no-cef-sandbox` |
| Time from `wine SteamSetup.exe` to a loaded library | **UNRECORDED** — the session of record spent its time on the engine comparison, not on a clean single-pass install |

### Every error, verbatim

Paste the exact text. An approximated error message cannot be searched for.

| # | Where | Error (verbatim) | Fix that worked | Time lost |
|---|---|---|---|---|
| 1 | client startup, **Gcenx Wine 11.15 staging/devel** | *(no error — the window simply painted `0.0/255` black; CS2 later named the cause: `err: Failed to create metal view, it seems like your Wine has no exported symbols needed by DXMT`)* | change the engine to Sikarugir Wine 10.0 | most of a day, across nine tested configurations |
| 2 | client startup, **Gcenx staging** only | `gpu_process_host.cc(1002): GPU process exited unexpectedly: exit_code=-2147483645` (0xC0000005), 9x per launch | Gcenx **devel** has zero such crashes — and is still unusable for the reason above | — |
| 3 | client startup, **FOSS CrossOver 24.0.7** | `An unexpected error occurred while starting Steam (0x3008)`; in `logs/transport_client.txt`: `WebUITransport: Connection rejected` (82x); in `console_log.txt`: `src\steamUI\webuitransportcontroller.cpp (165) : Failed to reconnect to websocket: wine` | none — no flag fixes it; change the engine | — |
| 4 | any engine, sandbox on | 0x3008 as above, on the first launch | `-no-cef-sandbox`, from a clean process table | — |
| 5 | first `wineserver` start on a bare engine | `Library not loaded: @rpath/libinotify.0.dylib` | stage `Contents/Frameworks/*.dylib` from Template 1.0.11 into `<engine>/lib/` | — |
| 6 | CrossOver engine, during bootstrap | `err:bcrypt:key_asymmetric_create no encryption support` | did not block login on the Sikarugir engine; recorded because it looked like a cause and was not | — |

### Library reuse outcome (feeds T-008)

| Question | Answer |
|---|---|
| Did the in-bottle client see the macOS library? | **Yes — through a symlink at `drive_c/Program Files (x86)/Steam/steamapps`.** As a *Library Folder* added in the UI: **no**, Steam rewrites `libraryfolders.vdf` on every start |
| Did it recognise depot 2347770 as already present? | **Not on the `steamcmd` route** — it re-downloaded ~71.7 GB. The finished install was then reused by the client with **no second download** |
| Bytes actually downloaded for appid 730 | **~71.7 GB** (steamcmd, full install). The ~4.99 GB depot-gap route remains **unproven** |
| `game/bin/win64/cs2.exe` present afterwards? | **Yes** — 2 967 704 bytes, one of 123 files in that directory |
| `buildid` after install | **24828357** (`StateFlags 4`, `SizeOnDisk 71 644 882 396`) |
| "Verify integrity of game files" clean on first pass? | **Yes** — `steamcmd`'s own `validate` pass; 137 binaries were baselined immediately after ([../11-validation-log.md](../project/validation-log.md), T-021) |

### Acceptance (T-007)

* In-bottle client shows the library and idles 10 minutes without crashing: **YES, 2026-08-24, on Sikarugir Wine
  10.0.** On the other two engines: **NO** — black window, and 0x3008 respectively.
* Recorded by: the session logged in [../implementation-status.md](../project/measured-results.md) - Date: **2026-08-24**
