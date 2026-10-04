# 2019 extraction forensics - Soul Sacrifice Delta (PCSA00152)

All read-only. Evidence tags: CONFIRMED = seen in bytes/code/timestamps, INFERRED = best reading.
Supporting lists in this folder: `original_files.txt`, `owner_derived_files.txt`, `shipped_inside_archives.txt`.

## 1. Original vs extracted

**Rule (CONFIRMED): mtime. Anything under `decrypted/` modified after 2019-09-08 01:03 is an owner artefact; everything at or before 01:02 (psvpfsparser output) shipped on the cartridge.**
The split is clean: no mtimes between 01:03 and 02:31, and the 2018-06-30 `sce_sys/param.sfo` + `clearsign` sit in the original group.

| Group | Files | Bytes |
|---|---|---|
| Shipped, physical files (psvpfsparser output, mtime <= 01:02) | 420 | 3,168,505,885 (2.95 GiB) |
| - of which `resource/data/pack/` triples (55 x pk/pkh/pfs) | 165 | 2,486,222,684 |
| - of which everything else (eboot, suprx, sce_sys, icons, config ini, pem...) | 255 | 682,283,201 |
| Owner extraction (mtime 14:13 onward) | 79,036 | 3,508,520,003 (3.27 GiB) |

Extraction timeline (all 2019-09-08, local time of the owner's PC):
- 14:13 `memory/magic_effect/` (11,783 files; four archives magic_effect, _1, _2, _3 merged into one folder)
- 14:15-14:18 `mount/retail/archive/` (50,813 files)
- 15:52-15:54 `mount/retail/voice_ue/` (16,417 files)
- Conversion artefacts: 02:31 (2: `ef04_eff_emg140_000_aout.png/.tga`), 16:38-16:41 (6: `model/NE000out.fbx/.obj`, `Dummy_texture.dds/.png`, `NE000_01_EF56_A.dds/.png`)

**Archive-content verification (CONFIRMED).** I rebuilt the pkh hash (see 2) and matched every extracted file to a pkh entry:
- archive: 50,821 pkh entries, 50,813 files on disk match, 8 entries have no file, 23 disk files have no entry
- voice_ue: 16,417 entries, 16,417 matches (exact)
- magic_effect(+_1,_2,_3): 11,783 entries, 11,783 matches (exact)
- Byte comparison of 400 random-order extracted files against decompressed pk data: 400/400 identical.

So of the 79,036 extracted files, **79,013 are verbatim content of the shipped archives** (`shipped_inside_archives.txt`) and **23 are owner-made/renamed** (`owner_derived_files.txt`): 8 conversion outputs listed above plus 15 `mdltex` files named `~~*.gxt` or `NP600_02_S - Copy.mxt`. The 8 pkh entries without a file on disk are most likely the originals the owner renamed with the `~~` prefix (INFERRED; hashes cannot name them).

Caveats: (a) 49 motion-set archives (`memory/*_motion_set`, `pc_motion_set`) were never unpacked, so their contents exist only inside the pk. (b) "Shipped" content therefore = 420 physical files + the 79,013 archive members + the un-extracted 49 motion archives. (c) Mtime relies on the files not having been touched since; the folder was later copied (dirs show 2024), but file mtimes survived.

## 2. Archive format (.pk / .pkh / .pfs)

Same "LSPK" family as The Last Story / Fate-Extella. All integers **big-endian**.

**.pkh (CONFIRMED, decoded and validated on 3 archives)**
- `u32 count`, then `count` x 16-byte records: `u32 hash, u32 offset, u32 uncompressed_size, u32 compressed_size`. File size = 4 + 16*count exactly (archive.pkh 813,140 = 4 + 16*50,821).
- Records sorted ascending by hash (binary search table).
- `compressed_size == 0` (or equal size, 8 cases in archive) means stored raw at `offset` with `uncompressed_size` bytes (voice_ue: all 16,417 are raw, csz sum = 0).
- **hash = CRC-32/BZIP2 (MSB-first, poly 0x04C11DB7, init 0xFFFFFFFF, final xor 0xFFFFFFFF) of the lower-cased full path with forward slashes, e.g. `resource/data/motion/ez024_bs_look-idle-_--_lp.mtb`.** Proven on all 5 entries of ez024_motion_set and on ~67k files overall. (`PkCrc32.class` in fate-tools has a custom table; matches.)

**.pk (CONFIRMED)**
- No header. Raw concatenation of members at the pkh offsets (offsets 16-aligned in practice).
- Compressed members are individual zlib streams (`78 da`), decompressed with `zlib.decompress`. In archive.pk the first 2000 members: 1963 `78da`, plus 37 raw (members whose own magic is `SX`/`MO` etc.).
- Whole-file magic is the first member's zlib header (`78da 7d54...`).

**.pfs (CONFIRMED layout skeleton, INFERRED field names)**
- Header words: `0, 0, dirCount(4), fileCount(5)`, then directory records, then file records, then a u32 table of string offsets, then a NUL-separated ASCII string pool (`\0resource\0data\0motion\0EZ024_BS_LOOK-IDLE-_--_LP.mtb\0...`).
- It is the only place the real file names live (the pkh has hashes only). Extractors walk the dir tree, build `path`, hash it, look up the pkh. Fate pktools `PkFile` has `PfsDirEntry / PfsOffsetEntry / PfsNameEntry` and says "N directories, M files", matching.
- `PkFile` also auto-detects "Fate/Extella" vs "Fate/Extella Link" pkh variant (Link uses 64-bit values: `readLong`). Soul Sacrifice Delta is the 32-bit Extella-style variant (confirmed by sizes above).

Tool README/code evidence: `LSPK-Extractor_v3.0/README.md` (describes pk/pkh/pfs, "Block Size : 16 bytes", zlib or LZ11 auto-detect); `fate-tools/lib/fate-1.0.0-SNAPSHOT.jar` (classes `com.kotcrab.fate.file.extella.PkFile`, `PkCrc32`; CLI `pktools extract | extractAll | extractDnD`).

## 3. Pipeline the owner most likely used (2019-09-07/08)

1. **Dump decrypt**: `psvpfsparser.exe` (root, 2019-09-07) + `<your-license>.rif` (root, license) -> `decrypted/` at 2019-09-08 01:01. (`libcurl.dll` beside it is the parser's dependency.) CONFIRMED by timestamps and by the group of files; exact command line unknown (psvpfsparser takes `-i <title dir> -o <out> -z <zRIF/rif key> -f <cma/key>`; INFERRED).
2. **Unpack archives** at 14:13-15:54: either `fate-tools/drag-and-drop pk extract.bat` (-> `bin/pktools.bat extractDnD <pk>`, Java, Kotcrab) or `LSPK-Extractor.exe <pk>` (drag-and-drop, README). Both zips arrive in the root with mtime 2019-09-08. Evidence for pktools: extraction order is the pfs directory order (boot/bp, boot/cn ... then data/*, sorted by name) not pkh hash order, and output folders are named after the archive (`memory/magic_effect`, `mount/retail/archive`, `voice_ue`). Evidence against: pktools wants an empty output dir, yet four archives landed in one `magic_effect` folder. Cannot be decided; I lean pktools with manual folder merging. The `.pkh` hashing proof means either tool would have produced identical content.
3. **Models**: `noesisv42.zip` -> `noesis/`; plugin `data_fate_extella_ge3.py` (Noesis Python, header "Loader for Fate/Extella .mdl", file mtime 2019-02-09, checks magic `KPKy` = 0x794B504B) copied to `noesis/plugins/python/`; the owner then hand-edited it to `data_fate_extella_ge3-nobones.py` (Sep 8 and again Sep 12, diff: disabled index-buffer branch, changed `bindBones` offsets 0x24/0x20 -> 0x28/0x24, added debug prints). That edit is what made Soul Sacrifice vertex layouts load (INFERRED, the diff is real). Output in `Extracted models/`: `.fbx`, `.obj`, `.dds`, `.png`, `.tga`, a ZBrush `.ZPR` and a 180 MB `libromzbrush.OBJ` (model "Librom"/NE000, "Octoguy", "jackolantern"); mtimes 09-08 02:32 to 09-12 18:44.
4. **Textures**: `.mxt` and `.gxt` both start with `GXT\0` (Vita GXT). Plugin `getTexExtensions` = `[".mxt", ".gxt"]`, handler `.gxt`, `fmt_pvrtc_pvr.py` in noesis plugins. `FateMXTDemo_gxt2pvr.zip` holds a QuickBMS script `FateMXTDemo_gxt2pvr.bms` that wraps a GXT payload in a PVR header (PVRTC 2bpp, width/height at 0x38) for stand-alone viewing/export to png/tga. CONFIRMED (script contents read).
5. **Audio**: `*.sxd1/*.sxd2` (stream) and `*.sxd` (SFX bank) begin `SXDF`/`SXDS` (Sony SXD). `vgmstream/` (CLI + foobar plugin dlls; its USAGE mentions `bgm.sxd#10` subsong syntax) + `foobar2000_v1.4.6.exe` installer (2019) -> `foobar2000/` portable; `music/` has 111 mp3 named like `04_SacrificeED_bgm [1].mp3` (suffix `[1]` is the foobar converter/duplicate naming), mtime 2019-09-09 00:12-00:13. Note the vgmstream binaries are dated 2025-07-13, so they were refreshed later; the 2019 route was most likely the foo_input_vgmstream component (INFERRED).
6. **Other**: `gallery/` is Japanese official special-edition extras (illustration sets, wallpapers, PV), unrelated to the dump. `vita dns.txt` = `212.47.229.76` (a Vita DNS server for the PSN/store, irrelevant to extraction).

## 4. File format map

Counts are over the 2019 extraction (all three groups); location is relative to `mount/retail/archive/resource/` unless noted.

| Ext | Count | What | Evidence |
|---|---|---|---|
| efp | 14,451 | Effect sequencer XML ("EffectSequencer", Shift-JIS) tying `.eff` files with start/end frames, pos/rot/scl, colour | text `<?xml ...<EffectSequencer version="2">`, `data/eff/EFF_mg004_008.efp` |
| eff | 12,191 | Binary particle/effect definition | magic `@EFF$` (`40 45 46 46 24`), `data/eff/EFE_item_point.eff` |
| sxd1 + sxd2 | 8,962 each | Streamed audio pair (header + data), BGM and voice | `SXDF`/`SXDS`; 813 BGM streams, 8,149 voice (voice_ue) |
| mtb | 6,583 | Motion/animation (bone tracks) | magic `60AE` (`36 30 41 45`), `data/motion/CS16F_BS_IDLE------_00_--.mtb`; companion `.skl` skeleton has `60SE` |
| mxt | 5,995 | Model texture, Vita GXT | `GXT\0` + version 0x10000003; `data/mdltex/AP000_A.mxt` (suffix _A albedo, _N normal, _S spec, _M, _W) |
| mdl | 4,498 | Model (meshes, materials, skeleton refs) | magic `KPKy` -> Noesis plugin `fateCheckType`; `data/efmodel/EFF_mg012_000.mdl`, `data/model/SE00B_GROUND.mdl` |
| gxt | 3,560 | Texture (same as mxt, other source) | `GXT\0`; many in `mdltex` |
| msgt | 2,458 | Localised message tables, UTF-16LE TSV | BOM `ff fe`, header `EF_MESSAGE_TEXT 20111110 N`; `boot/us/item_param_text_us.msgt`, `message/<lang>/` |
| txt | 1,748 | Book/catalogue text, rules, per language | `message/us/book_catalogue_Alice01_G_us.txt`, `database/network/rules_test.txt` |
| scene | 1,577 | **Level/quest population (XML)**: enemies, player starts, waypoints, gimmicks, event boxes | `data/scene/*.scene`, see snippet A |
| csv | 1,472 | Game balance/data tables, Shift-JIS | `boot/quest_param.csv` (562 rows), `magic_*_param_*.csv`, `enemy_ai_param.csv`... |
| chr | 1,267 | Character def: model + motion/state-name map | `MODEL<TAB>NE010.mdl` / `MOTION<TAB>...mtb<TAB>CH_WTN00` |
| d2b | 1,197 | Story-book / 2D animation binary | `data/d2anime/book_talk_000.d2b`; companion `d2a_text_*.u16` |
| efmdl | 635 | Effect model | `01 00 00 00 EFMD` |
| csp / cgfx | 487 / 487 | Compiled Vita shader (`KPKy`) / source Cg shader for Windows | `shader/psp2/3BG_B.csp`, `shader/win/3BG_B.cgfx` (`#define ...`) |
| u16 | 466 | UTF-16 text tables | `ff fe`, `quest_name_text_us.u16` |
| xsca | 284 | Camera animation | magic `@FSX` |
| uchr / evep / ict / egm / map / area / mef / event | 248 / 211 / 48 / 122 / 98 / 93 / 209 / 60 | Utility character, episode (book) event script, intro-camera, gimmick effect sequence, map definition, area/lighting, map effect, cutscene XML | see snippets |
| hkt / hks / hkp | 156 / 72 / 7 | Havok collision | magic `1e0db0cacefa11d0` (Havok packfile) |
| shlt | 67 | Baked lighting data | `shlt\0\2` in `SHData/` |
| sndloc | 24 | Positional sound XML | XML |

### Snippets
Removed for the public repo (verbatim game-file excerpts). The formats are described in the table above.

## 5. Config flags

Both ini files are tab-separated, `;` = commented out, and **contain several stacked blocks separated by blank lines**. Treat later blocks as overrides of earlier ones (INFERRED: classic dev-default block, then region/retail overrides; the retail block at the bottom wins). All meanings are guesses from the names; `eboot.bin` is encrypted so I could not confirm in code.

`resource/config.ini`
| Block | Key | Value | Guess |
|---|---|---|---|
| 1 (dev) | BootSequence | DebugMenu | boot into the developer debug menu instead of the title |
| 1 | DebugCommandOn | true | enable debug-command/cheat input |
| 1 | BootCaching | true | cache on boot |
| 1 | PreLoadEnable | false | preload resources |
| 1 | PlayStageNeedPressButton | true | require button press to start a stage |
| 1 | NoCostMagicAll | false | all magic free (cheat) |
| 1 | ;SyncFps | true | (disabled) vsync-lock frame rate |
| 1 | ;SystemInfoType | 2 | (disabled) on-screen system info mode |
| 1 | ;DrawWorkMeter | true | (disabled) show CPU/GPU work meter |
| 1 | DrawPerfNotify | false 20 | perf warning overlay, threshold 20 |
| 1 | NoAbort | false | suppress abort-on-error |
| 1 | CamNearClipChara | false | near-clip camera for characters |
| 2 (retail) | BootSequence | Title | normal boot to title |
| 2 | BootCaching | true | |
| 2 | AllMagicCache | false | cache all magic effects |
| 2 | SyncFps | false | |
| 2 | DrawWorkMeter | false | |
| 2 | DrawErrorMessage | false | on-screen error text |
| 2 | PreLoadEnable | true | preload on |

`resource/boot_config.ini`
| Block | Key | Value | Guess |
|---|---|---|---|
| 1 | Version | 01.10 | app/data version |
| 1 | FPS | 30 | frame rate target |
| 1 | ResoDown | 1 | resolution divisor/downscale (1 = full) |
| 1 | PackFileFirst | false | prefer packed (pk) files over loose files; flips to **true** in block 2 |
| 1 | Trophy | false | trophies; true in block 3 |
| 1 | DebugRegionType | jp | forced region (JP) in dev; us in block 3 |
| 1 | DebugLanguageType | jp | forced language; us in block 3 |
| 1 | CaptureMode | false | clean screen-capture mode |
| 1 | ;PowerMode on, ;ScreenShot true, ;ScreenShotOverlay true, ;ModeTrial false, ;ForceDLC false | disabled | power mode, screenshot feature/overlay, trial build, force DLC availability |
| 1 | EffectReload | true | hot-reload effect files (dev); false in block 3 |
| 2 | PackFileFirst | true | retail: read from the .pk archives |
| 3 | Version | 01.10 | |
| 3 | DebugRegionType / DebugLanguageType | us / us | US build |
| 3 | Trophy | true | |
| 3 | PowerMode | on | |
| 3 | ScreenShotOverlay | false | |
| 3 | ForceDLC | false | |
| 3 | EffectReload | false | |
| 3 | EffectGpuLimitThreshold | 45.0 | GPU time (ms?) threshold for dropping/limiting effects |

Implication for modding (INFERRED): `PackFileFirst false` is the developer "loose files win over archives" mode; the retail block sets it true, so loose-file overrides will not work unless that flag is flipped, which requires patching the ini (outside the pk, loadable from the app folder) - worth testing since the ini is a plain file in `resource/`, not in an archive.

`resource/network/scej-network.pem`: a single Sony Computer Entertainment Inc. CA certificate (PEM, JP/Tokyo/Minato-Ku) for the online features; not a debug flag.
