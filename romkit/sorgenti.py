"""Sorgenti SD: quelle del config.toml piu' quelle aggiunte dalla pagina (sorgenti.json accanto al config)."""
import os, json, re, tempfile

RADICI = ('/media', '/run/media', '/mnt')
NOME = re.compile(r'^[\w .()+-]{1,40}$')


def _file(cfg):
    return os.path.join(cfg.base, 'sorgenti.json')


def salvate(cfg):
    try:
        d = json.load(open(_file(cfg)))
        return {k: v for k, v in d.items() if isinstance(k, str) and isinstance(v, str)}
    except (OSError, ValueError):
        return {}


def tutte(cfg):
    return {**cfg['sd']['sorgenti'], **salvate(cfg)}


def _sistemi(cfg):
    ign = set(cfg['catalogo']['ignora'])
    try:
        return {s for s in os.listdir(cfg.archivio) if s not in ign and os.path.isdir(os.path.join(cfg.archivio, s))}
    except OSError:
        return set()


def valida(cfg, percorso):
    """Cartella che contiene almeno una cartella di sistema dell'archivio."""
    try:
        return bool(_sistemi(cfg) & set(os.listdir(percorso)))
    except OSError:
        return False


def _montati():
    try:
        for r in open('/proc/mounts'):
            p = r.split()[1].replace('\\040', ' ')
            if p.startswith(RADICI):
                yield p
    except OSError:
        return


def volumi(cfg):
    """Candidati: volumi montati sotto /media, /run/media, /mnt (e le loro sottocartelle dirette)."""
    out, visti = [], set()
    for m in _montati():
        try:
            cand = [m] + [e.path for e in os.scandir(m) if e.is_dir() and not e.name.startswith('.')]
        except OSError:
            continue
        for c in cand:
            if c not in visti and valida(cfg, c):
                visti.add(c)
                out.append(c)
    return out


def _scrivi(cfg, d):
    fd, tmp = tempfile.mkstemp(dir=cfg.base, prefix='.sorgenti-')
    with os.fdopen(fd, 'w') as fh:
        json.dump(d, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, _file(cfg))


def aggiungi(cfg, nome, percorso):
    """Il percorso deve essere uno dei volumi rilevati; solleva ValueError con il motivo."""
    if not NOME.match(nome or ''):
        raise ValueError('Nome non valido (lettere, numeri, spazi, max 40)')
    percorso = os.path.normpath(percorso or '')
    if percorso not in volumi(cfg):
        raise ValueError('Percorso non tra i volumi rilevati')
    if nome in cfg['sd']['sorgenti']:
        raise ValueError('Nome gia\' usato dalla configurazione')
    d = salvate(cfg)
    d[nome] = percorso
    _scrivi(cfg, d)


def rimuovi(cfg, nome):
    d = salvate(cfg)
    if nome not in d:
        raise ValueError('Sorgente non rimovibile da qui')
    del d[nome]
    _scrivi(cfg, d)
