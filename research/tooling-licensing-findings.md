# macOS Windows-compatibility tooling & licensing landscape (2026)

Research date: **2026-08-23**. Target: running Windows-only CS2 on an Apple Silicon MacBook.
Every claim is marked **CONFIRMED** (primary source), **LIKELY** (secondary/community) or **UNKNOWN**.
Anti-cheat is out of scope here except where a vendor states a policy.

Environment context verified while researching (CONFIRMED):
- Current shipping macOS is **macOS 26 "Tahoe" (26.6.2, build 25G83, released 2026-08-17)**; **macOS 27 is in beta (27.0 beta 6, 26A5416b, 2026-08-17)**, WWDC26 was 2026-06-08. Source: <https://developer.apple.com/news/releases/rss/releases.rss>
- Third-party projects call macOS 27 by codename "Golden Gate" (LIKELY): <https://github.com/italomandara/Procyon/releases/tag/PRE2>

---

## 1. CrossOver (CodeWeavers)

### Version / price / requirements
| Fact | Value | Status | Source |
|---|---|---|---|
| Latest version | **CrossOver 26.3.0, released 2026-07-21** | CONFIRMED | <https://www.codeweavers.com/crossover/changelog> |
| 26.0.0 base | Released **2026-02-10**, contains **Wine 11.0**, Wine Mono 10.4.1, **vkd3d 1.18**, **D3DMetal 3.0**, **DXMT v0.72**; "UI updates for macOS Tahoe" | CONFIRMED | same changelog |
| Price | **€74.00** for "CrossOver +" (full version + 12 months support/upgrades); **€484** for "CrossOver Life" (lifetime). 14-day fully functional free trial. Prices shown are the EU/NL storefront (research host geolocated to NL) — USD list has historically been $74.95/$494 (LIKELY, not re-verified) | CONFIRMED (EUR) / LIKELY (USD) | <https://www.codeweavers.com/store>, <https://www.codeweavers.com/crossover> |
| Licence model | Per-user perpetual licence, **not** a subscription; you keep the version you bought forever, upgrades cost less than a new licence | CONFIRMED | <https://docs.getwhisky.app/maintenance-notice> (Whisky author) + <https://www.codeweavers.com/crossover/eula> |
| macOS support matrix | CrossOver **26** supports Tahoe (26.0) … Catalina; **macOS 26 Tahoe requires CrossOver 25.1.1 or higher**; beta/unreleased macOS is unsupported | CONFIRMED | <https://www.codeweavers.com/crossover> |
| Apple Silicon | Supported since CrossOver 21 (M1+, macOS 11.1+) | CONFIRMED | same page |

### CS2 rating in the CodeWeavers compatibility database
App entry: **"Counter-Strike 2", App Id 10470**, slug still `counter-strike-global-offensive` (the CS:GO entry was renamed) — <https://www.codeweavers.com/compatibility/crossover/counter-strike-global-offensive>

- **Mac rating: 4 stars = "Runs Well"**, **last tested on CrossOver 26.3.0**, 10 submitted ranks, entry modified **2026-06-25**. CONFIRMED.
- CodeWeavers' own definition of 4 stars: *"This application installs and runs quite well, with only minor glitches found… The core functionality of this Windows application works fine under CrossOver."* (5 stars = "Runs Great", i.e. CS2 is **not** rated as flawless). CONFIRMED — <https://www.codeweavers.com/compatibility/rating-system>
- **CrossOver Linux rating for CS2: 2 stars "Installs, Will Not Run", last tested 21.1.0**, flagged by the site as an *"Outdated Rating!"*. This is a database artefact, not a statement that CS2 fails on Linux. **CONTRADICTS the naive reading of the appdb** — do not cite it as evidence about Linux. CONFIRMED.
- Community stats: 9 votes, 660 CrossTie downloads, #1106 by number of submitted ranks. CONFIRMED.
- Historical: **CrossOver 23.6.0 (2023-10-18) changelog literally says "Support for Counter-Strike 2"**. CS2 has been a targeted, supported title for ~3 years. CONFIRMED.

### CS2-specific guidance published on the CodeWeavers site
Tips tab (<https://www.codeweavers.com/compatibility/crossover/tips/counter-strike-global-offensive>) — community tips, not official support:
1. **"If you experience stutters on macOS" (2025-10-11)** — *"Use these bottle settings: Graphics: **D3DMetal**; Synchronization: **MSync**"*. CONFIRMED (this is the single most actionable CS2 setting found).
2. **"Broken audio on Mac" (2024-08-17)** — if audio crackles, open Audio MIDI Setup → your output device → Format → **96.0 kHz**. CONFIRMED.
3. Two 2014-era tips (ATI cards, "gameplay not smooth") — obsolete, ignore.

### What CrossOver bundles
From the changelog + EULA Appendix A (CONFIRMED):
- **Wine 11.0** (CrossOver 26); Wine Mono 10.4.1; **vkd3d 1.18** (D3D12→Vulkan); **DXVK** (listed under zlib licence in Appendix A; last explicit changelog bump was **DXVK 1.10.3 in CrossOver 23.0.0**); **MoltenVK** (Apache-2.0; last explicit bump **MoltenVK 1.2.10 in CrossOver 25.0.0**); FAudio, SDL, LLVM, DirectXShaderCompiler, GStreamer.
- **D3DMetal** (Apple, D3D11/12→Metal): toggle added in **23.5.0**, "Support for translation layer from the game porting toolkit"; **D3DMetal 2.1** in CrossOver 25, **D3DMetal 3.0** in CrossOver 26. D3DMetal is **not** in the open-source Appendix A — it is proprietary Apple code shipped by CodeWeavers.
- **DXMT** (Metal-based D3D11/D3D10, by 3Shain): added in CrossOver 25.0.0, **v0.72** in CrossOver 26.
- **MSync** (Mach-semaphore synchronisation, marzent/wine-msync, LGPL-2.1): *"MSync included"* in CrossOver **23.7.0** (2023-11-27). ESync is the Linux-side equivalent; on macOS the CrossOver bottle synchronisation options are the relevant control (MSync is the one recommended for CS2).
- Linux-only in CrossOver 26: **NTsync**.
- CrossOver 23.0.0 also added *"Initial support for geometry shaders and transform feedback"* (i.e. CodeWeavers implemented these above/around MoltenVK's gaps — see §5). CONFIRMED.

### CrossOver EULA — can a launcher wrap/ship it?
<https://www.codeweavers.com/crossover/eula> (CONFIRMED):
- §1: one-user licence, transferable as a whole.
- §3(b): *"you may not … rent, lend, loan, distribute or create derivative works based upon the Software in whole or in part."* → **a third-party launcher may not redistribute CrossOver.**
- §2 explicitly grants the opposite for the free bits: *"you are explicitly granted license to build alternate versions of the Wine software for use in conjunction with the Software"* and CrossOver Wine sources are published at <https://www.codeweavers.com/crossover/source>. This is why CXPatcher/Procyon **patch a user-supplied CrossOver install** instead of shipping one.
- CodeWeavers claims *"95% of the Wine code base we develop for CrossOver gets released back into the Wine project"*.

---

## 2. Apple Game Porting Toolkit — and the licence question (the decisive finding)

### Version and content
- **Game Porting Toolkit 4** is current (announced at WWDC26, June 2026). The Apple page advertises: agent skills repo, **Metal 4 support in the evaluation environment**, Metal Shader Converter, Metal-cpp, Metal Developer Tools for Windows. CONFIRMED — <https://developer.apple.com/games/game-porting-toolkit/>
- Apple's public GitHub repo <https://github.com/apple/game-porting-toolkit> is **Apache-2.0 but contains only agent skills, metal-cpp and samples — NOT the evaluation environment / D3DMetal.** Prereqs listed: Apple silicon Mac, **macOS 27, Xcode 27**. CONFIRMED.
- The runtime piece is a separate developer-login download named **"Evaluation environment for Windows games"**, e.g. `https://download.developer.apple.com/Developer_Tools/Game_Porting_Toolkit_3.0/Evaluation_environment_for_Windows_games_3.0.dmg`. CONFIRMED via the MacPorts portfile: <https://github.com/macports/macports-ports/blob/master/devel/d3dmetal/Portfile>
- **What D3DMetal is:** `D3DMetal.framework` plus a `/redist` tree of Wine-side stubs — a Direct3D 11/12 → **Metal** translation layer (not Vulkan). The MacPorts port ships `external/D3DMetal.framework`, `wine/x86_64-unix/*.so`, `wine/x86_64-windows/*.dll`, and notably `nvngx-on-metalfx.so/.dll` (**DLSS → MetalFX upscaling shim**, renamed to `nvngx` to enable it). `supported_archs x86_64` — **D3DMetal is an x86-64 binary that runs under Rosetta**, even though it only works on Apple Silicon. CONFIRMED (Portfile).
- D3DMetal versions: 1.1 → 2.0 (2025-01) → 2.1 (2025-03) → **3.0 (2025-12-07)**. MacPorts labels the port `license Restrictive` and **refuses to auto-download it**, telling the user to log into their Apple Developer account and fetch the DMG manually. CONFIRMED.
- **D3DMetal 4 exists but is in beta as of 2026-07-29** ("Updated D3DMetal 4 to Beta2") — LIKELY, from <https://github.com/italomandara/Procyon/releases/tag/PRE4>.

### THE LICENCE — full text obtained
Apple's **"APPLE INC. SOFTWARE LICENSE AGREEMENT FOR GAME PORTING TOOLKIT"** (the `License.rtf`/`License.pdf` shipped inside the GPTK 3.0 DMG), mirrored by the Sikarugir (ex-Kegworks) project:
<https://github.com/Sikarugir-App/Sikarugir/blob/main/D3DMetal/3.0/License.pdf> (also linked from Gcenx's GPTK releases). **CONFIRMED — verbatim quotes:**

> **"Apple Software" means the Apple Game Porting Toolkit software, including the Redistributables and Framework, and documentation, updates, interfaces, content, fonts, and any data or other materials.**
> **"Framework" means the "D3DMetal.framework" within the Apple Game Porting Toolkit.**
> **"Redistributables" means components within the "/redist" directory of the Apple Game Porting Toolkit.**

> **2. Permitted Agreement Uses and Restrictions.
> A. License.** Subject to the terms and conditions of this License, you are granted a limited, non-exclusive, non-transferable, personal copyright license to **(i) install, internally use, and test the Apple Software for the sole purpose of developing, testing, or evaluating video games for use on Apple-branded products**; (ii) sublicense the Apple Software to your third-party service providers … and **(iii) distribute the Apple Software solely for non-commercial purposes and in accordance with this Agreement, including Section 2C.**

> **C. Other Use Restrictions** … "You may not rent, lease, lend, host, sell, or sublicense (except as expressly set forth in Section 2A) the Apple Software … **The Apple Software is provided as part of a bundle and its components may not be separated from the Apple Software for distribution. Notwithstanding the foregoing, the Framework in its entirety or any part of the Redistributables may be distributed separately from the Apple Software. For clarity, all distribution of the Apple Software, including the Framework in its entirety and any individual Redistributables, are subject to the non-commercial restriction in Section 2(A)(iii)."**

> **B. System Requirements.** "the Apple Software is supported only on Apple-branded hardware…"
> **C.** "The grants … do not permit you to … install, use or run the Apple Software on any non-Apple-branded devices, or to enable others to do so."
> **D. No Reverse Engineering.** no decompiling / modifying / derivative works.
> **5. Termination.** Automatic on any breach; destroy all copies.

**>>> CONTRADICTS A COMMON ASSUMPTION <<<**
The widely repeated claim that *"GPTK/D3DMetal is developer-evaluation-only and can never be redistributed, so an open-source launcher can't ship it"* is **wrong as written**. Apple's own EULA **expressly permits redistribution of `D3DMetal.framework` in its entirety and of any `/redist` component — provided the distribution is NON-COMMERCIAL**, and provided the framework is not split up. The real constraints for a launcher are:
1. **Non-commercial only** — no paid app, no paid tier, arguably no monetised distribution. (This is exactly why CodeWeavers must have a *separate* commercial agreement with Apple to ship D3DMetal in the €74 CrossOver, and why Apple's own GPTK page name-checks "products (like **CrossOver** from CodeWeavers)".)
2. **Apple-branded hardware only** (fine for this project).
3. The *use* grant (§2A(i)) is framed as "developing, testing, or evaluating video games" — a launcher whose purpose is to *play* a shipped game sits outside the stated purpose of the **use** grant even though the **distribution** grant is broader. This is the genuine legal grey zone; flag it to counsel, don't hand-wave it. (Assessment, not a quoted term.)

**Evidence that third parties do in fact redistribute it:**
- **Gcenx** publishes complete GPTK binary tarballs on GitHub: `Game-Porting-Toolkit-3.0-3` (2026-03-03), installable via `brew install --cask game-porting-toolkit` from the `Gcenx/homebrew-wine` tap, with release text *"please ensure you comply with Apple's License.pdf for D3DMetal"*. CONFIRMED — <https://github.com/Gcenx/game-porting-toolkit/releases>, <https://github.com/Gcenx/homebrew-wine/blob/master/Casks/game-porting-toolkit.rb>
- Sikarugir ships D3DMetal as a toggle and mirrors the licence. CXPatcher/Procyon inject D3DMetal/GPTK4 into CrossOver.
- Sikarugir's README states the practical rule plainly: *"Apples D3DMetal commonly refered to as GPTK is closed source and has a restrictive license, **it can not be used for commercial ports**, that's not the case for all other renders."* CONFIRMED.
- Apple's own Wine part of GPTK is **LGPL-2.1 CrossOver 22.1.1 source** (`crossover-sources-22.1.1.tar.gz`), so the Wine half is freely redistributable — only D3DMetal is encumbered. CONFIRMED — <https://github.com/apple/homebrew-apple/blob/main/Formula/game-porting-toolkit.rb>

**Secondary/backstop restriction:** anything pulled from developer.apple.com is also governed by the **Apple Developer Agreement (20250318)**: *"you may only download one (1) copy of the Content… You shall not modify, translate, reproduce, distribute, or create derivative works of the Content"* (§7) and Pre-Release Materials may not be "modif[ied], network[ed], rent[ed], lease[d], transmit[ted], sold, or loan[ed] … in whole or in part" (§6A). CONFIRMED — <https://developer.apple.com/support/downloads/terms/apple-developer-agreement/Apple-Developer-Agreement-20250318-English.pdf>. Where this conflicts with the GPTK SLA, the GPTK SLA is the software-specific licence accompanying the materials; §6A of the ADA itself defers to "the license agreement accompanying such materials". A launcher that tells the user to download the DMG themselves avoids the whole question.

---

## 3. Whisky — dead, and the author said why

- **Repository archived by the owner on 2025-05-11; now read-only.** GPL-3.0, 15.1k stars, 434 open issues. CONFIRMED — <https://github.com/Whisky-App/Whisky>
- Maintenance notice (last changed **2025-04-09**, commit f157e66): <https://docs.getwhisky.app/maintenance-notice>. CONFIRMED. The author, **Isaac Marovitz**, wrote (verbatim):
  > *"Whisky is no longer actively maintained. WhiskyWine will no longer be receiving any further updates. We will not be upgrading to Wine 8+, and fixes for specific apps and games, like Steam, will not be produced."*
  > *"I lost interest in the project. Running it is incredibly time-consuming, and as I'm still a student and also not being paid for work on Whisky it becomes hard to justify working on it if I no longer enjoy it."*
  > *"Whisky, in my opinion, has not been a positive on the Wine community as a whole. My original goal for the project was to be 'engine' agnostic … That all changed when GPTK came out at WWDC."*
  > *"Without CodeWeavers there would be no Wine on Mac. There would be no GPTK. Hell, even Rosetta would likely be more restricted as many of the extensions added in recent months were only added due to pressure from Mac gamers. The revenue from CrossOver is what keeps Wine on Mac alive."*
  > *"Whisky is based on CrossOver, but we don't produce any bespoke fixes … the amount that Whisky as a whole contributes to Wine is practically zero. This is not a fair trade, and continuing this parasitic relationship could easily harm CrossOver's continued profitability … **TLDR; Whisky harms Wine on Mac.**"*
  > *"How do I play my games then?" → **"buy CrossOver."***
- Technical baseline it froze at: **Whisky was built on CrossOver 22.1.1 Wine + Apple's GPTK**, credits msync, DXVK-macOS (Gcenx), MoltenVK, "D3DMetal by Apple". Requires Apple Silicon + macOS 14+. CONFIRMED — <https://raw.githubusercontent.com/Whisky-App/Whisky/main/README.md>
- **>>> CONTRADICTION <<<** The common assumption that Whisky died for *legal* reasons (Apple/CodeWeavers pressure) is false. The author explicitly says *"There's no conspiracy"* and that he receives no payment from CodeWeavers beyond a small affiliate commission. It was burnout + an ethical judgement about free-riding on CrossOver.

---

## 4. Live alternatives — maintenance status as of 2026-08-23

| Project | Status | Last activity | Notes | Source |
|---|---|---|---|---|
| **CrossOver 26.3.0** | **Actively maintained, commercial** | 2026-07-21 | The reference implementation; €74 | codeweavers.com/crossover/changelog |
| **Kegworks → renamed "Sikarugir"** | **MAINTAINED** (`Kegworks-App/Kegworks` now 301-redirects to `Sikarugir-App/Sikarugir`) | repo pushed 2026-08-04; 3.5k stars | Wineskin successor. macOS 14+. **Requires Rosetta 2** (`softwareupdate --install-rosetta`). Backends: WineD3D (default, ≤DX11), VKD3D (limited DX12), **D3DMetal toggle (DX11/12 via Metal, Apple Silicon)**, **DXMT toggle (DX10/11 via Metal)**, **DXVK toggle (DX10/11 via Vulkan)**, D9VK (dead). Install: `brew install --cask Sikarugir-App/sikarugir/sikarugir` | <https://github.com/Sikarugir-App/Sikarugir> |
| **Heroic Games Launcher** | **MAINTAINED** | v2.22.1, 2026-08-09; 12k stars; GPL-3.0 | macOS 14+. On macOS it plays games "using Crossover" and pulls **Gcenx GPTK**, Gcenx wine-staging/winecx, **DXVK-macOS**, **DXMT**. README states *"Play Epic games online [AntiCheat on macOS and on Linux depends on the game]"* | <https://github.com/Heroic-Games-Launcher/HeroicGamesLauncher> |
| **Gcenx wine builds** (`macOS_Wine_builds`, official WineHQ macOS packages) | **MAINTAINED** | **Wine 11.15, 2026-08-08** | Built `--build=x86_64-apple-darwin --enable-archs=i386,x86_64`, i.e. **x86-64 + i386 only → Rosetta 2 required on Apple Silicon**. Built `--with-vulkan`, runtime deps include **moltenvk + vulkan-loader**; `--without-opengl`. `brew install --cask wine-stable` | <https://github.com/Gcenx/macOS_Wine_builds> |
| **Gcenx `game-porting-toolkit`** | **MAINTAINED** | GPTK 3.0-3, 2026-03-03 | Prebuilt GPTK (wine + D3DMetal) tarball + Homebrew cask; `depends_on macos: :sonoma`, cask declares `requires_rosetta`, ships `wine64` **and `wine64-preloader`** | <https://github.com/Gcenx/game-porting-toolkit> |
| **CXPatcher** | **WINDING DOWN** — "Soon to be replaced by **Procyon**" | v0.7.1, 2026-03-21 (for CrossOver 26.x) | Patches a *user-supplied* CrossOver with newer DXVK / D3DMetal(GPTK) / MoltenVK / DXMT / GStreamer. Voids CodeWeavers support. Author's note: *"for new updates the patcher project has been moved to Procyon … check Procyon latest pre-release for GPTK4"* | <https://github.com/italomandara/CXPatcher> |
| **Procyon** (CXPatcher successor) | **ACTIVE, pre-release** | PRE5, 2026-08-17; created 2026-02-06; GPL-3.0 | Steam launcher for macOS on top of CrossOver; per-game graphics/Vulkan backend config; **ships GPTK3 *and* GPTK4 (D3DMetal 4 beta2)**; MoltenVK experimental builds that run Doom 2016/Eternal; *"can run 32bit games much faster thanks to x87 via rosettaX87"* | <https://github.com/italomandara/Procyon/releases> |
| **Mythic** | **SEMI-DORMANT** | last release **v0.6.0, 2025-12-27**; last push 2026-03-09; 1.4k stars; GPL-3.0 | Self-described: *"open-source macOS game launcher … through a custom implementation of Apple's Game Porting Toolkit"*. Not archived, but ~5 months without commits and ~8 without a release | <https://github.com/MythicApp/Mythic> |
| **Porting Kit** | **UNKNOWN / LIKELY stale** | site copyright still reads **"Copyright © 2019 Porting Kit"** and the games list is JS-rendered (couldn't verify build dates) | Wineskin/CrossOver-based wrapper installer | <https://portingkit.com/> |
| **DXMT** (3Shain, D3D11/10 → Metal) | **VERY ACTIVE** | **v0.80, 2026-04-23**; pushed 2026-08-21 | Licence is `NOASSERTION`/"Other" on GitHub — check before bundling | <https://github.com/3Shain/dxmt> |
| **DXVK-macOS** (Gcenx fork) | **FROZEN at 1.10.3** | last release **v1.10.3-20230507-repack (2024-07-23)**; repo pushed 2026-08-08 | The macOS DXVK line never moved past 1.10.x, while upstream DXVK is at **3.0.2 (2026-07-17)** | <https://github.com/Gcenx/DXVK-macOS>, <https://github.com/doitsujin/dxvk/releases> |
| **wine-msync** (marzent) | Stable/idle | last push 2024-08-13; LGPL-2.1 | The MSync bundled in CrossOver ≥23.7.0 | <https://github.com/marzent/wine-msync> |
| **winetricks-based DIY** | Repo reachable, status **UNKNOWN** (not verified in depth in the time available) | — | Works against any wine prefix incl. Gcenx builds | <https://github.com/Winetricks/winetricks> |

---

## 5. Graphics backends for a Vulkan-capable game

**What actually exists on Apple Silicon Wine in 2026 (CONFIRMED unless noted):**

| Path | What it is | Where it ships | Reality check |
|---|---|---|---|
| **D3DMetal** | Apple: **D3D11 + D3D12 → Metal**, plus `nvngx-on-metalfx` (DLSS→MetalFX) | CrossOver 26 (v3.0), GPTK 3.0/4, Sikarugir toggle, Procyon | Proprietary, non-commercial redistribution only, x86-64 binary under Rosetta. **This is what CodeWeavers' own CS2 tip tells you to use.** |
| **DXMT** | 3Shain: **D3D10/11 → Metal** | CrossOver 25+ (v0.72 in CX26), Sikarugir, Heroic | Open-ish, fast-moving (v0.80) |
| **DXVK + MoltenVK** | **D3D9/10/11 → Vulkan → Metal** | CrossOver (DXVK in EULA Appendix A; last named bump 1.10.3), Sikarugir toggle, DXVK-macOS | Two translation hops; macOS fork stuck on 1.10.3 |
| **vkd3d (+MoltenVK)** | **D3D12 → Vulkan → Metal** | CrossOver 26 ships **vkd3d 1.18**; Sikarugir "limited DX12" | Generally beaten by D3DMetal for D3D12 on Metal |
| **wined3d** | D3D → OpenGL/Vulkan inside Wine | Sikarugir default | Wine 11.0: the Wine **Vulkan renderer for wined3d is "not yet at parity with the GL renderer, and is therefore not yet the default"** (`WINE_D3D_CONFIG` / `Direct3D` registry key, `renderer=vulkan`) — <ANNOUNCE.md, wine-11.0> |
| **Native Vulkan in Wine → MoltenVK** | For a game that itself renders with Vulkan (CS2 has a Vulkan renderer on Linux) | Gcenx wine builds are configured `--with-vulkan` with `moltenvk`+`vulkan-loader` runtime deps; CrossOver bundles MoltenVK | The most direct path in principle; see gaps below |

**MoltenVK status — this CONTRADICTS the stale "MoltenVK is stuck on Vulkan 1.2" assumption:**
- **MoltenVK 1.3.0 (2025-04-27) added Vulkan 1.3; MoltenVK 1.4.0 (2025-08-20) added Vulkan 1.4.** Latest release **1.4.2 (2026-07-24)**, 1.4.3 in development. CONFIRMED — <https://github.com/KhronosGroup/MoltenVK/blob/main/Docs/Whats_New.md>
- Wine 11.0 supports **Vulkan API 1.4.335**. CONFIRMED (ANNOUNCE.md).
- So the Vulkan *version* objection is dead. The remaining objections are **feature**-shaped:

**MoltenVK feature gaps that matter (CONFIRMED from source, `MoltenVK/MoltenVK/GPUObjects/MVKDevice.mm`, main branch, Aug 2026):**
- **Geometry shaders: NOT supported.** `_features.geometryShader` is never set true; under the comment `// Unsupported features - set to zeros generally` the driver reports `maxGeometryShaderInvocations = 0`, `maxGeometryInputComponents = 0`, `maxGeometryOutputComponents = 0`, `maxGeometryOutputVertices = 0`, `maxGeometryTotalOutputComponents = 0`. `multiviewGeometryShader = false`.
- **Transform feedback (`VK_EXT_transform_feedback`): NOT implemented.** The only references are `transformFeedbackPreservesProvokingVertex = false` and `transformFeedbackPreservesTriangleFanProvokingVertex = false` in the provoking-vertex extension. (Metal has no equivalent; DXVK needs it for D3D11 stream-output.)
- **Tessellation IS supported** (`_features.tessellationShader = true` on Apple3+/Mac1+, emulated via compute).
- Other documented limitations: `VK_QUERY_TYPE_PIPELINE_STATISTICS` unsupported; `VkAllocationCallbacks` ignored; PVRTC upload restrictions; MoltenVK does not load Vulkan layers itself. `logicOp`, `wideLines`, `provokingVertexLast` only with `useMetalPrivateAPI`. Sources: <https://github.com/KhronosGroup/MoltenVK/blob/main/Docs/MoltenVK_Runtime_UserGuide.md>, MVKDevice.mm.
- Note: **CrossOver 23.0.0 changelog claims "Initial support for geometry shaders and transform feedback"** — i.e. CodeWeavers works around these gaps at the Wine/DXVK level rather than in MoltenVK. CONFIRMED (changelog); how complete this is: **UNKNOWN**.

**Practical ranking for a D3D11 game on Apple Silicon in 2026 (LIKELY, from vendor defaults + the CS2 tip):** D3DMetal ≥ DXMT > DXVK+MoltenVK > wined3d. For a game with a *native Vulkan* renderer, Wine→MoltenVK is one hop instead of two, but it is the least-trodden path on macOS and Procyon still ships "MoltenVK experimental" custom builds per-game (Doom 2016/Eternal, Detroit: Become Human) rather than one general build — evidence that stock MoltenVK is not yet a turnkey game path. LIKELY.

**Also worth flagging for a multiplayer title (CONFIRMED, DXVK README):** *"Manipulation of Direct3D libraries in multi-player games may be considered cheating and can get your account **banned**. This may also apply to single-player games with an embedded or dedicated multiplayer portion. Use at your own risk."* — <https://github.com/doitsujin/dxvk/blob/master/README.md>. This is DXVK's own policy statement, not Valve's.

---

## 6. Rosetta 2 future — Apple's own words

**CONFIRMED**, from Apple's developer documentation *"About the Rosetta translation environment"* (fetched via the docs JSON API; the HTML page is JS-only):
<https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment>

> **"Rosetta was designed to make the transition to Apple silicon easier, and will be available through macOS 27 — as a general-purpose tool for Intel apps to help developers complete the migration of their apps. Beyond this timeframe, we will keep a subset of Rosetta functionality aimed at supporting older unmaintained gaming titles, that rely on Intel-based frameworks."**

> **"macOS 27 directly integrates support for Intel binary translation, without needing to install Rosetta. This enables support for Intel Linux binaries running in ARM virtual machines (VMs) as well as Intel Linux containers."**

Also from the same page:
- Rosetta translates **AVX and AVX2** but **does not support AVX-512**.
- Rosetta does **not** translate kernel extensions or VM apps that virtualise x86_64.
- x86_64 and arm64 code **cannot be mixed in one process**; translation applies to the whole process and all dynamically loaded modules.

**Risk assessment for an x86-64 Windows-game translation stack (assessment, flagged as such):**
- macOS 26 (now) and macOS 27 (this autumn) are safe. The cliff is **macOS 28 (autumn 2027)**, when general-purpose Rosetta is scheduled to go away.
- Apple's carve-out is *"a subset of Rosetta functionality aimed at supporting older unmaintained gaming titles"*. Wine/CrossOver is an x86-64 **translation host**, not an "older unmaintained gaming title" — whether the carve-out covers it is **UNKNOWN and is the single biggest strategic risk to this whole approach.** Do not plan past macOS 27 on the assumption that it does.
- Mitigating datapoint (LIKELY): the Whisky author asserts *"even Rosetta would likely be more restricted as many of the extensions added in recent months were only added due to pressure from Mac gamers"* — Apple has been actively adding gaming-motivated Rosetta features (<https://docs.getwhisky.app/maintenance-notice>).
- macOS 27 *gaining* built-in Intel translation for Linux VMs/containers is a hedge worth studying: an Intel-Linux container running Proton is an entirely different architecture for this project than Wine-on-macOS. Not researched further here — **UNKNOWN**.

**Is there an ARM64 Windows path (Wine ARM64EC)? Yes, and it is real — CONFIRMED** from the Wine 10.0 release announcement (<https://github.com/wine-mirror/wine> tag `wine-10.0`, `ANNOUNCE.md`):
> *"The **ARM64EC** architecture is fully supported, with feature parity with the ARM64 support."*
> *"Hybrid ARM64X modules are fully supported… All of Wine can be built as ARM64X by passing the `--enable-archs=arm64ec,aarch64` option to configure."*
> *"The 64-bit x86 emulation interface is implemented. This takes advantage of the ARM64EC support to run all of the Wine code as native, with only the application's x86-64 code requiring emulation. **No emulation library is provided with Wine at this point**, but an external library that exports the emulation interface can be used, by specifying its name in the `HKLM\Software\Microsoft\Wow64\amd64` registry key. The **FEX emulator** implements this interface when built as ARM64EC."*

**But the blocker is the macOS page size — CONFIRMED, Wine 10.0 ANNOUNCE.md:**
> *"It should be noted that **ARM64 support requires the system page size to be 4K, since that is what the Windows ABI specifies. Running on kernels with 16K or 64K pages is not supported at this point.**"*

Apple Silicon macOS uses **16K** pages. Wine 11.0 took a first step (ANNOUNCE.md, wine-11.0):
> *"On ARM64, there is support for **simulating a 4K page size on top of larger host pages (typically 16K or 64K)**. This works for simple applications, but because it is not possible to completely hide the differences, **more demanding applications may not work correctly. Using a 4K-page kernel is strongly recommended.**"*

Net: **ARM64EC Wine + FEX is the credible post-Rosetta escape route, but as of Wine 11.0 the 16K-page simulation is explicitly "simple applications" only** — a Source 2 FPS is not a simple application. Status for CS2 specifically: **UNKNOWN / not demonstrated.**

---

## 7. wine64 on Apple Silicon: how x86-64 Windows code actually runs

- **The mechanism:** Wine on macOS is compiled as an **x86-64 (and i386) Mach-O binary** and the whole `wine`/`wineserver` process tree is executed by **Rosetta 2**; Windows PE code is then run by Wine as ordinary x86-64 code inside that already-translated process. There is no Windows-ARM64 involved. Evidence: Gcenx's official WineHQ macOS packages configure `--build=x86_64-apple-darwin --enable-archs=i386,x86_64` (<https://github.com/Gcenx/macOS_Wine_builds>), the Homebrew GPTK cask declares `requires_rosetta` and installs `wine64` / `wine64-preloader` (<https://github.com/Gcenx/homebrew-wine/blob/master/Casks/game-porting-toolkit.rb>), Sikarugir tells Apple Silicon users to run `/usr/sbin/softwareupdate --install-rosetta --agree-to-license`, and Apple's own D3DMetal port is `supported_archs x86_64`. CONFIRMED.
- Consequence of Apple's rule that a process is either wholly x86-64 or wholly arm64: **every part of the stack — Wine, D3DMetal, DXVK, MoltenVK-in-the-prefix — must be x86-64.** You cannot have native-ARM Wine calling an x86 D3D layer or vice versa. CONFIRMED (Apple docs, §6).
- **`wine64` no longer exists in Wine 11.** From ANNOUNCE.md (wine-11.0): *"The `wine64` loader binary is removed, in favor of a single `wine` loader that selects the correct mode based on the binary being executed… The 32-bit version can then be launched with an explicit path, e.g. `wine c:\windows\syswow64\notepad.exe`."* Also: new WoW64 is now fully supported and **pure 32-bit prefixes (`WINEARCH=win32`) are deprecated and unsupported in new WoW64 mode**; you can force new WoW64 on a 64-bit prefix with `WINEARCH=wow64`. Any script or doc that hardcodes `wine64` is Wine ≤10 era. CONFIRMED.
- **The preloader:** from ANNOUNCE.md (wine-10.0), macOS section: *"When building with **Xcode >= 15.3** on macOS, **the preloader is no longer needed**."* Older/other builds still ship `wine64-preloader` (the Gcenx GPTK cask still installs it, because GPTK's Wine is the CrossOver 22.1.1 tree built with an old pinned compiler). So preloader breakage is a **legacy-toolchain** problem, not an inherent macOS one. CONFIRMED.
- Other Wine 10/11 macOS-relevant items (CONFIRMED, ANNOUNCE.md): syscall emulation for apps doing direct NT syscalls is supported **on macOS Sonoma and later** (Wine 10.0); **on macOS the `%gs` register is swapped in the syscall dispatcher** to avoid Windows-TEB vs macOS-thread-descriptor conflicts (Wine 11.0); thread priority changes implemented on macOS (Wine 11.0). NTSync is **Linux-only** (needs kernel ≥6.14) — macOS uses MSync/ESync instead.
- 32-bit x87 performance is a known Rosetta weak spot; Procyon claims *"It can run 32bit games much faster thanks to x87 via **rosettaX87**"* (LIKELY, <https://github.com/italomandara/Procyon>). Not relevant to 64-bit CS2, but relevant to old Source-engine tooling.
- **UNKNOWN:** exact Rosetta-vs-native throughput numbers for Wine on macOS 26, and whether 16K page size causes CS2-specific failures under the x86-64 (Rosetta) path — the Wine 4K-page caveat quoted above applies to *native ARM64 Wine*, not to the Rosetta path, where Rosetta presents the x86 process with the host's 16K pages.

---

## Summary of the four things that should change the plan

1. **D3DMetal CAN legally be shipped by a non-commercial open-source launcher** — Apple's GPTK SLA §2A(iii)+§2C expressly allow redistributing `D3DMetal.framework` in its entirety and `/redist` components, for non-commercial purposes, Apple hardware only. Gcenx/Sikarugir/Procyon already do it. The moment money is involved, you need CodeWeavers' path (a bilateral Apple agreement) instead.
2. **CodeWeavers' own database says CS2 "Runs Well" (4/5) on CrossOver 26.3.0**, and their community tip is a two-line recipe: **Graphics = D3DMetal, Synchronization = MSync**. That is the fastest known-good configuration and the natural baseline to beat.
3. **The Vulkan story is no longer version-blocked** (MoltenVK ships Vulkan 1.4 since 1.4.0/Aug-2025) but is still **feature**-blocked: **no geometry shaders, no transform feedback**, and the macOS DXVK fork is frozen at 1.10.3 while upstream is at 3.0.2.
4. **The clock is Rosetta's.** Apple states general-purpose Rosetta is available *through macOS 27* only, with a residual carve-out for "older unmaintained gaming titles". The entire x86-64 Wine stack is exposed. The only visible successor — ARM64EC Wine + FEX — is blocked on Apple Silicon's 16K page size, with Wine 11.0's 4K simulation explicitly limited to "simple applications".
