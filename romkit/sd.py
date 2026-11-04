"""Inventario e confronto di una SD (montata o via SSH) con l'archivio. Solo lettura: non scrive mai."""
import os, re, shutil, subprocess
from .catalogo import MEDIA, NOT_GAME

NON_GIOCO = re.compile(r'\.(state\d*|torrent|sqlite|auto|a1\.bin|b1\.bin)$')


def _voci_locali(root, skip):
    """(parti, tipo, dimensione) fino a profondita' 3, come fa find sul remoto."""
    for s in sorted(os.listdir(root)):
        if s in skip or s.startswith(('.', '_')) or not os.path.isdir(os.path.join(root, s)):
            continue
        for e in os.scandir(os.path.join(root, s)):
            if e.is_dir():
                yield (s, e.name), 'd', 0
                for e2 in os.scandir(e.path):
                    if e2.is_file():
                        yield (s, e.name, e2.name), 'f', e2.stat().st_size
            elif e.is_file():
                yield (s, e.name), 'f', e.stat().st_size


def _voci_ssh(dove, skip):
    host, _, path = dove.partition(':')
    cmd = f"cd {path!r} && find . -mindepth 2 -maxdepth 3 \\( -type f -o -type d \\) -printf '%y\\t%s\\t%P\\n'"
    r = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', host, cmd],
                       capture_output=True, text=True, timeout=300)
    if r.returncode:
        raise SystemExit(f'SSH fallito verso {host}: {r.stderr.strip()[:200]}')
    for riga in r.stdout.splitlines():
        t, sz, p = riga.split('\t', 2)
        parti = tuple(p.split('/'))
        if parti[0] not in skip and not parti[0].startswith(('.', '_')):
            yield parti, t, int(sz)


def inventario(cfg, dove):
    """{sistema: {nome_gioco: dimensione}} con le stesse regole del catalogo."""
    skip = set(cfg['catalogo']['ignora'])
    dir_sys = set(cfg['catalogo']['sistemi_cartelle'])
    sub = cfg['catalogo']['sottocartelle']
    solo = {k: v.lower() for k, v in cfg['catalogo']['solo_estensione'].items()}
    voci = list(_voci_ssh(dove, skip) if ':' in dove and not os.path.isabs(dove) else _voci_locali(dove, skip))
    nomi = {}
    for parti, t, sz in voci:
        nomi.setdefault(parti[:-1], set()).add(parti[-1])
    out = {}
    for parti, t, sz in voci:
        s = parti[0]
        base = (s, sub[s]) if s in sub and sub[s] in nomi.get((s,), set()) else (s,)
        if parti[:-1] != base:
            continue
        f = parti[-1]
        fl = f.lower()
        if f.startswith('.') or fl in MEDIA or fl.startswith('gamelist.xml') or NON_GIOCO.search(fl):
            continue
        if t == 'd':
            if s not in dir_sys:
                continue
        elif not (fl.endswith(solo[s]) if s in solo else not fl.endswith(NOT_GAME)):
            continue
        elif fl.endswith('.bin') and os.path.splitext(f)[0] + '.cue' in nomi.get(base, set()):
            continue
        out.setdefault(s, {})[f] = sz
    return out


def _gb(n):
    return f'{n / 1e9:7.2f} GB'


def _spazio_ssh(dove):
    host, _, path = dove.partition(':')
    try:
        r = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', host, f'df -B1 --output=used,avail {path!r} | tail -n 1'],
                           capture_output=True, text=True, timeout=30)
        usati, liberi = r.stdout.split()
        return {'usati': int(usati), 'liberi': int(liberi)}
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def analizza(cfg, dove, pack=None):
    """Dati strutturati del riepilogo e del confronto (pack se indicato, altrimenti archivio)."""
    sd = inventario(cfg, dove)
    out = {'dove': dove, 'riepilogo': {s: {'n': len(g), 'b': sum(g.values())} for s, g in sd.items()}}
    if os.path.isdir(dove):
        du = shutil.disk_usage(dove)
        out['spazio'] = {'usati': du.used, 'liberi': du.free}
    elif ':' in dove:
        sp = _spazio_ssh(dove)
        if sp:
            out['spazio'] = sp
    if pack:
        from .packs import carica_packs
        voluto = {}
        for i in carica_packs(cfg)[pack]['ids']:
            s, f = i.split('/', 1)
            voluto.setdefault(s, {})[f] = None
        out['rispetto_a'] = f'pack «{pack}»'
    else:
        voluto = inventario(cfg, cfg.archivio)
        out['rispetto_a'] = 'archivio'
    conf, dett = {}, []
    for s in sorted(set(sd) | set(voluto)):
        a, b = sd.get(s, {}), voluto.get(s, {})
        manca = sorted(set(b) - set(a))
        extra = sorted(set(a) - set(b))
        diversi = sorted(f for f in set(a) & set(b) if b[f] is not None and a[f] != b[f])
        conf[s] = {'sd': len(a), 'atteso': len(b), 'manca': len(manca), 'extra': len(extra), 'diversi': len(diversi)}
        dett += [('+', s, f) for f in manca] + [('-', s, f) for f in extra] + [('~', s, f) for f in diversi]
    out['confronto'], out['dettagli'] = conf, dett
    return out


def riepilogo(cfg, dove):
    r = analizza(cfg, dove)
    print(f'SD: {dove}')
    if 'spazio' in r:
        print(f'Spazio: {_gb(r["spazio"]["usati"])} usati, {_gb(r["spazio"]["liberi"])} liberi')
    print(f'{"sistema":14}{"giochi":>8}{"dimensione":>13}')
    for s, x in sorted(r['riepilogo'].items(), key=lambda k: -k[1]['b']):
        print(f'{s:14}{x["n"]:8}{_gb(x["b"]):>13}')
    print(f'{"TOTALE":14}{sum(x["n"] for x in r["riepilogo"].values()):8}{_gb(sum(x["b"] for x in r["riepilogo"].values())):>13}')
    return r


def confronta(cfg, dove, pack=None, dettagli=False):
    """Confronta la SD con l'archivio, o con un pack (cio' che la SD dovrebbe contenere)."""
    r = analizza(cfg, dove, pack)
    print(f'Confronto SD ({dove}) con {r["rispetto_a"]}\n')
    print(f'{"sistema":14}{"SD":>7}{"atteso":>8}{"mancano":>9}{"in piu":>8}{"diversi":>9}')
    t = {k: 0 for k in ('sd', 'atteso', 'manca', 'extra', 'diversi')}
    for s, x in r['confronto'].items():
        print(f'{s:14}{x["sd"]:7}{x["atteso"]:8}{x["manca"]:9}{x["extra"]:8}{x["diversi"]:9}')
        for k in t:
            t[k] += x[k]
    print(f'{"TOTALE":14}{t["sd"]:7}{t["atteso"]:8}{t["manca"]:9}{t["extra"]:8}{t["diversi"]:9}')
    print('\nLegenda: mancano = da aggiungere; in piu = non previsti (da togliere); diversi = stessa voce, dimensione diversa.')
    if dettagli:
        print()
        for seg, s, f in r['dettagli']:
            print(f'{seg} {s}/{f}')
    return r['dettagli']
