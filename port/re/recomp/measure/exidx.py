"""Classify the ARM EHABI unwind tables of eboot.elf (exidx 0x81AED7AC-0x81B3011C, extab -0x81B3E36C).
Answers: does the game use C++ exceptions (generic-model entries with a personality routine + LSDA)
or only compact unwind entries (pr0/pr1/pr2, used for backtraces/cleanup with no catch)?"""
import struct, collections, sys

ELF = r"E:\soul sacrifice\port\re\elf\eboot.elf"
EXIDX = (0x81AED7AC, 0x81B3011C)
EXTAB = (0x81B3011C, 0x81B3E36C)
data = open(ELF, "rb").read()
phoff, = struct.unpack_from("<I", data, 0x1C)
phentsize, phnum = struct.unpack_from("<HH", data, 0x2A)
segs = []
for i in range(phnum):
    p_type, p_off, p_vaddr, _, p_filesz, _, _, _ = struct.unpack_from("<8I", data, phoff + i * phentsize)
    if p_type == 1:
        segs.append((p_vaddr, p_off, p_filesz))

def word(va):
    for v, o, n in segs:
        if v <= va < v + n:
            return struct.unpack_from("<I", data, o + va - v)[0]
    raise KeyError(hex(va))

def prel31(at):
    x = word(at) & 0x7FFFFFFF
    if x & 0x40000000:
        x -= 0x80000000
    return (at + x) & 0xFFFFFFFF

kinds = collections.Counter()
personalities = collections.Counter()
lsda_entries = 0
n = (EXIDX[1] - EXIDX[0]) // 8
for i in range(n):
    e = EXIDX[0] + 8 * i
    second = word(e + 4)
    if second == 1:
        kinds["EXIDX_CANTUNWIND"] += 1
    elif second & 0x80000000:
        kinds["inline compact (pr%d)" % ((second >> 24) & 0xF)] += 1
    else:
        tab = prel31(e + 4)
        w0 = word(tab)
        if w0 & 0x80000000:
            kinds["extab compact (pr%d)" % ((w0 >> 24) & 0xF)] += 1
        else:
            pers = prel31(tab)
            kinds["extab generic (personality routine)"] += 1
            personalities[hex(pers | 0)] += 1
            lsda_entries += 1
print("exidx entries:", n)
for k, v in sorted(kinds.items()):
    print("  %-40s %d" % (k, v))
print("generic-model entries (personality + LSDA, i.e. try/catch or EH cleanups):", lsda_entries)
for p, c in personalities.most_common():
    print("  personality routine at", p, "used by", c)

# pr1/pr2 extab entries may carry EHABI descriptors (cleanup / catch / exception-spec) after the
# unwind opcodes; a zero word right after the opcodes means "no descriptors".
with_desc = 0
for i in range(n):
    e = EXIDX[0] + 8 * i
    second = word(e + 4)
    if second == 1 or second & 0x80000000:
        continue
    tab = prel31(e + 4)
    w0 = word(tab)
    if w0 & 0x80000000 and (w0 >> 24) & 0xF in (1, 2):
        extra = (w0 >> 16) & 0xFF
        if word(tab + 4 * (1 + extra)) != 0:
            with_desc += 1
print("pr1/pr2 entries carrying EH descriptors (cleanup/catch):", with_desc)

# Compare EHABI function starts (one exidx entry per function) with Ghidra's functions (out/functions.csv).
import csv, os
fcsv = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "functions.csv")
if os.path.exists(fcsv):
    ghidra = {}
    for r in csv.DictReader(open(fcsv)):
        ghidra[int(r["entry"], 16)] = (int(r["thumb"]), int(r["size"]))
    starts = [prel31(EXIDX[0] + 8 * i) for i in range(n)]
    thumb_bit = sum(1 for s in starts if s & 1)
    starts = sorted(set(s & ~1 for s in starts))
    missing = [s for s in starts if s not in ghidra]
    extra = [a for a in ghidra if a not in set(starts) and a < 0x81AE8000]
    print("\nexidx function starts: %d distinct (%d with Thumb bit set in the table)" % (len(starts), thumb_bit))
    print("  first %#x last %#x" % (starts[0], starts[-1]))
    print("  exidx starts with a Ghidra function: %d" % (len(starts) - len(missing)))
    print("  exidx starts WITHOUT a Ghidra function: %d" % len(missing))
    print("  Ghidra functions (below the stub area) with no exidx entry: %d" % len(extra))
