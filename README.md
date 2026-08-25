
# CS2 on Apple Silicon

[![ci](https://github.com/piwas-21/cs2-apple-silicon/actions/workflows/ci.yml/badge.svg)](https://github.com/piwas-21/cs2-apple-silicon/actions/workflows/ci.yml)
[![licence: GPL-3.0](https://img.shields.io/badge/licence-GPL--3.0-blue.svg)](LICENSE)

**Play Counter-Strike 2 on an Apple Silicon Mac.** Free software only. One command to install.

CS2 has no macOS build, so this runs the Windows version in a Wine bottle with DXMT translating
Direct3D 11 to Metal — and `cs2kit` sets the whole thing up for you.

## Install

```bash
git clone https://github.com/piwas-21/cs2-apple-silicon.git
cd cs2-apple-silicon
./bin/cs2kit setup
```

That fetches the Wine build that works, fetches DXMT, builds the bottle, installs the Windows Steam
client and writes a **Counter-Strike 2 app in your Applications folder**. Takes about 10 minutes.

Then: **open the app, log in to Steam** (scan the QR code with the Steam mobile app), and install CS2 —
if you already have it, `cs2kit` points Steam at your existing copy instead of downloading 70 GB again.

## Play

Double-click **CS2Kit** in Applications. No terminal.
(That app just runs `./bin/cs2kit play`, which resolves everything at launch and
tells you in one sentence if something is missing.)

## When something breaks

```bash
./bin/cs2kit doctor
```

Every check ends in one line telling you what to run. If that is not enough,
[docs/troubleshooting.md](docs/troubleshooting.md) covers 23 known failures.

## What to expect

Measured on a MacBook Pro M2 Pro (32 GB, macOS 26.5.2):

* **128 fps** on the Ancient benchmark map at low settings; worst frame 13 ms
* 48 minutes of bot matches across three maps: **no crashes**
* Audio works. Input works.

**Not yet validated: competitive play.** Nobody has run the ten VAC-protected matches that would make
that claim safe, so treat this as **practice and offline only** for now. There is no evidence of anyone
being banned for a compatibility layer, and Valve has published no policy either way —
[the details](docs/legal-and-vac.md).

Also worth knowing: this whole stack is x86-64, and **Rosetta 2 goes away after macOS 27**.

## Requirements

Apple Silicon Mac · macOS 13+ · Rosetta 2 · ~90 GB free · a Steam account that owns nothing special
(CS2 is free-to-play)

## More

| | |
|---|---|
| Full install walkthrough | [docs/install.md](docs/install.md) |
| Every command | [docs/cli-reference.md](docs/cli-reference.md) |
| Why this Wine build and not another | [docs/architecture.md](docs/architecture.md) |
| What was actually measured | [docs/project/measured-results.md](docs/project/measured-results.md) |

Our code is GPL-3.0. We ship no third-party binaries: Wine and MSync are LGPL-2.1, DXMT is MIT, and
`cs2kit setup` downloads them from upstream with checksums. Not affiliated with or supported by Valve.
