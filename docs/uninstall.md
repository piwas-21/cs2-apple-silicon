# Uninstall CS2Kit

A Wine **bottle** and a Wine **prefix** are the same directory. They are not two separate installs.
CS2Kit runs from its checkout and has no automatic uninstall command. Remove the confirmed paths
below with Finder's **Move to Trash**, and empty Trash only after checking your backups.

The layout below is **CONFIRMED from the current implementation**, rather than a scan of your Mac:
[setup.py](../cs2kit/setup.py), [bottle.py](../cs2kit/bottle.py),
[engine.py](../cs2kit/engine.py), [app.py](../cs2kit/app.py),
[config.py](../cs2kit/config.py), and [util.py](../cs2kit/util.py).

## 1. Identify your paths before removing anything

| Component | Default location | Custom location or notes |
|---|---|---|
| Launcher | `/Applications/CS2Kit.app` or `~/Applications/CS2Kit.app` | `setup --app-dest` or `app create --dest` can choose another path. |
| Bottle / prefix | `~/CS2/prefix` | `--prefix` or `WINEPREFIX`; setup also uses `CS2KIT_SETUP_HOME/prefix` when neither is supplied. |
| Engines and downloaded engine archives | `~/.cs2kit/engines` | `CS2KIT_HOME/engines`; `engine install --dest` can put an extracted engine elsewhere. |
| Profiles, baselines, benchmarks, reports, caches | `~/.cs2kit` | `CS2KIT_HOME` changes the state location. A profile's `DXMT_SHADER_CACHE` can point elsewhere, including the default `~/.cs2kit/shader-cache`. |
| DXMT and installer downloads | `~/CS2/dxmt`, `~/CS2/downloads` | `CS2KIT_SETUP_HOME` changes the setup directory. |
| Game library | `~/CS2/library` | `CS2KIT_LIBRARY`, `bottle migrate --dest`, or `bottle link-steamapps --target` can choose another location. |
| Manual Wine / wrapper extracts | Often `~/CS2/engine` or `~/CS2/wine` | Check the directory used in the manual installation commands. |
| Logs | `~/CS2/cs2kit-app.log` | The launcher uses this path even with a custom setup directory. |
| Source checkout | Wherever you cloned this repository | Keep it until you have inspected the installation and restored any shared Wine files. |

These commands only list candidates. Environment variables describe this shell, so they may not
match the settings used during an earlier installation:

```bash
cs2kit_setup_dir="${CS2KIT_SETUP_HOME:-$HOME/CS2}"
cs2kit_prefix="${WINEPREFIX:-$cs2kit_setup_dir/prefix}"
cs2kit_state_dir="${CS2KIT_HOME:-$HOME/.cs2kit}"
cs2kit_library="${CS2KIT_LIBRARY:-$HOME/CS2/library}"
for path in /Applications/CS2Kit.app "$HOME/Applications/CS2Kit.app" \
    "$cs2kit_prefix" "$cs2kit_state_dir" "$cs2kit_setup_dir" "$cs2kit_library"; do
    if [ -e "$path" ] || [ -L "$path" ]; then ls -ld "$path"; fi
done
```

Set `cs2kit_prefix` to the actual custom prefix if you used one. Inspect its CS2Kit record and its
Steam library link:

```bash
cat "$cs2kit_prefix/.cs2kit/state.json"   # wine_root records the engine used by this bottle
ls -ld "$cs2kit_prefix/drive_c/Program Files (x86)/Steam/steamapps"
```

The second command displays a symlink's target without deleting or traversing it. A missing record
can mean setup stopped partway through or the prefix predates that record; absence is not proof
that a directory is safe to delete. Check your original setup command and custom app destination.
There is no complete installation manifest that can rediscover every custom path automatically.

## 2. Quit the bottle and preserve your data

Exit CS2 and use **Steam > Exit** in the Windows Steam client. If the bottle remains running,
use its own Wine server with the confirmed prefix. Replace the example path with `wine_root` from
the record above:

```bash
cs2kit_wine_root="/actual/path/to/wswine.bundle"
WINEPREFIX="$cs2kit_prefix" "$cs2kit_wine_root/bin/wineserver" -k
```

This targets the selected prefix. Avoid killing every process named Wine or Steam: other bottles
may be in use. Do not remove a bottle while its processes are writing to it.

Before removing the prefix, back up Steam's `userdata` and any local settings or saves you need
under `drive_c/Program Files (x86)/Steam`, `drive_c/users`, and any
`steamapps.cs2kit-backup` directory. Check what is actually there; do not assume Steam Cloud has
uploaded every file. Keep the game library in place until you decide whether to remove the game.

**Setup may have moved an existing CS2 installation into `~/CS2/library`.** That directory is not
just a disposable cache. If you want to keep CS2, retain the actual linked library, its
`appmanifest_730.acf`, and any data you need. Removing a prefix symlink does not remove its target;
manually deleting that target does. Do not merge the Windows install back into a live macOS Steam
library; see [the library-sharing failure](troubleshooting.md#24-macos-steam-deleted-your-windows-cs2-install).

## 3. Restore shared Wine files, if applicable

Skip this step for an engine used only by CS2Kit that you are removing completely. If you keep a
Wine installation used by other bottles, CS2Kit may have copied DXMT into that Wine tree. Preview
restoring the original backed-up DLLs before deleting the checkout or engine:

```bash
./bin/cs2kit bottle restore-wine --wine-root "$cs2kit_wine_root" --dry-run
```

Quit all bottles using that engine, inspect the preview, and run the same command without
`--dry-run` only if those are the files you want restored. This restores backed-up Wine DLLs;
it does not promise to undo every manual file copy. If no backup exists, reinstall the original
engine through its provider rather than guessing which shared files to delete.

## 4. Move only the components you intend to remove to Trash

Remove the confirmed launcher app, the dedicated prefix after backing it up, CS2Kit-only engines,
installer downloads, DXMT extracts, and logs. Remove the state directory if you no longer need its
benchmarks, reports, integrity baselines or caches. Check any custom shader-cache location too.
A staged `runtime` subdirectory, if present from another version, belongs to that state directory.

**Keep the game library unless you also want to uninstall the game.** Do not delete all of
`~/CS2` without reviewing its contents, and do not delete a shared Wine installation or another
application's prefix just because it contains Wine or Steam files.

If keeping the game, `config apply` may have written `game/csgo/cfg/cs2kit.cfg` and, with `--video`,
`CS2Video.txt` or a custom `--video-path`. The active-profile record in the state directory records
those output paths. Remove `cs2kit.cfg` only if it is yours to remove, remove any `exec cs2kit` line
you added to `autoexec.cfg`, and clear CS2Kit launch options you set in Steam. Restore video settings
from your own backup or the game's settings; CS2Kit does not keep the previous video file.

Finally, remove the source checkout, any symlink you created to its `bin/cs2kit`, and any PATH or
CS2Kit environment-variable lines you added to your shell configuration. The setup command does
not edit those shell files. If you separately installed the Python package with pip or uv, remove
it using the same tool and environment; the normal checkout-based setup does not install it.

Leave native macOS Steam, Rosetta, Python, Homebrew, and other applications' Wine engines installed
unless you independently want to remove them. They are shared tools, not CS2Kit-owned data.

## 5. Check before emptying Trash

Confirm that the intended app and prefix are gone, that retained libraries and backups remain,
and that other Wine applications still work. Empty Trash only once you no longer need to undo the
removal. You do not need to run setup again to verify an uninstall.
