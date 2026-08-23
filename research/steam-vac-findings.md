# CS2 on Apple Silicon — Steam acquisition / runtime path + anti-cheat reality

Research date: **2026-08-23**. Researcher: `cs2-steam-vac` subagent.
Confidence tags: **CONFIRMED** = Valve/CodeWeavers/vendor primary data. **LIKELY** = secondary/community. **UNKNOWN** = not verified.

> **Tooling caveat:** the `websearch` skill was unavailable this session ("no Serper API key is configured"),
> and DuckDuckGo/Bing/Mojeek/SearXNG/Reddit/SteamDB all returned bot-challenges. Everything below was obtained by
> fetching **primary endpoints directly** (Steam Web APIs, Steam appinfo, Steamworks docs, CodeWeavers,
> GitHub API, Wayback). That is actually a strength for the CONFIRMED items — most are raw Valve data, not blog posts.

---

## 0. TL;DR / decisions this forces

1. **You cannot use native macOS Steam + `steam://run/730`.** appid 730 is `oslist = windows,linux`. There is no macOS
   executable in any depot. The plan **must** run the **Windows Steam client inside a Wine/CrossOver bottle** (recommended),
   or use `steamcmd @sSteamCmdForcePlatformType windows` (works for bytes, but see §2 for the recognition caveat).
2. **The stalled 54.9 GB download you observed is not a bug you can fix** — macOS Steam is queueing the *wrong depot set*
   (proved by exact byte arithmetic in §1b). It would never produce a `cs2.exe`. **Cancel it and reclaim the disk.**
3. **Anti-cheat risk for a legitimate Wine user is LOW, not zero**, and Valve has **no published statement** that
   blesses Wine specifically. The strongest structural argument is that CS2 ships a **native Linux build with VAC enabled**
   and is Steam-Deck-"Playable", so VAC demonstrably does not require Windows. (§3)
4. **⚠️ BIGGEST CONTRADICTION: `github.com/alien-agent/cs2-macos-patcher` has NOTHING TO DO WITH COUNTER-STRIKE 2.**
   In that repo "CS2" = **Cities: Skylines II**. Do not put it in the plan. (§6)

---

## 1. Can native macOS Steam download/install/launch CS2 (appid 730)?

### 1a. Is 730 macOS-supported? — **NO. CONFIRMED.**

| Source | Evidence |
|---|---|
| Steam appinfo (Valve's own app metadata) via `https://api.steamcmd.net/v1/info/730` | `common.oslist = "windows,linux"` — **no `macos`** |
| Steam storefront API `https://store.steampowered.com/api/appdetails?appids=730&cc=us` | `"platforms": {"windows": true, "mac": false, "linux": true}` |
| Steam store search API `https://store.steampowered.com/api/storesearch/?term=Counter-Strike%202&cc=US` | `730 Counter-Strike 2 {'windows': True, 'mac': False, 'linux': True}` |
| Store page `https://store.steampowered.com/app/730/CounterStrike_2/` | System-requirements tabs are only `win` ("Windows") and `linux` ("SteamOS + Linux"). No macOS tab. |
| Rock Paper Shotgun, 2023-10-10 (secondary, historical) `https://www.rockpapershotgun.com/valve-bins-counter-strike-2s-mac-support-offers-a-csgo-legacy-version-in-return` | "Valve have decided to discontinue support for MacOS… in future, the game will be exclusive to 64-bit Windows and Linux systems." **LIKELY** |
| Valve's own public statement explaining the drop | **UNKNOWN** — I could not find a Valve blog/support post that says it in words. Valve communicated it by *removing the platform icon*. Steam Support told a user in 2023 they "have no information regarding future updates" (`https://steamcommunity.com/app/730/discussions/0/3881596897251897025/`). |

**CONTRADICTS A COMMON ASSUMPTION:** `store.steampowered.com/api/appdetails?appids=730` **still returns a
`mac_requirements` block** ("MacOS X 10.11 (El Capitan) or later, Intel Core Duo, 15 GB") — leftover CS:GO text.
Automated tooling (and LLMs) reading that field will wrongly conclude CS2 supports macOS. The authoritative field is
`platforms.mac == false`. Same trap in the appinfo: 730 still carries `config.vacmodulefilename_macos`,
macOS launch entries for the `csgo_legacy` / `csgo_demo_viewer` branches, and a macOS depot — all CS:GO-era residue.

### 1b. What *exactly* happens when a Mac user clicks install — **explained, CONFIRMED by byte arithmetic**

Your machine (macOS 26.5.2, M2 Pro) produced `appmanifest_730.acf` with:

* `TargetBuildID 24828357` → matches Valve's current **public** branch buildid `24828357`, `timeupdated 2026-08-19T23:35:17Z`
  (appinfo `depots.branches.public`). So the manifest is current, not stale. **CONFIRMED**
* `BytesToDownload 54,888,337,776`, `BytesToStage 63,933,013,362`, `BytesDownloaded 0`, `StateFlags 1026`,
  `installdir "Counter-Strike Global Offensive"` (matches appinfo `config.installdir`). **CONFIRMED**

**Depot table for 730 (public manifest, from Valve appinfo):**

| Depot | OS filter | Download bytes | Staged (on-disk) bytes | Contents (per SteamDB `files.json`) |
|---|---|---|---|---|
| 2347770 | *(none — all OS)*, osarch 64 | 53,938,731,200 | 62,790,947,954 | "cs2 content" — vpk/assets, incl. `shaders_vulkan_*.vpk` |
| **2347771** | **windows** | **4,994,900,000** | **7,711,878,310** | **"cs2 windows" — regex `.+?\.(dll\|exe)` — i.e. ALL executables** |
| 2347772 | macos | **1,696** | **9,276** | vestigial CS:GO-era stub (~9 KB) |
| 2347773 | linux, osarch 64 | 4,604,081,968 | 7,221,564,478 | "cs2 linux" — `.sh` + ELF binaries |
| 2347774 | *(none)*, osarch 64 | 949,604,816 | 1,142,056,124 | shared content |
| 2347777 | *(none)* | 26,893,488 | 87,955,504 | shared content |
| 2347779 | DLC 2279721 | 565,880,640 | 2,091,728,725 | Workshop Tools (optional DLC) |
| 731–738 | mixed | 64 each | 8 each | CS:GO-era system-defined stubs |

Sources: `https://api.steamcmd.net/v1/info/730` (mirror of Valve appinfo) and
`https://raw.githubusercontent.com/SteamDatabase/GameTracking-CS2/master/files.json` (SteamDB's depot→file-type map).

**The arithmetic is exact:**

```
2347770 download 53,938,731,200
2347774 download        949,604,816
2347772 download              1,696   <- the 9 KB macOS stub
733     download                 64   <- macOS 8-byte stub depot
                       ---------------
                       54,888,337,776  == your BytesToDownload  ✅

2347770 size 62,790,947,954
2347774 size  1,142,056,124
2347772 size          9,276
733     size              8
                       ---------------
             63,933,013,362  == your BytesToStage  ✅
```

**Conclusion (CONFIRMED, not inference):** macOS Steam queued the **OS-agnostic content depots + the 9 KB macOS stub**.
It did **NOT** queue depot **2347771** (the Windows `.exe`/`.dll` depot, 4.99 GB) and did **not** queue 2347773 (Linux).
Steamworks depot rule: *"OS — If this is set, the depot is only mounted on systems of given OS"*
(`https://partner.steamgames.com/doc/store/application/depots`). So a macOS client can never receive `cs2.exe`.

If that download ever finished you would have **~63.9 GB of maps/models/sounds/shaders and zero executables**.
That is precisely the historical symptom Mac users reported at CS2 launch: *"missing executable… it's incorrectly
looking for a `cs2.exe`"* — `https://steamcommunity.com/app/730/discussions/0/3881596897251897025/` (2023-09-27, **LIKELY**).
The reason Steam looks for `cs2.exe` is that 730 has **no macOS launch entry on the `public` branch**; the only macOS
launch entries in appinfo are `betakey: csgo_legacy` (`csgo.sh`) and `betakey: csgo_demo_viewer`. **CONFIRMED**

**Why `downloading/730/game/bin/win64` exists with 0 DLLs:** depot 2347770 is OS-agnostic and its manifest contains
paths under `game/bin/win64/` (non-executable data, e.g. `*_dir.vpk`, `.cfg`, `.txt`; note the files.json regex for
2347770 explicitly includes `dll` and `cfg` for tracking purposes). Steam pre-creates the directory tree from the
manifest before writing chunks. **LIKELY** — the decisive check is the `InstalledDepots`/`StagedDepots` block inside
your `appmanifest_730.acf`: it should list 2347770 / 2347774 / 2347772 (and *not* 2347771). Absence of
`linuxsteamrt64` and `osx64` is consistent and expected.

**`StateFlags 1026` decoded — CONFIRMED (two independent open-source enum tables agree):**

* `1026 = 1024 + 2 = StateUpdateStarted | StateUpdateRequired`
* Sources: `https://raw.githubusercontent.com/lutris/lutris/master/docs/steam.rst` and
  `https://raw.githubusercontent.com/beeradmoore/dlss-swapper/main/src/Data/Steam/SteamStateFlag.cs`
  (`StateUpdateRequired = 1<<1 = 2`, `StateUpdateStarted = 1<<10 = 1024`).
* **Not** set: `StateUpdateRunning (256)`, `StateDownloading (1048576)`, `StateStaging (2097152)`, `StateFullyInstalled (4)`.
* Reading: *"an update job has been created/queued and the app is flagged as needing content, but the update is not
  running."* Consistent with `BytesDownloaded 0`. It is a **queued-but-never-scheduled** job, not a network problem.
  Why Steam refuses to actually run it on an unsupported platform: **LIKELY** (client-side platform gate), Valve has no
  published doc for this state — **UNKNOWN** as a documented behaviour.

**Action:** in macOS Steam, cancel/remove the CS2 download and delete
`~/Library/Application Support/Steam/steamapps/downloading/730` and `appmanifest_730.acf`.
Do **not** try to "fix" it. Nothing that macOS Steam downloads is reusable as a game install (though the 54.9 GB of
content depot bytes *are* the same bytes the Windows install needs — see §2 caveat).

---

## 2. Getting the CS2 **Windows** depot onto a Mac

### Option A — Windows `Steam.exe` inside a Wine/CrossOver bottle  ✅ **RECOMMENDED**

* The bottle's Steam client reports itself as Windows, so 730 shows as installable and it pulls
  **2347770 + 2347771 + 2347774 + 2347777** = **59,910,129,504 B download ≈ 55.8 GiB / 59.9 GB**,
  **71,732,837,892 B staged ≈ 66.8 GiB / 71.7 GB on disk**. (Computed from the depot table above. **CONFIRMED**)
  Store page says "85 GB available space" — that is Valve's padded figure. Plan for **~70 GB free + headroom**.
* Community-verified procedure (Whisky, Apple Silicon, 2023-09-28, still the canonical recipe):
  install Whisky/CrossOver → new **Windows 10** bottle → run `SteamSetup.exe` → log in → install CS2 normally.
  `https://steamcommunity.com/app/730/discussions/0/3881596897254712215/` **LIKELY**
* **This is the only option that yields an install the in-bottle Steam client fully owns** (it writes its own
  `steamapps/appmanifest_730.acf`, `config/`, `depotcache/`, and can update + verify it). **CONFIRMED by construction.**

### Option B — `steamcmd` with `@sSteamCmdForcePlatformType windows`

* The flag is real and documented by Valve's own wiki: *"It is possible to choose the platform for which SteamCMD
  should download files, even if it isn't the platform it is currently running on… `@sSteamCmdForcePlatformType`…
  The supported values are `windows`, `macos` and `linux`."*
  Source (Anubis-blocked live; read via Wayback snapshot **2026-08-18**):
  `http://web.archive.org/web/20260818211210/https://developer.valvesoftware.com/wiki/SteamCMD` **CONFIRMED**
* Form: `./steamcmd.sh +@sSteamCmdForcePlatformType windows +force_install_dir <dir> +login <user> +app_update 730 validate +quit`
* **Caveats you must design around:**
  * 730 is **not** anonymous-downloadable (it is a free-to-play *account* entitlement); you must `login <steamaccount>`.
    Anonymous login works for the *dedicated server* app **740**, not 730. **LIKELY** (740 is the documented anon example on the same wiki page).
  * steamcmd writes a plain directory + its **own** `appmanifest_730.acf` in `<dir>/steamapps/`. To make the in-bottle
    Windows Steam client adopt it you must place the tree at `<bottle>/…/Steam/steamapps/common/Counter-Strike Global Offensive`
    (`installdir` = `Counter-Strike Global Offensive`, **CONFIRMED** from appinfo `config.installdir`) **and** move the
    matching `appmanifest_730.acf` next to it, then let Steam validate. Whether Steam accepts a steamcmd-produced manifest
    without a full re-verify: **UNKNOWN** (untested here). Expect a "Validating" pass at minimum.
  * `config.checkforupdatesbeforelaunch = 1` on 730 (**CONFIRMED**, appinfo) — Steam will re-check/patch before every
    launch anyway, so a hand-placed tree gets reconciled by the client regardless.
* **Verdict:** Option B is useful to *pre-seed bytes over a fast link or a different machine*, but Option A is what
  actually produces a launchable, updatable install. **Prefer A; use B only as a bandwidth optimisation.**

### Does CS2 need the Steam client running at all? — **YES. CONFIRMED.**

* Both launch entries pass `-steam` (`game\bin\win64\cs2.exe -steam`, `game/cs2.sh -steam`).
* `config.usemms = 1` (Steam Matchmaking/MMS), `config.matchmaking_mms_appidinvitenf = 624820`,
  `matchmaking_rate_limit`, `sdr-groups` (Steam Datagram Relay), `config.usesfrenemies = 1`, `config.cegpublickey`.
* Category list includes **"Valve Anti-Cheat enabled"**, Steam Workshop, Steam Inventory/Trading.
* All of that is Steamworks: **no Steam client process in the bottle ⇒ no login, no matchmaking, no inventory, no VAC session.**
  Launching `cs2.exe` standalone is not a supported path. Source: `https://api.steamcmd.net/v1/info/730`.

---

## 3. VAC + CS2 under Wine/CrossOver on macOS — ban risk & failure modes

### Valve's *stated* policy

* **Steam Support, "Valve Anti-Cheat (VAC) System"** — `https://help.steampowered.com/en/faqs/view/571A-97DA-70E9-FF74` (**CONFIRMED**, primary):
  * *"VAC … designed to detect **cheats installed on users' computers** … reliably detects cheats using their **cheat signatures**."*
  * *"Any third-party modifications to a game designed to give one player an advantage over another is classified as a cheat…
    **This includes modifications to a game's core executable files and dynamic link libraries.**"* ← directly relevant to any "patcher"
  * *"The following will **not** trigger a VAC ban: **System hardware configurations. Updated system drivers**, such as video card drivers."*
  * *"You will **not** be banned by the VAC system unless you log in to a VAC-secure server **with a cheat installed** on your computer."*
  * *"VAC bans are permanent, non-negotiable, and cannot be removed by Steam Support."*
* **Steamworks "Anti-cheat and Game Bans"** — `https://partner.steamgames.com/doc/features/anticheat` — **contains no mention
  of Wine, Proton, or compatibility layers at all.** (**CONFIRMED** by full-text read.)
* **There is no Valve statement anywhere I could reach that explicitly says "running CS2 under Wine/CrossOver is allowed
  and will not be banned".** Mark that as **UNKNOWN** and say so in the plan. Do not claim Valve blesses it.

### The structural argument that makes the risk low (**CONFIRMED facts, inference is mine**)

1. CS2 has a **native Linux build** (depot 2347773, `game/cs2.sh`, `SteamLinuxRuntime_sniper` via appinfo `config.app_mappings`)
   and the store page carries the **"Valve Anti-Cheat enabled"** category for the whole app.
   ⇒ **VAC operates on a non-Windows, non-kernel-anticheat platform today.** CS2 has no kernel-mode anti-cheat driver.
2. 730's Steam Deck compatibility category is **2 = "Playable"** with `recommended_runtime: "native"` (appinfo
   `common.steam_deck_compatibility`) — Valve itself ships CS2 to a Linux handheld. **CONFIRMED**
3. VAC bans are **signature-based on detected cheats** (Valve's own wording above), not "you are running an unusual OS".
   A translation layer is closer to Valve's own "system configuration / drivers" exclusion than to a cheat.

### Reported real-world outcomes for legitimate Wine/CrossOver users

* **CodeWeavers official compatibility DB — this is the strongest single data point:**
  `https://www.codeweavers.com/compatibility/crossover/counter-strike-global-offensive`
  * Title: "Will Counter-Strike 2 run on Mac or Linux?"
  * **Mac rating: "Runs Well", last tested CrossOver 26.3.0** (page modified **2026-06-25**), 9 votes, 10 macOS rating submissions
    spanning CrossOver 21.x → 26.3.0. **CONFIRMED (vendor primary).**
  * CrossOver **Linux** rating is "Installs, Will Not Run" but flagged *"Outdated Rating!"* (last tested 21.1.0) — ignore it,
    and note you'd use the native Linux build there anyway.
  * A commercial vendor would not carry a "Runs Well" rating for a VAC title that got customers banned. That is the
    best available proxy for "legitimate users are not being banned".
* CodeWeavers forum, CS2 thread "Some bugs": *"THX Crossover — **played CS2 online with nearly no problems**"*
  (`https://www.codeweavers.com/compatibility/crossover/forum/counter-strike-global-offensive?;msg=291438`) **LIKELY**
* Steam Community: "Can I get banned for using Whisky to play CS 2?" (2024-11-24) — answers "no"/"No..".
  `https://steamcommunity.com/app/730/discussions/0/4637114181344075435/` **LIKELY (community opinion, not Valve)**
* Russian-language thread asking the same about CrossOver on Apple Silicon, no ban reports:
  `https://steamcommunity.com/app/730/discussions/0/4354498956232290465/` **LIKELY**
* **I found no credible report of a VAC ban caused by Wine/CrossOver itself.** **LIKELY (absence of evidence, not proof).**

### Named failure modes to expect (not bans)

* **"VAC was unable to verify your game session"** — this is a *kick*, not a ban. It is an extremely common generic CS2
  error on plain Windows too (nine separate threads in the CS2 forum alone, e.g.
  `https://steamcommunity.com/app/730/discussions/0/4637114675688927108/`, `…/3834298194198184474/`). Standard remedies are
  restart Steam / verify files / re-login. Whether it fires *more often* under Wine: **UNKNOWN** — I found no Wine-specific dataset.
  Budget for it in the plan as "expected occasional kick, retry", not "ban".
* **Trust Factor degradation** rather than bans is the realistic downside for unusual client environments. Community
  consensus in the CS2 forum for odd third-party software is *"It will reduce your trust factor, but you won't get banned for it"*
  (`https://steamcommunity.com/app/730/discussions/0/4853281047671209179/`). **LIKELY.** Valve does not publish Trust Factor inputs — **UNKNOWN**.
* Concrete CrossOver-specific breakages actually reported (all cosmetic/perf, none anti-cheat):
  black screen until alt-tab on M1 (fixed by enabling D3DMetal) — `…forum/…?;msg=308731`;
  audio dies after alt-tab with a headset, workaround = set `cs2.exe` to Windows 8 in winecfg — `…?;msg=290698`;
  `SteamNetworkingSockets lock held for N ms … thread starvation` spam on M1 Pro — `…?;msg=308728`;
  weapon-skin thumbnails blank in inventory and sticker drag-placement broken — `…?;msg=291438`, `…?;msg=342292`. **LIKELY**

### Trusted Mode

* **CS:GO's Trusted Mode is real and Valve-documented** — Valve blog, **2020-07-08**:
  *"By default, players will launch CS:GO in **Trusted mode**, which will **block third-party files from interacting with the game**.
  If you would like to play while using third party software that interacts with CS:GO, launch with the **`-untrusted`** launch option.
  Note that in this case **your Trust score may be negatively affected**."*
  Source (live blog is dead; Wayback): `http://web.archive.org/web/20200918000323/https://blog.counter-strike.net/?p=30736` **CONFIRMED (Valve primary, 2020)**
* **Does Trusted Mode still exist / behave differently in CS2 under Wine? → UNKNOWN.**
  I searched all 500 Steam news items for 730 (2022-03 → 2026-08-19): **zero** CS2-era mentions of "Trusted Mode",
  `-untrusted`, `-allow_third_party_software`, or "third-party software". Valve has neither re-announced nor
  publicly retired it for Source 2. Do not assert either way in the plan.
  * Mechanically, Trusted Mode is a **user-mode Windows process-integrity check (blocking foreign DLL injection)**.
    Inside a Wine bottle *everything* in the bottle is a "Windows" module, and Wine's own loader injects its builtin
    DLLs — so a false positive is theoretically possible. **No evidence it happens**; CodeWeavers "Runs Well" +
    "played online with nearly no problems" argue it does not. **UNKNOWN/LIKELY-OK.**

### Verdict for the plan

> Running the **unmodified** CS2 Windows build under CrossOver/Wine, launched by the **unmodified** Windows Steam client,
> with **no injected overlays/cheats/trainers**, is **LOW ban risk** — but Valve gives no guarantee (**UNKNOWN policy**),
> and VAC bans are **permanent and non-appealable** (**CONFIRMED**). Recommend: use a **secondary Steam account with no
> inventory** for the first weeks of the experiment, and **never** patch or replace files inside
> `…/Counter-Strike Global Offensive/game/bin/win64/`.

---

## 4. Premier / Competitive / Prime requirements and platform gating

* **No platform gating exists in CS2's matchmaking.** There is no per-OS restriction anywhere in 730's appinfo,
  and CS2's store category list includes **"Cross-Platform Multiplayer"** — Windows and Linux players share the same
  matchmaking pool. **CONFIRMED** (`store.steampowered.com/api/appdetails?appids=730`).
  ⇒ A Wine-run client presents as a Windows client; there is nothing to "unlock".
* **Prime Status Upgrade** — sold on the CS2 store page itself, **$14.99 USD / €13.29 EUR** (checked 2026-08-23,
  `https://store.steampowered.com/app/730/CounterStrike_2/?cc=us`). Store text (**CONFIRMED**):
  *"Counter-Strike 2 players with Prime Status are matched with other Prime Status players and are eligible to receive
  Prime-exclusive souvenir items, item drops, and weapon cases."* / *"This package grants Prime Account Status in Counter-Strike 2."*
  / **"This product is not eligible for refund."** ← note that: no refund safety net if the bottle turns out unplayable.
  Buy Prime **only after** the bottle is proven.
  * The old standalone appid **624820** is now named **"Counter-Strike 2 Full Edition"**, `type: Config`, `parent: 730`,
    and has **no separate store page** (`store.steampowered.com/app/624820/` redirects to the Steam homepage;
    `appdetails?appids=624820` returns `success:false`). **CONFIRMED** — so any doc telling you to open the 624820 store page is stale.
* **Premier:** Valve's own posts confirm Premier is the Active-Duty pick/ban ranked mode with **CS Rating** and global/regional
  leaderboards, max **24 rounds** in regulation + 6-round OT (`https://steamstore-a.akamaihd.net/news/externalpost/steam_community_announcements/5141476355659151610`, 2023-08-31). **CONFIRMED**
  * Party gating that *does* exist: *"In Premier, players with a very high established CS Rating are not allowed to party
    with accounts that do not have an established CS Rating"*, and cheat-ban penalties propagate to party members
    (Release Notes 2023-09-27, `…/5220291886484673985`). **CONFIRMED**
  * Whether **Prime is strictly required to queue Premier**: **UNKNOWN** — I could not find a Valve page stating it in
    2025/2026 terms. (It is widely believed and almost certainly true; treat it as an assumption to verify in-client.)
  * Seasons are live and current: "Season 5, Armory, and More" (2026-07-08), "The Fourth Season" (2026-01-21). **CONFIRMED**
* Current game state, for the plan's version pinning: **public branch buildid `24828357`, updated 2026-08-19T23:35:17Z**;
  most recent named version branch **1.41.7.4 (2026-08-03)**. **CONFIRMED** (appinfo `depots.branches`).

---

## 5. Launch flags / config that matter under Wine — and **does the Windows build have Vulkan?**

### Does the CS2 **Windows** build have a Vulkan renderer? — **YES. CONFIRMED.** (this contradicts the common "Vulkan is Linux-only" assumption)

1. Valve's own appinfo launch entry #6, `oslist: windows`, Workshop Tools:
   `arguments: "-steam -retail -gpuraytracing -vulkan"`, `executable: game\bin\win64\csgocfg.exe`.
   Valve ships a **Windows** launch option that passes `-vulkan`. **CONFIRMED** (`https://api.steamcmd.net/v1/info/730`)
2. CS2 release notes **2024-10-30**: *"Fixed a crash in page file usage when **Vulkan initialization fails and the game
   falls back to DX11**."* — "page file" is a Windows concept. **CONFIRMED**
   (`https://steamstore-a.akamaihd.net/news/externalpost/steam_community_announcements/6146943657173880254`)
3. CS2 release notes **2024-06-25**: *"Added an 'NVIDIA G-Sync' row… **This row may be hidden if you're using the Vulkan
   renderer** or if you're not using an NVIDIA graphics card."* — NVIDIA G-Sync UI ⇒ Windows path. **CONFIRMED**
4. The **OS-agnostic** content depot 2347770 ships `shaders_vulkan_[0-9]+.vpk`
   (`https://raw.githubusercontent.com/SteamDatabase/GameTracking-CS2/master/files.json`) ⇒ Vulkan shaders are delivered
   to Windows installs too. **CONFIRMED**
5. Still active in 2025: *"Enabled **Vulkan defragmentation** to help alleviate texture streaming overhead"* (2025-09-26,
   `…/1811772772259703`). **CONFIRMED**

**Why this matters enormously for the Apple Silicon plan:** it means you have **two** renderer paths inside the bottle —
`-dx11` → D3DMetal/DXMT translation, or `-vulkan` → MoltenVK/DXVK-style path. **Which is faster on M-series under
CrossOver 26 is UNKNOWN and must be benchmarked**; I found no measured comparison. Test both.

### Flags / settings with evidence

| Flag / setting | Evidence | Tag |
|---|---|---|
| `-steam` | Valve's own launch args for both OS entries | CONFIRMED |
| `-vulkan` | see above; Valve uses it on Windows for Workshop Tools | CONFIRMED |
| `-dx11` | implied fallback path ("falls back to DX11"); Windows min-spec is "DirectX 11 / Shader Model 5.0" | CONFIRMED |
| `-vulkan` fixes AMD sticker-placement bug | CodeWeavers CS2 forum, 2025-12-25: *"this issue usually happens with AMD GPUs and fixed by starting cs2 with the command `-vulkan`"* | LIKELY |
| `-nojoy -novid -console -low` | the canonical Apple-Silicon/Whisky recipe posted 2023-09-28: `https://steamcommunity.com/app/730/discussions/0/3881596897254712215/` | LIKELY |
| `-untrusted` | Valve, CS:GO 2020 (Trusted Mode). CS2 status UNKNOWN — do **not** ship it by default | CONFIRMED(2020)/UNKNOWN(CS2) |
| `-high` | no Valve documentation found for CS2; Windows priority hint, meaningless-to-harmful under Wine | UNKNOWN |
| `-perfectworld` / `-worldwide` / `-promptperfectworld` | Valve release notes 2023-09-29 (China realm only) — irrelevant here but shows externalarguments are honoured | CONFIRMED |
| `config.uselaunchcommandline = 1`, `config.externalarguments = {allowunknown: 1}` | appinfo — 730 accepts arbitrary user launch options | CONFIRMED |
| **CrossOver bottle: Graphics = D3DMetal, Synchronization = MSync** | CodeWeavers community tip for CS2 specifically, 2025-10-11: `https://www.codeweavers.com/compatibility/crossover/tips/counter-strike-global-offensive/if-you-experience-stutters-on-macos` | LIKELY (CodeWeavers-hosted) |
| Set `cs2.exe` to **Windows 8** in winecfg to fix headset audio dying after alt-tab | CodeWeavers CS2 forum `…?;msg=290698` | LIKELY |
| Enable **D3DMetal** to fix black-screen-until-alt-tab on M1 | CodeWeavers CS2 forum `…?;msg=308731` | LIKELY |

### FPS reality check (hardware + settings)

* **No trustworthy CS2-on-Apple-Silicon FPS number with stated settings could be verified.** The only concrete figures I
  reached are CodeWeavers forum posts, both *negative* and without settings:
  * "MacBook Air M4, CrossOver trial, CS2: **30 fps**, random video lag and freezes" (2025-09-27) and a reply
    "My performance also sucks. Unplayable. **M1 Mac Studio**" (2025-09-30) —
    `https://www.codeweavers.com/compatibility/crossover/forum/counter-strike-global-offensive?;msg=336617` **LIKELY**
  * Steam Community rule-of-thumb: *"translation from a different OS always costs ~40% of the performance"* — folklore, **UNKNOWN**.
* Note the tension: CodeWeavers' **official rating is "Runs Well" on CrossOver 26.3.0 (2026-06-25)** while the newest
  *forum* posts (2025-09, CrossOver ~25.x) say "unplayable". Those posters likely had **D3DMetal/MSync off** (that is
  exactly what the 2025-10-11 tip addresses). **Benchmark it yourself; do not put a number in the plan without measuring.**

---

## 6. ⚠️ `github.com/alien-agent/cs2-macos-patcher` — **WRONG GAME. DO NOT USE.**

**This is the single most important correction in this document.**

`https://github.com/alien-agent/cs2-macos-patcher` — README first line:

> **# Cities: Skylines 2 — macOS / Wine Patcher**
> *"Fixes crashes and enables **Paradox Mods** for **Cities: Skylines 2** running under CrossOver on macOS."*

Verified facts (**CONFIRMED**, GitHub API + raw README on 2026-08-23):

* Repo description: *"A small patcher to fix **CS2** crashes and incompatibilities under CrossOver on macOS"* —
  the ambiguous "CS2" is what makes this repo look like a Counter-Strike tool in search results. It is **Cities: Skylines II**.
* What it actually patches: **.NET/Unity managed assemblies** — `Colossal.IO.dll`, `Colossal.IO.AssetDatabase.dll`,
  `Game.dll`, `PDX.SDK.dll` inside `…/Cities2_Data/Managed`. It IL-patches them, backs up `*.bak`, and writes
  `HKCU\Environment` PATH inside the bottle for the Paradox launcher. It installs .NET SDK 9+ via Homebrew.
  Counter-Strike 2 has **no** managed assemblies, no `Cities2_Data`, and no Paradox launcher.
* Maintenance: created **2026-05-13**, last push **2026-08-10**, 48 stars, 4 forks, 1 open issue, **0 releases**,
  **no LICENSE**, language C#, not archived. So it *is* actively maintained — for the wrong game.
* Tested against: "CrossOver 26 · Game v1.5.8f1–v1.6.0f1 · Apple Silicon (M3 Pro → M5 Max)".

**Would something like it be safe for CS2 anyway? NO — and the plan should say why:**
Valve's VAC FAQ states cheats include *"**modifications to a game's core executable files and dynamic link libraries**"*
(`https://help.steampowered.com/en/faqs/view/571A-97DA-70E9-FF74`). Patching anything in
`Counter-Strike Global Offensive/game/bin/win64/*.dll|*.exe` is exactly the category Valve names, and 730 carries
`config.signedfiles` / `config.signaturescheckedonlaunch` (**CONFIRMED**, appinfo). Even a benign patch would at best be
reverted by `checkforupdatesbeforelaunch = 1` on the next launch, and at worst be indistinguishable from a cheat.
**Rule for the plan: zero modifications inside the CS2 install directory. All fixes go in the bottle (winecfg, DXVK/D3DMetal,
env vars, launch options), never in the game files.**

*Useful bycatch from that repo's README (it is genuinely good CrossOver-on-Apple-Silicon knowledge, just for another game):*
CrossOver 26 exposes **DLSS via MetalFX**; **D3DMetal** is the only DX12-capable translator; **DXMT is DX11-only**;
**MSync** beat ESync in their testing; CrossOver 25+ advertises AVX to the guest via `ROSETTA_ADVERTISE_AVX=1`;
macOS **Tahoe (26)** gives fuller Metal 4 support than Sequoia 15.x; CrossOver **26.2** changed executable lookup and
broke launchers that spawn a sibling `.exe` (`spawn X.exe ENOENT`) — worth knowing if in-bottle Steam misbehaves. **LIKELY**

---

## 7. Loose ends explicitly marked UNKNOWN

1. Valve's own worded statement on dropping macOS for CS2 — never found; only the removal of the platform icon + RPS coverage.
2. Whether Trusted Mode exists in CS2 at all, and whether `-untrusted` is still parsed by the Source 2 build.
3. Whether Prime is strictly required to queue Premier in 2026.
4. Whether a steamcmd-forced-Windows tree is adopted by the in-bottle Steam client without a full re-validate.
5. Any measured, settings-qualified CS2 FPS number on M-series under CrossOver 26.x.
6. Whether "VAC was unable to verify your game session" occurs more often under Wine than on native Windows.
7. Why Steam macOS never advances the queued update out of `StateUpdateStarted` (no Valve documentation of this state).
8. `-vulkan` vs `-dx11` performance ranking on Apple Silicon.

---

### Appendix — reproducible commands used

```bash
# Valve app metadata (oslist, launch entries, depots, branches, config)
curl -s 'https://api.steamcmd.net/v1/info/730' | jq '.data["730"].common.oslist, .data["730"].config.launch, .data["730"].depots'
# Storefront platform flags
curl -s 'https://store.steampowered.com/api/appdetails?appids=730&cc=us&l=en' | jq '.["730"].data.platforms'
# All CS2 news/patch notes (searchable, Valve primary)
curl -s 'https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=730&count=500&maxlength=0'
# Depot -> file-type map
curl -s 'https://raw.githubusercontent.com/SteamDatabase/GameTracking-CS2/master/files.json'
```
