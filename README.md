# cs2-apple-silicon

Run **Counter-Strike 2** on an **Apple Silicon MacBook**, using **only free software**, and build `CS2Kit` — a small
CLI that makes the setup reproducible, diagnosable and measurable.

**Status:** planning complete, ready to implement. **Cost to us and to every future user: €0.**
**Machine of record:** MacBook Pro **M2 Pro, 32 GB, macOS 26.5.2**, 16-core GPU, Metal 4.

---

## The stack (decided — no alternatives to evaluate)

```
cs2.exe (Windows x64)
   └─ Windows Steam client        ← runs INSIDE the bottle; macOS Steam cannot serve CS2
        └─ Wine 11.x  (Gcenx build, LGPL-2.1)
             ├─ DXMT   (LGPL-2.1)  DirectX 11 → Metal
             └─ MSync  (LGPL-2.1)  synchronisation
                  └─ Rosetta 2 → Metal 4 → Apple M2 Pro
```

Every component is free software, so `CS2Kit` can ship a complete working stack with no licence entanglement.
Apple's proprietary **D3DMetal is deliberately excluded**; if T-012 ever shows DXMT is inadequate on some machine,
the user installs GPTK themselves — we never redistribute it.

## The one-paragraph verdict

CS2 has **no macOS build and never will** (Valve dropped it 2023-10-10; appid 730 is `oslist = "windows,linux"`).
So this is not a port, it is a **Windows-bottle integration problem** — and other people have already shown it works:
a documented M5 Pro run hits **190 avg / 140 1%-low at 1080p**, and an M1 Pro player holds a **15,000 Premier CS
Rating** through Wine. There is no evidence of a legitimate player ever being VAC-banned for using a compatibility
layer. **The value here is not "make it run" — it is making it reproducible, measured, legal and maintainable.**
The one thing we cannot engineer around: **Apple retires general-purpose Rosetta 2 after macOS 27**, and this entire
stack is x86-64.

## Hard rules

| Never | Why |
|---|---|
| Use macOS Steam to install CS2 | It **cannot**. Proven on this machine — a "complete" 66 GB install with no `cs2.exe`. See [target-machine.md](docs/reference/target-machine.md). |
| Modify `cs2.exe` or any Valve DLL | Valve's VAC FAQ names modifying core executables/DLLs as cheating. Enforced by a hash guard (T-021). |
| Use `-vulkan` | On Apple Silicon it lands on a DXVK fork frozen since 2023 and a MoltenVK with no geometry shaders. One confirmation run, then dropped. |
| Redistribute D3DMetal | Apple's licence permits it only non-commercially. We avoid the question entirely by shipping DXMT. |
| Buy Prime before T-020 passes | €13.29 / $14.99 and **non-refundable**. |

## Start here

```bash
bash scripts/preflight.sh          # grades the machine, finds the disk trap
```

Then read [docs/00-executive-summary.md](docs/00-executive-summary.md) and work
[docs/03-development-plan.md](docs/03-development-plan.md) from **T-001**.
The **⚡ Fast path** at the top of that file is seven tasks to a playable game in ~2 days.

## Repo map

```
docs/
  00-executive-summary.md      verdict, success criteria, go/no-go
  01-gap-analysis.md           9 corrections to the prior analysis this supersedes
  02-architecture.md           the stack, and why each rejected option was rejected
  03-development-plan.md       ← THE PLAN. Fast path + 33 tasks + acceptance criteria
  04-test-matrix.md            the regression suite a CS2 update must survive
  05-risk-register.md          scored risks + the Rosetta-27 exit plan
  06-legal-and-policy.md       licences, VAC policy, absolute rules
  07-benchmark-protocol.md     how to produce an FPS number that means something
  08-cost-and-dependencies.md  every component's licence; why users pay nothing
  reference/target-machine.md  measured state of this Mac
research/                      URL-cited primary-source findings + the prior analysis
scripts/preflight.sh           machine grader (run this first)
```

Every claim in `docs/` traces to a URL-cited entry in `research/`, tagged **CONFIRMED** (vendor/primary),
**LIKELY** (community), or **UNKNOWN** (not verified).
