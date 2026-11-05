"""Sorgenti SD: quelle del config.toml (percorso fisso o utente@host:/percorso) piu' le schede
riconosciute per identita' del volume (UUID) e salvate in sorgenti.json accanto al config."""
import os, sys, json, re, subprocess, tempfile

RADICI = ('/media', '/run/media', '/mnt')
MIN_SISTEMI = 5      # cartelle di sistema minime perche' una partizione senza firma sia proposta
NOME = re.compile(r'^[\w .()+-]{1,40}$')


def _file(cfg):
    return os.path.join(cfg.base, 'sorgenti.json')


def salvate(cfg):
    """{nome: {'uuid': .., 'etichetta': ..}}; le voci vecchie con solo il percorso sono ignorate."""
    try:
        d = json.load(open(_file(cfg)))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in d.items() if isinstance(k, str) and isinstance(v, dict) and isinstance(v.get('uuid'), str)}


def _lsblk():
    r = subprocess.run(['lsblk', '-J', '-b', '-o', 'NAME,PATH,TYPE,UUID,LABEL,FSTYPE,SIZE,MOUNTPOINTS,RM,HOTPLUG'],
                       capture_output=True, text=True, timeout=15)
    return json.loads(r.stdout or '{}')


def _sistemi(cfg):
    ign = set(cfg['catalogo']['ignora'])
    try:
        return {s for s in os.listdir(cfg.archivio) if s not in ign and os.path.isdir(os.path.join(cfg.archivio, s))}
    except OSError:
        return set()


def valida(cfg, percorso):
    """Cartella con almeno MIN_SISTEMI cartelle di sistema dell'archivio (non basta una come 'dos')."""
    try:
        return len(_sistemi(cfg) & set(os.listdir(percorso))) >= MIN_SISTEMI
    except OSError:
        return False


def _mount(p):
    m = [x for x in (p.get('mountpoints') or []) if x and x.startswith(RADICI)]
    return sorted(m, key=lambda x: (not x.startswith('/media'), x))[0] if m else None


def schede(cfg, dati=None):
    """Schede della console rilevate. forza='forte': stesso disco con partizione di avvio e partizione
    dei giochi (firma in [sd].firma); 'debole': solo una partizione montata con cartelle di sistema."""
    firma = cfg['sd']['firma']
    out = []
    for disco in (dati if dati is not None else _lsblk()).get('blockdevices', []):
        parti = [c for c in disco.get('children', []) if c.get('uuid')]
        avvio = any(c.get('label') == firma['avvio'] for c in disco.get('children', []))
        for c in parti:
            perc = _mount(c)
            forte = avvio and c.get('label') == firma['dati']
            if not forte and not (perc and valida(cfg, perc)):
                continue
            out.append({'uuid': c['uuid'], 'etichetta': c.get('label') or '', 'fs': c.get('fstype') or '',
                        'dimensione': int(c.get('size') or 0), 'percorso': perc,
                        'forza': 'forte' if forte else 'debole'})
    return out


def risolte(cfg, dati=None):
    """{nome: percorso o None}: None se la scheda non e' collegata/montata."""
    out = dict(cfg['sd']['sorgenti'])
    if salvate(cfg):
        per_uuid = {s['uuid']: s['percorso'] for s in schede(cfg, dati)}
        for nome, v in salvate(cfg).items():
            out[nome] = per_uuid.get(v['uuid'])
    return out


def elenco(cfg, dati=None):
    """[{nome, stato}]: 'collegata', 'assente' o None quando non si sa (console via SSH)."""
    out = []
    for nome, perc in risolte(cfg, dati).items():
        if perc is None:
            stato = 'assente'
        elif ':' in perc and not os.path.isabs(perc):
            stato = None
        else:
            stato = 'collegata' if os.path.isdir(perc) else 'assente'
        out.append({'nome': nome, 'stato': stato})
    return out


def percorso(cfg, nome):
    return risolte(cfg).get(nome)


def _scrivi(cfg, d):
    fd, tmp = tempfile.mkstemp(dir=cfg.base, prefix='.sorgenti-')
    with os.fdopen(fd, 'w') as fh:
        json.dump(d, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, _file(cfg))


def aggiungi(cfg, nome, uuid):
    """La scheda deve essere tra quelle rilevate; solleva ValueError con il motivo."""
    if not NOME.match(nome or ''):
        raise ValueError('Nome non valido (lettere, numeri, spazi, max 40)')
    s = {x['uuid']: x for x in schede(cfg)}.get(uuid)
    if not s:
        raise ValueError('Scheda non tra quelle rilevate')
    if nome in cfg['sd']['sorgenti'] or nome in salvate(cfg):
        raise ValueError('Nome gia\' in uso')
    if any(v['uuid'] == uuid for v in salvate(cfg).values()):
        raise ValueError('Scheda gia\' registrata')
    d = salvate(cfg)
    d[nome] = {'uuid': uuid, 'etichetta': s['etichetta']}
    _scrivi(cfg, d)


def rimuovi(cfg, nome):
    d = salvate(cfg)
    if nome not in d:
        raise ValueError('Sorgente non rimovibile da qui')
    del d[nome]
    _scrivi(cfg, d)


def rinomina(cfg, vecchio, nuovo):
    """Cambia solo il nome mostrato: l'identita' (UUID) della scheda resta la stessa."""
    d = salvate(cfg)
    if vecchio not in d:
        raise ValueError('Sorgente non modificabile da qui')
    if not NOME.match(nuovo or ''):
        raise ValueError('Nome non valido (lettere, numeri, spazi, max 40)')
    if nuovo != vecchio and (nuovo in d or nuovo in cfg['sd']['sorgenti']):
        raise ValueError('Nome gia\' in uso')
    d = {(nuovo if k == vecchio else k): v for k, v in d.items()}      # mantiene l'ordine
    _scrivi(cfg, d)


def _vero(v):
    return v in (True, 1, '1', 'true')


def smonta(cfg, nome, dati=None, esegui=None):
    """Smonta in sicurezza la scheda (solo Linux, solo disco rimovibile montato sotto /media, /run/media, /mnt).
    Smonta tutte le sue partizioni (BOOT, EASYROMS...) e poi, se possibile, spegne il disco.
    Solleva SystemExit con il motivo. Ritorna {'smontate': n, 'spenta': bool}."""
    if not sys.platform.startswith('linux'):
        raise SystemExit('Smontare dal programma funziona solo su Linux: usa «Rimuovi in sicurezza» del sistema')
    dove = risolte(cfg).get(nome)
    if not dove or ':' in dove and not os.path.isabs(dove):
        raise SystemExit('Scheda non collegata a questo PC')
    dove = os.path.realpath(dove)
    esegui = esegui or (lambda cmd: subprocess.run(cmd, capture_output=True, text=True, timeout=60))
    disco = part = None
    for d in (dati if dati is not None else _lsblk()).get('blockdevices', []):
        for c in d.get('children', []):
            if dove in [os.path.realpath(m) for m in (c.get('mountpoints') or []) if m]:
                disco, part = d, c
    if not disco:
        raise SystemExit('Non trovo il disco di questa scheda')
    if not (_vero(disco.get('rm')) or _vero(disco.get('hotplug'))):
        raise SystemExit('Non è un disco rimovibile: non lo smonto da qui')
    montate = [(c.get('path') or '/dev/' + c['name'], m) for c in disco.get('children', []) for m in (c.get('mountpoints') or []) if m]
    if any(not m.startswith(RADICI) for _, m in montate):
        raise SystemExit('Il disco contiene partizioni di sistema montate: non lo smonto da qui')
    esegui(['sync'])
    n = 0
    for dev in dict.fromkeys(d for d, _ in montate):
        r = esegui(['udisksctl', 'unmount', '-b', dev])
        if r.returncode:
            msg = (r.stderr or r.stdout or '').strip()
            raise SystemExit('Non riesco a smontare ' + dev + (': ' + msg[-200:] if msg else ' (qualcosa la sta usando?)'))
        n += 1
    r = esegui(['udisksctl', 'power-off', '-b', disco.get('path') or '/dev/' + disco['name']])
    return {'smontate': n, 'spenta': r.returncode == 0}
