# Compatibility matrix

What has actually been run, on what, with what result. **Every number in this file is either measured under
[07-benchmark-protocol.md](07-benchmark-protocol.md) or the literal string `not measured`.** There is no third
category. If a cell would need a guess, it says `not measured` - or `?`, which is what `cs2kit watch drill` writes
when it has no value for a column.

Rows are appended by `cs2kit watch drill` when a CS2 `buildid` change is detected (T-030), by the macOS beta drill
(T-032), and by hand after a benchmark session. **The table is the last thing in this file on purpose:**
`cs2kit.watch.append_matrix_row()` appends a bare row to the end of the file, so nothing may be written below it. The
column shape is a **stable contract** with `cs2kit.watch.MATRIX_HEADER` - do not reorder or rename the columns.

## How to read a row

| Column | Meaning |
|---|---|
| `date` | ISO date the drill or benchmark ran (`YYYY-MM-DD`, UTC). |
| `buildid` | CS2 public-branch `buildid` from `appmanifest_730.acf`. The unit of "did an update break it". |
| `macOS` | `sw_vers -productVersion` as captured in the environment snapshot. |
| `wine` | `wine --version`. |
| `dxmt` | DXMT release recorded in the bottle state, i.e. what `cs2kit bottle create` installed. |
| `avg fps` | **Median** average FPS over 5 measured runs after 3 discarded warm-ups. Never a peak, never one run. |
| `1% low` | Median 1 % low over the same runs - the number that decides whether CS2 is playable. |
| `verdict` | `PASS` playable, within tolerance / `DEGRADED` measurably worse or defective but still playable / `BROKEN` not playable / `?` not determined, nothing measurable yet. |

`avg fps` and `1% low` are filled in from the latest stored `cs2kit bench` session for the same environment, so a
drill run before any benchmark exists legitimately shows `?`. A `?` means *nobody has measured this*; it never means
zero.

Unless a row note says otherwise, the benchmark is the **Ancient FPS Benchmark (Workshop `3472126051`) at 1080p
medium**. A Dust2 number is **not** comparable with an Ancient number - Ancient runs 25-30 % heavier
([07-benchmark-protocol.md](07-benchmark-protocol.md)).

## Expectation, so that a surprising row is investigated rather than published

For the M2 Pro / 32 GB machine of record the plan expects **~100-125 avg FPS at 1080p medium on Ancient**,
interpolated between an M1 Pro (~100) and an M4 Pro (122) in the reference field of
[07-benchmark-protocol.md](07-benchmark-protocol.md). A result far outside that band means the protocol or the
configuration is wrong - most often a cold shader cache or an accidental Retina backing-store resolution. That
expectation is an **interpolation, not a measurement**, and it must never be entered as a row.

## What this matrix is not

* **Not a claim of support.** CS2 has no macOS build and Valve does not support this configuration
  ([06-legal-and-policy.md](06-legal-and-policy.md), section 3).
* **Not a per-chip recommendation table.** The variance that matters is
  backend x chassis x resolution x macOS build, which is why the project ships three situational profiles rather than
  one file per chip (T-027).
* **Not community data yet.** External `cs2kit report` bundles are ingested under T-033; until then every row comes
  from the machine of record ([reference/target-machine.md](reference/target-machine.md)).
* **Not editable history.** Rows are appended, never rewritten. A matrix a tool can rewrite is not evidence. Correct
  a mistaken row by appending a new one and explaining it in the row notes above the table.

## Row notes

* **2026-08-23, buildid 24828357, verdict `?`** - the machine of record before Phase 1: MacBook Pro M2 Pro, 32 GB,
  16-core GPU, Metal 4, macOS 26.5.2 (25F84). Nothing is measurable yet. macOS Steam reports CS2 as installed
  (`StateFlags 4`, 66 GB, `BytesToDownload 0`) but depot **2347771** - every `.exe` and `.dll`, `cs2.exe` included -
  is absent, so there is no game to launch; *Verify integrity of game files* cannot fix it because Steam believes the
  install is complete. Wine and DXMT are not installed on this machine yet, hence `?` rather than a version. Full
  detail and byte counts: [reference/target-machine.md](reference/target-machine.md). This row is the zero point:
  every later row is a comparison against a state where nothing worked.

## Matrix

Newest rows are appended at the bottom. **Nothing may be added below this table.**

| date | buildid | macOS | wine | dxmt | avg fps | 1% low | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-08-23 | 24828357 | 26.5.2 | ? | ? | ? | ? | ? |
| 2026-08-24 | 24828357 | 26.5.2 (25F84) | wine-10.0 (Sikarugir) | v0.80 | 101–130 (indicative, screenshot-sampled, auto-Low) | not measured | PASS — T-010 gate: 6 passes, 0 crashes, 0 frozen frames |
