# 04 — Test matrix

Run the **full** matrix at the end of each phase and after every CS2 buildid change (T-030). Run the ⚡ subset as a
smoke test after any bottle change.

Result codes: **P** pass · **F** fail · **W** works with caveat · **–** not applicable · **?** untested.

## A. Install & client
| ⚡ | Test | Acceptance | Task |
|---|---|---|---|
| ⚡ | `wine --version` ≥ 11.0, DXMT DLLs overridden | free stack present | T-004 |
| ⚡ | In-bottle Steam login (incl. Steam Guard) | reaches library < 60 s | T-007 |
|  | Steam client self-update | completes, client relaunches | T-007 |
|  | CS2 install includes depot 2347771 | `game/bin/win64/cs2.exe` exists | T-008 |
| ⚡ | Steam *Verify integrity* | 0 files re-acquired | T-008, T-021 |
|  | CS2 update applies inside bottle | new buildid, game still launches | T-030 |
|  | Free disk after install | ≥ 20 GB headroom remains | T-024 |

## B. Launch & render
| ⚡ | Test | Acceptance | Task |
|---|---|---|---|
| ⚡ | Main menu renders | no black screen (else `CS2Video.txt fullscreen=0`) | T-009 |
| ⚡ | Bot match, Dust2 / Mirage / Ancient | 30 min, no crash | T-010 |
|  | Windowed / borderless / fullscreen | all three usable | T-014 |
|  | Retina/HiDPI OFF verified | not rendering at 3024×1964 | T-014 |
|  | Alt-tab and back | returns, no lost device | T-009 |
|  | External monitor + refresh rate | **UNKNOWN — generate data** | T-014 |
|  | Second-exposure map load | hitch count ≥70 % lower than cold | T-013 |

## C. Performance
| Test | Acceptance | Task |
|---|---|---|
| Ancient benchmark, 5 runs after 3 warm-ups | median avg + median 1 % low recorded | T-011 |
| **1 % low at chosen resolution** | **≥ 60 FPS** | T-014 |
| Hitch count (frametime > 50 ms) per 10 min | trending to 0 after warm-up | T-013 |
| DXMT confirmed as backend (+1 `-vulkan` control run) | ranked, ≥ 5 runs each | T-012 |
| MSync vs ESync | winner recorded | T-012 |
| 2 h soak: minute 5 vs minute 90 | < 15 % sustained drop | T-017 |
| On battery vs plugged in | both documented | T-017 |
| Peak RSS of full stack | < 24 GB on 32 GB machine | T-017 |

## D. Input
| Test | Acceptance | Task |
|---|---|---|
| `m_rawinput 1` effective in bottle | verified, not assumed | T-015 |
| macOS pointer acceleration disabled | linear tracking | T-015 |
| High-polling-rate mouse recognised | rate confirmed | T-015 |
| **Click-to-photon latency, 20 trials** | median + IQR published, delta vs native | T-015 |
| USB / Bluetooth / dongle mice | each rated | T-015 |
| Keyboard, incl. rapid counter-strafe | no dropped inputs | T-010 |

## E. Audio & comms
| ⚡ | Test | Acceptance | Task |
|---|---|---|---|
| ⚡ | Game audio clean 30 min | no crackle (`cs2.exe` = Windows 8) | T-016 |
|  | Positional accuracy | footstep direction correct | T-016 |
|  | Mic heard by a real teammate | confirmed by second party | T-016 |
|  | Push-to-talk | reliable | T-016 |
|  | Built-in / USB / AirPods | each rated; BT may be declared unsupported | T-016 |
|  | Hot-swap device mid-match | recovers or documented as failing | T-016 |
|  | Alt-tab does not kill audio | pass or documented workaround | T-016 |

## F. Network
| ⚡ | Test | Acceptance | Task |
|---|---|---|---|
| ⚡ | Casual match completes | no disconnect | T-019 |
|  | Ping vs native macOS Steam to same relay | within ±10 ms | T-019 |
|  | Loss / choke on `net_graph` | 0 sustained | T-019 |
|  | Wi-Fi vs Ethernet | both documented | T-019 |
|  | AWDL disabled (AirDrop/Handoff off) | jitter improvement quantified | T-019 |
|  | Community server join | works | T-019 |
|  | Reconnect after sleep / network switch | recovers | T-019 |
|  | Friends, invites, lobby | work from bottle | T-019 |

## G. Anti-cheat & competitive `[the gate]`
| Test | Acceptance | Task |
|---|---|---|
| 5 Competitive matches, ≥ 3 separate days | 0 kicks, 0 warnings | T-020 |
| 5 Premier matches (after Prime purchase) | 0 kicks, 0 warnings | T-020 |
| "VAC unable to verify game session" occurrences | 0 (1 isolated ≠ verdict; it happens on Windows too) | T-020 |
| Game-file hash manifest re-verified after every session | unchanged | T-021 |
| Account warnings / restrictions | none, ever | T-020 |

## H. `CS2Kit`
| Test | Acceptance | Task |
|---|---|---|
| `doctor` on a seeded-fault bottle | finds ≥ 5 faults with correct fixes | T-024 |
| `bottle create` from recipe only | fresh bottle → main menu, no manual step | T-025 |
| `bench` reproducibility | ±5 % on unchanged machine | T-026 |
| `report` privacy review | 0 personal identifiers | T-028 |
| Integrity guard | refuses to launch on modified game file | T-021 |

## I. Regression triggers
Run the full matrix when: CS2 `buildid` changes · macOS updates · Wine / DXMT / MSync updates · bottle recipe
changes · any hardware change.
