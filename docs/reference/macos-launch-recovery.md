# macOS launcher and fullscreen recovery, 2026-11-18

Scope: T-009 (first launch/display settings), T-024 (diagnosis), T-027 (profile repair).
Local machine: Apple M2 Max, 64 GB, macOS 27.2 (26B123), Sikarugir Wine 10.0,
DXMT v0.80, CS2 build 26393695. These are observations from this recovery, not a
general compatibility claim or performance benchmark.

## Findings

**CONFIRMED:** the installed launcher had `Contents/MacOS/cs2kit-launch`, a Bash
script. `build_app` unconditionally called `_write_script_app` although the
native `_compile_applet` implementation was available. Opening the old bundle
through the app UI timed out. The generated applet now uses a native universal
Mach-O executable and hands over to Steam with `--steam-only --gui --detach`.
Its plist and icons are applied before ad-hoc signing; editing these after
`osacompile` otherwise invalidates the signature.

**CONFIRMED:** after Steam updated and restarted itself, `ps` showed its name as
`C:\Program Files (x86)\Steam\steam.exe`, while `steam_running()` returned false.
After changing detection to compare executable basenames in `ps`'s `comm` field,
it returned true. Shell arguments and Steam service/web helpers do not count.

**CONFIRMED:** the user saw the game render normally in a window, changed it to
fullscreen and 16:9, then reported that applying those settings closed the game.
The existing `userdata/<account>/730/local/cfg/cs2_video.txt` contained:

```text
"setting.defaultres"        "-1"
"setting.defaultresheight"  "-1"
"setting.fullscreen"        "1"
```

The local launcher log recorded the matching failure:

```text
-[MTLTextureDescriptorInternal validateWithDevice:]:1421: failed assertion `Texture Descriptor Validation
MTLTextureDescriptor has width (4294967295) greater than the maximum allowed size of 16384.
MTLTextureDescriptor has height (4294967295) greater than the maximum allowed size of 16384.
```

**LIKELY mechanism:** the invalid signed dimensions reached Metal as unsigned
32-bit values (`-1` becomes `4294967295`). The exact upstream component responsible
for generating/accepting these dimensions has not been isolated. This does not
establish that the macOS upgrade caused the earlier black screen.

## Recovery and limits

After exiting Steam, `config apply balanced-1080p --video --no-cfg` repaired the
existing account file and preserved the original as `.cs2kit-backup`. The command
now discovers this file instead of writing only the unused install-tree
`CS2Video.txt`. It preserves unrelated quality settings and refuses to guess
between multiple accounts; `--video-path` selects a particular one.

**CONFIRMED:** `app create --json` reported `"kind": "applet"`;
`codesign --verify --verbose /Applications/CS2Kit.app` reported `valid on disk`
and `satisfies its Designated Requirement`; `open /Applications/CS2Kit.app`
returned zero and started Steam. Steam logged in and launched CS2 again after
the repair. The game log reported `Successfully created dx11 swap chain` and
the process survived beyond the previous fullscreen failure point. The game
persisted a positive window size and `setting.fullscreen = 0`.

**UNKNOWN:** exclusive-fullscreen switching is not repaired inside Wine/DXMT
by this change; another switch can reproduce the crash. Use windowed mode on
this configuration. Post-repair gameplay, performance, and secure-server play
were not measured. No game executable or DLL was modified.

## External display and Steam exit follow-up

**CONFIRMED, 2026-11-18:** after more video-menu changes, the saved mode was
1728×1117, exclusive fullscreen, 120 Hz, monitor index 0, and borderless enabled.
The connected laptop was the main display; the Samsung C49HG9x external display
was 3840×1080 at 60 Hz. Steam's CS2 `LaunchOptions` was empty. The startup log
showed repeated exclusive display-mode switches and another Metal encoder abort.
**LIKELY:** persisting the laptop's exclusive mode across a monitor change is
the trigger; the exact upstream graphics defect remains unisolated.

**CONFIRMED:** Steam's main macOS PID stayed 41833 from 23:29 through the apparent
relaunches at 23:47. Its web helper restarted with start counts 1, 2, and 3, while
the bootstrap log showed no new Steam startup. There was no active CS2Kit
launcher/watchdog process. This was the client recreating its UI rather than a
new Steam client being launched. A `steam.exe -shutdown` request removed the main
client, then `cs2kit stop` confirmed the selected bottle was down. It stayed down
until explicitly started for the next test.

Local recovery backed up the current account files, restored 1600×900 windowed
mode, selected monitor index 1, and saved `-windowed -w 1600 -h 900 -novid` in
Steam's CS2 launch-options field. Only that field of `localconfig.vdf` changed;
no authentication data was edited. The next `steam.exe -applaunch 730` request
supplied no temporary video arguments, and Steam's game-process log confirmed
it appended those persisted options. The saved video file showed 1600×900,
fullscreen 0, monitor 1, refresh numerator/denominator 0/0, and borderless 0.

The profile repair now clears stale exclusive refresh and borderless settings
when applying a windowed profile. `cs2kit app create --stop` creates a separate
native, signed Quit CS2Kit app which runs only the existing prefix-scoped stop
command. This makes the working shutdown path accessible from Finder.

**CONFIRMED shutdown test:** opening `/Applications/Quit CS2Kit.app` with
`open -W` returned successfully; the client, web-helper, and game PID lists were
all empty. Seven samples over the following 60 seconds remained empty. The
native play app then started a new Steam session, and only newly appended
connection-log entries were used to confirm that it logged in.

The user reported another apparent closure during this testing, so a live
process alone was not accepted as proof of successful rendering. The next
launch enabled `-condebug`: it logged the persisted windowed arguments, created
its DX11 swap chain, initialized the game server, loaded the UI scene, and
persisted configuration successfully. No new Metal assertion or error-reporter
process appeared during the initial observation. Human confirmation of the
external window and gameplay remains separate from these startup checks.

**CONFIRMED visual result:** the user supplied a screenshot at 23:58 showing the
CS2 video menu rendering on monitor 2, Windowed, 16:9, 1600×900, with a desktop
refresh rate of 60 Hz. This confirms the external-display menu result; it does
not establish gameplay or exclusive-fullscreen stability. The final test
session was left open for the user.

**CONFIRMED display-link limit:** the user identified a USB-C hub/dock with HDMI.
A read-only CoreGraphics mode enumeration exposed only 60 Hz at 3840×1080,
with no 120/144 Hz mode at that resolution. This establishes what this connection
currently advertises, not which hub, cable, or monitor input setting is responsible.
