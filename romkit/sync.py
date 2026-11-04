"""Piano di sincronizzazione di una SD con un pack: cosa aggiungere, aggiornare, togliere. Solo lettura."""
import os, re, fnmatch, subprocess, shutil, time
from . import packs

SUPPORTO = ('.txt', '.cfg', '.ini', '.sh', '.db', '.xml', '.json')   # file di configurazione degli emulatori: mai da togliere
SALVATAGGI = ('.srm', '.sav', '.state', '.auto', '.rtc', '.mcr', '.mcd', '.eep', '.fla', '.sra', '.nv')


def _remoto(dove):
    return ':' in dove and not os.path.isabs(dove)


def _file_sd(dove, escludi, ignora, stato=None):
    """{percorso relativo: dimensione} dei file nelle cartelle dei sistemi della SD."""
    out = {}
    if _remoto(dove):
        host, _, path = dove.partition(':')
        cmd = f"cd {path!r} && find . -mindepth 2 -type f -printf '%s\\t%P\\n'"
        r = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', host, cmd],
                           capture_output=True, text=True, timeout=600)
        if r.returncode:
            raise SystemExit(f'SSH fallito verso {host}: {r.stderr.strip()[:200]}')
        for riga in r.stdout.splitlines():
            sz, p = riga.split('\t', 1)
            out[p] = int(sz)
    else:
        for s in os.listdir(dove):
            if s.startswith(('.', '_')) or not os.path.isdir(os.path.join(dove, s)):
                continue
            for r, dd, ff in os.walk(os.path.join(dove, s)):
                for f in ff:
                    p = os.path.join(r, f)
                    out[os.path.relpath(p, dove)] = os.path.getsize(p)
                if stato is not None:
                    stato['contati'] = len(out)
    return {p: n for p, n in out.items()
            if p.split('/', 1)[0] not in ignora and not any(fnmatch.fnmatch(os.path.basename(p), e) for e in escludi)}


def piano(cfg, dove, pack, cartella='_anteprima', stato=None):
    """Confronta file per file la SD con la lista di copia del pack.

    Si toglie solo cio' che sta in un sistema del pack, esiste anche nell'archivio con lo stesso percorso e non e' nel pack:
    salvataggi, cartelle di servizio, sistemi fuori dal pack e file estranei all'archivio non vengono mai proposti."""
    stato = stato if stato is not None else {}
    stato.update(fase='pack', passo=1)
    r = packs.prepara(cfg, pack, cartella, cache=True, avanza=lambda s, k, n, **x: stato.update(sistema=s, fatti=k, totale=n, **x))
    with open(os.path.join(r['dest'], 'lista-copia.txt')) as fh:
        voluto = {x for x in fh.read().split('\n') if x}
    arch, dims = cfg.archivio, r.get('dimensioni') or {}
    sistemi = {i.split('/', 1)[0] for i in packs.carica_packs(cfg)[pack]['ids']} - set(cfg['sync']['non_toccare'])
    ignora = set(cfg['catalogo']['ignora']) | set(cfg['pack']['servizio'])
    stato.update(fase='scheda', passo=2, contati=0)
    sd = _file_sd(dove, cfg['pack']['escludi'], ignora, stato)
    stato.update(fase='confronto', passo=3, fatti=0, totale=len(voluto))
    sd_tutti = sd
    agg, upd, tog = [], [], []
    for k, p in enumerate(sorted(voluto)):
        if k % 500 == 0:
            stato['fatti'] = k
        n = dims.get(p)
        if n is None:
            try:
                n = os.path.getsize(os.path.join(arch, p))
            except OSError:
                continue
        if p.split('/', 1)[0] in ignora:
            continue                                   # file di servizio: non fanno parte del confronto
        if p not in sd:
            agg.append((p, n))
        elif sd[p] != n:
            upd.append((p, n))
    for p, n in sorted(sd.items()):
        b = os.path.basename(p).lower()
        if p.split('/', 1)[0] not in sistemi or p in voluto or b.startswith('gamelist.xml') or b.endswith(SALVATAGGI + SUPPORTO) or '.state' in b:
            continue
        if os.path.isfile(os.path.join(arch, p)):
            tog.append((p, n))
    def somma(l):
        return sum(n for _, n in l)
    per = {}
    for k, l in (('aggiungi', agg), ('aggiorna', upd), ('togli', tog)):
        for p, n in l:
            x = per.setdefault(p.split('/', 1)[0], {'aggiungi': [0, 0], 'aggiorna': [0, 0], 'togli': [0, 0]})[k]
            x[0] += 1
            x[1] += n
    return {'pack': pack, 'cartella': r['dest'], 'anomalie': r['anomalie'],
            'aggiungi': agg, 'aggiorna': upd, 'togli': tog,
            'byte': {'aggiungi': somma(agg), 'aggiorna': somma(upd), 'togli': somma(tog)},
            'per_sistema': per, 'file_sd': len(sd_tutti), 'byte_sd': sum(sd_tutti.values())}


SOGLIA_TOGLI = 0.20          # oltre questa quota della scheda serve una seconda conferma


def _sicuro(p):
    return p and not os.path.isabs(p) and '..' not in p.split('/')


def richiede_conferma(piano, sistemi=None):
    """True se le rimozioni superano la soglia (per numero di file o per dimensione)."""
    t = [(p, n) for p, n in piano['togli'] if sistemi is None or p.split('/', 1)[0] in sistemi]
    return bool(piano['file_sd']) and (len(t) > SOGLIA_TOGLI * piano['file_sd'] or sum(n for _, n in t) > SOGLIA_TOGLI * max(1, piano['byte_sd']))


def applica(cfg, dove, piano, aggiungi=True, togli=True, sistemi=None, stato=None):
    """Esegue il piano su una SD montata. Le rimozioni vanno in _rimossi/<data>/, mai cancellate.

    `sistemi` limita l'operazione a quei sistemi; `stato` e' un dict aggiornato con la fase corrente."""
    if _remoto(dove) or not os.path.isdir(dove):
        raise SystemExit('La sincronizzazione scrive solo su schede montate su questo PC')
    stato = stato if stato is not None else {}
    scelti = lambda l: [(p, n) for p, n in l if _sicuro(p) and (sistemi is None or p.split('/', 1)[0] in sistemi)]
    agg = scelti(piano['aggiungi'] + piano['aggiorna']) if aggiungi else []
    tog = scelti(piano['togli']) if togli else []
    if agg:
        libero = shutil.disk_usage(dove).free + sum(n for _, n in tog)
        servono = sum(n for _, n in agg)
        if servono * 1.02 > libero:
            raise SystemExit(f'Spazio insufficiente: servono {servono / 1e9:.1f} GB, disponibili {libero / 1e9:.1f} GB')
    data = time.strftime('%Y-%m-%d_%H%M%S')
    log = [f'Sincronizzazione {data} - {piano["pack"]} -> {dove}']
    stato.update(fase='togli', fatti=0, totale=len(tog), passi=(bool(tog) + bool(agg) + 1))
    for i, (p, n) in enumerate(tog):
        src = os.path.join(dove, p)
        dst = os.path.join(dove, '_rimossi', data, p)
        if os.path.isfile(src):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            os.replace(src, dst)
            log.append(f'- {p}')
        stato['fatti'] = i + 1
    stato.update(fase='copia', fatti=0, totale=len(agg))
    if agg:
        lista = os.path.join(piano['cartella'], 'lista-sync.txt')
        with open(lista, 'w') as fh:
            fh.write('\n'.join(p for p, _ in agg) + '\n')
        ex = [f'--exclude={e}' for e in cfg['pack']['escludi']]
        stato.update(byte_tot=sum(n for _, n in agg), byte_fatti=0, pct=0, velocita='', resta='')
        pr = subprocess.Popen(['rsync', '-rt', '--no-perms', '--no-owner', '--no-group', '--info=progress2,name0', *ex,
                               f'--files-from={lista}', cfg.archivio + '/', dove + '/'],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        buf = ''
        while True:
            c = pr.stdout.read(1)
            if not c:
                break
            if c in '\r\n':
                m = re.match(r'\s*([\d.,]+)\s+(\d+)%\s+(\S+/s)\s+(\d+:\d+:\d+)', buf)
                if m:
                    stato.update(byte_fatti=int(re.sub(r'\D', '', m.group(1))), pct=int(m.group(2)),
                                 velocita=m.group(3), resta=m.group(4))
                buf = ''
            else:
                buf += c
        err = pr.stderr.read()
        if pr.wait():
            raise SystemExit('Copia interrotta: ' + (err.strip()[-300:] or f'rsync {pr.returncode}'))
        log += [f'+ {p}' for p, _ in agg]
    stato['fase'] = 'gamelist'
    gl = os.path.join(piano['cartella'], 'gamelist')
    if os.path.isdir(gl) and (agg or tog):
        r = subprocess.run(['rsync', '-rt', '--no-perms', '--no-owner', '--no-group', gl + '/', dove + '/'], capture_output=True, text=True)
        if r.returncode:
            raise SystemExit('Gamelist non aggiornati: ' + r.stderr.strip()[-300:])
    registro = os.path.join(piano['cartella'], f'sync-{data}.log')
    try:
        with open(registro, 'w') as fh:
            fh.write('\n'.join(log) + '\n')
    except OSError:
        registro = None
    return {'aggiunti': len(agg), 'tolti': len(tog), 'cestino': f'_rimossi/{data}' if tog else None, 'registro': registro}


# ---- cestino _rimossi/<data>/ sulla scheda: elenco, ripristino, svuotamento ----
DATA_CESTINO = re.compile(r'^\d{4}-\d{2}-\d{2}_\d{6}$')


def _cartella_cestino(dove, data):
    if _remoto(dove) or not os.path.isdir(dove):
        raise SystemExit('Il cestino si gestisce solo su schede montate su questo PC')
    if not DATA_CESTINO.match(data or ''):
        raise SystemExit('Cestino sconosciuto')
    base = os.path.join(dove, '_rimossi', data)
    if not os.path.isdir(base):
        raise SystemExit('Cestino non trovato')
    return base


def _file_cestino(base):
    for r, _, ff in os.walk(base):
        for f in ff:
            yield os.path.relpath(os.path.join(r, f), base), os.path.join(r, f)


def cestino(dove):
    """Elenco dei cestini sulla scheda, dal piu' recente: [{data, file, byte, sistemi}]."""
    if _remoto(dove) or not os.path.isdir(dove):
        return []
    base = os.path.join(dove, '_rimossi')
    if not os.path.isdir(base):
        return []
    out = []
    for data in sorted(os.listdir(base), reverse=True):
        if not DATA_CESTINO.match(data) or not os.path.isdir(os.path.join(base, data)):
            continue
        n, tot, sis = 0, 0, {}
        for rel, p in _file_cestino(os.path.join(base, data)):
            n += 1
            sz = os.path.getsize(p)
            tot += sz
            s = rel.split(os.sep, 1)[0]
            sis[s] = sis.get(s, 0) + 1
        out.append({'data': data, 'file': n, 'byte': tot, 'sistemi': sis})
    return out


def ripristina(dove, data, stato=None):
    """Rimette i file del cestino al loro posto. Non sovrascrive mai: se sulla scheda c'e' gia' un file con
    lo stesso nome, quello nel cestino resta dov'e'. Ritorna {'ripristinati', 'rimasti'}."""
    base = _cartella_cestino(dove, data)
    voci = [(rel, p) for rel, p in _file_cestino(base) if _sicuro(rel.replace(os.sep, '/'))]
    stato = stato if stato is not None else {}
    stato.update(fase='ripristino', fatti=0, totale=len(voci))
    ok = 0
    for i, (rel, p) in enumerate(voci):
        dst = os.path.join(dove, rel)
        if not os.path.exists(dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            os.replace(p, dst)
            ok += 1
        stato['fatti'] = i + 1
    for r, dd, ff in os.walk(base, topdown=False):     # toglie le cartelle rimaste vuote, cestino compreso
        if not os.listdir(r):
            os.rmdir(r)
    return {'ripristinati': ok, 'rimasti': len(voci) - ok}


def svuota(dove, data):
    """Cancella definitivamente un cestino. Ritorna {'cancellati', 'byte'}."""
    base = _cartella_cestino(dove, data)
    voci = list(_file_cestino(base))
    byte = sum(os.path.getsize(p) for _, p in voci)
    shutil.rmtree(base)
    return {'cancellati': len(voci), 'byte': byte}
