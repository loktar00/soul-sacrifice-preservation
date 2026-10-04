# Dump printable strings from eboot.elf with virtual addresses, filtered to network-related keywords.
import re, struct, sys
d = open(r"E:/soul sacrifice/port/re/elf/eboot.elf", "rb").read()
phoff, = struct.unpack_from("<I", d, 0x1C); phnum, = struct.unpack_from("<H", d, 0x2C)
segs = []
for i in range(phnum):
    t, off, va, pa, fsz, msz, fl, al = struct.unpack_from("<8I", d, phoff + i * 32)
    if t == 1: segs.append((off, va, fsz))
def va_of(o):
    for off, va, fsz in segs:
        if off <= o < off + fsz: return va + o - off
kw = re.compile(rb"(?i)net|adhoc|match|rudp|p2p|room|lobby|online|psn|np[A-Z_]|signal|party|host|guest|server|ping|latency|lag|session|invite|join|ranking|score|tus|http|https?://|\.com|\.net|\.jp|world|nat|socket|peer|member|connect|disconnect|kick|voice|chat|sigil|avalon|sanctuary|grim|faction|covenant|pact|reward|download|dlc")
out = []
for m in re.finditer(rb"[\x20-\x7e]{5,}", d):
    s = m.group()
    if kw.search(s):
        out.append("%08x %s" % (va_of(m.start()) or 0, s.decode()))
open("out/strings_net.txt", "w", encoding="utf-8").write("\n".join(out))
print(len(out))
