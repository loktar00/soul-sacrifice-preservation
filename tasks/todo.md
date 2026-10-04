# Soul Sacrifice Delta: preservation / PC port

Goal: native PC port (user supplies own cart dump, no assets distributed), then a modding pipeline.

## Phase 1: Baseline in Vita3K
- [x] Inventory the 2019 dump; separate shipped files from 2019 extractions (mtime split)
- [x] Download Vita3K (continuous, v0.2.1 4115) into `port/tools/vita3k`, with storage kept in `port/vita3k-fs`
- [x] Install firmware 3.74 + font package (official Sony PUPs, md5 matches)
- [x] Build clean staging copy `port/staging/PCSA00152` (hardlinked data, license as work.bin)
- [x] Install + first boot in Vita3K: boots to title screen, 30 FPS, Vulkan (install recipe in NOTES.md)
- [x] Automated input + screenshots (`port/tools/vpad.py`)
- [x] In-game check via debug menu ELDER DEFAULT MAP: movement, camera, spells OK, 30 FPS, no errors
- [x] Real quest (q_e0001, Leviathan 1st Floor) via Stage Select: level, combat, effects OK, no errors
- [x] Retail New Game -> save -> restart -> Continue -> load: works. Prologue FMV plays.
- [x] Boss-quest combat: enemies (likely eb730 boss pair) spawn and fight, no errors (full kill not attempted)
- [ ] Known emulator gap: DOWNLOAD hangs on unimplemented sceNetCheckDialogInit (dead feature)
- [x] Visual bug #1 (blocky fog/particles) fixed with `high-accuracy: true`

## Phase 2: Decrypted executable + RE workspace
- [x] Recover decrypted `eboot.bin` ELF + 4 sce_module libs (`port/re/elf/`, via py3 sceutils port in `port/tools/re/`), verified against Vita3K load log
- [x] Ghidra project with Vita NID import labels: 26,392 functions, 713/713 imports named (`port/re/ghidra/`)
- [ ] Map engine subsystems: file I/O / pack loader, renderer (GXM), audio, input, script/scene

## Phase 3: Modding pipeline (no re-encryption)
- [x] Debug menu test: WORKS (dev sequence menu with test maps, quest/cutscene select, SaveEditMode)
- [x] Loose-file loading: WORKS with `PackFileFirst false` (renamed First Quest -> Elder Fantasy)
- [x] `archive_patch1` patch-archive channel WORKS with retail config (preferred mod format)
- [x] First level edit: moved player spawn in `bu_pla_16a_e0100.scene`; verified in-game
- [x] Document .pk/.pkh/.pfs format (NOTES.md; hash verified 11783/11783)
- [x] Packer `port/tools/pk/pktool.py`: byte-identical round trip, verified
- [ ] rePatch path for real hardware (`ux0:rePatch/PCSA00152/`)

## PRIORITIES (user, 2026-10-03, updated): MODDING + modder guide ONLY. Multiplayer/master server PARKED. Native port PARKED.

## Phase 5: Mod kit
- [x] `port/modkit/ssmod.py` (new/extract/build/install/validate/text) + modder README
- [x] Patch slots: ONLY archive_patch1 is opened (patch0 ignored)
- [x] End-to-end example mod built only with ssmod (rename + spawn move), verified in-game
- [x] New quest q_x0001 via recipe only: in Stage Select (562/562), loads, new spawn
- [ ] Texture round trip: GXT -> PNG -> GXT, replace one visible texture via patch archive
- [x] Modder guide `port/modkit/GUIDE.md` (dump -> Vita3K -> dev menu -> first mod -> level edit -> rePatch -> troubleshooting)
- [x] Recipe mod format: shared mods contain no game files (byte-identical builds, pack-share safeguard)

## Phase 6: Multiplayer revival (PARKED by user; partial string dump in port/re/netplay/)
- [ ] Study: modes, call flow (Matching2/Signaling/RUDP, PspnetAdhoc/AdhocMatching), prior art (RPCN, PPSSPP adhoc server, XLink Kai) -> `port/re/netplay/NETPLAY.md`
- [ ] M-A: two Vita3K instances see each other via local relay
- [ ] M-B: over the internet via the master server
- [ ] M-C: online/Matching2 mode
- [ ] M-D: real Vita interop

## Phase 4: Static recompilation prototype (PARKED; Vita3K source build still needed for netplay)
- [x] Design study + measurements (`port/re/recomp/DESIGN.md`): hybrid AOT + Vita3K fork + dynarmic fallback
- [x] M1.0 Vita3K builds from source (MSVC 14.41 + 1-line patch); built exe boots the game
- [ ] M1.1 exidx function list (34,094) + Capstone decoder + C++ emitter (integer/VFP-scalar/ldrex/TLS subset)
- [ ] M1.2 Dispatch hook in Vita3K CPU layer (AOT table, dynarmic fallback)
- [ ] M1.3 Differential mode (native vs dynarmic per function)
- [ ] M1 gate: AQL splash with AOT DLL, >=80% native, 0 mismatches / 1000 frames

## Review
