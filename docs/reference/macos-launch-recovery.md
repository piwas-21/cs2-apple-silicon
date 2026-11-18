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
Mach-O executable. The recovery used `--steam-only --gui --detach` to hand over
to Steam manually. Following review, generated launchers use `--gui --detach`
and Steam's `-applaunch` path, preserving the profile's game launch options.
Manual handoff remains available through the explicit CLI `--steam-only` flag.
Its plist and icons are applied before ad-hoc signing; editing these after
`osacompile` otherwise invalidates the signature.

**CONFIRMED:** after Steam updated and restarted itself, `ps` showed its name as
`C:\Program Files (x86)\Steam\steam.exe`, while `steam_running()` returned false.
After changing detection to compare executable basenames in `ps`'s `comm` field,
it returned true. Shell arguments and Steam service/web helpers do not count.
Following review, candidates must also carry the selected bottle's `WINEPREFIX`;
identical Windows paths in another bottle cannot suppress startup. Hermetic
regression tests cover both process-name forms and multiple bottles. A local
macOS subprocess smoke check verified environment ownership detection with a
prefix containing spaces; a second live Wine bottle was not started for testing.

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
Following review, repair recognizes quoted strings and comments before locating
the root block and its display keys. It preserves comments and nested quality
settings, and rejects incomplete or malformed blocks before writing any files.

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
