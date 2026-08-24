# Installing the free stack for real: Wine 11.15 + DXMT v0.80 on Apple Silicon

Research date: **2026-08-24**. Machine of record: **Apple M2 Pro, macOS 26.5.2 (25F84)**
([../docs/reference/target-machine.md](../docs/reference/target-machine.md)).
Method: every line below is either a command run on that machine on that date, or a primary source fetched over
HTTPS on that date. No secondary sources, no forum posts, no inference presented as measurement.
Confidence tags: **CONFIRMED** = executed here or read from the vendor's own artefact; **LIKELY** = consistent
primary evidence but not directly executed; **UNKNOWN** = not established.

> **Why this file exists.** `docs/03-development-plan.md` T-004 and `docs/09-install-guide.md` step 3 told the
> reader to install Wine with `brew install --cask gcenx/wine/wine-crossover`. That command **cannot succeed on any
> machine today** — the cask was deleted upstream four months ago. The plan was also wrong about which Wine that
> cask would have installed. This file records what was measured instead, and §9 names the exact lines it corrects.

---

## 0. The verdict in one paragraph

The Homebrew route this project shipped is dead in three independent ways (§1), and Homebrew's *own* Wine casks are
eight days from being disabled (§2). The route that works needs no Homebrew, no admin rights and no Gatekeeper
argument: two signed-by-nobody tarballs, two SHA-256s, `tar -x` (§3). DXMT's published release is the **builtin**
build, which installs into the **Wine tree** and requires the `d3d11`/`dxgi` overrides to be **off** — the opposite
of what this project's bottle recipe did (§4). DXMT's wiki demands "CrossOver Wine 24+"; on v0.80 that requirement
no longer binds, and DXMT was measured loading and initialising Metal under **stock Wine 11.15 staging** (§5).
DXMT v0.80 is **MIT**, not LGPL-2.1 (§7).

---

## 1. `brew install --cask gcenx/wine/wine-crossover` cannot work — three separate failures

### 1a. The cask was deleted from the tap (CONFIRMED)

```console
$ brew install --cask gcenx/wine/wine-crossover
Warning: Cask 'wine-crossover' is unavailable: '/opt/homebrew/Library/Taps/gcenx/homebrew-wine/Casks/wine-crossover.rb' does not exist.
Error: No casks found for wine-crossover.
```

The tap's own git history says when and by whom:

```console
$ git -C /opt/homebrew/Library/Taps/gcenx/homebrew-wine log --oneline -5
8fa0df7 Fix homebrew warning by using newer depends_on syntax
f201026 Delete Casks/wine-crossover.rb
3df0f22 Update game-porting-toolkit.rb
...
$ git -C /opt/homebrew/Library/Taps/gcenx/homebrew-wine show --stat f201026
commit f2010264750946da91893971c094a3cfb5bdcfb0
Author: Dean M Greer <38226388+Gcenx@users.noreply.github.com>
Date:   Thu Apr 16 09:44:35 2026 -0400

    Delete Casks/wine-crossover.rb

 Casks/wine-crossover.rb | 60 -------------------------------------------------
$ ls /opt/homebrew/Library/Taps/gcenx/homebrew-wine/Casks/
game-porting-toolkit.rb
```

**Deleted 2026-04-16.** One cask remains in the tap: `game-porting-toolkit`.

### 1b. The tap's README still advertises it — the documentation upstream is stale too (CONFIRMED)

```console
$ sed -n '5,8p' /opt/homebrew/Library/Taps/gcenx/homebrew-wine/README.md
## casks
- `game-porting-toolkit` *(v3.0)*
- `wine-crossover`       *(wine-8.0.1 [crossover-sources-23.7.1](...))*
```

Four months after the deletion, the tap's front page still lists a cask that no longer exists. **A README is not a
package index.** This is why §3 pins URLs and checksums rather than package names.

### 1c. Even if it existed, it shipped Wine 8.0.1 — not "Wine 11.x" (CONFIRMED)

The deleted file, recovered from git:

```console
$ git -C /opt/homebrew/Library/Taps/gcenx/homebrew-wine show f201026^:Casks/wine-crossover.rb | head -8
cask "wine-crossover" do
  version "23.7.1-1"
  sha256 "e24ba084737c8823e8439f7cb75d436a917fd92fc34b832bcaa0c0037eb33d03"

  url "https://github.com/Gcenx/winecx/releases/download/crossover-wine-#{version}/wine-crossover-#{version}-osx64.tar.xz"
```

`crossover-sources-23.7.1` is **wine-8.0.1** (the tap README states the mapping explicitly). Our plan and install
guide both annotated this command `# Wine 11.x`. That annotation was **wrong by three major versions**, and it was
wrong before the cask was deleted. Nobody had run the command.

### 1d. Homebrew now refuses third-party casks by default (CONFIRMED)

The one cask that *does* survive in that tap cannot be installed without an extra, undocumented step:

```console
$ brew info --cask game-porting-toolkit
Error: Refusing to load cask gcenx/wine/game-porting-toolkit from untrusted tap gcenx/wine.
Run `brew trust --cask gcenx/wine/game-porting-toolkit` or `brew trust gcenx/wine` to trust it.
```

This matters beyond Wine: `game-porting-toolkit` is how `docs/03` and `docs/06` describe a user installing Apple's
D3DMetal for the T-012 fallback. That instruction now needs a `brew trust` line or it fails at the first command.

---

## 2. Homebrew's own Wine casks are on a dated cliff: **2026-09-01** (CONFIRMED)

```console
$ brew info --cask wine-stable
==> wine-stable (WineHQ-stable): 11.0_1
Deprecated because it does not pass the macOS Gatekeeper check! It will be disabled on 2026-09-01.
Required (1): gstreamer-runtime (cask)

$ brew info --cask wine@staging
==> wine@staging (WineHQ-staging): 11.15
Deprecated because it does not pass the macOS Gatekeeper check! It will be disabled on 2026-09-01.
Required (1): gstreamer-runtime (cask)
```

**Eight days from this research date.** Both official WineHQ macOS casks. The stated reason is the *delivery*, not
the software — Homebrew's own words are *"does not pass the macOS Gatekeeper check"*; that the mechanism is an
unsigned/un-notarised `.app` is **LIKELY**, inferred from the message, not quoted from it. This is a **second dated
risk** alongside the Rosetta-27 horizon and is scored as **R-15** in
[../docs/05-risk-register.md](../docs/05-risk-register.md).

Consequence for this project: **no Homebrew route to Wine survives the month.** Not `gcenx/wine/wine-crossover`
(gone), not `wine-stable`, not `wine@staging` (disabled 2026-09-01). This is not a reason to pick a different cask;
it is the reason the install guide stopped using casks at all.

---

## 3. What works: two tarballs, verified, extracted, run (CONFIRMED — installed on this machine)

| Component | URL | Released | Size (bytes) | SHA-256 |
|---|---|---|---|---|
| **Wine 11.15 staging** (Gcenx) | `https://github.com/Gcenx/macOS_Wine_builds/releases/download/11.15/wine-staging-11.15-osx64.tar.xz` | **2026-08-08** | 193 561 920 (~185 MiB) | `a8c50d0e14fb7982a21506287e1e41e1990fe77c74fa2a32da7dbcf7b21de1e2` |
| **DXMT v0.80 builtin** (3Shain) | `https://github.com/3Shain/DXMT/releases/download/v0.80/dxmt-v0.80-builtin.tar.gz` | **2026-04-23** | 18 681 669 (~17.8 MiB) | `8f260e36b5739e68f3bad613381441385c4dc7b85b78ba8de653d5a6a264529d` |

Both checksums were computed locally with `shasum -a 256` on the downloaded files. Both release dates, asset names
and byte counts were read back from the GitHub releases API on 2026-08-24
(`https://api.github.com/repos/Gcenx/macOS_Wine_builds/releases/tags/11.15`,
`https://api.github.com/repos/3Shain/DXMT/releases/tags/v0.80`).

**A tarball is not a cask.** It needs no `sudo`, and it can be pinned by checksum, which a moving cask cannot. On
Gatekeeper, measured rather than assumed:

```console
$ xattr -p com.apple.quarantine ~/CS2/downloads/wine-staging-11.15-osx64.tar.xz
xattr: ...: No such xattr: com.apple.quarantine
$ xattr -l ~/CS2/downloads/wine-staging-11.15-osx64.tar.xz
...: com.apple.provenance:
```

**CONFIRMED: a `curl`-downloaded tarball carries no quarantine attribute** (only `com.apple.provenance`), and a
fresh extraction into a scratch directory ran `wine --version` → `wine-11.15 (Staging)` with no Gatekeeper prompt
and no `--no-quarantine` equivalent needed. **LIKELY** that a *browser* download would be quarantined — browsers set
the attribute, `curl` does not — in which case `xattr -dr com.apple.quarantine ~/CS2/wine` clears it. Not tested.

After extraction the Wine installation lives at:

```
~/CS2/wine/Wine Staging.app/Contents/Resources/wine/     <- the "wine root": holds bin/ and lib/wine/
  bin/wine
  lib/wine/x86_64-unix/     lib/wine/x86_64-windows/     lib/wine/i386-windows/
```

```console
$ "$HOME/CS2/wine/Wine Staging.app/Contents/Resources/wine/bin/wine" --version
wine-11.15 (Staging)
```

**Wine 11 has one `wine` loader; there is no `wine64`.** (Already stated in the plan; re-confirmed here — the
tarball contains no `wine64` binary.)

DXMT's archive layout, as extracted (CONFIRMED, `tar -tzf` and `find`). The archive carries its own top-level
version directory, so `tar -xzf … -C ~/CS2/dxmt` produces `~/CS2/dxmt/v0.80/…`:

```
v0.80/x86_64-unix/winemetal.so
v0.80/x86_64-windows/{d3d11,dxgi,d3d10core,winemetal,nvapi64,nvngx}.dll
v0.80/i386-windows/{d3d11,dxgi,d3d10core,winemetal}.dll
```

`nvngx.dll` / `nvapi64.dll` are DXMT's DLSS-shim surface. **UNKNOWN** whether they matter for CS2; not placed, not
tested.

### 3a. One upstream requirement we are not yet honouring (CONFIRMED that it is stated; UNKNOWN whether it binds CS2)

The Gcenx 11.15 release page states under **Requirements**: *"macOS Catalina and greater"* and
*"GStreamer.framework installed for all users"*, linking
`https://gstreamer.freedesktop.org/data/pkg/osx/1.28.5/gstreamer-1.0-1.28.5-universal.pkg`. Homebrew's own Wine
casks encode the same dependency (`Required (1): gstreamer-runtime (cask)`, §2).

GStreamer is Wine's media backend. Whether CS2 — which plays no video once `-novid` is set — needs it is
**UNKNOWN**. It was **not** installed on this machine, and Wine 11.15, DXMT and the Metal probe in §5 all ran
without it. Recorded so that a future audio/video failure has somewhere to look first.

---

## 4. DXMT installs into the **Wine tree**, and the DLL overrides must be **OFF**

Source: DXMT wiki, *"DXMT Installation Guide for Geeks"*,
<https://github.com/3Shain/DXMT/wiki/DXMT-Installation-Guide-for-Geeks>, fetched 2026-08-24. **CONFIRMED, verbatim.**

The published asset is `dxmt-v0.80-**builtin**.tar.gz`, i.e. the `-Dwine_builtin_dll=true` build. The wiki gives two
mutually exclusive layouts and this project shipped the wrong one:

| File | `-Dwine_builtin_dll=true` — **the published release** | `-Dwine_builtin_dll=false` — *not published* |
|---|---|---|
| `winemetal.so` | `<wine>/lib/wine/x86_64-unix/` | `<wine>/lib/wine/x86_64-unix/` |
| `winemetal.dll` | `<wine>/lib/wine/x86_64-windows/` **and** `<prefix>/drive_c/windows/system32/` | same |
| `d3d11.dll` | `<wine>/lib/wine/x86_64-windows/` | `<prefix>/drive_c/windows/system32/` |
| `dxgi.dll` | `<wine>/lib/wine/x86_64-windows/` | `<prefix>/drive_c/windows/system32/` |
| `d3d10core.dll` (optional) | `<wine>/lib/wine/x86_64-windows/` | `<prefix>/drive_c/windows/system32/` |
| **DLL overrides** | wiki, verbatim: *"Ensure these dlls are **NOT** set overrides `native,builtin`."* | `WINEDLLOVERRIDES="dxgi,d3d11,d3d10core=n,b;"` |

**What we shipped was the inverse of both.** `profiles/bottle-recipe.yaml` v0 copied the DLLs into the prefix's
`system32`/`syswow64` *and* set `d3d11`/`dxgi` to `native,builtin` — the prefix layout with the prefix overrides,
applied to a builtin build. The failure mode is silent: Wine is told to prefer a *native* `d3d11.dll`, the builtin
DXMT one is not native, so Wine falls back to its own Direct3D and the user gets a slow, working game and no
indication that the backend they installed is not the backend they are running.

**Measured on the corrected install (CONFIRMED):** with `Software\Wine\DllOverrides` **empty** in `user.reg` and the
files in the Wine tree, all three DLLs load as `builtin`:

```console
$ grep -A2 'DllOverrides' ~/CS2/prefix/user.reg
[Software\\Wine\\DllOverrides] 1787523577
#time=1dd334d7b99836c
```

The key exists and is **empty** — the two lines above are the whole of it, and there is no `"d3d11"` or `"dxgi"`
value under it. The loader trace in §5 is the proof that this is the copy that wins.

Stale native copies of `d3d11.dll`/`dxgi.dll`/`d3d10core.dll` left in the prefix's `system32` by the old recipe are
**inert as long as no override names them** — the trace still reports `builtin`. They are still worth deleting,
because the moment somebody sets an override "to be safe" they become live.

---

## 5. [SUPERSEDED — see research/steam-black-window-2026-08-24.md §UPDATE: the requirement DOES bind; a static `nm` dump cannot see a runtime `dlsym`/unix-call lookup]

### original text, kept for the record

## 5. The wiki's "CrossOver Wine 24+" requirement does not bind DXMT v0.80 — measured

The wiki's *Grab essential files* section says: *"You need the wine binary that fulfils certain specifications, A
FOSS CrossOver Wine 24+ built from the sources is sufficient… you need to expose all the API declared
[here](https://github.com/3Shain/dxmt/blob/v0.41/include/winemacdrv.h) from Wine's `winemac.drv` module, since by
default these symbols are hidden."*

**That link points at the v0.41 header.** The requirement is documentation written against DXMT **v0.41**; the
release in question is **v0.80**. Whether it still holds is answerable by looking at what v0.80 actually imports:

```console
$ nm -m ~/CS2/dxmt/v0.80/x86_64-unix/winemetal.so | grep undefined | grep '\.so'
                 (undefined) external _NtSetEvent (from @rpath/ntdll.so)
$ nm -m ~/CS2/dxmt/v0.80/x86_64-unix/winemetal.so | grep -c undefined
419
$ nm -m ~/CS2/dxmt/v0.80/x86_64-unix/winemetal.so | grep -i winemac | wc -l
       0
```

**CONFIRMED: zero symbols bound to `winemac.so`.** Of 419 undefined symbols, exactly one comes from a Wine module —
`_NtSetEvent` from `ntdll.so`, which stock Wine exports. Everything else is CoreFoundation, CoreGraphics, ColorSync,
Foundation and Metal. **v0.80 no longer needs the patched `winemac.drv`.**

### The functional proof

Inside the bottle, with no game installed, ask Wine to load `d3d11.dll` and fail to find an entry point. The load
happens before the failure, so the trace tells you which implementation won:

```console
$ export WINEPREFIX="$HOME/CS2/prefix"
$ WINEDEBUG=+loaddll,+dxmt wine rundll32 d3d11.dll,NoSuchEntry
...
	Metal Shading Language 3.1
		GPU Family Metal 3
		GPU Family Apple 8
		GPU Family Mac 2
00d4:trace:loaddll:build_module Loaded L"C:\\windows\\system32\\winemetal.dll" at 00006FFFFE850000: builtin
00d4:trace:loaddll:build_module Loaded L"C:\\windows\\system32\\DXGI.DLL" at 00006FFFFE090000: builtin
00d4:trace:loaddll:build_module Loaded L"C:\\windows\\system32\\d3d11.dll" at 00006FFFFE200000: builtin
info:  Failed to set Metal cache path, fallback to system default
00d4:err:rundll32:wWinMain Unable to find the entry point L"NoSuchEntry" in L"d3d11.dll"
```

Reproduced twice on 2026-08-24. Reading it line by line:

* `winemetal.dll`, `DXGI.DLL` and `d3d11.dll` all load, all tagged **`builtin`** — these are DXMT's copies from the
  Wine tree, not Wine's own Direct3D and not a native DLL in `system32`.
* `info:  Failed to set Metal cache path…` is **DXMT's own log line**, not Wine's. Its presence means DXMT ran its
  initialisation, not merely that a file was mapped.
* MoltenVK reports **Metal Shading Language 3.1 / GPU Family Metal 3** — the Metal side came up.
* The `err:rundll32` line is the expected, deliberate failure: `NoSuchEntry` does not exist. That is the point; the
  DLL had to load first.

**Status: CONFIRMED — DXMT v0.80 loads and initialises Metal under stock Gcenx Wine 11.15 staging on an M2 Pro.**
**Status: UNKNOWN — whether it renders CS2 correctly.** No game is installed. Loading is not rendering; a smoke test
is not a frame. T-010 remains the gate it always was.

---

## 6. A lead for T-013: DXMT could not set its Metal shader cache path

`info:  Failed to set Metal cache path, fallback to system default` fires on every run above. T-013 ("kill
shader-compilation stutter") depends on locating that cache and proving it persists, so this is a lead worth
recording precisely — and worth **narrowing**, because one obvious hypothesis is already dead.

`winemetal.so` imports the private cache-path entry points as **weak** externals:

```console
$ nm -m ~/CS2/dxmt/v0.80/x86_64-unix/winemetal.so | grep -i shadercache
                 (undefined) weak external _MTLGetShaderCachePath (from Metal)
                 (undefined) weak external _MTLSetShaderCachePath (from Metal)
000000000000e2e0 (__TEXT,__text) external __WMTSetMetalShaderCachePath
```

(The third line is DXMT's own exported wrapper, `__WMTSetMetalShaderCachePath` — the caller of the two weak imports.)

A weak import that the host framework does not export resolves to NULL, which would explain a graceful fallback.
**That is not what is happening here** — the symbols exist on this machine, in both architectures:

```console
$ arch -x86_64 /usr/bin/python3 -c "import ctypes,ctypes.util; l=ctypes.CDLL(ctypes.util.find_library('Metal')); \
    print([hasattr(l,s) for s in ('MTLSetShaderCachePath','MTLGetShaderCachePath')])"
[True, True]
```

(Checked under `arch -x86_64` because the Wine process is x86-64 under Rosetta; also present natively on arm64.)

**Status: CONFIRMED** that the fallback fires and **CONFIRMED** that a missing-symbol explanation is wrong.
**Status: UNKNOWN** why it fires — the remaining candidates (a path DXMT cannot create inside the prefix, an
ordering constraint relative to Metal device creation, an environment variable we have not set) are untested.
**This is a lead, not a conclusion**, and it belongs to T-013, not to the install guide.

---

## 7. Licence correction: DXMT v0.80 is **MIT**

From the v0.80 release notes, <https://github.com/3Shain/DXMT/releases/tag/v0.80> (fetched via the GitHub releases
API, 2026-08-24), under the heading **News**, verbatim:

> "We are changing the license of DXMT from MIT to LGPL. **v0.80 will be the last release distributed in MIT
> license.**"

**CONFIRMED: the release this project ships instructions for is MIT-licensed. v0.81 onward will be LGPL.**

This corrects `docs/06` and `docs/08`, which call DXMT LGPL-2.1. It also explains the older observation in
[tooling-licensing-findings.md](tooling-licensing-findings.md) §4 that GitHub reports DXMT's licence as
`NOASSERTION`/"Other" — that entry was right to flag it and this file resolves it.

**Nothing in the project's conclusion changes.** MIT is strictly more permissive than LGPL-2.1: it imposes no
relinking obligation and no copyleft, only attribution. Our position is unchanged and is now stated exactly:
**we redistribute no third-party binaries at all.** The user fetches Wine and DXMT themselves from the URLs in §3;
CS2Kit only places files the user already has. GPL-3.0 for our own code remains compatible either way, and the
MIT→LGPL flip at v0.81 changes nothing for us because we would still not be shipping it.

---

## 8. Cost and effort, measured

| | |
|---|---|
| Money | **EUR 0.** No Homebrew, no admin password, no CrossOver. |
| Download | 193 561 920 + 18 681 669 bytes ≈ **202 MB** |
| Wall time | Download, verify, extract, `wineboot`, smoke test: well under the 1 h that T-004 budgets |
| Admin rights | **None.** Everything lives under `~/CS2`. (GStreamer, §3a, would need an installer — not required here.) |

---

## 9. What this supersedes

Line numbers are as of commit `f0fd474`, before this file's corrections were applied.

| File:line | What it said | Correction |
|---|---|---|
| `docs/03-development-plan.md:91-92` | `brew tap gcenx/wine` / `brew install --cask --no-quarantine gcenx/wine/wine-crossover   # Wine 11.x, LGPL-2.1` | Command fails (§1a); the cask shipped **wine-8.0.1**, not 11.x (§1c). Replaced by the tarball route (§3). |
| `docs/09-install-guide.md:110-111` | the same two `brew` lines | Same. Replaced by `curl` + `shasum -a 256` + `tar` (§3). |
| `docs/09-install-guide.md`, step 3 note | *"`--no-quarantine` is not optional"* | Moot: no cask, no quarantine. A tarball is not quarantined. |
| `docs/03-development-plan.md:14`, `docs/06-legal-and-policy.md:19` | `brew install --cask game-porting-toolkit` | Still exists, but only in the `gcenx/wine` tap, which Homebrew now refuses by default: needs `brew trust gcenx/wine` first (§1d). |
| `docs/02-architecture.md:17` | `Wine 11.x  (Gcenx macOS build, LGPL-2.1)` | Pinned: **Wine 11.15 staging**, Gcenx **tarball** (not cask), 2026-08-08 (§3). |
| `docs/02-architecture.md:19,41`; `docs/08-cost-and-dependencies.md:11` | DXMT is **LGPL-2.1** | **MIT through v0.80**; LGPL from v0.81 (§7). |
| `docs/05-risk-register.md:12` (R-5), `:17` (R-10) | "DXMT is LGPL-2.1"; "we ship only LGPL-2.1/Zlib/Apache components" | MIT through v0.80 (§7); and we ship **no** third-party components at all. |
| `docs/03-development-plan.md`, T-006 step 2 | *"place the DLLs, set the `d3d11`/`dxgi` overrides to `native`"* | **Wrong for the published build.** Files go into the Wine tree and the overrides must stay **off** (§4). |
| `docs/09-install-guide.md`, step 4 | *"installs the DXMT DLLs, sets the `d3d11`/`dxgi` overrides to `native`"* | Same correction. |
| `profiles/bottle-recipe.yaml` v0 | `dll_overrides:` `d3d11`, `dxgi`, `d3d10core`, `winemetal` all `"native,builtin"`, with the DLLs copied into `system32`/`syswow64`, under the comment *"without 'native' first, Wine loads its builtin and DXMT never runs"* — which is **exactly backwards** for the published build | Same correction; the recipe gains `dxmt.build: builtin\|prefix` and `wine.root` so the two layouts can no longer be confused. Applied in commit `1cb46cd`. |
| `docs/reference/toolchain.md:40,43-44,103` | `wine-crossover` cask as the Wine row, its `brew` install commands and its `brew info` version probe, with `UNRECORDED` checksums | Superseded by §3's URL + SHA-256 rows. Rewritten in commit `1cb46cd`. |
| — | *(nothing said it)* | **New:** Homebrew's `wine-stable` / `wine@staging` casks are **disabled 2026-09-01** (§2) → R-15. |

Not corrected here, and still true: Wine is LGPL-2.1; MSync is LGPL-2.1; the whole stack is x86-64 under Rosetta 2
and inherits the macOS-27 horizon.

---

## 10. What is still UNKNOWN after today

| Question | Why it is open |
|---|---|
| Does CS2 render correctly under DXMT v0.80 + Wine 11.15? | Nothing is installed. §5 proves initialisation, not rendering. **T-010 is still the gate.** |
| Why does DXMT fail to set its Metal cache path? | §6 kills the missing-symbol hypothesis and nothing else has been tested. T-013. |
| Does the stack need GStreamer.framework? | Upstream requires it; we ran without it. Nothing has yet asked Wine to decode media. §3a. |
| Do `nvapi64.dll` / `nvngx.dll` matter for CS2? | Not placed, not tested. §3. |
| Will Gcenx keep publishing tarballs? | The `wine-crossover` cask was deleted with no deprecation notice (§1a). A pinned URL + checksum is a mitigation, not a guarantee — see R-16. |
| Does `winemetal.dll` in `system32` have to be the x86_64 one when a 32-bit Steam client is running? | The archive ships an `i386-windows` set; only the 64-bit path was exercised. |
