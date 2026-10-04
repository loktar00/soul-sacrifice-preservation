# Modding Soul Sacrifice Delta: a complete guide

This takes you from your own copy of the game to a working mod you can play, on PC (Vita3K) and, untested so far, on a
hacked Vita. Everything here was tested on 2026-10-03 unless it is marked **UNTESTED**.

You need your own copy of **Soul Sacrifice Delta (US, PCSA00152)**. Nothing in this kit contains game files, and mods
should be shared without them (see "Sharing mods").

## 1. What you need
- Your Soul Sacrifice Delta cart (or digital copy) and a Vita with HENkaku/Ensō, used once to dump it.
- A Windows PC with Python 3.12+ (`pip install pillow pycaw` if you want the automated boot test).
- Vita3K (continuous build) from https://github.com/Vita3K/Vita3K/releases.
- This kit: `ssmod.py` + `recipe.py` + `README.md` (reference) + `../tools/pk/pktool.py` (archive tool).

## 2. Dump the game (one time, on the Vita)
Dump the game together with its license. Two dump styles work:

- **A. Encrypted dump + license** (`sce_sys/package/work.bin` in the dump, as NoNpDrm-style dumpers produce).
  Vita3K decrypts these itself on install. **UNTESTED** with this game: the path below was the one tested.
- **B. Already-decrypted dump + `.rif` license** (what this project used): the game's PFS layer decrypted on PC with
  `psvpfsparser.exe` and the cart's license file (`<hash>.rif`). The executables (`eboot.bin`, `sce_module/*.suprx`)
  stay encrypted, which is fine: Vita3K decrypts them at load time with the license.

You should end up with a folder containing `eboot.bin`, `sce_module/`, `sce_sys/` and `resource/` (about 3.2 GB for the
US cart: 420 files, 55 archive triples under `resource/data/pack/`).

> If you extracted archives in place years ago (folders next to the `.pk` files), install a copy with only the shipped
> files. Loose extracted files can change what the game loads.

## 3. Set up Vita3K
1. Unzip Vita3K somewhere. In `config.yml`, `pref-path` sets where its virtual memory card lives (`<pref-path>/ux0/...`).
2. Install the firmware and fonts. Both are Sony's official update files:
   - `PSVUPDAT.PUP` (system 3.74): `http://dus01.psv.update.playstation.net/update/psv/image/2022_0209/rel_f2c7b12fe85496ec88a0391b514d6e3b/PSVUPDAT.PUP`
   - `PSP2UPDAT.PUP` (fonts): `http://dus01.psp2.update.playstation.net/update/psp2/image/2019_0924/sd_8b5f60b56c3da8365b973dba570c53a5/PSP2UPDAT.PUP`
   - The MD5 of each file equals the hash in its URL. Install with `Vita3K.exe --firmware <file.PUP>` (once per file).
3. Install the game.
   - **Dump style B** (decrypted): make sure the folder has **no** `sce_sys/package/work.bin`, then run
     `Vita3K.exe "<dump folder>"`. Then copy your `.rif` to
     `<pref-path>/ux0/license/PCSA00152/UP9000-PCSA00152_00-SOULSACDELTAUS00.rif`.
     If `work.bin` is present, Vita3K tries to decrypt the dump again, fails with `failed to find files.db` and
     deletes its copy.
   - **Dump style A**: `Vita3K.exe "<dump folder>"` (UNTESTED here).
4. Recommended `config.yml` settings:
   - `high-accuracy: true` fixes blocky squares in fog and particle effects (no FPS cost on the test PC).
   - `initial-setup: true` and `show-welcome: false` skip the first-run wizard so `-r` boots straight into the game.
5. Boot it: `Vita3K.exe -r PCSA00152`. You should get the SCE and Marvelous AQL logos, then the title screen at 30 FPS.

Things that are normal:
- The save dialog defaults to **No**: press Right, then Cross.
- **DOWNLOAD** on the main menu hangs. It needs a network dialog Vita3K doesn't implement, and Sony's store is gone.
- The log shows "Missing file" lines for `archive_patch1.pkh` (until you install a mod), for trophies and for empty save slots.

## 4. Turn on the developer menu (your test bench)
The retail game still contains Marvelous' developer menu. Open the INSTALLED copy of
`<pref-path>/ux0/app/PCSA00152/resource/config.ini` (keep a backup). The file has two blocks: dev settings first, then
retail overrides. In the second block, change

```
BootSequence	Title
```
to
```
BootSequence	DebugMenu
DebugCommandOn	true
```
(Fields are separated by a TAB, line ends are CRLF.)

The game now boots into **SELECT SEQUENCE MODULE**. In this menu **Circle confirms** (Japanese convention), Cross does nothing.
- `00 Title`: the normal game.
- `01 Quest Select`: **Stage Select**, all 561 quests. Left/Right (or L/R) change the quest, Circle starts it, Cross exits.
  It shows the quest name, map ID and name, and bosses: the fastest way to check a mod.
- `05 ELDER DEFAULT MAP`, `06`/`07`: developer test maps (one developer's own, one for enemies/NPCs).
- `08 CutEvent Select`: cutscene viewer. `13 SaveEditMode`: save editor.

## 5. Your first mod: rename a quest
```
cd port/modkit
set SS_APP=<pref-path>\ux0\app\PCSA00152
python ssmod.py new my_first_mod
python ssmod.py text get quest_name_text_us q_e0001
python ssmod.py text set quest_name_text_us q_e0001 "Elder Fantasy" --mod my_first_mod
python ssmod.py validate my_first_mod
python ssmod.py build my_first_mod
python ssmod.py install
```
Boot the game, open `01 Quest Select`: Quest Name now reads **Elder Fantasy** instead of "First Quest".
`python ssmod.py uninstall` returns the game to retail.

How it works: `build` packs your files into `archive_patch1.{pk,pkh,pfs}`, the game's own update slot. The game opens it at
boot and its files override the same paths in the main archive. Only slot 1 is ever opened (slot 0 is ignored), so all mods
for one install are merged into one patch: `python ssmod.py build mod_a mod_b`.

## 6. Editing a level
Every quest is a row in `resource/boot/quest_param.csv` (Shift-JIS CSV, 65 columns). Quest `q_e0001`:
- map `ST16A` (Leviathan 1st Floor)
- player spawn scene `bu_pla_16a_e0100`, objects scene `bu_gim_16a_e0100`, enemy scene `q_e0001`
- bosses `ch7302`/`ch7312`, music `bgm_leviathan`

Scenes (`resource/data/scene/<name>.scene`) are Shift-JIS XML. Each object is an `<anyType type="PlayerInfo|EnemyInfo|EventPoint|EventBox">`
with a position, a rotation in degrees, and a scale. Event points carry commands, e.g. `BossAppearCheck` with
`boss_appear_time` (seconds) and `zako_kill_num` (minion kills needed).

Move the player spawn:
```
python ssmod.py extract resource/data/scene/bu_pla_16a_e0100.scene --mod my_first_mod
```
Edit `mods/my_first_mod/files/resource/data/scene/bu_pla_16a_e0100.scene`: change the two PlayerInfo positions
(originally about x=22.86 z=10.87 and x=21.91 z=8.24) to `0,0,0` and `1.5,0,1.5`, and their rotation y from `-135` to `45`.
Validate, build and install, then start q_e0001 from Stage Select. You now begin by the waterfall tower instead of the
open plaza. The ready-made version is `mods/elder_fantasy_demo`.

### A brand-new quest (tested in Vita3K, 2026-10-03)
A quest is a `quest_param.csv` row plus a name row and a purpose row. Nothing else in `resource/boot` or `resource/database` mentions a
quest ID. `mods/new_quest_demo` adds `q_x0001` as a recipe only (see "Sharing mods"):
- `csv.tsv`: `clone q_e0001 q_x0001 PlayerInfo=bu_pla_x0001` (same map ST16A, same bosses and enemy scene, its own spawn scene);
- `text.tsv`: rows in `quest_name_text_us` ("Elder Fantasy: New Trial") and `quest_purpose_text_us`;
- `scene.json`: `create` of `bu_pla_x0001`, two PlayerInfo nodes at x=-20 z=1 / z=3.

Result: Stage Select reads 562 total, the new row is the last quest (ID 561, `q_x0001`) with the new name, map ST16A and the
Hansel and Gretel bosses, and starting it loads the level with the player at the new spawn. In Stage Select, move the cursor down to
`Set Quest ID` (the 7th row; tap Down with ~350 ms between presses, faster presses get dropped), then press Left once from the first
quest to wrap to the last.
Not tested: other languages (add the same rows to `quest_name_text_<lang>`, or those language settings show no name), enemy
placement changes, clear/progress state for a new quest in a real save.

## 7. Testing automatically (optional)
`python tools/boot_test.py 35 "wait 500, down, wait 500, circle, wait 6000, shot:a.png, circle, wait 14000, shot:b.png"`
launches Vita3K, mutes it, opens Stage Select, screenshots it, starts the quest, screenshots again and closes. If several
Vita3K windows are open, set `VPAD_EXE` to part of the exe path you want.

## 8. Real Vita (UNTESTED)
With the rePatch plugin installed, copy the three built files to
`ux0:rePatch/PCSA00152/resource/data/pack/mount/retail/`. No config edit is needed. For the developer menu on hardware,
also place your edited `config.ini` at `ux0:rePatch/PCSA00152/resource/config.ini`.

## 9. Sharing mods
A mod's `files/` folder holds whole game files (a full text table, a full scene), which are the game's own data and must not be
shared. Share a **recipe** instead: `recipe/text.tsv`, `recipe/csv.tsv` and `recipe/scene.json` list only your changes, and
`ssmod.py build` applies them to the player's own originals (format in README.md, "Sharing: recipes"). `export-recipe` converts a
`files/`-based mod (it proves the result is byte-identical), and `pack-share` zips `mod.json` + `recipe/` and refuses to include
any retail file. Original content you authored yourself (a brand-new scene, say) can go in `files/`, listed under `original_files`
in `mod.json`, or be a `create` entry in `scene.json`. Tested: `elder_fantasy_demo` and its recipe `elder_fantasy_recipe` build to
identical `archive_patch1` files. UNTESTED: recipes against non-US game regions.

## 10. Troubleshooting
| Symptom | Cause / fix |
|---|---|
| Install says `NoNpDrm installation failed, deleting data!` | Decrypted dump with `sce_sys/package/work.bin`: remove it, install, add the license by hand (section 3). |
| Game boots to the Vita3K setup screen | Set `initial-setup: true` in `config.yml`. |
| Fog or particles have blocky squares | `high-accuracy: true`. |
| Mod doesn't show | Check `vita3k.log` for `archive_patch1.pkh` being opened; check you built slot 1; re-run `validate`. |
| Cross does nothing in the dev menu | Circle confirms there. |
| Saving "does nothing" | The dialog defaults to No: Right, then Cross. |
| Game hangs after DOWNLOAD | Known: unimplemented network dialog. Restart. |
| `text get` prints garbage for Japanese | Use the current `ssmod.py` (it forces UTF-8 output). |
