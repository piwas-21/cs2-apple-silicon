# 05 — Risk register

Severity × likelihood, scored against evidence rather than intuition. Compare with the prior analysis's table —
**VAC drops from Critical/Unknown to Medium/Low, and Rosetta rises to the top slot with a date attached.**

| # | Risk | Sev | Lik | Evidence | Mitigation | Task |
|---|---|---|---|---|---|---|
| **R-1** | **Rosetta 2 retired after macOS 27; the whole x86-64 stack dies** | **Critical** | **High (dated)** | Apple: general-purpose Rosetta "available through macOS 27", then only a subset for "older unmaintained gaming titles" — CS2 is actively maintained, so it likely does **not** qualify. ARM64EC Wine+FEX blocked by 16 KB pages. | Cannot be engineered around. Monitor quarterly, pre-write the decommission notice, hold macOS 26 on the play machine as long as security allows, keep GeForce NOW warm as the migration path. | T-031 |
| R-2 | Valve changes anti-cheat in a way that excludes Wine | Critical | Low–Unknown | No written Valve policy (UNKNOWN). Counter-evidence: native Linux build with VAC, Steam Deck "Playable", CS2 served via GFN VMs. | Never touch game files; monitor patch notes; if it happens it is a policy wall — migrate to alternatives. | T-020, T-030 |
| R-3 | A CS2 update breaks the bottle | High | High | CS2 patches frequently; whether one has ever broken a bottle is **UNKNOWN**. Shader caches near-certainly invalidate. | Automated buildid watch + regression drill within 24 h; keep last-known-good bottle snapshot. | T-030 |
| R-4 | Frametime hitching from shader compilation ruins 1 % lows | High | High | Every source reports first-exposure stutter per map. | Warm-up protocol after each update; persistent shader cache; measure hitch count, not averages. | T-013 |
| R-5 | **DXMT underperforms on this machine** | Medium | Medium | 10× swings both directions across machines (one M3: DXMT 120 vs D3DMetal 11; one M4 Max: reverse). DXMT v0.80 is **MIT** (LGPL from v0.81) and actively developed (2026-08-21). It is CONFIRMED to load as a Wine builtin and initialise Metal under stock Wine 11.15 on this machine; whether it *renders CS2* is still UNKNOWN. | Measure in T-012. Fallback: user installs Apple GPTK locally — we never redistribute it, so no licence change. | T-012 |
| R-6 | Disk exhaustion | Medium | **Already occurring** | 60 GB dead download on this Mac; Windows path needs ~72 GB + staging. | T-001 first; `doctor` gates on ≥ 80 GB free. | T-001, T-024 |
| R-7 | Audio/mic unusable (esp. Bluetooth/AirPods) | High | Medium | Documented crackling (fixed by Win8 compat mode), alt-tab audio loss. | Dedicated audio matrix; declare Bluetooth unsupported if it fails. | T-016 |
| R-8 | Input latency too high for competitive play | High | **Unknown** | **No ms-level measurement of CS2-under-Wine-on-Apple-Silicon exists anywhere.** | Measure it (240 fps camera) as a delta vs. native/GFN; publish. | T-015 |
| R-9 | Thermal throttling on sustained sessions | Medium | Medium (High on Air) | M4 Air 30–40 FPS vs actively-cooled M3 Pro 120. | 2 h soak test; publish sustained not peak; `thermal-limited` profile. | T-017 |
| R-10 | Legal: licence entanglement | **Low** | Low | **Resolved by design** — we redistribute **nothing but our own GPL-3.0 code**; the user fetches Wine (LGPL-2.1) and DXMT (**MIT** through v0.80, LGPL from v0.81) themselves. D3DMetal is never redistributed. | Keep it that way. If we ever bundle an LGPL library: licence text, unmodified, dynamically linked. | T-002 |
| R-11 | Steam-in-Wine friction (login, Guard, self-update) — **and self-assembling the free stack, which CrossOver would have made trivial** | Medium | **High** | Common community friction point. | Document the exact click path and every error+fix. | T-007 |
| R-12 | Network jitter (SteamNetworkingSockets starvation, AWDL) | Medium | Medium | Documented thread-starvation jitter; AWDL Wi-Fi interference. | Ethernet recommended; disable AirDrop/Handoff during play; measure ±10 ms vs native. | T-019 |
| R-13 | A cheaper path was available all along | Low | Medium | CS2 is on GeForce NOW today, fully optimized, zero engineering. We chose to build anyway. | Accepted deliberately. GFN remains the fallback recommendation if T-020 fails. | T-020 |
| R-14 | Privacy leak in shared diagnostics | Medium | Medium | SteamID/paths/IPs are trivially embedded. | Redact + show-before-write; security review. | T-028 |
| **R-15** | **Homebrew's Wine casks are disabled on 2026-09-01** | Medium | **Certain (dated)** | `brew info --cask wine-stable` (11.0_1) and `wine@staging` (11.15) both print: *"Deprecated because it does not pass the macOS Gatekeeper check! It will be disabled on 2026-09-01."* CONFIRMED on the machine of record 2026-08-24 — **eight days out** at the time of writing. The second dated risk in this register after R-1. | **Already mitigated:** the install path uses the Gcenx **tarball**, which is not a cask, carries no quarantine attribute and is pinned by SHA-256. Any guide, script or doctor message that still names a cask is a defect. | T-004, T-024 |
| **R-16** | **Upstream deletes the install path without notice** | Medium | **High — it already happened** | `gcenx/wine/wine-crossover`, the cask this project's own plan and install guide told users to run, was **deleted from its tap on 2026-04-16** (commit `f201026`) with no deprecation notice; the tap README still advertised it four months later. Homebrew separately began **refusing third-party casks** without `brew trust`. Neither change was announced anywhere we were watching. CONFIRMED 2026-08-24. | Pin **URL + SHA-256**, never a package name (T-004). A deleted GitHub release asset is still detectable — the checksum tells you the artefact changed, a package name does not. Add "the documented install command still executes" to the quarterly review, and treat an unexecutable command in the guide as a P1 doc bug. | T-004, T-034 |

## The dated risks

Three risks in this register carry a **date** rather than a probability. They are the ones to check first:

| Risk | Date | What expires |
|---|---|---|
| **R-15** | **2026-09-01** | Homebrew's `wine-stable` / `wine@staging` casks are disabled. Already routed around (tarball). |
| **R-1** | end of **macOS 27** | General-purpose Rosetta 2, and with it the entire x86-64 stack. No route around it. |
| R-16 | *already occurred* (2026-04-16) | The install command this project shipped. Mitigated by pinning URL + checksum. |

## Risk posture in one line

The engineering risks are all **measurable and mitigable**. The two that can end the project — **Apple retiring
Rosetta** and **Valve's unwritten Wine policy** — are both external, and neither can be engineered around. Plan
accordingly: keep the owned surface small, keep the exit documented — and re-run the documented install commands
often enough that R-16 never surprises us twice.
