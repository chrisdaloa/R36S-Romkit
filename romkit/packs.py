"""Preparazione di un pack: gamelist ridotti, elenco di copia e report. Non scrive mai nell'archivio."""
import os, re, io, json, fnmatch, shutil, subprocess, hashlib
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


def _sbi(sdir, nomi):
    """File .sbi (protezione LibCrypt dei giochi PS1) con lo stesso nome di un disco: servono accanto a esso."""
    out = []
    for n in nomi:
        c = os.path.splitext(os.path.normpath(n))[0] + '.sbi'
        if c not in out and os.path.isfile(os.path.join(sdir, c)):
            out.append(c)
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
        'v': 2, 'ids': sorted(pack['ids']), 'escludi': cfg['pack']['escludi'], 'servizio': cfg['pack']['servizio'],
        'sottocart': cfg['catalogo']['sottocartelle'], 'solo': cfg['catalogo']['solo_estensione'],
        'sis': {s: [data(os.path.join(arch, s)), data(os.path.join(arch, s, 'gamelist.xml'))] for s in sistemi},
        'srv': {d: [data(os.path.join(arch, d)), data(os.path.join(arch, d, 'gamelist.xml'))] for d in cfg['pack']['servizio']},
    }
    return hashlib.sha1(json.dumps(dip, sort_keys=True, default=str).encode()).hexdigest()


def _data(p):
    try:
        st = os.stat(p)
        return [st.st_mtime_ns, st.st_size]
    except OSError:
        return None


def _firma(dip):
    return hashlib.sha1(json.dumps(dip, sort_keys=True, default=str).encode()).hexdigest()


def _cache_parte(cfg, tipo, nome, firma, calcola, usa):
    """Parte di pack (un sistema o una cartella di servizio) dalla cache su disco, o ricalcolata e salvata.
    La cache non dipende dal pack: lo stesso sistema con gli stessi giochi si riusa anche cambiando pack."""
    f = os.path.join(cfg.pack, '.cache-parti', tipo, re.sub(r'[^\w.-]+', '_', nome) + '.json')
    if usa:
        try:
            with open(f) as fh:
                c = json.load(fh)
            if c.get('firma') == firma:
                return c['parte'], True
        except (OSError, ValueError, KeyError):
            pass
    parte = calcola()
    if usa:
        try:
            os.makedirs(os.path.dirname(f), exist_ok=True)
            with open(f + '.tmp', 'w') as fh:
                json.dump({'firma': firma, 'parte': parte}, fh)
            os.replace(f + '.tmp', f)
        except OSError:
            pass
    return parte, False


def _sistema(cfg, s, ids):
    """Giochi scelti di un sistema: file da copiare con tipo e dimensione, gamelist ridotto, note e anomalie."""
    arch, escludi = cfg.archivio, cfg['pack']['escludi']
    sottocart = cfg['catalogo']['sottocartelle']
    solo_gamelist = {x for x, e in cfg['catalogo']['solo_estensione'].items() if x in cfg['pack']['servizio']}
    lista, anomalie, note = {}, [], []
    tot = {'rom': 0, 'media': 0, 'servizio': 0}
    parte = {'lista': lista, 'tot': tot, 'anomalie': anomalie, 'note': note, 'tab': None, 'gamelist': None}

    def dim(rel):
        try:
            return os.path.getsize(os.path.join(arch, rel))
        except OSError:
            return None

    def aggiungi(rel, tipo):
        if rel in lista:
            return
        d = dim(rel)
        if d is None:
            anomalie.append(f'MANCANTE  {rel}')
            return
        lista[rel] = [tipo, d]
        tot[tipo] += d
        b = os.path.basename(rel)
        if ILLEGALI.search(b) or len(b.encode()) > 255:
            anomalie.append(f'NOME NON VALIDO PER exFAT  {rel}')

    base = os.path.join(s, sottocart.get(s, ''))
    sdir = os.path.join(arch, base)
    if not os.path.isdir(sdir):
        anomalie.append(f'CARTELLA SISTEMA ASSENTE  {s}')
        return parte
    tab = parte['tab'] = {'n': 0, 'rom': 0, 'media': 0, 'servizio': 0}
    fatti = set()
    for f in sorted(ids):
        p = os.path.join(sdir, f)
        if not os.path.exists(p):
            anomalie.append(f'MANCANTE  {os.path.join(base, f)}')
            continue
        tab['n'] += 1
        fatti.add(f)
        if os.path.isdir(p):                       # sistema a cartelle (es. scummvm)
            for r, dd, ff in os.walk(p):
                dd[:] = [x for x in dd if not _escluso(x, escludi)]
                for x in ff:
                    if not _escluso(x, escludi):
                        aggiungi(os.path.relpath(os.path.join(r, x), arch), 'rom')
            continue
        if s in solo_gamelist:
            continue                               # copiato con la sua cartella di servizio
        aggiungi(os.path.join(base, f), 'rom')
        coll = _collegati(sdir, f)
        for c in coll:
            aggiungi(os.path.join(base, os.path.normpath(c)), 'rom')
        for c in _sbi(sdir, [f] + coll):
            aggiungi(os.path.join(base, c), 'rom')
    gl = os.path.join(sdir, 'gamelist.xml')
    if os.path.exists(gl):
        try:
            tree = ET.parse(gl)
        except ET.ParseError:
            anomalie.append(f'GAMELIST NON VALIDO  {s}')
            tree = None
        if tree is not None:
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
                            aggiungi(rel, 'media')
            ET.indent(tree)
            buf = io.BytesIO()
            tree.write(buf, encoding='utf-8', xml_declaration=True)
            parte['gamelist'] = [base, buf.getvalue().decode('utf-8')]
            if len(fatti) - tenuti > 0 and s not in solo_gamelist:
                note.append(f'{s}: {len(fatti) - tenuti} giochi senza voce nel gamelist (niente immagine/descrizione)')
    for rel, (tipo, d) in lista.items():
        tab[tipo] += d
    return parte


def _servizio(cfg, d):
    """File di una cartella di servizio (bios, temi...), senza il suo gamelist.xml: [percorso, byte, nome non valido]."""
    arch, escludi = cfg.archivio, cfg['pack']['escludi']
    out = []
    for r, dd, ff in os.walk(os.path.join(arch, d)):
        dd[:] = [x for x in dd if not _escluso(x, escludi)]
        for x in ff:
            if _escluso(x, escludi) or (r == os.path.join(arch, d) and x.lower() == 'gamelist.xml'):
                continue
            out.append([os.path.relpath(os.path.join(r, x), arch), os.path.getsize(os.path.join(r, x)), bool(ILLEGALI.search(x))])
    return {'file': out}


def prepara(cfg, nome, cartella, libero=None, avanza=None, cache=False):
    """Crea in <pack>/<cartella>: gamelist/, lista-copia.txt, report.txt. Restituisce il riepilogo.

    Con `cache` riusa l'esito precedente se pack, impostazioni e date di gamelist e cartelle non sono cambiati;
    altrimenti ricalcola solo i sistemi (e le cartelle di servizio) cambiati, riprendendo gli altri dalla cache."""
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
    solo_gamelist = {x for x, e in cfg['catalogo']['solo_estensione'].items() if x in cfg['pack']['servizio']}
    pack = carica_packs(cfg)[nome]
    per_sis = {}
    for i in pack['ids']:
        s, f = i.split('/', 1)
        per_sis.setdefault(s, []).append(f)

    shutil.rmtree(os.path.join(dest, 'gamelist'), ignore_errors=True)    # niente gamelist di altri pack
    os.makedirs(os.path.join(dest, 'gamelist'), exist_ok=True)
    lista, anomalie, note, ricalcolati = set(), [], [], []
    tot = {'rom': 0, 'media': 0, 'servizio': 0}
    tab, dims = {}, {}

    for k, s in enumerate(sorted(per_sis)):
        if avanza:
            avanza(s, k, len(per_sis), sub='', file=0)
        base = os.path.join(s, sottocart.get(s, ''))
        firma = _firma({'v': 3, 'ids': sorted(per_sis[s]), 'escludi': escludi, 'sub': sottocart.get(s, ''),
                        'solo': cfg['catalogo']['solo_estensione'].get(s), 'sg': s in solo_gamelist,
                        'd': [_data(os.path.join(arch, s)), _data(os.path.join(arch, base)),
                              _data(os.path.join(arch, base, 'gamelist.xml'))]})
        parte, dalla_cache = _cache_parte(cfg, 'sistemi', s, firma, lambda: _sistema(cfg, s, per_sis[s]), cache)
        if not dalla_cache:
            ricalcolati.append(s)
        anomalie += parte['anomalie']
        note += parte['note']
        if parte['tab'] is not None:
            tab[s] = dict(parte['tab'])
        for rel, (tipo, d) in parte['lista'].items():
            lista.add(rel)
            dims[rel] = d
        for t in tot:
            tot[t] += parte['tot'][t]
        if parte['gamelist']:
            od = os.path.join(dest, 'gamelist', parte['gamelist'][0])
            os.makedirs(od, exist_ok=True)
            with open(os.path.join(od, 'gamelist.xml'), 'wb') as fh:
                fh.write(parte['gamelist'][1].encode('utf-8'))

    servizio = []
    cart = [d for d in cfg['pack']['servizio'] if os.path.isdir(os.path.join(arch, d))]
    for kd, d in enumerate(cart):
        if avanza:
            avanza(d, kd, len(cart), sub='servizio', file=0)
        tab.setdefault(d, {'n': 0, 'rom': 0, 'media': 0, 'servizio': 0})
        firma = _firma({'v': 3, 'escludi': escludi, 'd': [_data(os.path.join(arch, d)), _data(os.path.join(arch, d, 'gamelist.xml'))]})
        parte, dalla_cache = _cache_parte(cfg, 'servizio', d, firma, lambda: _servizio(cfg, d), cache)
        if not dalla_cache:
            ricalcolati.append(d)
        for rel, sz, brutto in parte['file']:
            if rel in lista:
                continue
            lista.add(rel)
            dims[rel] = sz
            tot['servizio'] += sz
            tab[d]['servizio'] += sz
            if brutto:
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
    esito = {'totale': totale, 'file': len(lista), 'anomalie': anomalie, 'libero': libero, 'dest': dest, 'dimensioni': dims,
             'ricalcolati': ricalcolati}
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
