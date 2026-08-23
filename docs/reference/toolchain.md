# Reference - toolchain of record (T-004)

**Status: TEMPLATE. Nothing below the "to be filled in on first run" markers has been executed on hardware yet.**
Every machine-specific value in this file reads **UNRECORDED** until a human runs the procedure on the machine of
record ([target-machine.md](target-machine.md)) and pastes the real output in. **Never write a checksum, a version
string or a URL into this file that you did not read off your own terminal.** A fabricated SHA-256 is worse than a
missing one: it makes an unreproducible stack look reproducible.

Scope: the four components of the free stack and nothing else -
Rosetta 2, Wine (Gcenx build), DXMT, MSync. See [../02-architecture.md](../02-architecture.md) for why each
alternative was rejected, and [../08-cost-and-dependencies.md](../08-cost-and-dependencies.md) for the licence of each.

---

## 0. Preconditions

| Precondition | How to check | Required |
|---|---|---|
| Apple Silicon | `uname -m` | `arm64` |
| macOS | `sw_vers -productVersion` | 14 or later; **26.x is the machine of record** |
| Free disk | `bash scripts/preflight.sh` | >= 85 GiB for the T-008 reuse route |
| Rosetta 2 | `pgrep -q oahd && echo active` | active |

`bash scripts/preflight.sh` grades all four at once and exits non-zero on a blocker.

---

## 1. Rosetta 2

Wine's macOS build is compiled `--build=x86_64-apple-darwin --enable-archs=i386,x86_64`, so **the whole Wine process
tree is x86-64 and runs under Rosetta 2** (CONFIRMED, `research/tooling-licensing-findings.md` section 4, Gcenx row).
There is no arm64 Wine path for this stack today; see [../rosetta-watch.md](../rosetta-watch.md) for the shelf life
this imposes.

```bash
softwareupdate --install-rosetta --agree-to-license
pgrep -q oahd && echo "rosetta active"
```

## 2. Wine (Gcenx `wine-crossover`, LGPL-2.1)

```bash
brew tap gcenx/wine
brew install --cask --no-quarantine gcenx/wine/wine-crossover
wine --version
```

Two things that trip people up:

* **Wine 11 has no separate `wine64` binary.** There is one `wine` loader. Any guide that tells you to run `wine64`
  is pre-11 (`docs/03-development-plan.md` T-004 step 2).
* `--no-quarantine` matters: without it Gatekeeper quarantines the cask's binaries and Wine fails in ways that look
  like Wine bugs.

**Acceptance (T-004):** `wine --version` prints >= 11.0.

## 3. DXMT (LGPL-2.1) - D3D10/11 to Metal

DXMT is **our critical dependency**: it is the graphics path, and it is the one component whose upstream health the
project tracks quarterly (T-034). Releases: <https://github.com/3Shain/DXMT/releases>.

```bash
# in a scratch directory
curl -LO "<the release asset URL you actually used>"
shasum -a 256 <asset>
```

Do **not** install D3DMetal here. It is deliberately excluded from what this project ships
([../06-legal-and-policy.md](../06-legal-and-policy.md) section 1, Distribution model, Tier 1). If T-012 later shows
DXMT is inadequate on your machine, you install Apple's GPTK yourself and record it as a local fallback.

## 4. MSync (LGPL-2.1)

MSync is the synchronisation primitive the 2026 community consensus uses; ESync is being removed from CrossOver
(`research/performance-alternatives-findings.md` item 14, flagged as a CONTRADICTION with macresearch.org's older
advice). It is enabled per-bottle with `WINEMSYNC=1`, not installed separately, and is applied by
`cs2kit bottle create` from the recipe (T-025).

## 5. What must NOT be installed

| Not installed | Why | Source |
|---|---|---|
| CrossOver | EUR 74 per user; the parts that matter (DXMT, MSync) are LGPL-2.1 without it | `../02-architecture.md` |
| Whisky | archived 2025-05-11 by its author | `research/tooling-licensing-findings.md` section 3 |
| Heroic / Porting Kit / Sikarugir | launchers around the same Wine; extra moving parts, no benefit here | `../03-development-plan.md` T-004 step 4 |
| Apple GPTK / D3DMetal | never redistributed by this project; user-installed fallback only | `../06-legal-and-policy.md` section 1 |

---

## To be filled in on first run

Run the procedure above on the target machine and replace every **UNRECORDED**. Commit the result together with
`docs/reference/env-snapshot-0.json` (T-005) so that a benchmark can always be traced to the exact stack that produced it.

### Component versions

| Component | Command | Value | Date recorded |
|---|---|---|---|
| macOS | `sw_vers -productVersion` (+ `-buildVersion`) | UNRECORDED | UNRECORDED |
| Rosetta 2 | `pgrep -q oahd` | UNRECORDED | UNRECORDED |
| Homebrew | `brew --version` | UNRECORDED | UNRECORDED |
| Wine | `wine --version` | UNRECORDED | UNRECORDED |
| Wine cask | `brew info --cask gcenx/wine/wine-crossover` (version line) | UNRECORDED | UNRECORDED |
| DXMT | release tag | UNRECORDED | UNRECORDED |
| MSync | `WINEMSYNC=1` accepted by this Wine build (yes/no) | UNRECORDED | UNRECORDED |
| CS2 `buildid` | `cs2kit doctor --json` -> `env.stable.cs2_buildid` | UNRECORDED | UNRECORDED |

### Download URLs and checksums

Every artefact that lands on disk gets a row. `shasum -a 256 <file>`.

| Artefact | URL | SHA-256 | Size (bytes) | Date |
|---|---|---|---|---|
| Wine cask (Homebrew-managed) | UNRECORDED | UNRECORDED | UNRECORDED | UNRECORDED |
| DXMT release archive | UNRECORDED | UNRECORDED | UNRECORDED | UNRECORDED |
| Windows `SteamSetup.exe` | UNRECORDED | UNRECORDED | UNRECORDED | UNRECORDED |

### Deviations from this procedure

Anything you had to do that is not written above belongs here, verbatim, including the error that forced it. This is
the section that makes the next machine cheap.

| # | Step | What actually happened | What fixed it |
|---|---|---|---|
| 1 | UNRECORDED | UNRECORDED | UNRECORDED |

### Verdict

* Acceptance (T-004: `wine --version` >= 11.0 **and** a DXMT archive on disk with a recorded checksum): **UNRECORDED**
* Recorded by: UNRECORDED - Date: UNRECORDED
