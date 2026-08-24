# Rosetta 2 watch (T-031)

**The highest-severity risk in this project, and the only one with a date.** Every component below `macOS` in the
stack is x86-64: Wine's macOS build is compiled `--build=x86_64-apple-darwin --enable-archs=i386,x86_64`, so the
entire Wine process tree - and `cs2.exe` inside it - runs under Rosetta 2 (CONFIRMED,
`research/tooling-licensing-findings.md` sections 4 and 7). When general-purpose Rosetta goes, this stack goes with
it, and **no amount of work inside this repository changes that date.**

This file is the quarterly log required by T-031 ([03-development-plan.md](03-development-plan.md)). One dated entry
per quarter, whether or not anything changed. "Nothing changed" is a finding and must be written down.

---

## 1. What Apple actually said

From Apple's developer documentation, *"About the Rosetta translation environment"*
(<https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment>), fetched via the
docs JSON API on 2026-08-23 - **CONFIRMED, Apple primary**, quoted in full in
`research/tooling-licensing-findings.md` section 6:

> **"Rosetta was designed to make the transition to Apple silicon easier, and will be available through macOS 27 - as
> a general-purpose tool for Intel apps to help developers complete the migration of their apps. Beyond this
> timeframe, we will keep a subset of Rosetta functionality aimed at supporting older unmaintained gaming titles,
> that rely on Intel-based frameworks."**

> **"macOS 27 directly integrates support for Intel binary translation, without needing to install Rosetta. This
> enables support for Intel Linux binaries running in ARM virtual machines (VMs) as well as Intel Linux
> containers."**

Also confirmed on the same page: Rosetta translates AVX and AVX2 but **not AVX-512**; it does not translate kernel
extensions or x86-64-virtualising VM apps; and **x86-64 and arm64 code cannot be mixed in one process** - translation
applies to the whole process and every module it loads.

### What that means for CS2Kit

| Question | Answer | Tag |
|---|---|---|
| Is macOS 26 safe? | Yes. | CONFIRMED |
| Is macOS 27 safe? | Yes - "available through macOS 27". | CONFIRMED |
| Is macOS 28 (expected autumn 2027) safe? | **No, not for a general-purpose x86-64 translation host.** | CONFIRMED (the general-purpose grant ends) |
| Does the "older unmaintained gaming titles" carve-out cover this stack? | **UNKNOWN, and probably not.** Wine is an x86-64 *translation host*, not a title; and CS2 is **actively maintained** - it is patched continuously (public buildid 24828357, updated 2026-08-19). Both halves of the carve-out's wording point away from us. | UNKNOWN |
| Can we engineer around it? | No. It is Apple's decision, outside the project. | CONFIRMED |

One mitigating datapoint, **LIKELY** not confirmed: the Whisky author observes that *"even Rosetta would likely be
more restricted as many of the extensions added in recent months were only added due to pressure from Mac gamers"* -
i.e. Apple has been actively adding gaming-motivated Rosetta features
(<https://docs.getwhisky.app/maintenance-notice>). That is a reason to keep watching, not a reason to plan on it.

## 2. The escape route, and why it is blocked today

**ARM64EC Wine + FEX** is the only credible post-Rosetta architecture: Wine itself runs as native ARM64 code and only
the application's x86-64 code is emulated.

* Wine 10.0 ANNOUNCE.md, **CONFIRMED**: *"The ARM64EC architecture is fully supported, with feature parity with the
  ARM64 support."* and *"The 64-bit x86 emulation interface is implemented ... No emulation library is provided with
  Wine at this point, but an external library that exports the emulation interface can be used ... The FEX emulator
  implements this interface when built as ARM64EC."*
* **The blocker is the page size.** Wine 10.0 ANNOUNCE.md, **CONFIRMED**: *"ARM64 support requires the system page
  size to be 4K, since that is what the Windows ABI specifies. Running on kernels with 16K or 64K pages is not
  supported at this point."* **Apple Silicon macOS uses 16K pages.**
* Wine 11.0 took the first step, **CONFIRMED**: *"On ARM64, there is support for simulating a 4K page size on top of
  larger host pages (typically 16K or 64K). This works for simple applications, but because it is not possible to
  completely hide the differences, more demanding applications may not work correctly. Using a 4K-page kernel is
  strongly recommended."*

A Source 2 competitive FPS is not a "simple application". **Status for CS2 specifically: UNKNOWN / not
demonstrated.** Full sourcing: `research/tooling-licensing-findings.md` section 6.

A second, unresearched hedge: macOS 27 gains **built-in Intel binary translation for ARM VMs and Intel Linux
containers**. An Intel-Linux container running Proton is an entirely different architecture from Wine-on-macOS and
would need its own feasibility study. **UNKNOWN** - not investigated.

## 3. Review checklist (run this every quarter)

Copy the block, fill it in, append a dated entry to section 5. Ten minutes if nothing has changed.

1. **Apple wording** - re-fetch the Rosetta page; has the "through macOS 27" sentence or the carve-out wording
   changed? Paste the current text verbatim, do not paraphrase.
2. **macOS releases** - what is the current shipping major, and what is in beta? Does the beta still have working
   Rosetta for a Wine bottle (T-032 runs `cs2kit doctor` + `cs2kit bench` on a separate APFS volume)?
3. **Wine ARM64EC** - latest Wine ANNOUNCE.md: has the 4K-page requirement been relaxed, or has 16K-page simulation
   moved beyond "simple applications"?
4. **FEX** - is there a shipping ARM64EC FEX build usable on macOS?
5. **Sikarugir Engines** (the engine of record) and **Gcenx builds** - is there any `--enable-archs` line that
   is not `i386,x86_64`? The Sikarugir engine has **not** been checked yet: UNKNOWN.
6. **DXMT** (T-034) - does it build for an ARM64EC Wine at all?
7. **Community** - has anyone run *any* Windows game on macOS without Rosetta?
8. **Decision** - CONTINUE / PREPARE-EXIT / EXIT. If PREPARE-EXIT, publish the notice in section 4 and set a date.
9. **Set the next review date** and write it at the top of section 5.

## 4. Pre-written decommission notice (publish unchanged when the trigger fires)

Trigger: the first macOS release in which a Wine bottle no longer runs on this project's stack, **or** Apple stating
that general-purpose Rosetta is removed - whichever comes first. It is written in advance so that the announcement is
a five-minute act rather than a fortnight of hesitation.

> ### CS2Kit is end-of-life on macOS <VERSION>
>
> Apple's general-purpose Rosetta 2 translation is no longer available on macOS <VERSION>. CS2Kit configures a
> **Windows x86-64** Wine bottle; the entire stack - Wine, the Windows Steam client and `cs2.exe` - is x86-64 code
> and cannot execute without it. This is not a bug we can fix: there is no arm64 build of this stack, and Wine's
> ARM64EC path requires a 4 KB system page size that Apple Silicon does not provide.
>
> **If you have not upgraded macOS: do not upgrade** if CS2 matters to you. The last known-good configuration is
> recorded in [compatibility-matrix.md](compatibility-matrix.md). Disable automatic macOS updates.
>
> **If you have upgraded:** CS2Kit cannot help you. The honest options, in order of how much we can vouch for them:
> 1. **GeForce NOW.** CS2 is served on GFN through Valve's own arrangement, from a cloud Windows VM, on an
>    unmodified client. It is the recommendation this project has carried as its fallback from day one
>    ([02-architecture.md](02-architecture.md)).
> 2. **A separate Windows machine**, or Steam Remote Play / Sunshine+Moonlight from one.
> 3. **A Windows-on-ARM VM** - adds virtualisation *plus* Windows-on-ARM's own x86 translation, and anti-cheat
>    behaviour inside a VM is an unresolved UNKNOWN. We do not recommend it for VAC-protected play.
>
> The repository stays up, read-only, as a record of what worked and how it was measured. Nothing in it was ever a
> patch to Counter-Strike 2, so nothing in it becomes unsafe - it simply stops having anything to configure.

**Migration recommendation, in one sentence:** when Rosetta goes, move competitive play to **GeForce NOW** and keep
the local bottle only if you are prepared to freeze macOS at the last working release - the local stack has no
successor we can build.

## 5. Quarterly log

**Next review due: 2026-11-23.**

### 2026-08-23 - entry 1 (baseline)

| Item | Finding | Tag |
|---|---|---|
| Apple wording | Unchanged from the text quoted in section 1; re-read on 2026-08-23. General-purpose Rosetta **through macOS 27**; afterwards only *"a subset ... aimed at supporting older unmaintained gaming titles"*. | CONFIRMED |
| Current macOS on the machine of record | **26.5.2** (build 25F84) - see [reference/target-machine.md](reference/target-machine.md) | CONFIRMED |
| Expected cliff | **macOS 28, expected autumn 2027.** macOS 27 is the last release with the general-purpose grant. | CONFIRMED (grant), assessment (date) |
| Does the carve-out cover us? | No evidence that it does. CS2 is actively maintained (buildid 24828357, updated 2026-08-19), and Wine is a translation host rather than a "title". | UNKNOWN, leaning no |
| Wine ARM64EC | ARM64EC fully supported since Wine 10.0; **blocked on macOS by the 16K page size**. Wine 11.0 simulates 4K pages for "simple applications" only. | CONFIRMED |
| FEX on macOS | No shipping ARM64EC FEX-on-macOS path found. | UNKNOWN |
| Gcenx Wine builds | `--enable-archs=i386,x86_64` as of Wine 11.15 (2026-08-08) - x86-64 only, Rosetta required. | CONFIRMED |
| Sikarugir Wine 10.0 (engine of record) | build flags not yet inspected; it is an x86-64 Wine under Rosetta like the others, so R-1 applies unchanged. | UNKNOWN |
| macOS 27 Intel-Linux containers | New hedge worth a feasibility study; entirely unresearched. | UNKNOWN |
| **Decision** | **CONTINUE.** Two macOS releases of runway. Do not plan features past macOS 27; keep the notice in section 4 current. | - |

Actions carried forward:
* Re-fetch the Apple page verbatim each quarter (it is a JS-only HTML page; use the docs JSON API).
* When the macOS 27 beta appears, run T-032 on a separate APFS volume and record the row in
  [compatibility-matrix.md](compatibility-matrix.md).
* Keep `docs/05-risk-register.md` R-1 in sync with the decision line above.

<!-- Append the next entry immediately below this comment, newest last, using the table shape above. -->
