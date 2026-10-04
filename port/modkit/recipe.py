"""Recipes: a mod's changes as edits that ssmod applies to the player's OWN originals (bytes in, bytes out; no game data here).

  recipe/text.tsv    table<TAB>id<TAB>english                       set a row of a text table, or add it when missing
  recipe/csv.tsv     set<TAB>row<TAB>column<TAB>value              quest_param.csv cell by (row ID, column name)
                     clone<TAB>src<TAB>new<TAB>col=val<TAB>col=val  new row = copy of src with overrides (appended)
  recipe/scene.json  [{"scene": name, "set": {"Type[i]/field.path": value}, "append": [node...]},
                      {"scene": name, "create": {"bg": "ST16A", "nodes": [node...]}}]   (node = {"node": Type, field: value, ...})

Edits are textual and in place, so every byte a recipe does not touch stays exactly as in the original.
"""
import csv, io, json, os, re
from xml.sax.saxutils import escape, unescape

CSV_PATH = 'resource/boot/quest_param.csv'
SCENE_DIR = 'resource/data/scene/'
SCENE_SKELETON = ['<?xml version="1.0" encoding="shift_jis"?>', '<MapSetData>', '\t<GrimoireInfo>', '\t\t<bg>%s</bg>',
                  '\t\t<comment>TransformInspector.cs</comment>', '\t\t<xmlFilter>1</xmlFilter>', '\t\t<filter>100000</filter>',
                  '\t</GrimoireInfo>', '\t<chunk>', '\t\t<chkname>chnk</chkname>', '\t\t<data>data</data>',
                  '\t\t<version>0.8</version>', '\t\t<platform>psp2</platform>', '\t</chunk>', '\t<name>quest</name>',
                  '\t<version>0</version>', '\t<nodes>', '\t</nodes>', '</MapSetData>']


class RecipeError(Exception):
    pass


def fail(msg):
    raise RecipeError(msg)


# ------------------------------------------------------------------ text tables (UTF-16LE + BOM, CRLF; TSV, or CSV for purpose tables)
def table_lines(raw):
    if raw[:2] != b'\xff\xfe':
        fail('text table is not UTF-16LE with BOM')
    return raw[2:].decode('utf-16-le').split('\r\n')


def table_bytes(lines):
    return b'\xff\xfe' + '\r\n'.join(lines).encode('utf-16-le')


def table_set(raw, id, english, add=True):
    """Set the English cell (column 1) of row `id`; append the row (columns shaped like the table's usual row) when missing."""
    lines = table_lines(raw)
    sep = '\t' if '\t' in lines[0] else ','
    if sep in english or re.search(r'[\r\n]', english):
        fail('english text %r may not contain %r or a newline' % (english, sep))
    first = 1 if lines[0].startswith(('EF_MESSAGE_TEXT\t', 'ID,')) else 0
    idx = next((i for i in range(first, len(lines)) if lines[i].split(sep)[0] == id), None)
    if idx is not None:
        c = lines[idx].split(sep)
        c[1] = english
        lines[idx] = sep.join(c)
    elif not add:
        fail('no row %s' % id)
    else:
        cols = [l.count(sep) for l in lines[first:] if l]
        lines.insert(len(lines) - 1 if lines[-1] == '' else len(lines),
                     sep.join([id, english] + [''] * (max(set(cols), key=cols.count) - 1)))
    return table_bytes(lines)


# ------------------------------------------------------------------ scenes: a tiny span-tracking XML reader, so edits keep all other bytes
TAG = re.compile(r'<(/?)([A-Za-z_][\w.-]*)((?:[^<>"]|"[^"]*")*?)(/?)>')
ATTR = re.compile(r'([\w.-]+)="([^"]*)"')


class El:
    def __init__(self, tag, attrs, start, istart):
        self.tag, self.attrs, self.start, self.istart, self.iend, self.kids = tag, dict(ATTR.findall(attrs)), start, istart, istart, []

    def child(self, tag):
        return next((k for k in self.kids if k.tag == tag), None)

    def text(self, src):
        return unescape(src[self.istart:self.iend])


def parse(src):
    root = El('', '', 0, 0)
    stack = [root]
    for m in TAG.finditer(src):
        if m.group(1):
            e = stack.pop()
            if e.tag != m.group(2):
                fail('malformed XML: </%s> closes <%s>' % (m.group(2), e.tag))
            e.iend = m.start()
        else:
            e = El(m.group(2), m.group(3), m.start(), m.end())
            stack[-1].kids.append(e)
            if not m.group(4):
                stack.append(e)
    if len(stack) != 1 or len(root.kids) != 1:
        fail('malformed XML')
    return root.kids[0]


def fmt(v):
    return '%.6f' % v if isinstance(v, float) else str(v)


def pick(kids, sel, what):
    """One child of `kids` chosen by `[i]` (index) or `[name]` (name attribute); no selector needs exactly one candidate."""
    if sel is not None and not sel.isdigit():
        kids = [k for k in kids if k.attrs.get('name') == sel]
        sel = None
    if not kids or (sel is None and len(kids) > 1) or (sel is not None and int(sel) >= len(kids)):
        fail('%s: %s' % (what, 'no match' if not kids or sel else 'ambiguous, add [index]'))
    return kids[int(sel or 0)]


def find_node(root, sel):
    m = re.fullmatch(r'(\w+)(?::([^\[\]]+))?(?:\[(\d+)\])?', sel)
    if not m:
        fail('bad node selector %r (want Type, Type:name, Type[i] or Type:name[i])' % sel)
    nodes = root.child('nodes')
    named = lambda n: n.child('name') is not None and n.child('name').text(root.src) == m.group(2)
    kids = [n for n in nodes.kids if n.attrs.get('type') == m.group(1) and (not m.group(2) or named(n))]
    return pick(kids, m.group(3), 'node ' + sel)


def parse_scene(raw):
    try:
        src = raw.decode('cp932')
    except UnicodeDecodeError as e:
        fail('scene is not Shift-JIS: %s' % e)
    root = parse(src)
    root.src = src
    return root


def set_field(src, root, node_sel, path, value):
    """Replace the text (or an @attribute) at node/path with value, returning the new source."""
    e = find_node(root, node_sel) if node_sel else root
    segs = path.split('.')
    for s in segs[:-1] if segs[-1].startswith('@') else segs:
        m = re.fullmatch(r'([\w-]+)(?:\[([^\]]+)\])?', s)
        if not m:
            fail('bad field path %r' % path)
        e = pick([k for k in e.kids if k.tag == m.group(1)], m.group(2), 'field %s of %s' % (path, node_sel or 'scene'))
    v = escape(fmt(value))
    if segs[-1].startswith('@'):
        a = re.search(r'\b%s="[^"]*"' % re.escape(segs[-1][1:]), src[e.start:e.istart])
        if not a:
            fail('no attribute %s at %s' % (segs[-1], path))
        return src[:e.start + a.start()] + '%s="%s"' % (segs[-1][1:], v) + src[e.start + a.end():]
    if e.kids:
        fail('%s is not a leaf value' % path)
    if e.istart == e.iend and src[e.istart - 2:e.istart] == '/>':
        fail('%s is a self-closing tag' % path)
    return src[:e.istart] + v + src[e.iend:]


def render(tag, v, ind):
    """Lines for <tag> from a JSON value: scalar, or {"@": {attrs}, "#": text, child: value-or-list, ...}."""
    if not isinstance(v, dict):
        return ['%s<%s>%s</%s>' % (ind, tag, escape(fmt(v)), tag)]
    attrs = ''.join(' %s="%s"' % (k, escape(fmt(a), {'"': '&quot;'})) for k, a in v.get('@', {}).items())
    kids = [(k, x) for k, c in v.items() if k not in ('@', '#') for x in (c if isinstance(c, list) else [c])]
    if not kids:
        return ['%s<%s%s>%s</%s>' % (ind, tag, attrs, escape(fmt(v.get('#', ''))), tag)]
    out = ['%s<%s%s>' % (ind, tag, attrs)]
    for k, x in kids:
        out += render(k, x, ind + '\t')
    return out + ['%s</%s>' % (ind, tag)]


def render_node(node, ind):
    node = dict(node)
    return render('anyType', {'@': {'type': node.pop('node')}, **node}, ind)


def append_nodes(src, root, nodes):
    end = root.child('nodes').iend
    line = src.rfind('\n', 0, end) + 1  # start of the "</nodes>" line
    first = root.child('nodes').kids
    ind = re.match(r'[ \t]*', src[src.rfind('\n', 0, first[0].start) + 1:]).group() if first else src[line:end] + '\t'
    return src[:line] + ''.join(l + '\r\n' for n in nodes for l in render_node(n, ind)) + src[line:]


def scene_encode(src, name):
    try:
        return src.encode('cp932')
    except UnicodeEncodeError as e:
        fail('scene %s: not representable in Shift-JIS: %s' % (name, e))


def create_scene(spec):
    src = '\r\n'.join(SCENE_SKELETON) % escape(spec.get('bg', 'ST16A'))
    return append_nodes(src, parse_scene(src.encode('cp932')), spec.get('nodes', []))


def scene_path(name):
    return name if '/' in name else SCENE_DIR + name + '.scene'


# ------------------------------------------------------------------ quest_param.csv (Shift-JIS, CRLF, no quoting; the last row has no CRLF)
def csv_load(raw):
    text = raw.decode('cp932')
    tail = '\r' if text.endswith('\r') else ''
    rows = [r.split(',') for r in (text[:len(text) - len(tail)]).split('\r\n')]
    return rows, tail


def csv_dump(rows, tail):
    return ('\r\n'.join(','.join(r) for r in rows) + tail).encode('cp932')


def csv_cell(v):
    if re.search(r'[,"\r\n]', v):
        fail('csv value %r may not contain comma, quote or newline' % v)
    return v


def csv_apply(raw, ops):
    rows, tail = csv_load(raw)
    head, col = rows[0], lambda n: head.index(n) if n in head else fail('no column %r in quest_param.csv' % n)
    byid = lambda i: next((r for r in rows[1:] if r[col('ID')] == i), None) or fail('no row %r in quest_param.csv' % i)
    for op in ops:
        if op[0] == 'set' and len(op) == 4:
            byid(op[1])[col(op[2])] = csv_cell(op[3])
        elif op[0] == 'clone' and len(op) >= 3:
            if any(r[col('ID')] == op[2] for r in rows[1:]):
                fail('row %r already exists' % op[2])
            new = list(byid(op[1]))
            new[col('ID')] = csv_cell(op[2])
            for ov in op[3:]:
                k, _, v = ov.partition('=')
                new[col(k)] = csv_cell(v)
            rows.append(new)
        else:
            fail('bad csv.tsv line: %s' % '\t'.join(op))
    return csv_dump(rows, tail)


# ------------------------------------------------------------------ apply
def tsv(path):
    if os.path.exists(path):
        for n, l in enumerate(open(path, encoding='utf-8').read().splitlines(), 1):
            if l.strip() and not l.startswith('#'):
                yield n, l.split('\t')


def apply(rdir, get, resolve_table):
    """Apply recipe dir `rdir`; get(path) -> current bytes or None. Returns {archive path: new bytes}."""
    out = {}
    cur = lambda p: out.get(p) if p in out else get(p)

    def need(p):
        return cur(p) if cur(p) is not None else fail('%s is not in the game files' % p)
    for n, c in tsv(os.path.join(rdir, 'text.tsv')):
        if len(c) != 3:
            fail('text.tsv line %d: want table<TAB>id<TAB>english' % n)
        p = resolve_table(c[0])
        try:
            out[p] = table_set(need(p), c[1], c[2])
        except RecipeError as e:
            fail('text.tsv line %d: %s' % (n, e))
    ops = [c for _, c in tsv(os.path.join(rdir, 'csv.tsv'))]
    if ops:
        out[CSV_PATH] = csv_apply(need(CSV_PATH), ops)
    sf = os.path.join(rdir, 'scene.json')
    for e in json.load(open(sf, encoding='utf-8')) if os.path.exists(sf) else []:
        p = scene_path(e['scene'])
        if 'create' in e:
            if cur(p) is not None:
                fail('scene %s already exists; use set/append instead of create' % e['scene'])
            out[p] = scene_encode(create_scene(e['create']), p)
            continue
        root = parse_scene(need(p))
        src = root.src
        for key, value in e.get('set', {}).items():
            node, _, path = key.rpartition('/')
            src = set_field(src, parse_scene(src.encode('cp932')), node, path, value)
        if e.get('append'):
            src = append_nodes(src, parse_scene(src.encode('cp932')), e['append'])
        out[p] = scene_encode(src, p)
    return out


# ------------------------------------------------------------------ export: diff a files/-based mod against the originals
def to_val(e, src):
    if not e.kids and not e.attrs:
        return e.text(src)
    v = {'@': e.attrs} if e.attrs else {}
    if not e.kids:
        v['#'] = e.text(src)
    for k in e.kids:
        x = to_val(k, src)
        v[k.tag] = v[k.tag] + [x] if isinstance(v.get(k.tag), list) else [v[k.tag], x] if k.tag in v else x
    return v


def node_val(n, src):
    return {'node': n.attrs['type'], **{k.tag: to_val(k, src) for k in n.kids}}


def diff_el(a, b, sa, sb, segs, out):
    if a.tag != b.tag or a.attrs.keys() != b.attrs.keys() or [k.tag for k in a.kids] != [k.tag for k in b.kids]:
        fail('structure differs at %s' % '.'.join(segs))
    out += [('.'.join(segs + ['@' + k]), v) for k, v in b.attrs.items() if v != a.attrs[k]]
    if not a.kids:
        if a.text(sa) != b.text(sb):
            out.append(('.'.join(segs), b.text(sb)))
        return
    seen = {}
    for ka, kb in zip(a.kids, b.kids):
        i = seen[ka.tag] = seen.get(ka.tag, -1) + 1
        multi = sum(k.tag == ka.tag for k in a.kids) > 1
        diff_el(ka, kb, sa, sb, segs + [ka.tag + ('[%d]' % i if multi else '')], out)


def export_scene(path, raw, orig):
    name = os.path.splitext(os.path.basename(path))[0]
    b = parse_scene(raw)
    if orig is None:
        nodes = [node_val(n, b.src) for n in b.child('nodes').kids]
        return {'scene': name, 'create': {'bg': b.child('GrimoireInfo').child('bg').text(b.src), 'nodes': nodes}}
    a = parse_scene(orig)
    na, nb = a.child('nodes').kids, b.child('nodes').kids
    if len(nb) < len(na):
        fail('%s: nodes were removed (recipes can set values and append nodes)' % path)
    sets = []
    for ea, eb in zip([k for k in a.kids if k.tag != 'nodes'], [k for k in b.kids if k.tag != 'nodes']):
        diff_el(ea, eb, a.src, b.src, [ea.tag], sets)
    seen = {}
    for ea, eb in zip(na, nb):
        t = ea.attrs['type']
        i = seen[t] = seen.get(t, -1) + 1
        mark = len(sets)
        diff_el(ea, eb, a.src, b.src, [], sets)
        sets[mark:] = [('%s[%d]/%s' % (t, i, k), v) for k, v in sets[mark:]]
    rec = {'scene': name, 'set': dict(sets)}
    rec['append'] = [node_val(n, b.src) for n in nb[len(na):]]
    return {k: v for k, v in rec.items() if v}


def export(files, original, resolve_table):
    """files {path: bytes} -> {recipe file name: text}. Verified by re-applying the recipe to the originals."""
    tsv_text, tsv_csv, scenes = [], [], []
    for p, raw in sorted(files.items()):
        orig, ext = original(p), os.path.splitext(p)[1].lower()
        if ext in ('.u16', '.msgt') and orig is not None:
            a, b = table_lines(orig), table_lines(raw)
            sep = '\t' if '\t' in a[0] else ','
            old = {l.split(sep)[0]: l.split(sep) for l in a}
            short = os.path.splitext(os.path.basename(p))[0]
            name = short if resolve_table(short) == p else p
            for l in b:
                c = l.split(sep)
                if l and c[0] in old and old[c[0]][1:2] != c[1:2] or l and c[0] not in old:
                    tsv_text.append('\t'.join([name, c[0], c[1]]))
        elif ext == '.scene':
            scenes.append(export_scene(p, raw, orig))
        elif p == CSV_PATH:
            tsv_csv += export_csv(raw, orig)
        else:
            fail('%s: cannot be expressed as a recipe (%s); share it only if it is original content '
                 '(list it in mod.json "original_files")' % (p, 'binary or unsupported type' if orig is not None else 'new file'))
    res = {}
    if tsv_text:
        res['text.tsv'] = '\n'.join(tsv_text) + '\n'
    if tsv_csv:
        res['csv.tsv'] = '\n'.join('\t'.join(c) for c in tsv_csv) + '\n'
    if scenes:
        res['scene.json'] = json.dumps(scenes, indent=1, ensure_ascii=False) + '\n'
    return res


def export_csv(raw, orig):
    a, _ = csv_load(orig)
    b, _ = csv_load(raw)
    head, ida = a[0], {r[4]: r for r in a[1:]}
    if b[0] != head:
        fail('%s: header changed' % CSV_PATH)
    ops = []
    for r in b[1:]:
        if r[4] in ida:
            ops += [['set', r[4], head[i], v] for i, v in enumerate(r) if v != ida[r[4]][i]]
        else:
            src = min(a[1:], key=lambda s: sum(x != y for x, y in zip(s, r)))
            ops.append(['clone', src[4], r[4]] + ['%s=%s' % (head[i], v) for i, v in enumerate(r) if v != src[i] and i != 4])
    return ops
