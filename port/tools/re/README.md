# Decrypting a Vita dump (SELF -> ELF)

`sceutils3/` is a Python 3 port of TeamMolecule's sceutils (`src/sceutils`, Python 2).
`sceutils3/keys.py` is generated from Vita3K's retail key table, not committed by hand.

Run from `E:\soul sacrifice\port`:

    # regenerate keys.py (retail "case 0" block of sce_utils.cpp)
    python tools/re/make_keys.py src/Vita3K/vita3k/packages/src/sce_utils.cpp tools/re/sceutils3/keys.py

    # decrypt one SELF using the dump's NoNpDrm RIF (work.bin)
    python tools/re/sceutils3/self2elf.py -i staging/PCSA00152/eboot.bin -o re/elf/eboot.elf -k staging/work.bin

    # modules
    for n in libc libfios2 libsmart libult; do
      python tools/re/sceutils3/self2elf.py -i staging/PCSA00152/sce_module/$n.suprx -o re/elf/$n.elf -k staging/work.bin
    done
