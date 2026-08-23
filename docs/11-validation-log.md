# 11 - Validation log (Phase 3: T-018, T-019, T-020, T-022)

**Status: empty. No online session has been played on this machine.** Every table below is a form waiting to be
filled, and every number slot reads `not measured`. Nothing in this file is data yet - do not cite it, do not
summarise it, and do not let a reader mistake a printed table for a result.

Phase 3 is the part of the project that decides whether any of it counts. T-010 answered *does it run?*; T-020
answers *does it count?* ([03-development-plan.md](03-development-plan.md)). The corresponding rows of the test
matrix are sections **F** (network) and **G** (anti-cheat and competitive) in
[04-test-matrix.md](04-test-matrix.md).

---

## T-018 - Account safety `[read before any online task]`

Tick every box **before** the first online match. These are project rules, not suggestions: they exist because a VAC
ban is **permanent and non-appealable** (CONFIRMED, Steam Support) and because Prime is non-refundable.

- [ ] A **secondary, non-Prime** Steam account exists and is the **only** account used until T-020 passes.
- [ ] That account holds **no inventory** worth losing.
- [ ] **Prime is not purchased.** It is **EUR 13.29 / USD 14.99** and the store page states *"This product is not
      eligible for refund."* Buy it only *after* the T-020 gate passes on the secondary account.
- [ ] **Steam Guard is enabled** on every account involved.
- [ ] **No injected DLLs, no game-file modification, no macros, no input automation, no third-party overlays** beyond
      Steam's own. `cs2kit verify check` is clean before and after every session.
- [ ] The only configuration in play is the legitimate surface: bottle settings, Wine's own DLL overrides,
      environment variables, CS2 launch options and `autoexec.cfg`. Nothing else
      ([06-legal-and-policy.md](06-legal-and-policy.md), absolute rule 4).
- [ ] `-untrusted` is **not** in the launch options. Valve's 2020 Trusted Mode post says it may reduce your Trust
      score; CS2's status is UNKNOWN ([../research/steam-vac-findings.md](../research/steam-vac-findings.md)).

| Field | Value |
|---|---|
| Secondary account in use since | not recorded |
| Prime purchased? | **no** - and must stay `no` until the T-020 gate below says GO |
| Steam Guard | not recorded |

## T-019 - Casual online and community servers

**Why separately from T-020:** this separates *networking* faults from *anti-cheat* faults. Debugging them together
is intractable, so the network must be boring before a competitive match is worth interpreting.

**Acceptance:** three consecutive casual matches, no disconnect, and ping within **+/-10 ms** of native macOS Steam
to the same relay.

Before each session:

```bash
cs2kit doctor              # 'AWDL (AirDrop/Handoff)' and 'Low Power Mode' must not be WARN for a measured session
sudo ifconfig awdl0 down   # AirDrop/Handoff off: community-reported Wi-Fi jitter (LIKELY)
```

| # | Check | Acceptance | Result | Notes |
|---|---|---|---|---|
| 1 | Casual match completes | no disconnect, three consecutive | not measured | |
| 2 | Ping vs native macOS Steam, same relay | within +/-10 ms | not measured | record both numbers, not the delta alone |
| 3 | Loss / choke on `net_graph` | 0 sustained | not measured | |
| 4 | `SteamNetworkingSockets lock held ... thread starvation` console spam | absent, or quantified | not measured | CONFIRMED as reported elsewhere, **fix UNKNOWN** |
| 5 | Wi-Fi vs Ethernet | both documented | not measured | |
| 6 | AWDL down vs up | jitter improvement quantified | not measured | the point is the *difference*, not the absolute |
| 7 | Community server join | works | not measured | |
| 8 | Reconnect after sleep | recovers | not measured | |
| 9 | Reconnect after a network switch | recovers | not measured | |
| 10 | Friends, invites, lobby from the bottle | work | not measured | |

## T-020 `[GATE]` - VAC-protected competitive validation

**This is the project's actual success criterion. Everything before it is instrumentation.**

### Procedure

1. Competitive on the **secondary** account; complete full matches.
2. **5 matches across >= 3 separate days**, with a **bottle restart and a reboot** in between.
3. If clean: buy Prime, move to the main account, run **5 Premier** matches.
4. Log every anomaly with timestamp, `buildid` and environment snapshot:
   `cs2kit doctor --json > ~/cs2kit-match-<n>.json`.
5. Re-run `cs2kit verify check` after every session - the game files must be unchanged, every time
   (test matrix G, [04-test-matrix.md](04-test-matrix.md)).

### One kick is not a verdict

*"VAC was unable to verify your game session"* is a **kick, not a ban**, and it is an extremely common generic CS2
error **on plain Windows too** - nine separate threads in Valve's own CS2 forum. Whether it fires more often under
Wine is **UNKNOWN**; no Wine-specific dataset exists. Budget for it as "expected occasional kick, retry"
([../research/steam-vac-findings.md](../research/steam-vac-findings.md), *Named failure modes*). Record every
occurrence in the log below; a **pattern** is the finding, a single line is not.

### Match log

**no matches played yet.** The table is seeded with zero rows on purpose.

| # | date | mode (Competitive/Premier) | map | buildid | env_id | bottle restart? | reboot? | anti-cheat event | notes |
|---|---|---|---|---|---|---|---|---|---|

Fill one row per **completed** match. `buildid` and `env_id` come from `cs2kit doctor --json`
(`env.stable.cs2_buildid` and `env.env_id`) - a match logged without them cannot be compared with anything.
`anti-cheat event` is `none`, or the verbatim text of the message with its timestamp. An abandoned or requeued match
gets a row too, with the reason in `notes`.

### The gate

**Acceptance / GATE: 10 consecutive matches (5 Competitive + 5 Premier), zero anti-cheat kicks, zero warnings.**

| Outcome | Condition | What it means, verbatim from the plan |
|---|---|---|
| **GO** | 10 consecutive clean matches | Proceed to Phase 4. |
| **CONDITIONAL** | kicks recur | *"ship as practice/casual only, never claim competitive-ready."* |
| **NO-GO** | systematic kicks | *"stop. That is a **policy** wall; do not engineer around it. GeForce NOW is then the honest recommendation for competitive play."* |

**Decision: not reached - 0 of 10 matches played.**

| Field | Value |
|---|---|
| Competitive matches completed | 0 of 5 |
| Premier matches completed | 0 of 5 |
| Separate days covered | 0 of >= 3 |
| Anti-cheat kicks | none observed (no matches played) |
| Account warnings or restrictions | none observed (no matches played) |
| `cs2kit verify check` clean after every session | not measured |
| Decision | **not reached** |
| Decided by / date | not recorded |

Under NO-GO the correct response is to **stop**, not to engineer around it. Nothing in this project may be used to
interfere with, disable, spoof or study VAC ([06-legal-and-policy.md](06-legal-and-policy.md), absolute rule 2).

## T-022 - Competitive-readiness sign-off

The deliverable is **one honest paragraph a stranger can act on, with every number sourced to the task that
measured it**. Below is the template with the slots named. Do not publish it with a slot still reading
`not measured` - publish a shorter paragraph instead.

| Slot | Source task | Value |
|---|---|---|
| Sustained avg FPS (minute 90, Ancient, 1080p) | T-017 / T-011 | not measured |
| Median 1 % low at the chosen resolution | T-014 / T-011 | not measured |
| Hitch count after warm-up, per 10 minutes | T-013 | not measured |
| Click-to-photon latency, median + IQR, as a **delta** vs native | T-015 | not measured |
| Audio and microphone verdict (incl. Bluetooth) | T-016 | not measured |
| Network stability: ping delta, loss/choke, reconnect | T-019 | not measured |
| Anti-cheat log: matches played, kicks, warnings | T-020 | not measured |
| Thermal/power recommendation (plugged vs battery) | T-017 | not measured |

> **Template - do not publish until every slot is filled.**
>
> On a `<machine>` running macOS `<version>` with Wine `<version>`, DXMT `<release>` and CS2 buildid `<buildid>`,
> CS2 sustains `<avg>` avg FPS with a `<1% low>` 1 % low at `<resolution>` on the Ancient benchmark, measured under
> [07-benchmark-protocol.md](07-benchmark-protocol.md) (median of 5 runs after 3 discarded warm-ups). Input latency
> is `<delta>` ms `<higher/lower>` than `<the reference rig>` (T-015, 20 trials). Audio and microphone are
> `<verdict>`; networking is `<verdict>`, with ping within `<n>` ms of native macOS Steam to the same relay.
> Across `<n>` competitive and `<n>` Premier matches on `<n>` separate days there were `<n>` anti-cheat kicks and
> `<n>` account warnings. **This configuration is not supported by Valve**, CS2 has no macOS build, and the whole
> stack depends on Rosetta 2, which Apple provides as a general-purpose tool only **through macOS 27**
> ([rosetta-watch.md](rosetta-watch.md)). Verdict: `<GO / practice-and-casual-only / not recommended>`.

## What this file is not

* **Not a claim.** Until the tables carry rows, the honest summary of Phase 3 is: *nobody has tested this on this
  machine yet.*
* **Not a substitute for the matrix.** Per-run performance numbers live in
  [compatibility-matrix.md](compatibility-matrix.md) and in stored `cs2kit bench` sessions; this file records
  **online and anti-cheat** outcomes.
* **Not evidence about VAC policy.** A clean run here shows that *this configuration was not kicked in these
  matches*. Valve has published no policy on Wine and VAC, and no amount of local testing turns that UNKNOWN into a
  CONFIRMED ([06-legal-and-policy.md](06-legal-and-policy.md), section 2).
