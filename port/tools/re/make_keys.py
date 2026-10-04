"""Generate sceutils keys.py from Vita3K's retail key table (packages/src/sce_utils.cpp, case 0)."""
import re, sys
src = open(sys.argv[1], encoding="utf-8").read()
retail = src.split("case 0:", 1)[1].split("case 1:", 1)[0]
pat = re.compile(r'register_keys\(\s*KeyType::(\w+),\s*SceType::(\w+),\s*(\w+),\s*"([0-9A-Fa-f]+)",\s*"([0-9A-Fa-f]+)"'
                 r'(?:,\s*(0x[0-9A-Fa-f]+|\d+))?(?:,\s*(0x[0-9A-Fa-f]+|\d+))?(?:,\s*SelfType::(\w+))?\s*\)')
out = ["from scetypes import KeyStore, KeyType, SceType, SelfType", "SCE_KEYS = KeyStore()"]
n = 0
for kt, st, rev, key, iv, mn, mx, sf in pat.findall(retail):
    out.append(f"SCE_KEYS.register(KeyType.{kt}, SceType.{st}, {rev}, '{key}', '{iv}', "
               f"{mn or 0}, {mx or '0xffffffffffffffff'}, SelfType.{sf or 'NONE'})")
    n += 1
open(sys.argv[2], "w").write("\n".join(out) + "\n")
print(f"{n} keys written (register_keys calls in retail block: {retail.count('register_keys(')})")
