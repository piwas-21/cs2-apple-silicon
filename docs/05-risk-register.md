# 05 — Risk register

Severity × likelihood, scored against evidence rather than intuition. Compare with the prior analysis's table —
**VAC drops from Critical/Unknown to Medium/Low, and Rosetta rises to the top slot with a date attached.**

| # | Risk | Sev | Lik | Evidence | Mitigation | Task |
|---|---|---|---|---|---|---|
| **R-1** | **Rosetta 2 retired after macOS 27; the whole x86-64 stack dies** | **Critical** | **High (dated)** | Apple: general-purpose Rosetta "available through macOS 27", then only a subset for "older unmaintained gaming titles" — CS2 is actively maintained, so it likely does **not** qualify. ARM64EC Wine+FEX blocked by 16 KB pages. | Cannot be engineered around. Monitor quarterly, pre-write the decommission notice, hold macOS 26 on the play machine as long as security allows, keep the T-003 alternatives warm. | T-031 |
| R-2 | Valve changes anti-cheat in a way that excludes Wine | Critical | Low–Unknown | No written Valve policy (UNKNOWN). Counter-evidence: native Linux build with VAC, Steam Deck "Playable", CS2 served via GFN VMs. | Never touch game files; monitor patch notes; if it happens it is a policy wall — migrate to alternatives. | T-020, T-030 |
| R-3 | A CS2 update breaks the bottle | High | High | CS2 patches frequently; whether one has ever broken a bottle is **UNKNOWN**. Shader caches near-certainly invalidate. | Automated buildid watch + regression drill within 24 h; keep last-known-good bottle snapshot. | T-030 |
| R-4 | Frametime hitching from shader compilation ruins 1 % lows | High | High | Every source reports first-exposure stutter per map. | Warm-up protocol after each update; persistent shader cache; measure hitch count, not averages. | T-013 |
| R-5 | Wrong backend chosen by assumption | Medium | High | 10× swings both directions (M3: DXMT 120 vs D3DMetal 11; M4 Max: reverse). | Mandatory measured bake-off before tuning. | T-012 |
| R-6 | Disk exhaustion | Medium | **Already occurring** | 60 GB dead download on this Mac; Windows path needs ~72 GB + staging. | T-001 first; `doctor` gates on ≥ 80 GB free. | T-001, T-024 |
| R-7 | Audio/mic unusable (esp. Bluetooth/AirPods) | High | Medium | Documented crackling (fixed by Win8 compat mode), alt-tab audio loss. | Dedicated audio matrix; declare Bluetooth unsupported if it fails. | T-016 |
| R-8 | Input latency too high for competitive play | High | **Unknown** | **No ms-level measurement of CS2-under-Wine-on-Apple-Silicon exists anywhere.** | Measure it (240 fps camera) as a delta vs. native/GFN; publish. | T-015 |
| R-9 | Thermal throttling on sustained sessions | Medium | Medium (High on Air) | M4 Air 30–40 FPS vs actively-cooled M3 Pro 120. | 2 h soak test; publish sustained not peak; `thermal-limited` profile. | T-017 |
| R-10 | Legal: shipping D3DMetal | Medium | Low if non-commercial | GPTK SLA §2A(iii)+§2C allow non-commercial redistribution; §2A(i) use-grant wording is a grey zone. | Non-commercial only, decided in T-002; else depend on the user's CrossOver licence. | T-002 |
| R-11 | Steam-in-Wine friction (login, Guard, self-update) | Medium | Medium | Common community friction point. | Document the exact click path and every error+fix. | T-007 |
| R-12 | Network jitter (SteamNetworkingSockets starvation, AWDL) | Medium | Medium | Documented thread-starvation jitter; AWDL Wi-Fi interference. | Ethernet recommended; disable AirDrop/Handoff during play; measure ±10 ms vs native. | T-019 |
| R-13 | Project overtaken by a cheaper alternative | Low (good news) | Medium | CS2 is on GFN today, fully optimized. | T-003 gate before any build effort. | T-003 |
| R-14 | Privacy leak in shared diagnostics | Medium | Medium | SteamID/paths/IPs are trivially embedded. | Redact + show-before-write; security review. | T-028 |

## Risk posture in one line

The engineering risks are all **measurable and mitigable**. The two that can end the project — **Apple retiring
Rosetta** and **Valve's unwritten Wine policy** — are both external, and neither can be engineered around. Plan
accordingly: keep the owned surface small, keep the exit documented.
