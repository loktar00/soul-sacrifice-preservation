# Soul Sacrifice Delta mod kit

Mods for the PS Vita game Soul Sacrifice Delta (PCSA00152). A mod is a folder of replacement files that mirror the game's archive
paths. `ssmod.py` packs them into `archive_patch1.{pk,pkh,pfs}`, the game's own patch slot. No config edits, no changes to the
retail archives. Python 3 only (plus Pillow and pycaw if you use `tools/boot_test.py`).

## Setup
First-time setup (dump, Vita3K, debug menu) is in [GUIDE.md](GUIDE.md). Then:
- `SS_APP` = your installed game folder (Vita3K: `<pref-path>/ux0/app/PCSA00152`). Default: `port/vita3k-fs/ux0/app/PCSA00152`.
  `install`/`uninstall` write there (or `--target`).
- Original files are read from the retail `archive`/`voice_ue` archives in `SS_APP` (set `SS_DUMP` to a dump folder holding `resource/`
  to read them from elsewhere). They are unpacked on demand into `port/scratch/modkit_cache/`.
- The install should boot the dev menu (`resource/config.ini`: `BootSequence DebugMenu`) and keep retail `boot_config.ini` (`PackFileFirst true`).

## Workflow
```
python ssmod.py new my_mod                                 # mods/my_mod/{mod.json,files/}
python ssmod.py extract "resource/data/scene/q_e0001.scene" --mod my_mod    # copy originals to edit (globs ok, case-insensitive)
python ssmod.py text set quest_name_text_us.u16 q_e0001 "Elder Fantasy" --mod my_mod
python ssmod.py text get quest_name_text_us.u16 q_e0001 --mod my_mod
python ssmod.py validate my_mod
python ssmod.py build my_mod [other_mod ...] [--force] [--slot N] [--out DIR]   # -> build/archive_patch1.*, runs pktool verify
python ssmod.py install [build_dir] [--target APPDIR]
python ssmod.py uninstall [--slot N] [--target APPDIR]     # back to retail
```
- `mod.json`: `name, author, description, version, slot` (slot is 1; see "Patch slots").
- `files/` paths are archive paths (`files/resource/boot/us/...`). Anything under `resource/` that exists in the retail archives
  is replaced; new paths are added. Edit files in place; `extract` is just a starting copy.
- `build` merges several mods. Identical duplicate paths are fine. Different contents for one path is an error unless `--force`;
  then the mod listed later on the command line wins (printed as `override`). `build` validates first and refuses to build on failure.
- `text set ... --add` appends a row that does not exist (columns copied from the table's usual shape). A bare table name must be
  unique; otherwise give the full archive path (`resource/boot/us/quest_name_text_us.u16`, languages: us bp cn fr ge it jp kr sp tw ue).
- Example: `mods/elder_fantasy_demo` (renames q_e0001 and moves its player spawn, as whole files) and `mods/elder_fantasy_recipe`
  (the same mod as a recipe: the two build to byte-identical `archive_patch1`).

## Sharing: recipes
`files/` holds whole game files, so a mod with game-derived files in `files/` must never be shared. Share a **recipe** instead: a
`recipe/` folder of changes that `build` applies to each player's own originals (before validation and packing). A mod may have
`files/`, `recipe/` or both (recipes are applied on top of all mods' `files/`, in command-line order, so two recipe mods that
edit the same table merge cleanly). Edits are textual and in place: untouched bytes stay identical and added rows/nodes copy the
original's formatting (UTF-16LE + BOM + CRLF tables, Shift-JIS + CRLF scenes and CSV).

`recipe/text.tsv`: one line per row, `table<TAB>id<TAB>english`. Sets the English cell of an existing row or appends the row.
`table` is a bare name (`quest_name_text_us`) or a full archive path. The `quest_purpose_text_*` tables are comma-separated, so
their English text may not contain commas.

`recipe/csv.tsv` (quest_param.csv, columns by header name, e.g. `MAP(ID)`, `PlayerInfo`):
```
set<TAB>q_e0001<TAB>MAP(ID)<TAB>ST10A
clone<TAB>q_e0001<TAB>q_x0001<TAB>PlayerInfo=bu_pla_x0001<TAB>Gimmick1=bu_gim_16a_e0100     # new row at the end, copy of q_e0001
```
`recipe/scene.json`: a list; one entry per scene (`name` = `resource/data/scene/<name>.scene`, or a full archive path):
```
{"scene": "bu_pla_16a_e0100",                       # edit values of an existing scene
 "set": {"PlayerInfo[0]/position.x": 0.0,            # key = <node selector>/<field path>
         "PlayerInfo[1]/rotation.y": "45.000000",
         "GrimoireInfo.bg": "ST10A"},                # no node selector = a field of the scene itself
 "append": [{"node": "PlayerInfo", "name": "ch0000_01", "id": 3, "position": {"x": 0.0, "y": 0.0, "z": 0.0}}]}
{"scene": "bu_pla_x0001", "create": {"bg": "ST16A", "nodes": [ ...nodes as in append... ]}}   # brand-new scene file
```
Node selector: `Type[i]` (i-th node of that type), `Type:name[i]`, or just `Type` when it is unique. Field path: dotted child tags
(`position.x`); `tag[i]` picks the i-th repeated tag, `tag[name]` picks by `name` attribute (`argsType.param[boss_appear_time]`),
`@attr` as the last segment sets an attribute (`argsType.@command`). A node in `append`/`create` is `{"node": Type, tag: value,
...}`; a value is a scalar (numbers print as `%.6f` for floats), or a dict for nested tags (`"@": {attrs}`, `"#": text`, a list
repeats the tag). `create` makes a scene from the standard empty skeleton, so it must be wholly modder-authored.

`files/` may still hold raw files the modder authored (not derived from the game). When sharing, `files/` may ONLY contain such
original content, listed in `mod.json` as `"original_files": ["resource/..."]`.

```
python ssmod.py export-recipe my_mod [--out NAME]   # files/-based mod -> mods/my_mod_recipe (recipe only)
python ssmod.py pack-share my_mod                   # -> build/my_mod.zip: mod.json + recipe/ + original_files
```
`export-recipe` diffs `files/` against the originals (text rows, scene values, appended scene nodes, quest_param rows, new scenes) and
**verifies** by applying the result to the originals and comparing bytes. It refuses, with the file name, anything it cannot express:
binary or unsupported files (e.g. `.gxt`), removed rows/nodes, reordered rows, changed non-English cells. Files you list in
`original_files` are copied through. `pack-share` refuses when `files/` holds any file not listed in `original_files`, and when a
listed path exists in the retail archives or is missing. Importing someone's zip: unzip into `mods/<name>/` and build as usual.

## File formats
**Text tables** (`.u16`, `.msgt`, under `resource/boot/<lang>/`): UTF-16LE with BOM, CRLF row ends, TSV.
First line `EF_MESSAGE_TEXT<TAB>20111110<TAB><row count>`; rows `id<TAB>English<TAB>Japanese<TAB><TAB>timestamp`
(five columns for most tables; some `.u16` tables such as chara_name have no header). Row text length is free; no tabs/newlines inside a cell.
A few `.msgt` tables contain in-cell bare newlines already; the validator allows no more than the original has.
`validate` checks BOM, header, CRLF, column count per row against the original, and trailing line.
Quest titles are `quest_name_text_us.u16`; descriptions `quest_purpose_text_us.u16`; stage names `stage_name_text_us.u16`.

**Scenes** (`resource/data/scene/*.scene`): Shift-JIS XML, `<?xml version="1.0" encoding="shift_jis"?>`, root `<MapSetData>`,
nodes in `<nodes><anyType type="PlayerInfo|EnemyInfo|EventPoint|EventBox">` each with `name, id, position{x,y,z}, rotation{x,y,z} (degrees), scale`.
Keep the original CRLF and edit values in place. `validate` checks that it decodes as Shift-JIS, parses, has the same root, and that each
`anyType` kind keeps the original child schema. A quest picks its scenes in `quest_param.csv` (PlayerInfo = spawn scene, EnemyInfo = enemy placement,
Gimmick1-4 = gimmicks, EventBox).

**quest_param.csv** (`resource/boot/quest_param.csv`): Shift-JIS CSV, 561 quests, 65 columns. Key columns (0-based index):
0 Useful, 1 Chapter, 2 Rank, 3 Derivation, 4 ID (`q_e0001`), 5/6 Clear/Fail Condition, 7 MAP(ID) (`ST16A`), 8 Difficulty, 9 Rank_Table_ID,
10 BreakUpScene, 11 PlayerInfo, 12 WayPoint, 13 ExWayPoint, 14-17 Gimmick1-4, 18 EnemyInfo, 19 EventBox, 20 Start_Camera_File_Name, 21-22 Start_Voice,
23-25 BOSS_APPEAR_CONDITION / _MOB_KILL / BOSS_TREND, 26-29 BOSS_ID1/TYPE1/HELP_NPC_ID1/DYING_CHR_FILE1, 30-33 same for boss 2,
34-37 ENEMY ID 1-4, 38 NEED MOB KILL NUM, 39-43 SEARCH_ITEM_* , 44-48 Mandragora release settings, 49 Level_Limit, 50 Real Selection,
51 Request Type, 52 BGM, 53-54 BGM shuffle, 55 BattleBGM, 56-57 shuffle, 58 JudgeBGM, 59 ResultBGM, 60 SendMetrics, 61-64 BattleProgress1/2 + Command.
Example row q_e0001: map ST16A, PlayerInfo `bu_pla_16a_e0100`, Gimmick1 `bu_gim_16a_e0100`, EnemyInfo `q_e0001`, bosses ch7302/ch7312.
`validate` checks each row has the header's column count. A new quest needs a `quest_param.csv` row plus a row in `quest_name_text_*`
and `quest_purpose_text_*` (the only tables that mention a quest ID, besides the quest's own scene files). Tested: `mods/new_quest_demo`.
Stage Select orders quests by CSV row, so a new row appended at the end is quest 561 of 562 (Left from the first entry).

## Testing in the Vita3K debug menu
1. Boot: `Vita3K.exe -A -r PCSA00152` from `port/tools/vita3k/`, or `python tools/boot_test.py 35 "<vpad sequence>"`
   (launches, mutes via pycaw, drives buttons with `port/tools/vpad.py`, screenshots, closes that instance).
2. Dev menu: confirm is Circle (the main menu uses Cross). `01 Quest Select` is Stage Select: Down, Circle. It shows quest name, chapter, map and boss rows.
   Left/Right (or L/R) change the quest ID; Circle starts it; Cross exits.
3. Typical check: `boot_test.py 35 "wait 500, down, wait 500, circle, wait 6000, shot:a.png, circle, wait 14000, shot:b.png"`.
   Text mods show on the Stage Select page (a.png), level mods in the quest (b.png). Compare with `port/notes/play/33_q1_b.png`, the original q_e0001 spawn.
4. The log (`port/tools/vita3k/vita3k.log`) shows `archive_patch1.pkh/.pk` being opened when the patch is picked up.

## Patch slots
The eboot contains paths for `archive_patch0..3` (retail mount) and `trial/archive_patch1`. Tested in Vita3K (details in the test notes):
**only `archive_patch1` is ever opened**; `archive_patch0` files are ignored even when installed alone or alongside patch1
(the log shows no open of patch0). Always ship slot 1. Patch1 overrides the same path in `archive` (the game's update mechanism).
`voice_ue` is a separate archive. UNTESTED: whether a patch1 member also overrides a path that lives in `voice_ue`
(only overriding `archive` members is proven).

## Real Vita (UNTESTED on hardware)
Install via the rePatch plugin: copy `archive_patch1.{pk,pkh,pfs}` to
`ux0:rePatch/PCSA00152/resource/data/pack/mount/retail/`. Nothing else should be needed (retail `PackFileFirst true` stays). No hardware test has been done.
Do not use the loose-file route unless you also set `PackFileFirst false`, which probes loose files first and fills the log with missing-file lines.
