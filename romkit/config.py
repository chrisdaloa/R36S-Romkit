"""Lettura di config.toml con valori predefiniti; nessun percorso e' scritto nel codice."""
import os, tomllib
from dataclasses import dataclass, field

DEFAULT = {
    'archivio': {'percorso': ''},
    'uscite': {'dati': './dati', 'pack': './packs'},
    'catalogo': {
        'ignora': ['themes', 'bios', 'tools', 'backup', 'bezels', 'bgmusic', 'launchimages',
                   'savestates', 'overlays', 'System Volume Information', 'shutdownimages'],
        'sistemi_cartelle': ['scummvm'],
        'sottocartelle': {},
        'solo_estensione': {},
    },
    'server': {'host': '127.0.0.1', 'porta': 8765},
    'gioca': {'abilitato': False, 'sistemi': []},
    'sd': {'destinazione': '', 'sorgenti': {}},
    'pack': {
        'servizio': ['bios', 'bezels', 'bgmusic', 'launchimages', 'shutdownimages', 'themes', 'tools'],
        'escludi': ['*.bak', '*.bak*', '*.pre_scrape', '*.pre_zip', 'gamelist.xml.old', '*.part',
                    'Thumbs.db', '._*', '.DS_Store'],
    },
}


def _merge(base, extra):
    out = {k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v) for k, v in base.items()}
    for k, v in extra.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


@dataclass
class Config:
    dati_grezzi: dict
    base: str                               # cartella del file di configurazione
    archivio: str = ''
    dati: str = ''
    pack: str = ''

    def __getitem__(self, k):
        return self.dati_grezzi[k]


def _percorso(p, base):
    p = os.path.expanduser(p)
    return os.path.normpath(p if os.path.isabs(p) else os.path.join(base, p))


def carica(file):
    file = os.path.abspath(file)
    with open(file, 'rb') as fh:
        d = _merge(DEFAULT, tomllib.load(fh))
    base = os.path.dirname(file)
    c = Config(d, base)
    c.archivio = _percorso(d['archivio']['percorso'], base) if d['archivio']['percorso'] else ''
    c.dati = _percorso(d['uscite']['dati'], base)
    c.pack = _percorso(d['uscite']['pack'], base)
    return c
