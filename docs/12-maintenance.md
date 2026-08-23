# 12 - Maintenance (Phase 5: T-030, T-032, T-033, T-034)

Phase 5 has no end date. It exists because everything under CS2Kit moves on someone else's schedule: Valve patches
CS2 continuously, Apple ships a macOS major every autumn, and the graphics backend this project depends on is a
fast-moving third-party library. The job is to notice, run the same drill every time, and write down what happened -
including "nothing changed", which is a finding.

Cadence at a glance:

| Trigger | Task | Cadence | Owner action | Acceptance |
|---|---|---|---|---|
| CS2 `buildid` changes | T-030 | on change, within **24 h** | run the update drill, append a matrix row | drill runs within 24 h of the change |
| macOS beta appears | T-032 | per release | test on a separate APFS volume | one matrix row per beta, published before public release |
| A user sends a bundle | T-033 | continuous | ingest, aggregate, publish | **>= 10 external bundles** |
| Nothing at all | T-034 | **quarterly** | review DXMT, Wine, MSync, MoltenVK | one dated review per quarter |
| Nothing at all | T-031 | **quarterly** | the Rosetta clock - see [rosetta-watch.md](rosetta-watch.md) | one dated entry per quarter |

---

## T-030 - CS2 update watch and regression drill

**Why:** whether a CS2 patch has ever broken a working Wine bottle is recorded as **UNKNOWN** - no source was found
either way ([../research/performance-alternatives-findings.md](../research/performance-alternatives-findings.md),
item 15). This drill is how that becomes data instead of an anecdote.

### Detection

```bash
cs2kit watch check                    # compares the recorded buildid against Valve's public branch
cs2kit watch check --exit-on-change   # exit 5 on a change: what makes it usable from cron
```

One optional, unauthenticated GET with a hard timeout, no retries, no telemetry. Offline, DNS failure or a changed
mirror shape all degrade to `status: "unknown"` and a warning - never a false "unchanged" (which would suppress the
drill) and never a false "changed" (which would cry wolf nightly).

An unattended checker, e.g. a `launchd` job or cron entry that runs it daily:

```
0 9 * * *  /path/to/cs2-apple-silicon/bin/cs2kit watch check --exit-on-change --json >> ~/.cs2kit/watch.log 2>&1
```

**SLA: a `buildid` change triggers the drill within 24 hours.** That is the T-030 acceptance, and a daily check is
the minimum cadence that can meet it.

### The drill

```bash
cs2kit watch drill --verdict <PASS|DEGRADED|BROKEN>
```

It **prints** the steps and appends the matrix row; it does not execute them, because `doctor` and `bench` have
their own exit codes and the smoke test needs a human at the mouse. The steps, as the tool states them:

1. `cs2kit doctor` - environment first; most "the update broke it" reports are not the update.
2. `cs2kit bottle repair` - only if doctor FAILs a bottle check; re-apply the recipe, never hand-edit.
3. Launch CS2 to the main menu - a black screen here is the T-009 fullscreen fix, not a regression.
4. `cs2kit bench run` - 3 warm-up runs, 5 measured runs, Ancient (workshop `3472126051`).
5. `cs2kit bench compare` - exits `5` if a headline metric moved more than 5 % (T-026).
6. One-match smoke test - a bot match on Dust2: audio, mouse, alt-tab, no crash (test matrix rows A/B/E,
   [04-test-matrix.md](04-test-matrix.md)).
7. `cs2kit watch record` - store the new buildid so the next check compares against it.
8. Append the result to [compatibility-matrix.md](compatibility-matrix.md), verdict `PASS` / `DEGRADED` / `BROKEN`.

Two things a CS2 update is **expected** to do, and which must not be reported as regressions:

* **Invalidate the shader cache.** Re-warm before benchmarking, or step 5 measures shader compilation (T-013).
* **Change the guarded binaries.** `cs2kit verify check` will report a mismatch. If - and only if - the `buildid`
  changed, run Steam's *Verify integrity of game files* and then `cs2kit verify baseline` again. If the `buildid`
  did **not** change, do not re-baseline: find out what wrote to `game/bin/win64/` ([10-troubleshooting.md](10-troubleshooting.md), entry 13).

When the drill finds a real regression, run the **full** test matrix, not just the smoke subset
([04-test-matrix.md](04-test-matrix.md), section I).

## T-032 - macOS beta testing

**Why:** the machine of record plays CS2 on a stack Apple can break with an OS update, and the project's own advice
is to hold macOS still on a play machine. That advice is only credible if someone tests the next release early.

**Rules:**

* Install each macOS beta to a **separate APFS volume**. Never upgrade the play machine's boot volume in place -
  there is no downgrade path, and the last known-good configuration is the thing being protected.
* Boot the beta volume, then run: `cs2kit doctor`, `cs2kit bench run` (full protocol), and the one-match smoke test.
* **Publish before the public release**, so that a reader deciding whether to upgrade has the answer beforehand.
* Watch `rosetta` and `rosetta-horizon` in `doctor` first. If Rosetta itself is gone or restricted, this stops being
  a performance question and becomes [rosetta-watch.md](rosetta-watch.md)'s trigger.

**Acceptance: one matrix row per beta.** A row must carry - this is what
`cs2kit watch drill` writes, and the columns are a contract with `cs2kit.watch.MATRIX_HEADER`:

```
| date | buildid | macOS | wine | dxmt | avg fps | 1% low | verdict |
```

* `macOS` must be the **beta** version string, and the row note must say it is a beta and name the build.
* `avg fps` / `1% low` must come from a full `cs2kit bench` session on the same `env_id`, or read `?`. A beta row
  with an invented number is worse than no row.
* `verdict` is `PASS` (playable, within +/-5 % of the previous macOS), `DEGRADED` (measurably worse or defective but
  playable) or `BROKEN` (not playable).

Add the row and its note to [compatibility-matrix.md](compatibility-matrix.md); rows are appended, never rewritten.

## T-033 - Community data intake

**Why this is the project's most durable contribution:** the CS2-on-Mac ecosystem has published essentially no 1 %-low
data and **no ms-level input-latency measurement at all**. Aggregating honest bundles is something nobody else is
doing ([07-benchmark-protocol.md](07-benchmark-protocol.md)).

### What a contributor does

```bash
cs2kit doctor                 # fix the FAILs first: a broken environment is not a datapoint
cs2kit bench run --frametimes run1.csv run2.csv run3.csv run4.csv run5.csv
cs2kit report                 # prints exactly what will be shared, then asks before writing
```

`cs2kit report` writes `report.json`, `report.md` and a `.tar.gz` under `~/.cs2kit/reports/`. It **never uploads
anything** - sharing is the contributor's deliberate act.

### What is stripped before anything is written

The bundle carries tool versions, the environment snapshot, bottle state, recipe and profile names, every doctor
result, the latest benchmark session and the integrity summary. It is scrubbed of:

* the local username, in `$USER` and in every `/Users/<name>/` path, and any absolute path under `$HOME`
* SteamID64, Steam account / persona / login names, email addresses
* IPv4 and IPv6 addresses (`127.0.0.1` is kept), MAC addresses
* hardware serial numbers and UUIDs, computer name, local hostname and DNS hostname

Redaction is verified by re-scanning the redacted bundle: if the scanner still finds an identifier, `cs2kit report`
**refuses to write** and reports the *kinds* found, never the values. That is T-028's acceptance - zero personal
identifiers - executed rather than asserted. `--secret TEXT` scrubs an extra literal string; use it for anything
site-specific.

### Where to send it

Open an issue on <https://github.com/mahmutkaya/cs2-apple-silicon> and attach the `.tar.gz`, or paste `report.md`.
Say which step of [09-install-guide.md](09-install-guide.md) you reached and what you were doing. **Read the preview
`cs2kit report` printed before you attach anything** - it is your data, and the redaction is a tool, not a promise
about your particular machine.

### Intake rules

| Rule | Why |
|---|---|
| A bundle without a full `cs2kit bench` session is a **doctor** datapoint, not a performance one | a number without the protocol is a rumour |
| Never publish a bundle that arrives with an identifier in it - re-scan and drop it | a privacy defect is the embarrassing kind (risk R-14) |
| Aggregate by `env_id` and `buildid`, never across maps | Ancient runs 25-30 % heavier than Dust2 |
| Publish the aggregate, including the unflattering rows | the point is honest data, not a leaderboard |

**Acceptance: >= 10 external bundles ingested.**

| Field | Value |
|---|---|
| External bundles received | 0 |
| Bundles rejected (identifier found / no protocol) | 0 |
| Aggregate published | not yet |

## T-034 - Quarterly upstream tracking

Four dependencies, one review per quarter, one dated row each. **DXMT is the critical one:** it is the graphics path,
it is LGPL-2.1, and it moves fast ([02-architecture.md](02-architecture.md)).

| Project | Why it matters | What to check | Trigger to act |
|---|---|---|---|
| **DXMT** | our D3D11-to-Metal path; the project's critical dependency | new release, changelog, open CS2-relevant issues | a release lands -> update the bottle, re-run the T-030 drill, record the version in [reference/toolchain.md](reference/toolchain.md) |
| **Wine** (Gcenx macOS builds) | the runtime host | version, `--enable-archs` line, ARM64EC and 4K-page notes in `ANNOUNCE.md` | any `--enable-archs` that is not `i386,x86_64`, or 16K-page support beyond "simple applications" -> [rosetta-watch.md](rosetta-watch.md) |
| **MSync** | synchronisation; ESync is being removed from CrossOver | still maintained, still the 2026 consensus | if MSync stalls, re-run the MSync-vs-ESync A/B from T-012 |
| **MoltenVK** | would make the Vulkan renderer viable | **geometry shaders** and **`VK_EXT_transform_feedback`** | **if either lands, revisit T-012** - the `-vulkan` verdict was measured against their absence and would have to be re-measured |

The Vulkan trigger is the one worth restating: the project rejected `-vulkan` because on Apple Silicon it routes
through a frozen DXVK-macOS fork and a MoltenVK with **no geometry shaders and no `VK_EXT_transform_feedback`**
(CONFIRMED from MoltenVK source, [../research/tooling-licensing-findings.md](../research/tooling-licensing-findings.md)
section 5). The Vulkan *version* objection is already dead - MoltenVK shipped Vulkan 1.4 in 2025-08 - so the feature
gaps are the whole argument, and if they close the verdict must be re-measured rather than re-asserted.

### Review log

**Next review due: 2026-11-23.** Run it on the same day as the [rosetta-watch.md](rosetta-watch.md) review; they
share most of their sources.

| date | DXMT | Wine | MSync | MoltenVK | Action taken |
|---|---|---|---|---|---|
| 2026-08-23 | v0.80 line, actively developed (LGPL-2.1); nothing installed on the machine of record yet | Gcenx **11.15** (2026-08-08), built `--enable-archs=i386,x86_64` - x86-64 only, Rosetta required | 2026 community consensus; ESync being removed from CrossOver | 1.4.2 (2026-07-24): Vulkan 1.4 available, **geometry shaders and `VK_EXT_transform_feedback` still absent** | none - baseline entry; `-vulkan` stays rejected, T-012 not revisited |

<!-- Append the next quarterly review immediately below this comment, newest last. -->

## What a maintainer must never do

* Never respond to a regression by modifying a game file. The drill's answer to an integrity mismatch is Steam's
  *Verify integrity*, never an edit ([06-legal-and-policy.md](06-legal-and-policy.md), absolute rule 1).
* Never publish a matrix row or an aggregate that contains a number nobody measured. `?` and `not measured` are
  answers.
* Never rewrite matrix history to make a stack look better. Append a correcting row and explain it.
* Never let a quarter pass without an entry. "Nothing changed" is a finding; silence is not.
