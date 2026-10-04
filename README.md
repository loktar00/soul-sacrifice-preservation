# Soul Sacrifice Delta: preservation and modding

Tools and research for Soul Sacrifice Delta (PS Vita, PCSA00152), working title "Elder Fantasy". Everything here works on
**your own dump of your own copy** of the game. This repo contains **no game files**: no dump, archives, decrypted
executables, license, firmware, keys or extracted assets.

## What works (2026-10-03)
- The game runs in Vita3K at 30 FPS: menus, quests, combat, save/load, FMV. Setup and gotchas are in `port/modkit/GUIDE.md`.
- The developer debug menu still in the retail build: Stage Select for all 561 quests, test maps, cutscene viewer.
- Mods load through the game's own patch slot `archive_patch1`, with no re-encryption and no config edits.
- Mod kit `port/modkit/ssmod.py`: text, scene and quest edits; brand-new quests; shareable recipe mods that contain no game data.

## Layout
| Path | What |
|---|---|
| `port/modkit/` | Mod kit: `ssmod.py`, `recipe.py`, `GUIDE.md` (start here), `README.md` (reference), example mods (recipes only) |
| `port/tools/pk/` | `pktool.py`: .pk/.pkh/.pfs archive unpack/pack/verify (byte-identical round trip) + format spec |
| `port/tools/re/` | Python 3 SELF-to-ELF decryptor (port of TeamMolecule sceutils, MIT). `keys.py` is generated locally from Vita3K source by `make_keys.py` and is not committed |
| `port/tools/vpad.py` | Drives a Vita3K window (button input + screenshots) for automated testing |
| `port/re/ghidra/` | Ghidra 12.1.3 + VitaLoaderRedux setup scripts and export scripts (the project DB is not committed) |
| `port/re/recomp/` | Native-port (static recompilation) design study and measurement scripts. **Parked** |
| `port/re/netplay/` | Start of a multiplayer revival study. **Parked** |
| `port/build/` | Building Vita3K from source on MSVC 14.41 (`BUILD.md`, `vita3k-msvc1441.patch`) |
| `port/notes/` | 2019 forensics, i.e. how the original dump was processed |
| `NOTES.md` | Full running lab notebook: every finding, with evidence |
| `tasks/` | Checklist (`todo.md`) and lessons learned |
