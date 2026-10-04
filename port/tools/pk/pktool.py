#!/usr/bin/env python3
"""pktool: pack / unpack / verify Soul Sacrifice Delta .pk/.pkh/.pfs archives. See README.md."""
import argparse
import os
import struct
import sys
import zlib

ALIGN = 32
STORE_RATIO = 0.99  # default: store raw (csize 0) when zlib saves less than 1%, plus empty files and .sxd2
DEFAULT_PARAMS = (9, 8, 0)  # zlib level, memLevel, strategy


# ---------------------------------------------------------------- hashing
def _crc_table():
    t = []
    for i in range(256):
        c = i << 24
        for _ in range(8):
            c = ((c << 1) ^ 0x04C11DB7) & 0xFFFFFFFF if c & 0x80000000 else (c << 1) & 0xFFFFFFFF
        t.append(c)
    return t


_T = _crc_table()


def path_hash(path):
    """CRC-32/BZIP2 of the lowercased path (forward slashes)."""
    c = 0xFFFFFFFF
    for b in path.lower().encode('latin1'):
        c = ((c << 8) & 0xFFFFFFFF) ^ _T[(c >> 24) ^ b]
    return c ^ 0xFFFFFFFF


# ---------------------------------------------------------------- pkh
def read_pkh(path):
    d = open(path, 'rb').read()
    n = struct.unpack('>I', d[:4])[0]
    if len(d) != 4 + 16 * n:
        raise ValueError('%s: size %d != 4+16*%d' % (path, len(d), n))
    return [struct.unpack('>4I', d[4 + 16 * i:20 + 16 * i]) for i in range(n)]  # (hash, off, size, csize)


def write_pkh(entries):
    entries = sorted(entries)
    return struct.pack('>I', len(entries)) + b''.join(struct.pack('>4I', *e) for e in entries)


# ---------------------------------------------------------------- pfs
def read_pfs(path):
    """Return full paths ('/' separated) of every file, in pfs order."""
    d = open(path, 'rb').read()
    z0, z1, nd, nf = struct.unpack('>4I', d[:16])
    dirs = [struct.unpack('>6i', d[16 + 24 * i:40 + 24 * i]) for i in range(nd)]
    t = 16 + 24 * nd
    offs = struct.unpack('>%dI' % (nd + nf), d[t:t + 4 * (nd + nf)])
    pool = t + 4 * (nd + nf)

    def s(i):
        a = pool + offs[i]
        return d[a:d.index(b'\0', a)].decode('latin1')

    def dpath(i):
        p = []
        while i != -1:
            n = s(i)
            if n:
                p.append(n)
            i = dirs[i][1]
        return '/'.join(reversed(p))

    out = []
    for i, dd in enumerate(dirs):
        base = dpath(i)
        for f in range(dd[4], dd[4] + dd[5]):
            out.append((base + '/' if base else '') + s(nd + f))
    return out


_SYMS = "_-,;:!?.'\"()[]{}@*/\\&#%`^+<=>|~$"


def _w(c):
    c = c.lower()
    if c in _SYMS:
        return _SYMS.index(c)
    return (100 if c.isdigit() else 200) + ord(c)


def _skey(name):
    """Sibling order inside a pfs directory (INFERRED, 0 violations on 94,414 adjacent pairs of all 55 archives):
    compare the stem (name without last extension) then the extension; case-insensitive; symbols < digits < letters;
    '-' is ignored on the first pass and only breaks ties, where it sorts after letters."""
    stem, dot, ext = name.rpartition('.')
    if not dot:
        stem, ext = name, ''
    return ([_w(c) for c in stem if c != '-'], [1000 if c == '-' else _w(c) for c in stem], [_w(c) for c in ext])


def build_pfs(paths):
    """Directory tree (BFS order, siblings sorted case-insensitively) + NUL-separated string pool."""
    tree = {(): ([], [])}  # dir tuple -> (subdir names, file names)
    for p in paths:
        parts = p.split('/')
        for i in range(len(parts) - 1):
            k = tuple(parts[:i + 1])
            if k not in tree:
                tree[k] = ([], [])
                tree[k[:-1]][0].append(parts[i])
        tree[tuple(parts[:-1])][1].append(parts[-1])
    # Row indices are handed out in blocks: visiting directories in depth-first pre-order, each visited
    # directory's sorted subdirectories get the next free contiguous block of indices.
    order = [()]
    parent = [-1]
    first = {}
    kids_of = {}

    def visit(i):
        subs = sorted(tree[order[i]][0], key=_skey)
        first[i] = len(order)
        kids_of[i] = len(subs)
        base = len(order)
        for sname in subs:
            order.append(order[i] + (sname,))
            parent.append(i)
        for j in range(base, base + len(subs)):
            visit(j)

    visit(0)
    rows = []
    files = []
    for i, key in enumerate(order):
        fl = sorted(tree[key][1], key=_skey)
        rows.append((i, parent[i], first[i], kids_of[i], len(files), len(fl)))
        files += fl
    strings = [k[-1] if k else '' for k in order] + files
    offs, pool, pos = [], bytearray(), 0
    for s in strings:
        offs.append(pos)
        b = s.encode('latin1') + b'\0'
        pool += b
        pos += len(b)
    out = struct.pack('>4I', 0, 0, len(order), len(files))
    out += b''.join(struct.pack('>6i', *r) for r in rows)
    out += struct.pack('>%dI' % len(offs), *offs) + bytes(pool)
    return out


# ---------------------------------------------------------------- compression
def find_params(raw, blob):
    """Find zlib settings (level, memLevel, strategy) that reproduce blob, or None."""
    for lv in (9, 8, 7, 6, 5, 4, 3, 2, 1):
        for ml in (8, 9):
            for st in (0, 1, 2, 3):
                if compress(raw, (lv, ml, st)) == blob:
                    return (lv, ml, st)
    return None


def compress(raw, params):
    lv, ml, st = params
    co = zlib.compressobj(lv, zlib.DEFLATED, 15, ml, st)
    return co.compress(raw) + co.flush()


def default_pk_key(path):
    """Member order inside .pk when no --like reference: per directory files first then subdirectories,
    names compared as ASCII upper-case. Matches 54/55 archives exactly; 'archive' deviates in one pair."""
    parts = path.split('/')
    return tuple((0 if i == len(parts) - 1 else 1, x.upper()) for i, x in enumerate(parts))


def member_data(pk, e):
    h, off, size, cs = e
    pk.seek(off)
    if cs == 0 or cs == size:
        return pk.read(size)
    return zlib.decompress(pk.read(cs))


# ---------------------------------------------------------------- commands
def cmd_unpack(a):
    base = a.archive_base
    ents = read_pkh(base + '.pkh')
    pk = open(base + '.pk', 'rb')
    byhash = {e[0]: e for e in ents}
    names = read_pfs(base + '.pfs') if os.path.exists(base + '.pfs') else []
    done = set()
    for n in names:
        e = byhash.get(path_hash(n))
        if e is None:
            print('warning: pfs name not in pkh:', n, file=sys.stderr)
            continue
        dest = os.path.join(a.out_dir, *n.split('/'))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, 'wb') as f:
            f.write(member_data(pk, e))
        done.add(e[0])
    un = 0
    for e in ents:
        if e[0] in done:
            continue
        dest = os.path.join(a.out_dir, '_unnamed', '%08x.bin' % e[0])
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, 'wb') as f:
            f.write(member_data(pk, e))
        un += 1
    print('unpacked %d named + %d unnamed members to %s' % (len(done), un, a.out_dir))


def scan_dir(root):
    out = []
    for dp, _, fn in os.walk(root):
        for f in fn:
            out.append(os.path.relpath(os.path.join(dp, f), root).replace(os.sep, '/'))
    return sorted(out)


def cmd_pack(a):
    paths = [p for p in scan_dir(a.in_dir) if not p.startswith('_unnamed/')]
    seen = {}
    for p in paths:
        h = path_hash(p)
        if h in seen:
            sys.exit('hash collision: %s / %s' % (seen[h], p))
        seen[h] = p
    ref, rank, rpk = {}, {}, None
    if a.like:
        rents = read_pkh(a.like + '.pkh')
        rpk = open(a.like + '.pk', 'rb')
        for n, e in enumerate(sorted(rents, key=lambda e: e[1])):
            rank[e[0]] = n
            ref[e[0]] = e

    def okey(p):
        h = path_hash(p)
        return (0, rank[h], ()) if h in rank else (1 if rank else 0, 0, default_pk_key(p))

    pk = bytearray()
    ents = []
    stats = {}
    for p in sorted(paths, key=okey):
        raw = open(os.path.join(a.in_dir, *p.split('/')), 'rb').read()
        h = path_hash(p)
        pk += b'\0' * ((-len(pk)) % ALIGN)
        off = len(pk)
        r = ref.get(h)
        mode, params = 'z', DEFAULT_PARAMS
        if r:
            _, roff, rsize, rcs = r
            if rcs == 0:
                mode = 'raw0'
            elif rcs == rsize:
                mode = 'rawN'
            elif rsize == len(raw):
                rpk.seek(roff)
                params = find_params(raw, rpk.read(rcs)) or params
        if mode == 'z':
            blob = compress(raw, params)
            if not r and (not raw or p.lower().endswith('.sxd2') or len(blob) >= STORE_RATIO * len(raw)):
                mode = 'raw0'
        if mode == 'z':
            ents.append((h, off, len(raw), len(blob)))
            pk += blob
        else:
            ents.append((h, off, len(raw), 0 if mode == 'raw0' else len(raw)))
            pk += raw
        k = (mode, params if mode == 'z' else None)
        stats[k] = stats.get(k, 0) + 1
    os.makedirs(os.path.dirname(os.path.abspath(a.archive_base)), exist_ok=True)
    open(a.archive_base + '.pk', 'wb').write(pk)
    open(a.archive_base + '.pkh', 'wb').write(write_pkh(ents))
    open(a.archive_base + '.pfs', 'wb').write(build_pfs(paths))
    print('packed %d members, %d bytes pk; modes: %s' % (len(ents), len(pk), stats))


def cmd_verify(a):
    base = a.archive_base
    ents = read_pkh(base + '.pkh')
    pk = open(base + '.pk', 'rb')
    byhash = {e[0]: e for e in ents}
    pksize = os.path.getsize(base + '.pk')
    bad = 0
    if len(byhash) != len(ents) or [e[0] for e in ents] != sorted(byhash):
        print('BAD pkh: duplicate hashes or not sorted by hash')
        bad += 1
    for e in ents:
        h, off, size, cs = e
        try:
            if off + (size if cs in (0, size) else cs) > pksize:
                raise ValueError('extends beyond end of pk')
            if len(member_data(pk, e)) != size:
                raise ValueError('decompressed size mismatch')
        except Exception as ex:
            bad += 1
            print('BAD member %08x: %s' % (h, ex))
    names = read_pfs(base + '.pfs')
    miss = [n for n in names if path_hash(n) not in byhash]
    for n in miss[:20]:
        print('pfs name without pkh entry:', n)
    unnamed = len(set(byhash) - {path_hash(n) for n in names})
    print('members %d (bad %d), pfs names %d, names missing in pkh %d, pkh entries without name %d'
          % (len(ents), bad, len(names), len(miss), unnamed))
    ok = bad == 0 and not miss
    print('VERIFY', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sp = ap.add_subparsers(dest='cmd', required=True)
    u = sp.add_parser('unpack')
    u.add_argument('archive_base')
    u.add_argument('out_dir')
    u.set_defaults(f=cmd_unpack)
    p = sp.add_parser('pack')
    p.add_argument('in_dir')
    p.add_argument('archive_base')
    p.add_argument('--like')
    p.set_defaults(f=cmd_pack)
    v = sp.add_parser('verify')
    v.add_argument('archive_base')
    v.set_defaults(f=cmd_verify)
    a = ap.parse_args()
    sys.exit(a.f(a) or 0)


if __name__ == '__main__':
    main()
