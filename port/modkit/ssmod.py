#!/usr/bin/env python3
"""ssmod: mod kit for Soul Sacrifice Delta (PCSA00152). Mods ship as archive_patchN.{pk,pkh,pfs} built with pktool.

  ssmod.py new <mod>                          create mods/<mod>/{mod.json,files/}
  ssmod.py extract <path-or-glob> [--mod M]   copy original archive members into a mod's files/
  ssmod.py text get <table> <id> [--mod M]    read a row of a .u16/.msgt table
  ssmod.py text set <table> <id> <english> --mod M [--add]
  ssmod.py validate <mod...>                  check text tables, scenes, quest_param.csv
  ssmod.py export-recipe <mod> [--out NAME]   turn a files/-based mod into a shareable recipe-only mod (mods/<mod>_recipe)
  ssmod.py pack-share <mod>                   zip mod.json + recipe/ (+ original_files) for sharing, never retail game data
  ssmod.py build <mod...> [--force] [--slot N] [--out DIR]   merge mods (later mod wins) and pack
  ssmod.py install [build_dir] [--target APPDIR]             copy archive_patchN into the game
  ssmod.py uninstall [--slot N] [--target APPDIR]            remove patch archives (retail state)
"""
import argparse, csv, fnmatch, io, json, os, re, shutil, subprocess, sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = os.path.dirname(ROOT)
PKTOOL = os.path.join(PORT, 'tools', 'pk', 'pktool.py')
sys.path.insert(0, os.path.dirname(PKTOOL))
import pktool  # noqa: E402
import recipe  # noqa: E402

PACKDIR = os.path.join('resource', 'data', 'pack', 'mount', 'retail')
# SS_APP: the installed game (Vita3K: <pref-path>/ux0/app/PCSA00152). SS_DUMP: a dump folder holding resource/ (default: SS_APP),
# used only to read the retail archive.pk/voice_ue.pk originals.
APP = os.environ.get('SS_APP') or os.path.join(PORT, 'vita3k-fs', 'ux0', 'app', 'PCSA00152')
RETAIL = os.path.join(os.environ.get('SS_DUMP') or APP, PACKDIR)
CACHE = os.path.join(PORT, 'scratch', 'modkit_cache')
MODS = os.path.join(ROOT, 'mods')
BUILD = os.path.join(ROOT, 'build')
ORIG_ARCHIVES = ('archive', 'voice_ue')
TEXT_EXT = ('.u16', '.msgt')


def die(msg):
    sys.exit('error: ' + msg)


# ------------------------------------------------------------------ original archives
def names():
    """{lowercased path: (archive, real path)} for every named member of the retail archives (cached)."""
    cf = os.path.join(CACHE, 'names.json')
    if not os.path.exists(cf):
        idx = {}
        for a in ORIG_ARCHIVES:
            for n in pktool.read_pfs(os.path.join(RETAIL, a + '.pfs')):
                idx[n.lower()] = (a, n)
        os.makedirs(CACHE, exist_ok=True)
        json.dump(idx, open(cf, 'w'))
    return json.load(open(cf))


def original(path):
    """Bytes of an original archive member (unpacked once into the cache), or None if it is not in the retail archives."""
    hit = names().get(path.lower())
    if not hit:
        return None
    dest = os.path.join(CACHE, *hit[1].split('/'))
    if not os.path.exists(dest):
        base = os.path.join(RETAIL, hit[0])
        ent = {e[0]: e for e in pktool.read_pkh(base + '.pkh')}[pktool.path_hash(hit[1])]
        with open(base + '.pk', 'rb') as pk:
            data = pktool.member_data(pk, ent)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        open(dest, 'wb').write(data)
    return open(dest, 'rb').read()


def resolve_table(table):
    """Archive path of a text table given a full path or a bare file name, extension optional (must be unique)."""
    t = table.replace('\\', '/').lower()
    if t in names():
        return names()[t][1]
    hits = [v[1] for k, v in names().items() if k.endswith(TEXT_EXT)
            and (k.endswith('/' + t) or os.path.splitext(k)[0].endswith('/' + t))]
    if len(hits) != 1:
        die('table %r matches %d members%s' % (table, len(hits), ': ' + ', '.join(hits[:6]) if hits else ''))
    return hits[0]


# ------------------------------------------------------------------ mods
def mod_dir(name):
    d = os.path.join(MODS, name)
    if not os.path.isdir(d):
        die('no such mod: %s' % name)
    return d


def mod_files(name):
    root = os.path.join(mod_dir(name), 'files')
    return pktool.scan_dir(root) if os.path.isdir(root) else []


def mod_recipe(name):
    return os.path.join(mod_dir(name), 'recipe')


def mod_meta(name):
    return json.load(open(os.path.join(mod_dir(name), 'mod.json'), encoding='utf-8'))


def default_mod(a):
    if a.mod:
        return a.mod
    mods = [m for m in os.listdir(MODS) if os.path.isdir(os.path.join(MODS, m))] if os.path.isdir(MODS) else []
    if len(mods) != 1:
        die('pass --mod (existing mods: %s)' % ', '.join(mods) or 'none')
    return mods[0]


def cmd_new(a):
    d = os.path.join(MODS, a.mod)
    if os.path.exists(d):
        die('mod exists: ' + d)
    os.makedirs(os.path.join(d, 'files', 'resource'))
    meta = {'name': a.mod, 'author': '', 'description': '', 'version': '0.1.0', 'slot': 1}
    json.dump(meta, open(os.path.join(d, 'mod.json'), 'w', encoding='utf-8'), indent=2)
    print('created', d)


def cmd_extract(a):
    mod = default_mod(a)
    pat = a.pattern.replace('\\', '/').lower()
    hits = sorted(v[1] for k, v in names().items() if fnmatch.fnmatchcase(k, pat))
    if not hits:
        die('no archive member matches ' + a.pattern)
    for p in hits:
        dest = os.path.join(mod_dir(mod), 'files', *p.split('/'))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        open(dest, 'wb').write(original(p))
        print('extracted', p)


# ------------------------------------------------------------------ text tables
def read_table(path_or_bytes):
    raw = path_or_bytes if isinstance(path_or_bytes, bytes) else open(path_or_bytes, 'rb').read()
    if raw[:2] != b'\xff\xfe':
        die('text table is not UTF-16LE with BOM')
    return raw[2:].decode('utf-16-le').split('\r\n')


def cmd_text(a):
    arch = resolve_table(a.table)
    local = os.path.join(mod_dir(a.mod), 'files', *arch.split('/')) if a.mod else None
    src = local if local and os.path.exists(local) else None
    lines = read_table(src) if src else read_table(original(arch))
    idx = next((i for i, l in enumerate(lines) if i and l.split('\t')[0] == a.id), None)
    if a.op == 'get':
        if idx is None:
            die('no row %s in %s' % (a.id, arch))
        c = lines[idx].split('\t')
        print('%s\ten: %s\tjp: %s' % (c[0], c[1], c[2] if len(c) > 2 else ''))
        return
    if not a.mod or a.english is None:
        die('text set needs --mod and <english>')
    try:
        out = recipe.table_set(recipe.table_bytes(lines), a.id, a.english, add=a.add)
    except recipe.RecipeError as e:
        die('%s (use --add to append a missing row)' % e)
    os.makedirs(os.path.dirname(local), exist_ok=True)
    open(local, 'wb').write(out)
    print('set %s = %r in mods/%s/files/%s' % (a.id, a.english, a.mod, arch))


# ------------------------------------------------------------------ validation
def check_text(path, raw, orig, err):
    if raw[:2] != b'\xff\xfe':
        return err('missing UTF-16LE BOM')
    try:
        lines = raw[2:].decode('utf-16-le').split('\r\n')
    except UnicodeDecodeError as e:
        return err('not valid UTF-16LE: %s' % e)
    olines = read_table(orig) if orig else None
    has_header = olines is None or olines[0].startswith('EF_MESSAGE_TEXT\t')  # some retail tables have none
    if has_header and not lines[0].startswith('EF_MESSAGE_TEXT\t'):
        err('header is not EF_MESSAGE_TEXT')
    bare = lambda ls: sum(l.count('\n') + l.count('\r') for l in ls)  # a few originals have in-cell newlines
    if bare(lines) > (bare(olines) if olines else 0):
        err('bare LF/CR found (rows must end in CRLF)')
    if olines is None:
        return
    if has_header and lines[0].split('\t')[:2] != olines[0].split('\t')[:2]:
        err('header differs from original: %r vs %r' % (lines[0], olines[0]))
    if lines[-1] != olines[-1]:
        err('file should end like the original (%r)' % olines[-1])
    ocols = {l.split('\t')[0]: l.count('\t') for l in olines[has_header:] if l}
    common = max(set(ocols.values()), key=list(ocols.values()).count) if ocols else 0
    for n, l in enumerate(lines[has_header:], 1 + has_header):
        want = ocols.get(l.split('\t')[0], common)
        if l and l.count('\t') != want:
            err('line %d (%s): %d columns, original has %d' % (n, l.split('\t')[0], l.count('\t') + 1, want + 1))




def xml_sig(root):
    """Tag paths of the root, plus per anyType@type the tag paths below it."""
    out = {'': set()}

    def walk(e, path, key):
        for c in e:
            p = path + '/' + c.tag
            k = c.get('type') if c.tag == 'anyType' else key
            out.setdefault(k or '', set()).add(p)
            walk(c, p, k)
    walk(root, root.tag, None)
    return root.tag, out


def parse_scene(raw):
    text = raw.decode('cp932')
    return ET.fromstring(re.sub(r'^<\?xml[^>]*\?>', '', text.lstrip('﻿'), count=1).strip())


def check_scene(path, raw, orig, err):
    try:
        root = parse_scene(raw)
    except (UnicodeDecodeError, ET.ParseError) as e:
        return err('scene is not well-formed Shift-JIS XML: %s' % e)
    if b'shift_jis' not in raw[:80].lower():
        err('XML declaration should say encoding="shift_jis"')
    if orig is None:
        return
    (rt, sig), (ort, osig) = xml_sig(root), xml_sig(parse_scene(orig))
    if rt != ort:
        err('root <%s> differs from original <%s>' % (rt, ort))
    for k, paths in sig.items():
        if k in osig and paths != osig[k]:
            err('node schema for %r differs from original: %s' % (k, sorted(paths ^ osig[k])[:4]))


def check_csv(path, raw, orig, err):
    try:
        rows = list(csv.reader(io.StringIO(raw.decode('cp932'))))
    except UnicodeDecodeError as e:
        return err('not valid Shift-JIS: %s' % e)
    n = len(rows[0])
    for i, r in enumerate(rows, 1):
        if r and len(r) != n:
            err('line %d has %d columns, header has %d' % (i, len(r), n))
    if orig is not None and len(next(csv.reader(io.StringIO(orig.decode('cp932'))))) != n:
        err('header column count differs from original')


CHECKS = {'.u16': check_text, '.msgt': check_text, '.scene': check_scene, '.csv': check_csv}


def content(mods, force=True):
    """{archive path: bytes} of what the mods add: all files/ first (later mod wins), then each mod's recipe applied on top."""
    merged = {}  # path -> (mod, bytes)
    for m in mods:
        for p in mod_files(m):
            data = open(os.path.join(mod_dir(m), 'files', *p.split('/')), 'rb').read()
            if p in merged and merged[p][1] != data:
                if not force:
                    die('conflict on %s between %s and %s (use --force: later mod wins)' % (p, merged[p][0], m))
                print('  override %s: %s replaces %s' % (p, m, merged[p][0]))
            merged[p] = (m, data)
    files = {p: d for p, (_, d) in merged.items()}
    for m in mods:
        if os.path.isdir(mod_recipe(m)):
            try:
                files.update(recipe.apply(mod_recipe(m), lambda p: files[p] if p in files else original(p), resolve_table))
            except (recipe.RecipeError, KeyError, ValueError) as e:
                die('recipe of %s: %s' % (m, e))
    return files


def validate(mod):
    bad = 0
    files = content([mod])
    for p in sorted(files):
        ext = os.path.splitext(p)[1].lower()
        if not p.startswith('resource/'):
            print('  WARN %s: path should start with resource/' % p)
        if original(p) is None:
            print('  note %s: new file (not in retail archives)' % p)
        if ext in CHECKS:
            def err(msg, p=p):
                nonlocal bad
                bad += 1
                print('  FAIL %s: %s' % (p, msg))
            CHECKS[ext](p, files[p], original(p), err)
    print('validate %s: %s' % (mod, 'OK' if not bad else '%d problem(s)' % bad))
    return bad


def cmd_validate(a):
    sys.exit(1 if sum(validate(m) for m in a.mods) else 0)


# ------------------------------------------------------------------ sharing
def cmd_export_recipe(a):
    if os.path.isdir(mod_recipe(a.mod)):
        die('%s already has a recipe/ folder' % a.mod)
    keep = set(mod_meta(a.mod).get('original_files', []))
    if any(p.lower() in names() for p in keep):
        die('"original_files" may not name paths that exist in the retail archives')
    if os.path.exists(os.path.join(MODS, a.out or a.mod + '_recipe')):
        die('output mod exists: ' + (a.out or a.mod + '_recipe'))
    files = {p: open(os.path.join(mod_dir(a.mod), 'files', *p.split('/')), 'rb').read() for p in mod_files(a.mod)}
    todo = {p: d for p, d in files.items() if p not in keep}
    try:
        rec = recipe.export(todo, original, resolve_table)
        out = os.path.join(MODS, a.out or a.mod + '_recipe')
        os.makedirs(os.path.join(out, 'recipe'))
        for name, text in rec.items():
            open(os.path.join(out, 'recipe', name), 'wb').write(text.encode('utf-8'))
        if recipe.apply(os.path.join(out, 'recipe'), original, resolve_table) != todo:  # prove it reproduces the mod
            raise recipe.RecipeError('the exported recipe does not reproduce the mod byte for byte (unsupported edit, e.g. reordered rows)')
    except recipe.RecipeError as e:
        shutil.rmtree(os.path.join(MODS, a.out or a.mod + '_recipe'), ignore_errors=True)
        die(str(e))
    meta = dict(mod_meta(a.mod), name=os.path.basename(out))
    json.dump(meta, open(os.path.join(out, 'mod.json'), 'w', encoding='utf-8'), indent=2)
    for p in keep:
        os.makedirs(os.path.dirname(os.path.join(out, 'files', *p.split('/'))), exist_ok=True)
        shutil.copyfile(os.path.join(mod_dir(a.mod), 'files', *p.split('/')), os.path.join(out, 'files', *p.split('/')))
    print('wrote %s (%s) and verified it reproduces %d file(s) byte for byte' % (out, ', '.join(rec), len(todo)))


def cmd_pack_share(a):
    import zipfile
    keep = mod_meta(a.mod).get('original_files', [])
    stray = [p for p in mod_files(a.mod) if p not in keep]
    bad = [p for p in keep if p.lower() in names() or p not in mod_files(a.mod)]
    if stray:
        die('files/ holds files not listed in mod.json "original_files" (game data is never shared): ' + ', '.join(stray[:5]))
    if bad:
        die('"original_files" entries that exist in the retail archives or are missing from files/: ' + ', '.join(bad[:5]))
    rdir = mod_recipe(a.mod)
    members = [('mod.json', os.path.join(mod_dir(a.mod), 'mod.json'))]
    members += [('recipe/' + p, os.path.join(rdir, *p.split('/'))) for p in (pktool.scan_dir(rdir) if os.path.isdir(rdir) else [])]
    members += [('files/' + p, os.path.join(mod_dir(a.mod), 'files', *p.split('/'))) for p in keep]
    os.makedirs(BUILD, exist_ok=True)
    dest = os.path.join(BUILD, a.mod + '.zip')
    with zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED) as z:
        for arc, f in sorted(members):
            z.writestr(zipfile.ZipInfo(arc, (2020, 1, 1, 0, 0, 0)), open(f, 'rb').read(), zipfile.ZIP_DEFLATED)
    print('wrote %s: %s' % (dest, ', '.join(m[0] for m in sorted(members))))


# ------------------------------------------------------------------ build / install
def cmd_build(a):
    slots = {mod_meta(m).get('slot', 1) for m in a.mods}
    if a.slot is None and len(slots) != 1:
        die('mods use different slots %s; pass --slot' % sorted(slots))
    slot = a.slot if a.slot is not None else slots.pop()
    if sum(validate(m) for m in a.mods):
        die('validation failed')
    merged = content(a.mods, a.force)
    if not merged:
        die('nothing to build')
    out = os.path.abspath(a.out or BUILD)
    stage = os.path.join(out, '_stage')
    shutil.rmtree(stage, ignore_errors=True)
    for p, data in merged.items():
        os.makedirs(os.path.dirname(os.path.join(stage, *p.split('/'))), exist_ok=True)
        open(os.path.join(stage, *p.split('/')), 'wb').write(data)
    base = os.path.join(out, 'archive_patch%d' % slot)
    for run in (['pack', stage, base], ['verify', base]):
        if subprocess.call([sys.executable, PKTOOL] + run):
            die('pktool %s failed' % run[0])
    shutil.rmtree(stage)
    print('built %s.{pk,pkh,pfs}: %d file(s) from %s' % (base, len(merged), ', '.join(a.mods)))


def dest_dir(target):
    return os.path.join(os.path.abspath(target), PACKDIR)


def cmd_install(a):
    src = os.path.abspath(a.build or BUILD)
    found = sorted(f for f in os.listdir(src) if re.fullmatch(r'archive_patch\d+\.(pk|pkh|pfs)', f)) if os.path.isdir(src) else []
    if not found:
        die('no archive_patchN files in ' + src)
    for f in found:
        shutil.copyfile(os.path.join(src, f), os.path.join(dest_dir(a.target), f))
        print('installed', f)


def cmd_uninstall(a):
    d = dest_dir(a.target)
    pat = r'archive_patch%s\.(pk|pkh|pfs)' % (a.slot if a.slot is not None else r'\d+')
    for f in sorted(os.listdir(d)):
        if re.fullmatch(pat, f):
            os.remove(os.path.join(d, f))
            print('removed', f)


# ------------------------------------------------------------------ cli
def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # Japanese text on a cp1252 Windows console
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)

    def add(name, fn, *args):
        p = sub.add_parser(name)
        p.set_defaults(fn=fn)
        for flags, kw in args:
            p.add_argument(*flags, **kw)
        return p
    tgt = (('--target',), dict(default=APP, help='Vita3K app dir (default: the port install)'))
    add('new', cmd_new, (('mod',), {}))
    add('extract', cmd_extract, (('pattern',), {}), (('--mod',), {}))
    t = add('text', cmd_text, (('op',), dict(choices=['get', 'set'])), (('table',), {}), (('id',), {}),
            (('english',), dict(nargs='?')), (('--mod',), {}), (('--add',), dict(action='store_true')))
    add('validate', cmd_validate, (('mods',), dict(nargs='+')))
    add('export-recipe', cmd_export_recipe, (('mod',), {}), (('--out',), {}))
    add('pack-share', cmd_pack_share, (('mod',), {}))
    add('build', cmd_build, (('mods',), dict(nargs='+')), (('--force',), dict(action='store_true')),
        (('--slot',), dict(type=int)), (('--out',), {}))
    add('install', cmd_install, (('build',), dict(nargs='?')), tgt)
    add('uninstall', cmd_uninstall, (('--slot',), dict(type=int)), tgt)
    a = ap.parse_args()
    a.fn(a)


if __name__ == '__main__':
    main()
