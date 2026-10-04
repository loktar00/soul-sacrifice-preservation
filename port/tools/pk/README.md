# pktool: Soul Sacrifice Delta .pk / .pkh / .pfs packer

```
python3 pktool.py unpack <archive_base> <out_dir>
python3 pktool.py pack   <in_dir> <archive_base> [--like <reference_archive_base>]
python3 pktool.py verify <archive_base>
```
`<archive_base>` is the path without extension (`.../mount/retail/archive`). Python 3 standard library only.

- `unpack`: names come from the pfs; any pkh member without a pfs name goes to `<out_dir>/_unnamed/<hash>.bin`.
- `pack`: every file under `<in_dir>` (relative path, forward slashes, e.g. `resource/boot/us/x.u16`) becomes a member.
  `_unnamed/` is ignored. Without `--like`, rules below (INFERRED defaults) are used. With `--like`, member order, stored/zlib
  choice and the exact zlib settings are copied per member from the reference (members not in the reference use the defaults
  and are appended after the known ones). Round trips of tested archives are byte-exact either way.
- `verify`: every member decompresses to its declared size and lies inside the .pk, pkh is sorted and duplicate-free,
  every pfs name hashes to a pkh entry (and counts pkh entries with no name).

Status legend: CONFIRMED = reproduced byte-exactly on all 55 shipped archives (or stated count); INFERRED = rule consistent
with the data but not provably what the original tool did.

## .pkh (all integers big-endian)
| Offset | Field | Status |
|---|---|---|
| 0 | u32 count | CONFIRMED |
| 4 + 16*i | u32 hash, u32 offset, u32 size (uncompressed), u32 csize | CONFIRMED |

- Records sorted ascending by hash (CONFIRMED, all 55). File size = 4 + 16*count.
- hash = CRC-32/BZIP2 (poly 0x04C11DB7, MSB-first, init and xorout 0xFFFFFFFF) of the lowercased `/`-separated path with no
  leading slash, e.g. `resource/boot/us/quest_name_text_us.u16` -> 0xFF3B0988 (CONFIRMED; 50821/50821 names in `archive`).
- csize == 0: member stored raw, `size` bytes (CONFIRMED; 972 members in `archive`, all of `voice_ue`). csize == size never
  occurs in the retail archives (0 cases); the reader still accepts it as raw. Empty files are csize 0, size 0 (8 in `archive`).

## .pk
- Headerless concatenation of members (CONFIRMED). Offset of every member is a multiple of 32 (CONFIRMED, all 55 archives);
  gaps are zero bytes (CONFIRMED); no padding after the last member (CONFIRMED: pk size == end of last member).
- Compressed member = one zlib stream (`78 da`), CONFIRMED. Compressor matched exactly: **zlib level 9, memLevel 8, windowBits 15,
  default strategy** (Python `zlib.compressobj(9, DEFLATED, 15, 8, 0)`), i.e. stock zlib. 100% of members of magic_effect,
  eb802 and ez024 reproduce byte for byte (400/400 sampled from magic_effect also re-checked against levels 1-9, memLevel 8/9,
  strategies 0-3: level 9 always among the matches).
- Member order, no reference (INFERRED, matches 54 of 55 archives exactly): per directory, files first then subdirectories,
  names compared as ASCII upper-case. In `archive` one adjacent pair is the other way round
  (`EF08_EFF_Rock_005_A.mxt` before `EF08_EFF_Rock_005t_N.mxt`); `--like` reproduces it.
- Stored vs zlib, no reference (INFERRED, 50820/50821 correct on `archive`): store raw when the file is empty, ends in `.sxd2`,
  or zlib saves less than 1% (`STORE_RATIO`). The one miss is a 576-byte `.mxt` (zlib 571) that the original compressed.
  (`voice_ue` stores everything; use `--like` for that.)

## .pfs
Layout, all big-endian u32/i32 (CONFIRMED by byte-identical regeneration of all 55 .pfs files from their own name lists):

| Offset | Field | Status |
|---|---|---|
| 0 | u32 0 (reserved) | CONFIRMED (always 0) |
| 4 | u32 0 (reserved) | CONFIRMED (always 0) |
| 8 | u32 dirCount (includes the unnamed root) | CONFIRMED |
| 12 | u32 fileCount | CONFIRMED |
| 16 + 24*d | dir record d: i32 nameIdx, i32 parent, i32 firstChildDir, i32 childDirCount, i32 firstFile, i32 fileCount | CONFIRMED |
| 16 + 24*dirCount | u32 nameOffset[dirCount + fileCount] | CONFIRMED |
| then | string pool, NUL-terminated Latin-1 strings, no trailing padding | CONFIRMED |

Field meaning:
- nameIdx equals the dir's own row index d; the string for index i < dirCount is directory i's name, for i >= dirCount it is
  file (i - dirCount). nameOffset is relative to the pool start. Strings are stored once, in index order (root's name is the
  empty string at offset 0). There is no file record: files are only names, in the pool; their data is found by hashing
  the full path against the pkh.
- parent is -1 for the root (row 0).
- Subdirectories of a directory occupy the contiguous rows firstChildDir .. +childDirCount-1 (firstChildDir equals the next
  free row when childDirCount is 0). Files of a directory are the contiguous file indices firstFile .. +fileCount-1; file
  indices run in row order (row 0's files, row 1's files, ...).
- Row numbering rule (CONFIRMED by regeneration): visit directories in depth-first pre-order; each visited directory's sorted
  subdirectories receive the next free block of row indices. This is not plain breadth-first (in `archive`, `database`'s
  children get rows 98-101 after the grandchildren under `data`).
- Sibling order for both subdirs and files (INFERRED but 0 violations over 94,414 adjacent same-directory pairs): compare the
  name without its last extension first, then the extension; case-insensitive; punctuation < digits < letters; `-` is ignored
  in the first comparison and only breaks ties, where it sorts after letters (e.g. `ROLLING---_03` before `ROLL-STOP-_--`,
  `...005_A` stays before `...0050`). Looks like a Windows/culture-style collation. Real file names keep their original
  case (the pkh hash lowercases).

## Tested
- Round trip `unpack` + `pack --like` byte-identical (.pk, .pkh, .pfs): memory/magic_effect (11,783 members), eb802_motion_set,
  ez024_motion_set. `pack` without `--like` is also byte-identical for magic_effect and eb802.
- `pfs` regenerated identically from names for all 55 archives (incl. `archive`, 50,821 names / 209 dirs).
- `verify` PASS on `archive` (50,821 members), `pc_motion_set`, rebuilt archives.

## Not covered
- Other compression types (LZ10/LZ11 appear in the third-party Last Story tools): not seen in this game, not implemented.
- Unicode names: pfs strings are treated as Latin-1 (all retail names are ASCII).
