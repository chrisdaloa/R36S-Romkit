"""Configurazione guidata: scansione dell'archivio, scrittura di config.toml e primo catalogo.

Le funzioni qui sono chiamate dal server, che le espone solo a chi scrive da questo PC."""
import os, re, sys, threading, time
from . import config as C, sorgenti, catalogo

SISTEMI_GIOCA = ['nes', 'famicom', 'snes', 'sfc', 'gb', 'gbc', 'gba', 'megadrive', 'genesis', 'mastersystem', 'sg-1000', 'gamegear', 'pcengine', 'supergrafx', 'turbografx', 'ngp', 'ngpc', 'atari2600', 'atari5200', 'atari7800', 'atarilynx', 'virtualboy', 'wonderswan', 'wonderswancolor', 'coleco', 'sega32x']
LAVORO = {}                    # stato del catalogo in costruzione
_LOCK = threading.Lock()


def _tmp_cfg(archivio=''):
    c = C.Config(C._merge(C.DEFAULT, {}), os.getcwd())
    c.archivio = archivio
    return c


def cartelle(p):
    """Sottocartelle di p (solo i nomi), per il navigatore."""
    p = os.path.abspath(os.path.expanduser(p or '~'))
    if not os.path.isdir(p):
        raise ValueError('Cartella non trovata')
    try:
        figli = sorted(x for x in os.listdir(p) if not x.startswith('.') and os.path.isdir(os.path.join(p, x)))
    except OSError:
        raise ValueError('Cartella non leggibile')
    return {'percorso': p, 'sopra': os.path.dirname(p) if p != '/' else None, 'figli': figli}


def scansiona(p):
    """Quanti sistemi e giochi contiene una cartella archivio (conteggio veloce, senza leggere i gamelist)."""
    p = os.path.abspath(os.path.expanduser(p or ''))
    if not os.path.isdir(p):
        raise ValueError('Cartella non trovata')
    ign = set(C.DEFAULT['catalogo']['ignora'])
    sistemi, giochi, gl = 0, 0, 0
    try:
        voci = sorted(os.listdir(p))
    except OSError:
        raise ValueError('Cartella non leggibile')
    for s in voci:
        d = os.path.join(p, s)
        if s in ign or s.startswith(('.', '_')) or not os.path.isdir(d):
            continue
        try:
            f = os.listdir(d)
        except OSError:
            continue
        n = sum(1 for x in f if not x.startswith('.') and x.lower() != 'gamelist.xml' and os.path.isfile(os.path.join(d, x))
                and not x.lower().endswith(('.xml', '.txt', '.cfg', '.srm', '.sav', '.state')))
        if n:
            sistemi += 1
            giochi += n
            gl += 'gamelist.xml' in f
    return {'percorso': p, 'sistemi': sistemi, 'giochi': giochi, 'con_gamelist': gl, 'valido': sistemi >= 1}


def attuale(file):
    """Valori da mostrare nella procedura: quelli del config esistente, altrimenti proposte."""
    cwd = os.getcwd()
    r = {'esiste': os.path.exists(file), 'archivio': '', 'dati': os.path.join(cwd, 'dati'), 'pack': os.path.join(cwd, 'packs'),
         'rete': False, 'porta': 8765, 'gioca': False, 'cartella': cwd}
    if r['esiste']:
        c = C.carica(file)
        r.update(archivio=c.archivio, dati=c.dati, pack=c.pack, rete=c['server']['host'] not in ('127.0.0.1', 'localhost', '::1'),
                 porta=c['server']['porta'], gioca=c['gioca']['abilitato'])
    return r


def volumi(archivio=''):
    """Schede rilevate; l'archivio scelto serve a riconoscere le schede dalle cartelle di sistema."""
    return sorgenti.schede(_tmp_cfg(os.path.abspath(os.path.expanduser(archivio)) if archivio else ''))


# ---- scrittura del TOML -------------------------------------------------------------------------
def _v(x):
    if isinstance(x, bool):
        return 'true' if x else 'false'
    if isinstance(x, (int, float)):
        return str(x)
    if isinstance(x, list):
        return '[' + ', '.join(_v(i) for i in x) + ']'
    return '"' + str(x).replace('\\', '\\\\').replace('"', '\\"') + '"'


def _k(k):
    return k if re.fullmatch(r'[A-Za-z0-9_-]+', k) else _v(k)


def _tabella(d, nome, out):
    semplici = {k: v for k, v in d.items() if not isinstance(v, dict)}
    figli = {k: v for k, v in d.items() if isinstance(v, dict)}
    if semplici or not figli:
        out.append(f'[{nome}]')
        out += [f'{_k(k)} = {_v(v)}' for k, v in semplici.items()]
        out.append('')
    for k, v in figli.items():
        _tabella(v, f'{nome}.{_k(k)}', out)


def testo_toml(d):
    out = ['# Scritto dalla configurazione guidata di romkit. Si puo\' modificare a mano o rifare con: romkit serve --setup', '']
    for k, v in d.items():
        _tabella(v, _k(k), out)
    return '\n'.join(out).rstrip() + '\n'


def salva(file, d):
    """Valida i dati, scrive config.toml (con copia .bak dell'esistente) e crea le cartelle di uscita."""
    arch = os.path.abspath(os.path.expanduser(d.get('archivio') or ''))
    if not scansiona(arch)['valido']:
        raise ValueError('La cartella dell\'archivio non contiene sistemi con giochi')
    dati = os.path.abspath(os.path.expanduser(d.get('dati') or ''))
    pack = os.path.abspath(os.path.expanduser(d.get('pack') or ''))
    if not d.get('dati') or not d.get('pack'):
        raise ValueError('Indica le cartelle per il catalogo e per i pack')
    if dati == pack or arch in (dati, pack):
        raise ValueError('Archivio, catalogo e pack devono essere cartelle diverse')
    porta = int(d.get('porta') or 8765)
    if not 1024 <= porta <= 65535:
        raise ValueError('Porta non valida (1024-65535)')
    for c in (dati, pack):
        try:
            os.makedirs(c, exist_ok=True)
            if not os.access(c, os.W_OK):
                raise OSError
        except OSError:
            raise ValueError(f'Non posso scrivere in {c}')
    import tomllib
    grezzo = {}
    if os.path.exists(file):
        with open(file, 'rb') as fh:
            grezzo = tomllib.load(fh)
        with open(file + '.bak', 'wb') as fh, open(file, 'rb') as src:
            fh.write(src.read())
    g = lambda s: grezzo.setdefault(s, {})
    g('archivio')['percorso'] = arch
    g('uscite').update(dati=dati, pack=pack)
    g('server').update(host='0.0.0.0' if d.get('rete') else '127.0.0.1', porta=porta)
    g('gioca')['abilitato'] = bool(d.get('gioca'))
    if d.get('gioca') and not g('gioca').get('sistemi'):
        g('gioca')['sistemi'] = SISTEMI_GIOCA
    tmp = file + '.tmp'
    with open(tmp, 'w') as fh:
        fh.write(testo_toml(grezzo))
    os.replace(tmp, file)
    c = C.carica(file)
    nomi = []
    gia = {v['uuid'] for v in sorgenti.salvate(c).values()}
    for s in d.get('schede') or []:
        if s.get('uuid') in gia:
            continue
        sorgenti.aggiungi(c, s.get('nome'), s.get('uuid'))
        nomi.append(s['nome'])
    return {'config': file, 'schede': nomi}


def demo(file):
    """Crea l'archivio finto accanto a config.toml, scrive la configurazione e avvia il primo catalogo."""
    from . import demo as d
    cart = os.path.join(os.path.dirname(os.path.abspath(file)), 'demo-lavoro')
    d.crea(cart, avviso=False)
    dati = {'archivio': os.path.join(cart, 'EASYROMS'), 'dati': os.path.join(cart, 'dati'),
            'pack': os.path.join(cart, 'packs'), 'porta': 8765}
    r = salva(file, dati)
    costruisci(file)
    return {**dati, 'config': r['config']}


# ---- primo catalogo -----------------------------------------------------------------------------
def costruisci(file):
    with _LOCK:
        if LAVORO.get('stato') == 'in corso':
            return
        LAVORO.clear()
        LAVORO.update(stato='in corso', inizio=time.time(), sistema='', fatti=0, totale=0)
    cfg = C.carica(file)

    def corri():
        try:
            n, img, perse = catalogo.genera(cfg, avanza=lambda s, k, t: LAVORO.update(sistema=s, fatti=k, totale=t))
            LAVORO.update(stato='finito', giochi=n, immagini=img)
        except Exception as e:                                 # noqa: qualunque errore va mostrato nella pagina
            LAVORO.update(stato='errore', errore=str(e)[:300] or 'Costruzione non riuscita')
    threading.Thread(target=corri, daemon=True).start()


def riavvia(argv):
    """Rilancia il processo con gli stessi argomenti, dopo una breve pausa per chiudere la risposta."""
    def go():
        time.sleep(0.8)
        radice = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        os.environ['PYTHONPATH'] = radice + os.pathsep + os.environ.get('PYTHONPATH', '')
        os.execv(sys.executable, [sys.executable] + argv)
    threading.Thread(target=go, daemon=True).start()
