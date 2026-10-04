# Soul Sacrifice Delta: working notes

Running log so the process is never lost again. Newest findings are appended under each section.

## The game
- Soul Sacrifice Delta, US cart, content ID `UP9000-PCSA00152_00-SOULSACDELTAUS00`, data version 01.10
- Original working title "Elder Fantasy" (appears in assets; owner holds elderfantasy.com)
- Publisher SIE, developed by Marvelous + Comcept. The archive format (LSPK `.pk`) is the same engine family as Marvelous' Fate/Extella, so Fate modding tools work.

## Folder map (E:\soul sacrifice)
| Path | What |
|---|---|
| `<your-license>.rif` | Cart license (KEEP PRIVATE). Also copied as `sce_sys/package/work.bin` in staging. |
| `decrypted/` | psvpfsparser output: outer PFS layer decrypted. `eboot.bin` + `sce_module/*.suprx` are STILL encrypted SELFs. |
| `decrypted/resource/data/pack/` | 55 archive triples (`.pk`/`.pkh`/`.pfs`) **plus 2019 extractions unpacked in place** |
| `LSPK-Extractor_v3.0/`, `fate-tools/` | Archive extractors used in 2019 |
| `data_fate_extella_ge3.py`, `noesis/` | Noesis plugin for models/textures |
| `vgmstream/`, `foobar2000/`, `music/` | Audio decoding/playback |
| `Extracted models/` | 2019 model/texture exports |
| `port/` | 2026 work: tools, staging, Vita3K storage, notes |

## Shipped vs extracted (2026-10-02)
psvpfsparser ran in the early hours of 2019-09-08; extraction ran that afternoon. File mtimes split perfectly:
- at or before `2019-09-08 01:02` = shipped game: **420 files, 3.17 GB** (list: `port/notes/original_files.txt`)
- after = owner's work: 79,036 files, 3.51 GB. 79,013 are verbatim archive contents; 23 are owner-made
  (Noesis exports, png/tga conversions, renamed copies), listed in `port/notes/owner_derived_files.txt`
- Correction: my first cut at "before 12:00" wrongly included 2 owner-made texture conversions made at 02:31
  (`EF04_EFF_emg140_000_Aout.tga/.png`); removed from staging + Vita3K install on 2026-10-03.
- The 49 `*_motion_set` archives were never extracted in 2019.

> **WARNING:** `port/staging/PCSA00152/resource/` is HARDLINKED to `decrypted/resource/`. Editing a file there
> edits the original. For mods, edit the copy in `port/vita3k-fs/ux0/app/PCSA00152/` (a real copy) or use an overlay.

## Pipeline as rediscovered
1. Dump cart + license (.rif) with a hacked Vita (2019).
2. `psvpfsparser.exe` + the rif = `decrypted/` (PFS layer only).
3. LSPK-Extractor / fate-tools on `.pk` files = loose files in place.
   Extraction order by mtime: `magic_effect` 14:13, `archive` 14:15-14:18, `voice_ue` 15:52-15:54. Probably pktools (Kotcrab fate-tools), possibly LSPK-Extractor.
4. Noesis + `data_fate_extella_ge3.py` (hand-edited `-nobones` variant) for models; GXT textures via Noesis + a QuickBMS script.
5. vgmstream + foobar2000 for audio, exported to mp3 (`music/`).
Full detail: `port/notes/2019-forensics.md`.

## Archive format (confirmed 2026-10-03)
- `.pkh`: big-endian `u32 count`, then 16-byte records `{u32 hash, u32 offset, u32 size, u32 csize}`, sorted by hash.
- hash = CRC-32/BZIP2 (poly 0x04C11DB7, MSB-first, init/xorout 0xFFFFFFFF) of the lowercased relative path.
  Independently re-verified: `magic_effect.pkh` matched 11783/11783 extracted files.
- `.pk`: headerless blob; each member is a zlib stream, or raw when csize is 0 or equal to size.
- `.pfs`: directory tree + string pool with real names (record field names inferred).
- A repacker is therefore simple: zlib each file, CRC the path, sort, write pkh/pk/pfs.

## Level/content formats (from forensics)
- `.scene`: Shift-JIS XML placing enemies/player/gimmicks; `.map`/`.area`: TSV; `quest_param.csv` ties quests to maps/scenes
- `.event` (cutscene XML), `.evep` (episode script), `.chr`, `.efp`, `.msgt`/`.u16` (UTF-16 text tables): readable
- Binary: `.mdl` = `KPKy`, `.mxt`/`.gxt` = `GXT\0` (Vita GXT textures), `.mtb` = `60AE`, `.eff` = `@EFF$`

## Debug menu lead (`resource/config.ini`)
The file is stacked blocks: the dev block first, then retail overrides (the later block appears to win):
```
BootSequence    DebugMenu        <- dev block
DebugCommandOn  true
NoCostMagicAll  false
...
BootSequence    Title            <- retail block
```
`config.ini` is a loose file (not in a pack), so it's trivially editable. TEST: drop the retail block's `BootSequence Title` line
in the Vita3K install copy and see if the dev debug menu still exists in the retail build.

## Engine config flags (`resource/boot_config.ini`)
`FPS 30`, `ResoDown 1`, `PackFileFirst false/true`, `EffectReload true`, `DebugRegionType jp`, `CaptureMode false`, plus commented `ModeTrial`, `ForceDLC`, `ScreenShot`. `PackFileFirst` suggests a loose-file load path, which is the key modding lever to test.

## Vita3K setup (2026-10-02)
- Vita3K continuous build v0.2.1 4115-a366df69 in `port/tools/vita3k`
- `config.yml` `pref-path` = `E:/soul sacrifice/port/vita3k-fs/` (nothing in AppData)
- Firmware: official Sony PUPs in `port/firmware` (3.74 `PSVUPDAT.PUP` md5 f2c7b12f..., font `PSP2UPDAT.PUP` md5 8b5f60b5...), installed via `Vita3K.exe --firmware <pup>`
- Clean game copy: `port/staging/PCSA00152` = shipped files only; `resource/` hardlinked (no extra space), executables + sce_sys real copies, rif copied to `sce_sys/package/work.bin`
- Install + boot: `Vita3K.exe -A "E:/soul sacrifice/port/staging/PCSA00152"`; log in `port/notes/vita3k-first-boot.log`

### Install gotcha (cost one attempt)
Do NOT put `sce_sys/package/work.bin` in the folder. Vita3K then treats it as a raw NoNpDrm dump and tries to
PFS-decrypt it itself (`failed to find files.db` -> "NoNpDrm installation failed, deleting data!").
Our dump is already PFS-decrypted, so the working recipe is:
1. Install the folder WITHOUT work.bin (plain folder install, copies into `vita3k-fs/ux0/app/PCSA00152`).
2. Put the rif at `vita3k-fs/ux0/license/PCSA00152/UP9000-PCSA00152_00-SOULSACDELTAUS00.rif`.
3. Vita3K decrypts eboot.bin/suprx at LOAD time with that license (`modules/module_parent.cpp:300`, `decrypt_fself`).
4. `config.yml`: `initial-setup: true`, `show-welcome: false` or the first-run wizard blocks auto-boot.
5. Boot: `Vita3K.exe -A -r PCSA00152`

### First boot results (2026-10-03)
- eboot decrypts + loads: segment 0 (code) `0x81000000-0x81C4D200` (12.3 MB), segment 1 (data) `0x81C4E000-0x81DD5D00`
- Main module's internal name is **`efg`** (very likely "Elder Fantasy Game"), module NID `0x5F817831`
- Renders the Marvelous AQL splash at a locked 30 FPS, 960x544, Vulkan on RTX 4090
- Reaches save-data check (no save yet, as expected for a first boot)
- Game probes for `resource/data/pack/mount/retail/archive_patch1.pkh`: a patch archive slot (the v1.xx update package, not in the cart dump)
- Game `stat()`s loose files like `app0:/resource/database/gimmick/gm00_07_000_ext.csv`, which confirms the engine looks for loose
  files on disk. That's the modding hook.
- Decrypted ELF extraction: Vita3K app-list right-click -> "Decrypt selfs" writes to `tools/vita3k/cache/decrypted_selfs/PCSA00152`
  (`packages/src/sce_utils.cpp:1096`)

## Decrypted executables (2026-10-03)
- Tool: `port/tools/re/sceutils3/` = Python 3 port of TeamMolecule sceutils (mechanical py2->py3 only). Keys generated from
  Vita3K source by `port/tools/re/make_keys.py` (28 retail keys). Commands in `port/tools/re/README.md`:
  `python tools/re/sceutils3/self2elf.py -i staging/PCSA00152/eboot.bin -o re/elf/eboot.elf -k staging/work.bin`
- Output `port/re/elf/`: eboot.elf (13.25 MB), libc, libfios2, libsmart, libult (.elf)
- eboot.elf: ARM32 LE, type 0xFE00 (SCE exec), LOAD0 `0x81000000` memsz `0xC4D200` R+X, LOAD1 `0x81C4E000` memsz `0x187D00` RW
  (filesz 0x519CC, rest BSS), plus SCE segment 0x6FFFFF01. Matches Vita3K's load log exactly. 26,641 readable strings.
- Middleware: **Havok 2013.2.0-r1** statically linked (374 refs); a few `GFx` strings (Scaleform? unconfirmed).
- `libsmart.suprx` = libSceSmart = SmartAR (AR card feature). PC port can stub it.
- Imports 41 Sce libraries: AppMgr AppUtil Audio Audiodec AvPlayer Camera CommonDialog Ctrl Display Fios2 Gxm Http Ime Kernel
  Motion NearUtil Net NetAdhocMatching NetCtl NpActivity NpBasic NpCommon NpManager NpMatching2 NpMessage NpParty NpScore
  NpSnsFacebook NpTrophy NpTus NpUtility Power PspnetAdhoc Rtc Rudp ScreenShot Smart Ssl Sysmodule Touch Ult.
  That's the HLE surface for a native port; the Np*/Net*/Adhoc/Sns group (~17) is dead online service and stubbable.

## DEBUG MENU CONFIRMED (2026-10-03)
Retail build still contains Marvelous' dev sequence menu. Enable: in the INSTALLED copy
`port/vita3k-fs/ux0/app/PCSA00152/resource/config.ini` change the retail block's `BootSequence Title` to
`BootSequence DebugMenu` (+ `DebugCommandOn true`). Original backed up as `config.ini.orig` next to it.
**Confirm = Circle** (Japanese convention), Cross does nothing in the dev menu.

Screen header: `Revision : 51348  2014-04-02 12:38:57 <developer>`, `Build : Apr 2 2014 13:26:16 EF-BUILD-S6-5$@EF-BUILD-S6`
(EF = Elder Fantasy). `SELECT SEQUENCE MODULE <Main>`:
```
00 Title              06 a developer's personal test map   12 ARMode
01 Quest Select       07 EnemyNpc test map                 13 SaveEditMode
02 TGS Setting        08 CutEvent Select (cutscene viewer)       14 BookEpisode
03 |G| HarpyBattle Walhalla   09 DebugMenu                       15 BookEnding
04 QUEST999 verification map                 10 BootTask         16 BookMenu
05 ELDER DEFAULT MAP  11 Prison
```
Debug-related strings in eboot: `DEBUG MENU`, `SequenceDebugMenu`, `InvincibleMode`, `DrawDebugInfo`, `EndingSkipDebug`,
`DebugQuestBack`, `ControlFlyWarp`, `ControlAliceMapWarp`, `DebugPlayRecord`, `sndx debug service`...

## Gameplay test via automation (2026-10-03)
- `port/tools/vpad.py`: sends Vita buttons to the Vita3K window as scancodes + PrintWindow screenshots.
  e.g. `python tools/vpad.py seq "circle, wait 3000, hold:ls_up:2000, triangle, shot:notes/play/x.png"`
- ELDER DEFAULT MAP: loads into a full 3D field, HUD, sorcerer Lv1. Walk, camera, spells (Chain Punch etc.) all work,
  29-30 FPS, zero new log errors/warnings during play. Screens: `port/notes/play/sheet_gameplay1.png`.
- Visual bug #1: some particle/fog effects render with dark/blocky square artifacts (Chain Punch effect; green mist on
  title screen). Probably one Vita3K effect texture/blend issue. Not a blocker.

## Real quest via debug Stage Select (2026-10-03)
- Dev menu `01 Quest Select` = **Stage Select (1/561)**: filter by chapter/derivation/rank/boss/map, pick quest ID,
  NPC ally count + IDs (default `900000 : Magusar`), toggle quest-clear. `[o] Start  [x] Exit`, L/R or Left/Right to page.
- Stage 1: `q_e0001` "First Quest", chapter 1, derivation e, rank 1, map `ST16A` "Leviathan 1st Floor",
  boss "Hansel and Gretel". This gives the quest-ID -> map-ID mapping directly, useful for level modding.
- Played it: rain/waterfall level renders correctly; spells, shields, melee trails, fire particles, spell-swap menu all
  work, 30 FPS, **zero errors** in combat. Screens: `port/notes/play/sheet_quest1.png`, `sheet_fight.png`.
- Log probes for loose `resource/database/boss/message/us/bmv_eb731_us.msgt` and `gimmick/gm00_*_ext.csv`: the engine
  checks loose paths under `resource/database/`. That's the place to try a loose-file mod first.
- To return to normal boot: copy `config.ini.orig` over `config.ini` in the installed copy (or pick `00 : Title`).
- Vita3K test audio is muted: `audio-volume: 0` in `port/tools/vita3k/config.yml` (restore 100 to play with sound).

## LOOSE-FILE MODDING CONFIRMED (2026-10-03)
Recipe (no repack, no re-encryption):
1. In the INSTALLED `resource/boot_config.ini`, change the retail block's `PackFileFirst true` to `false`
   (backup `boot_config.ini.orig`). With `true`, the engine only reads loose files when a path is missing from every archive.
2. Place the edited file at its archive-internal path under `ux0/app/PCSA00152/`
   (archive member `resource/boot/us/quest_name_text_us.u16` -> `ux0/app/PCSA00152/resource/boot/us/quest_name_text_us.u16`).
3. Boot. Proof: renamed `q_e0001` "First Quest" -> "Elder Fantasy"; Stage Select shows "Elder Fantasy" and the log shows
   `sceIoOpen app0:/resource/boot/us/quest_name_text_us.u16`. Screenshot `port/notes/play/41_mod_stageselect.png`.
- Text tables (`.u16`/`.msgt`): UTF-16LE + BOM, header `EF_MESSAGE_TEXT	20111110	<n>`, rows `id	English	Japanese		timestamp`, CRLF.
  Row length is free (TSV), so no fixed-size string constraints.
- The engine also probes `whitepage_quest_name_text_us.u16` (an optional override table).
- Real hardware: same files via rePatch (`ux0:rePatch/PCSA00152/resource/...`, including the edited boot_config.ini).
- Alternative channel: the engine opens `resource/data/pack/mount/retail/archive_patch1.pkh/.pk` at boot (the official patch slot).
  We know the pk/pkh format, so a mod could ship as a patch archive with PackFileFirst left at retail default. Untested.

## Ghidra workspace (2026-10-03)
- `port/re/ghidra/SoulSacrifice.gpr`. Open with `port/re/ghidra/gui.bat` (sets JAVA_HOME + redirects Ghidra home under port/).
- Ghidra 12.1.3 + VitaLoaderRedux 1.09 (newest VLR build; Ghidra 12.1.4 not supported yet), Temurin JDK 21.0.12.1, all under `port/tools/`.
  URLs + SHA-256 in `port/re/ghidra/README.md`.
- Auto-analysis 845 s; **26,392 functions**; module `efg`, fingerprint 0x5F817831, `module_start` 0x817C7160.
- NIDs: VLR's built-in DB covers only kernel modules. Applied the vita-headers FW 3.60 DB (`re/ghidra/niddb`, commit e66ebe90)
  -> **713/713 imports named across 51 Sce libraries** (`imports.csv`). Biggest groups: SceGxm 116, SceLibc 78,
  SceCommonDialog 49, SceLibKernel 35, SceNet 30. That's the HLE surface a native port must implement or stub.
- Gotchas: Ghidra's application.log still goes to AppData; don't put spaced paths in JAVA_TOOL_OPTIONS.

## FIRST LEVEL EDIT CONFIRMED (2026-10-03)
- Quest wiring: `resource/boot/quest_param.csv` (Shift-JIS CSV, 561 rows). `q_e0001` -> MAP `ST16A`, PlayerInfo
  `bu_pla_16a_e0100`, Gimmick1 `bu_gim_16a_e0100`, EnemyInfo `q_e0001`, bosses `ch7302`/`ch7312`, NPC `ch0001_01`,
  BGM `bgm_start11`/`bgm_leviathan`/`bgm_result`.
- Scenes: `resource/data/scene/<name>.scene` = Shift-JIS XML `<MapSetData>` with `<anyType type="PlayerInfo|EnemyInfo|EventPoint|EventBox">`
  nodes (position/rotation/scale). q_e0001.scene: 2 EnemyInfo, 10 EventPoint, 2 EventBox; commands `BossAppearCheck`
  (zako_kill_num, boss_appear_time=10, b_fnc_fi=Stg00BossAppearEvent), `EnemyGeneratorBox`, `LocalFlagCheck`.
- Edit: moved both PlayerInfo spawns from ~(22,0,10) facing -135 to (0,0,0)/(1.5,0,1.5) facing +45, as a loose file at
  `ux0/app/PCSA00152/resource/data/scene/bu_pla_16a_e0100.scene`. In-game spawn moved as expected
  (`port/notes/play/sheet_spawnmod.png`), log confirms the loose scene was opened. New levels = new scene XML + a quest_param row.

### Active mods in the Vita3K install (revert by deleting the loose file / restoring .orig)
- `resource/config.ini` (DebugMenu boot; `.orig` saved)
- `resource/boot_config.ini` (PackFileFirst false; `.orig` saved)
- `resource/boot/us/quest_name_text_us.u16` (q_e0001 -> "Elder Fantasy")
- `resource/data/scene/bu_pla_16a_e0100.scene` (moved spawn)

## Retail flow (2026-10-03)
- Boot logos (SCE presents, Marvelous AQL) -> title -> NEW GAME / CONTINUE / DOWNLOAD. Main menu confirm = Cross.
- NEW GAME -> Vita system save dialog (emulated by Vita3K): pick slot -> "Do you want to save?" defaults to **No**
  (press Right then Cross) -> "Saving complete". Files: `vita3k-fs/ux0/user/00/savedata/PCSA00152/{datag0001.bin, SlotParam_1.bin, system.bin, system.bak}`.
- Prologue: narration text card then FMV (mp4 via SceAvPlayer). Works.
- With a save present, the main-menu cursor defaults to CONTINUE (enabled).
- **DOWNLOAD hangs**: it calls `sceNetCheckDialogInit` (unimplemented in Vita3K) and waits forever. Dead feature anyway
  (Sony's store is gone); a PC port should remove it. UNVERIFIED: whether any DLC content ships on the cart.
- Save/load round trip VERIFIED: fresh boot -> CONTINUE -> Load dialog (also defaults to **No**; Right then Cross)
  -> "Loading complete" -> resumes at prologue (the save was made before the prologue). Only errors: probes of empty slots 2/3.
- Boss test (q_e0001 via Stage Select): ~25 s in, several insectoid enemies engaged the player; combat, hit reactions and
  effects all fine, 30 FPS, no real errors. `eb730_motion_set` loaded, and eb730 matches the quest's `Eb730AppearPoint`
  boss-spawn EventPoints, so these were likely the boss pair (UNCONFIRMED by name on screen). Screens: `port/notes/play/sheet_boss.png`.
- With `PackFileFirst false` the log fills with `stat_file Missing file` lines: the loose-first probe for every asset
  before falling back to the pack. Expected, harmless.

## Visual bug #1 FIXED (2026-10-03)
Blocky squares in fog/particle effects: fixed by Vita3K `high-accuracy: true` (config.yml). A/B on the main-menu mist:
baseline shows rectangular blocks; 3 high-accuracy frames are clean; still 30 FPS. `disable-surface-sync: false` did
NOT help (reverted). Evidence: `port/notes/play/ab_highacc_zoom.png`. Baseline config saved as `config.yml.baseline`.
- Vita3K also supports `import-textures`/`export-textures`: an HD texture-replacement pack is a possible mod route.

## Archive packer (2026-10-03)
- `port/tools/pk/pktool.py` (`unpack` / `pack [--like ref]` / `verify`); spec in `port/tools/pk/README.md`.
- zlib settings that match retail: `zlib.compressobj(9, DEFLATED, 15, 8, 0)`; members 32-byte aligned, zero gaps.
- `.pfs`: 24-byte dir rows (name idx, parent, first child dir, child dir count, first file, file count) + string offset
  table + NUL-terminated name pool; no file records (file data located by hashing its full path into the pkh).
  Dir rows are depth-first pre-order with sorted children in contiguous blocks.
- Byte-identical round trip independently re-verified (md5) for magic_effect + eb802_motion_set, with and without --like.
- Main `archive` has 50,821 members, all named by its pfs (the forensics ~67k count included other archives).

## PATCH-ARCHIVE MOD CHANNEL CONFIRMED (2026-10-03), the preferred way to ship mods
- With retail `PackFileFirst true` restored and the loose quest-name file moved away (to `port/scratch/disabled_loose_mods/`),
  installed `archive_patch1.{pk,pkh,pfs}` (built by pktool, 1 member: modded `resource/boot/us/quest_name_text_us.u16`) into
  `ux0/app/PCSA00152/resource/data/pack/mount/retail/`. Stage Select shows "Elder Fantasy"; log shows archive_patch1.pkh/.pk opened.
- So `archive_patch1` OVERRIDES `archive` (the game's own update mechanism). A mod = 3 files, no config edits, retail archives untouched.
- Real hardware: the same 3 files via rePatch (`ux0:rePatch/PCSA00152/resource/data/pack/mount/retail/`). Untested on hardware.
- Build: `python port/tools/pk/pktool.py pack <dir-with-resource/...> <out>/archive_patch1`
- Install state now: boot_config.ini = retail (.orig), config.ini = DebugMenu, archive_patch1 installed, loose scene mod still
  present but inert (PackFileFirst true means the archived scene wins).

## Recompilation design study (2026-10-03): `port/re/recomp/DESIGN.md`
Measured (read-only Ghidra on a copy; scripts + raw output in `port/re/recomp/measure/`):
- 3,592,527 instructions, **99.85% Thumb-2**; ARM mode = 27 small functions (~22 KB).
- exidx table lists **34,094 function starts** (independently re-derived: (0x81B3011C-0x81AED7AC)/8). Ghidra found
  24,984, missing 8,436. exidx = an authoritative function list.
- 40,166 register calls: ~15.4k are really direct calls (r12 veneers); **24,764 true indirect calls** (vtables/callbacks),
  all landing on exidx starts. 1,312 tbb/tbh jump tables (97.7% resolved).
- **FP/SIMD 631,656 instr (17.6%)**: 241k NEON, 188k VFP. The biggest correctness risk (Havok physics).
- No C++ exceptions, no svc, no setjmp; 787 ldrex/strex, 74 TLS (TPIDRURO) reads, 2,367 IT blocks.
- 39 thread-creation sites (about half network, stubbable); libult used by 2 subsystems (model-draw jobs + one SCE runtime).
- sceDisplaySetFrameBuf is called only from the GXM display callback, so the first frame needs indirect calls to work.
Recommendation: **hybrid**. A Vita3K fork as runtime + an AOT Thumb-2 -> C++ recompiler called through an
address->function table, with dynarmic as fallback AND differential-test oracle; keep Vita3K's GXM->Vulkan renderer.
Licensing: the Vita3K-derived runtime = GPL (2.0-or-later, so GPL-3.0 like UnleashedRecomp); the recompiler tool can be MIT.
Generated code is never distributed, so users compile locally (bundled toolchain).
M1 gate: boot to AQL splash with the AOT DLL loaded, >=80% of executed instructions native, 0 differential mismatches over 1000 frames.
No existing PS Vita recompilation project found.

## Build toolchain on this machine
VS 2022 Build Tools at `C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools` with MSVC 14.41.34120;
CMake + Ninja bundled under `Common7\IDE\CommonExtensions\Microsoft\CMake\`. No clang-cl, no zig.

## Tooling note: multiple Vita3K instances
`port/tools/vpad.py` takes `VPAD_EXE=<substring of exe path>` (e.g. `tools\vita3k` prebuilt, `build\vita3k` self-built)
and refuses to guess if several game windows are open; it prints the exe path it captured. Kill emulators by PID, never by image name.

## Vita3K built from source (2026-10-03), needed for the netplay client
- `port/build/vita3k/bin/Release/Vita3K.exe` (v0.2.1 1-a366df6). Recipe + gotchas: `port/build/BUILD.md`.
- CI `windows-x64` recipe: preset `ci-windows-msvc` (Ninja Multi-Config), Release, vcpkg triplet `x64-windows-static-md`,
  Qt 6.11.0 msvc2022_64 (via the CI-pinned aqtinstall; stock 3.3.0 fails), MSVC 14.41. ~7 min vcpkg + ~2.5 min compile.
  Portable installs: `port/tools/{vcpkg, vcpkg-binary-cache, aqtvenv, qt}`.
- One source patch for MSVC 14.41 (C2338 incomplete type): `vita3k/emuenv/include/emuenv/state.h`
  `RendererPtr renderer{};` -> `RendererPtr renderer;`. Only diff in the tree.
- Configure with empty `-DCMAKE_C_COMPILER_LAUNCHER= -DCMAKE_CXX_COMPILER_LAUNCHER=` (no sccache).
- Gate: boots PCSA00152 into the dev menu at 30 FPS, 0 critical errors; screenshot `port/build/m10_boot.png` captured by
  the self-built process's window handle.

## Mod kit (2026-10-03): `port/modkit/`
- `ssmod.py` new/extract/text get|set/validate/build/install/uninstall; modder reference `README.md`; full walkthrough `GUIDE.md`;
  example `mods/elder_fantasy_demo`; `tools/boot_test.py` automated boot + screenshot.
- **Patch slots: only `archive_patch1` is ever opened.** archive_patch0 is ignored alone or alongside patch1 (log shows no open);
  eboot also names patch2/3 and `trial/archive_patch1`. Evidence `port/notes/modkit/slot0_only.png`, `slot0_and_1.png`.
- Verified by me: demo rebuild byte-identical to the installed patch; the validator rejects extra columns and a missing BOM,
  and build refuses invalid mods; the GUIDE section 5/6 commands run verbatim.
- My fixes: bare table names without extension; UTF-8 stdout (Japanese rows crashed on cp1252); paths via env
  `SS_APP` (installed game; default port/vita3k-fs/...) and `SS_DUMP` (originals; default = SS_APP's retail archives).
- Open: mods currently contain whole game files, so sharing them redistributes game data. Need a recipe/diff format
  applied to the player's own originals.

## Recipe mods + brand-new quest (2026-10-03)
- `port/modkit/recipe.py` (wired into ssmod): `recipe/text.tsv` (table, id, english), `recipe/csv.tsv` (set / clone rows of
  quest_param.csv by column name), `recipe/scene.json` (set fields, append nodes, create new scenes). Edits are textual,
  so untouched bytes stay identical. `export-recipe` converts a files/ mod and proves byte-identity; `pack-share` zips
  only mod.json + recipe/ + declared original_files and refuses retail paths.
- Verified by me: elder_fantasy_demo (files) and elder_fantasy_recipe (recipe) build IDENTICAL archive_patch1 (pk/pkh/pfs);
  pack-share refuses the files/ mod (names both game files) and zips new_quest_demo as 4 small recipe files.
- **A quest = 1 quest_param.csv row + quest_name_text_<lang> + quest_purpose_text_<lang> rows.** Nothing else in
  resource/boot or resource/database references quest IDs. `quest_purpose_text_*` tables are comma-separated, not TSV.
- `mods/new_quest_demo` adds q_x0001 (clone of q_e0001 with its own modder-authored spawn scene bu_pla_x0001):
  Stage Select shows **562/562**, ID 561 `q_x0001` "Elder Fantasy: New Trial"; it loads and the player spawns at the new
  point (seen by me: `port/scratch/newquest/sheet_newquest.png`). Stage Select drops fast inputs (~350 ms between presses).
- Install state after the tests: archive_patch1 = elder_fantasy_demo build (md5 a88348c0...), no emulator running.

## Repository (2026-10-03)
Public: https://github.com/loktar00/soul-sacrifice-preservation (54 files, code + docs only).
`.gitignore` is an ALLOWLIST: new folders stay untracked until added on purpose. Never commit: dump/archives/ELFs/Ghidra DB,
the .rif, firmware PUPs, `port/tools/re/sceutils3/keys.py` (generated Sony keys), logs (they contain the zRIF), `mods/*/files/`.
Pre-push scan: zRIF/klicensee, Sony key prefixes, tokens, AI attribution (positive-controlled against the log and keys.py).
