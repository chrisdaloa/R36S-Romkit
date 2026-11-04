"""Preparazione di un pack: gamelist ridotti, elenco di copia e report. Non scrive mai nell'archivio."""
import os, re, json, fnmatch, shutil, subprocess, hashlib
import xml.etree.ElementTree as ET
from .titoli import senza_numero

TAG_MEDIA = ('image', 'thumbnail', 'marquee', 'cover', 'video', 'fanart', 'titleshot', 'manual', 'wheel', 'screenshot')
ILLEGALI = re.compile(r'[\\:*?"<>|]|[. ]$')   # non validi su exFAT/FAT


def _escluso(nome, escludi):
    return any(fnmatch.fnmatch(nome, p) for p in escludi)


def _collegati(sdir, f):
    """File riferiti da .cue/.gdi/.m3u (relativi alla cartella del sistema)."""
    ext = f.lower().rsplit('.', 1)[-1]
    out = []
    if ext not in ('cue', 'gdi', 'm3u'):
        return out
    try:
        with open(os.path.join(sdir, f), errors='replace') as fh:
            testo = fh.read()
    except OSError:
        return out
    if ext == 'cue':
        out = re.findall(r'^\s*FILE\s+"([^"]+)"', testo, re.M | re.I)
    elif ext == 'gdi':
        for r in testo.splitlines()[1:]:
            m = re.match(r'\s*\d+\s+\d+\s+\d+\s+\d+\s+("?)(.+?)\1\s+\d+\s*$', r)
            if m:
                out.append(m.group(2))
    elif ext == 'm3u':
        out = [r.strip() for r in testo.splitlines() if r.strip() and not r.startswith('#')]
    return out


def carica_packs(cfg):
    with open(os.path.join(cfg.pack, 'packs.json')) as fh:
        return json.load(fh)


def _chiave(cfg, pack):
    """Impronta di tutto cio' da cui dipende la preparazione: scelta del pack, impostazioni, date di gamelist e cartelle."""
    arch = cfg.archivio
    def data(p):
        try:
            st = os.stat(p)
            return [st.st_mtime_ns, st.st_size]
        except OSError:
            return None
    sistemi = sorted({i.split('/', 1)[0] for i in pack['ids']})
    dip = {
        'v': 1, 'ids': sorted(pack['ids']), 'escludi': cfg['pack']['escludi'], 'servizio': cfg['pack']['servizio'],
        'sottocart': cfg['catalogo']['sottocartelle'], 'solo': cfg['catalogo']['solo_estensione'],
        'sis': {s: [data(os.path.join(arch, s)), data(os.path.join(arch, s, 'gamelist.xml'))] for s in sistemi},
        'srv': {d: [data(os.path.join(arch, d)), data(os.path.join(arch, d, 'gamelist.xml'))] for d in cfg['pack']['servizio']},
    }
    return hashlib.sha1(json.dumps(dip, sort_keys=True, default=str).encode()).hexdigest()


def prepara(cfg, nome, cartella, libero=None, avanza=None, cache=False):
    """Crea in <pack>/<cartella>: gamelist/, lista-copia.txt, report.txt. Restituisce il riepilogo.

    Con `cache` riusa l'esito precedente se pack, impostazioni e date di gamelist e cartelle non sono cambiati."""
    dest = os.path.join(cfg.pack, cartella)
    chiave = _chiave(cfg, carica_packs(cfg)[nome]) if cache else None
    fc = os.path.join(dest, '.cache.json')
    if cache:
        try:
            with open(fc) as fh:
                c = json.load(fh)
            if c.get('chiave') == chiave and all(os.path.exists(os.path.join(dest, x)) for x in ('lista-copia.txt', 'report.txt', 'gamelist')):
                r = c['esito']
                sd = cfg['sd']['destinazione']
                r['libero'] = shutil.disk_usage(sd).free if sd and os.path.isdir(sd) else None
                r['cache'] = True
                return r
        except (OSError, ValueError, KeyError):
            pass
    arch, escludi = cfg.archivio, cfg['pack']['escludi']
    sottocart = cfg['catalogo']['sottocartelle']
    solo_gamelist = {s for s, e in cfg['catalogo']['solo_estensione'].items() if s in cfg['pack']['servizio']}
    pack = carica_packs(cfg)[nome]
    per_sis = {}
    for i in pack['ids']:
        s, f = i.split('/', 1)
        per_sis.setdefault(s, []).append(f)

    os.makedirs(os.path.join(dest, 'gamelist'), exist_ok=True)
    lista, anomalie, note = set(), [], []
    tot = {'rom': 0, 'media': 0, 'servizio': 0}
    tab, dims = {}, {}

    def dim(rel):
        try:
            return os.path.getsize(os.path.join(arch, rel))
        except OSError:
            return None

    def aggiungi(rel, tipo, s):
        if rel in lista:
            return
        d = dim(rel)
        if d is None:
            anomalie.append(f'MANCANTE  {rel}')
            return
        lista.add(rel)
        dims[rel] = d
        tot[tipo] += d
        tab[s][tipo] += d
        b = os.path.basename(rel)
        if ILLEGALI.search(b) or len(b.encode()) > 255:
            anomalie.append(f'NOME NON VALIDO PER exFAT  {rel}')

    for k, s in enumerate(sorted(per_sis)):
        if avanza:
            avanza(s, k, len(per_sis), sub='', file=0)
        base = os.path.join(s, sottocart.get(s, ''))
        sdir = os.path.join(arch, base)
        if not os.path.isdir(sdir):
            anomalie.append(f'CARTELLA SISTEMA ASSENTE  {s}')
            continue
        tab[s] = {'n': 0, 'rom': 0, 'media': 0, 'servizio': 0}
        fatti = set()
        for f in sorted(per_sis[s]):
            p = os.path.join(sdir, f)
            if not os.path.exists(p):
                anomalie.append(f'MANCANTE  {os.path.join(base, f)}')
                continue
            tab[s]['n'] += 1
            fatti.add(f)
            if os.path.isdir(p):                       # sistema a cartelle (es. scummvm)
                for r, dd, ff in os.walk(p):
                    dd[:] = [x for x in dd if not _escluso(x, escludi)]
                    for x in ff:
                        if not _escluso(x, escludi):
                            aggiungi(os.path.relpath(os.path.join(r, x), arch), 'rom', s)
                continue
            if s in solo_gamelist:
                continue                               # copiato con la sua cartella di servizio
            aggiungi(os.path.join(base, f), 'rom', s)
            for c in _collegati(sdir, f):
                aggiungi(os.path.join(base, os.path.normpath(c)), 'rom', s)
        gl = os.path.join(sdir, 'gamelist.xml')
        if not os.path.exists(gl):
            continue
        try:
            tree = ET.parse(gl)
        except ET.ParseError:
            anomalie.append(f'GAMELIST NON VALIDO  {s}')
            continue
        root, tenuti = tree.getroot(), 0
        for g in list(root.findall('game')):
            if os.path.normpath(g.findtext('path') or '') not in fatti:
                root.remove(g)
                continue
            tenuti += 1
            voce = g.find('name')
            if voce is not None and voce.text:
                voce.text = senza_numero(s, voce.text, os.path.basename(g.findtext('path') or ''))
            for tag in TAG_MEDIA:
                r = (g.findtext(tag) or '').strip()
                if r and not r.startswith('/'):
                    rel = os.path.join(base, os.path.normpath(r))
                    if dim(rel) is not None:
                        aggiungi(rel, 'media', s)
        od = os.path.join(dest, 'gamelist', base)
        os.makedirs(od, exist_ok=True)
        ET.indent(tree)
        tree.write(os.path.join(od, 'gamelist.xml'), encoding='utf-8', xml_declaration=True)
        if len(fatti) - tenuti > 0 and s not in solo_gamelist:
            note.append(f'{s}: {len(fatti) - tenuti} giochi senza voce nel gamelist (niente immagine/descrizione)')

    servizio = []
    cart = [d for d in cfg['pack']['servizio'] if os.path.isdir(os.path.join(arch, d))]
    for kd, d in enumerate(cart):
        if avanza:
            avanza(d, kd, len(cart), sub='servizio', file=0)
        tab.setdefault(d, {'n': 0, 'rom': 0, 'media': 0, 'servizio': 0})
        nf = 0
        for r, dd, ff in os.walk(os.path.join(arch, d)):
            dd[:] = [x for x in dd if not _escluso(x, escludi)]
            for x in ff:
                if _escluso(x, escludi) or (r == os.path.join(arch, d) and x.lower() == 'gamelist.xml'):
                    continue
                rel = os.path.relpath(os.path.join(r, x), arch)
                if rel in lista:
                    continue
                lista.add(rel)
                nf += 1
                if avanza and nf % 100 == 0:
                    avanza(d, kd, len(cart), sub='servizio', file=nf)
                sz = os.path.getsize(os.path.join(r, x))
                dims[rel] = sz
                tot['servizio'] += sz
                tab[d]['servizio'] += sz
                if ILLEGALI.search(x):
                    anomalie.append(f'NOME NON VALIDO PER exFAT  {rel}')
        servizio.append(d)

    if avanza:
        avanza('', len(cart), len(cart), sub='scrivo', file=len(lista))
    with open(os.path.join(dest, 'lista-copia.txt'), 'w') as fh:
        fh.write('\n'.join(sorted(lista)) + '\n')
    totale = sum(tot.values())
    sd = cfg['sd']['destinazione']
    if libero is None and sd and os.path.isdir(sd):
        libero = shutil.disk_usage(sd).free
    gb = lambda n: f'{n / 1e9:7.2f} GB'
    with open(os.path.join(dest, 'report.txt'), 'w') as fh:
        w = lambda x='': fh.write(x + '\n')
        w(f'Pack «{nome}»  ({len(pack["ids"])} giochi scelti)')
        w(f'ROM e file collegati : {gb(tot["rom"])}')
        w(f'Immagini             : {gb(tot["media"])}')
        w(f'Cartelle di servizio : {gb(tot["servizio"])}  ({", ".join(servizio)})')
        w(f'TOTALE DA COPIARE    : {gb(totale)}   ({len(lista)} file)')
        if libero is not None:
            w(f'Libero sulla SD      : {gb(libero)}  ->  dopo la copia restano {gb(libero - totale)}')
        w()
        w(f'{"sistema":14}{"giochi":>7}{"ROM":>12}{"immagini":>12}{"servizio":>12}')
        for s, x in sorted(tab.items(), key=lambda k: -(k[1]['rom'] + k[1]['media'] + k[1]['servizio'])):
            w(f'{s:14}{x["n"]:7}{gb(x["rom"]):>12}{gb(x["media"]):>12}{gb(x["servizio"]):>12}')
        w()
        w('Note:')
        for r in note:
            w('  ' + r)
        w()
        w(f'Anomalie ({len(anomalie)}):')
        for a in anomalie[:300]:
            w('  ' + a)
    esito = {'totale': totale, 'file': len(lista), 'anomalie': anomalie, 'libero': libero, 'dest': dest, 'dimensioni': dims}
    if cache:
        try:
            with open(fc, 'w') as fh:
                json.dump({'chiave': chiave, 'esito': esito}, fh)
        except OSError:
            pass
    return esito


def copia(cfg, cartella, applica=False, destinazione=None):
    """Copia un pack preparato sulla destinazione con rsync (Linux/macOS). Senza `applica` e' un dry-run."""
    if not shutil.which('rsync'):
        raise SystemExit('rsync non trovato: installalo, oppure usa un altro copiatore con lista-copia.txt')
    dest = destinazione or cfg['sd']['destinazione']
    if not dest or not os.path.isdir(dest):
        raise SystemExit(f'Destinazione non raggiungibile: {dest!r} (imposta [sd].destinazione o passa --destinazione)')
    p = os.path.join(cfg.pack, cartella)
    opz = ['-rt', '--no-perms', '--no-owner', '--no-group', '--info=stats2,progress2']
    if not applica:
        opz.append('--dry-run')
        print('(dry-run: nulla viene scritto; usa --applica per copiare)')
    ex = [f'--exclude={e}' for e in cfg['pack']['escludi']]
    subprocess.run(['rsync', *opz, *ex, f'--files-from={p}/lista-copia.txt', cfg.archivio + '/', dest + '/'], check=True)
    if os.path.isdir(os.path.join(p, 'gamelist')):
        subprocess.run(['rsync', *opz, os.path.join(p, 'gamelist') + '/', dest + '/'], check=True)
