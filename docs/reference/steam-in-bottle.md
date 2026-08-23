# Reference - Windows Steam inside the bottle (T-007)

**Status: TEMPLATE.** The procedure is fully specified; every machine-specific output is **UNRECORDED** until a human
runs it. T-007 is, per the plan, *"the most likely place to lose a day"* - so the value of this file is the
**deviations table** at the bottom, not the happy path.

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
([../06-legal-and-policy.md](../06-legal-and-policy.md)). You type your password into Valve's own client. CS2Kit
never sees it, never stores it, and has no code path that touches it.

---

## Procedure

### 1. Preconditions

```bash
cs2kit doctor            # wine, bottle, DXMT, disk must not be FAIL
export WINEPREFIX="$HOME/CS2/prefix"
```

The bottle must already exist (T-006 / `cs2kit bottle create`). Do not create it by hand here.

### 2. Have Steam Guard ready **before** you start

The mobile authenticator prompt is the usual first wall (T-007 step 1). Losing the code round-trip mid-install is
the most common way this step turns into an hour. Keep Steam Guard **enabled** -
([../06-legal-and-policy.md](../06-legal-and-policy.md), Account safety).

### 3. Install the Windows Steam client

```bash
curl -LO https://cdn.akamai.steamstatic.com/client/installer/SteamSetup.exe
shasum -a 256 SteamSetup.exe        # record it in reference/toolchain.md
wine SteamSetup.exe
```

Accept the installer defaults. Let the client **self-update completely** before doing anything else; a
half-updated client produces errors that look like Wine faults and are not.

### 4. Log in and let the library load

Confirm: library list populates, friends list connects, the client idles **10 minutes without crashing**. That idle
is the acceptance test for T-007 - if the client cannot idle, CS2 will not help you diagnose it.

### 5. Disable the Steam overlay (globally)

Steam -> Settings -> In Game -> uncheck **Enable the Steam Overlay while in-game**. Disabling the overlay (plus
GPU-accelerated rendering and hardware video decoding in the client) is reported to take an M3/8 GB machine from
"max 80 / min 55" to "constant 120 / min 75" - LIKELY, two sources, `research/performance-alternatives-findings.md`
item 9. Revisit under measurement in T-016.

### 6. Point Steam at the existing 58 GB asset tree

This is what turns a 72 GB download into a ~5 GB one (T-008). Map a Wine drive to the macOS Steam library and add it
as a Steam library folder inside the bottle:

```bash
# a drive letter that points at the macOS Steam library
ln -s "$HOME/Library/Application Support/Steam/steamapps" "$WINEPREFIX/dosdevices/s:"
```

Then in the in-bottle client: Steam -> Settings -> Storage -> Add Drive -> `S:`.

**Timebox the reuse attempt to 2 hours** (T-008 step 2). If the in-bottle client insists on re-downloading
everything and the disk cannot hold both copies, uninstall the macOS copy first and install cleanly. The fallback
always works; the reuse route is *undocumented* and is the risk you are timeboxing.

---

## Known failure modes

| Symptom | Cause | Action |
|---|---|---|
| Steam Guard prompt never arrives | mobile authenticator not to hand | have it ready before step 3 |
| Client installs, then crashes on first run | usually an incomplete self-update, occasionally a missing DLL override | let it finish updating; `WINEDEBUG=+loaddll` and read the log before changing the bottle |
| Library folder `S:` not offered | the symlink points at a directory Steam cannot write | check ownership; Steam needs write access for its manifests |
| Library empty after login | account/region issue in Valve's client, not Wine | log out and back in inside the bottle |

If Steam will not run at all, **that is a Wine/stack problem - fix it here, not after CS2 is involved** (T-007 risk note).

---

## To be filled in on first run

### Environment

| Field | Value |
|---|---|
| Date | UNRECORDED |
| Wine version | UNRECORDED |
| `WINEPREFIX` | UNRECORDED |
| `SteamSetup.exe` SHA-256 | UNRECORDED |
| In-bottle Steam client build | UNRECORDED |
| Time from `wine SteamSetup.exe` to a loaded library | UNRECORDED |

### Every error, verbatim

Paste the exact text. An approximated error message cannot be searched for.

| # | Where | Error (verbatim) | Fix that worked | Time lost |
|---|---|---|---|---|
| 1 | UNRECORDED | UNRECORDED | UNRECORDED | UNRECORDED |

### Library reuse outcome (feeds T-008)

| Question | Answer |
|---|---|
| Did the in-bottle client see drive `S:` as a library folder? | UNRECORDED |
| Did it recognise depot 2347770 as already present? | UNRECORDED |
| Bytes actually downloaded for appid 730 | UNRECORDED (expected ~4.99 GB if reuse worked, ~60 GB if not) |
| `game/bin/win64/cs2.exe` present afterwards? | UNRECORDED |
| `buildid` after install | UNRECORDED (public buildid at planning time: 24828357) |
| "Verify integrity of game files" clean on first pass? | UNRECORDED |

### Acceptance (T-007)

* In-bottle client shows the library and idles 10 minutes without crashing: **UNRECORDED**
* Recorded by: UNRECORDED - Date: UNRECORDED
