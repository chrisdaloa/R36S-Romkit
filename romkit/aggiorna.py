"""Aggiornamento dell'eseguibile autonomo dalle release di GitHub: controllo, note di rilascio, download verificato, sostituzione."""
import os, sys, re, json, time, shutil, hashlib, tarfile, zipfile, platform, subprocess, tempfile
import urllib.request, urllib.error, urllib.parse
from . import versione

SISTEMA = {'Windows': 'windows', 'Linux': 'linux', 'Darwin': 'macos'}.get(platform.system(), '')
DURATA_CACHE = 3600
MAX_PACCHETTO = 400 * 1024 * 1024
_cache = {}                       # chiave -> (istante, risultato)
LAVORO = {'stato': 'fermo'}


def _numeri(v):
    return tuple(int(x) for x in re.findall(r'\d+', v.split('-')[0])[:3]) or (0,)


class _SenzaAuthAltrove(urllib.request.HTTPRedirectHandler):
    """Il download degli asset reindirizza ad altri host (storage): lì il token non va inviato."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        n = super().redirect_request(req, fp, code, msg, headers, newurl)
        if n is not None and urllib.parse.urlsplit(newurl).netloc != urllib.parse.urlsplit(req.full_url).netloc:
            n.remove_header('Authorization')
        return n


_apri = urllib.request.build_opener(_SenzaAuthAltrove).open


def _richiesta(cfg, url, accetta='application/vnd.github+json'):
    h = {'Accept': accetta, 'User-Agent': 'R36S-Romkit/' + versione.NUMERO}
    if cfg['aggiornamenti']['token']:
        h['Authorization'] = 'Bearer ' + cfg['aggiornamenti']['token']
    return urllib.request.Request(url, headers=h)


def _api(cfg):
    return cfg['aggiornamenti']['api'].rstrip('/') + '/repos/' + cfg['aggiornamenti']['repo']


def controlla(cfg, forza=False):
    """Dati dell'ultima release e se e' piu' recente di quella in uso. Non solleva eccezioni: l'esito e' nel risultato."""
    base = {'versione': versione.NUMERO, 'attivo': bool(cfg['aggiornamenti']['controlla']),
            'installabile': versione.CONGELATO and bool(SISTEMA), 'disponibile': False}
    if not base['attivo']:
        return base
    chiave = cfg['aggiornamenti']['repo']
    if not forza and chiave in _cache and time.time() - _cache[chiave][0] < DURATA_CACHE:
        return _cache[chiave][1]
    try:
        with _apri(_richiesta(cfg, _api(cfg) + '/releases/latest'), timeout=10) as r:
            rel = json.load(r)
    except urllib.error.HTTPError as e:
        base['errore'] = ('Release non trovate: se il repository e\' privato serve un token in [aggiornamenti].token'
                          if e.code in (401, 403, 404) else f'GitHub ha risposto {e.code}')
        return base
    except (OSError, ValueError) as e:
        base['errore'] = 'GitHub non raggiungibile'
        return base
    nuova = str(rel.get('tag_name', '')).lstrip('v')
    asset = {a['name']: a for a in rel.get('assets', [])}
    pacco = next((a for n, a in asset.items() if f'-{SISTEMA}.' in n and not n.endswith('.sha256')), None)
    base.update(ultima=nuova, note=rel.get('body') or '', pubblicata=(rel.get('published_at') or '')[:10],
                disponibile=_numeri(nuova) > _numeri(versione.NUMERO), pacchetto=pacco['name'] if pacco else None)
    if pacco:
        base['_asset'] = pacco['url']
        s = asset.get(pacco['name'] + '.sha256')
        base['_sha'] = s['url'] if s else None
    if base['disponibile'] and not pacco:
        base['errore'] = f'La release non contiene un pacchetto per {SISTEMA or platform.system()}'
    _cache[chiave] = (time.time(), base)
    return base


def pubblico(r):
    return {k: v for k, v in r.items() if not k.startswith('_')}


def _scarica(cfg, url, dest, stato=None):
    req = _richiesta(cfg, url, 'application/octet-stream')
    with _apri(req, timeout=30) as r, open(dest, 'wb') as fh:
        tot = int(r.headers.get('Content-Length') or 0)
        if tot > MAX_PACCHETTO:
            raise ValueError('Pacchetto troppo grande')
        letti = 0
        while True:
            b = r.read(256 * 1024)
            if not b:
                break
            letti += len(b)
            if letti > MAX_PACCHETTO:
                raise ValueError('Pacchetto troppo grande')
            fh.write(b)
            if stato is not None:
                stato.update(fatti=letti, totale=tot)


def _estrai(pacco, dest):
    """Estrae rifiutando percorsi che escono dalla cartella di destinazione."""
    base = os.path.realpath(dest)
    def sicuro(n):
        return os.path.realpath(os.path.join(base, n)).startswith(base + os.sep)
    if pacco.endswith('.zip'):
        with zipfile.ZipFile(pacco) as z:
            if not all(sicuro(n) for n in z.namelist()):
                raise ValueError('Pacchetto non valido')
            z.extractall(dest)
    else:
        with tarfile.open(pacco) as t:
            for m in t.getmembers():
                dove = os.path.join(os.path.dirname(m.name), m.linkname) if m.issym() else m.name
                if m.islnk() or m.isdev() or not sicuro(dove) or not sicuro(m.name):
                    raise ValueError('Pacchetto non valido')
            t.extractall(dest)


def installa(cfg, riavvia, stato=None):
    """Scarica, verifica e sostituisce i file del programma; poi chiama `riavvia`. I dati dell'utente non si toccano."""
    stato = stato if stato is not None else LAVORO
    if not versione.CONGELATO:
        raise SystemExit('L\'aggiornamento dall\'app funziona solo con l\'eseguibile autonomo; da sorgenti usa git pull')
    r = controlla(cfg, forza=True)
    if not r.get('disponibile') or not r.get('_asset'):
        raise SystemExit(r.get('errore') or 'Nessun aggiornamento disponibile')
    radice = versione.RADICE
    lav = tempfile.mkdtemp(prefix='aggiornamento-', dir=radice)
    try:
        stato.update(stato='scarico', fatti=0, totale=0)
        nome = r['pacchetto']
        pacco = os.path.join(lav, nome)
        _scarica(cfg, r['_asset'], pacco, stato)
        if r.get('_sha'):
            stato.update(stato='verifico')
            tmp = os.path.join(lav, 'sha')
            _scarica(cfg, r['_sha'], tmp)
            atteso = open(tmp).read().split()[0].lower()
            with open(pacco, 'rb') as fh:
                h = hashlib.file_digest(fh, 'sha256').hexdigest()
            if h != atteso:
                raise SystemExit('Il pacchetto scaricato non corrisponde alla firma SHA-256: aggiornamento annullato')
        else:
            raise SystemExit('La release non ha il file SHA-256: aggiornamento annullato')
        stato.update(stato='estraggo')
        nuovo = os.path.join(lav, 'nuovo')
        os.makedirs(nuovo)
        _estrai(pacco, nuovo)
        cart = os.path.join(nuovo, os.listdir(nuovo)[0])
        eseguibile = os.path.basename(sys.executable)
        if not os.path.isfile(os.path.join(cart, eseguibile)):
            raise SystemExit('Il pacchetto non contiene l\'eseguibile atteso')
        stato.update(stato='sostituisco')
        voci = os.listdir(cart)
        prec = os.path.join(radice, '_precedente', versione.NUMERO)
        shutil.rmtree(prec, ignore_errors=True)
        os.makedirs(prec)
        if os.name == 'nt':
            _sostituisci_windows(radice, cart, voci, prec, lav, eseguibile)
            return r['ultima']
        for v in voci:
            vecchio = os.path.join(radice, v)
            if os.path.lexists(vecchio):
                os.replace(vecchio, os.path.join(prec, v))
            shutil.move(os.path.join(cart, v), vecchio)
        shutil.rmtree(lav, ignore_errors=True)
        stato.update(stato='riavvio')
        riavvia()
        return r['ultima']
    except BaseException:
        shutil.rmtree(lav, ignore_errors=True)
        raise


def _sostituisci_windows(radice, cart, voci, prec, lav, eseguibile):
    """Su Windows i file in uso non si sostituiscono: uno script attende l'uscita del programma, poi sposta i file e lo riavvia."""
    bat = os.path.join(radice, '_aggiorna.bat')
    righe = ['@echo off', 'timeout /t 3 /nobreak >nul']
    for v in voci:
        righe += [f'if exist "{radice}\\{v}" move /y "{radice}\\{v}" "{prec}\\{v}" >nul',
                  f'move /y "{cart}\\{v}" "{radice}\\{v}" >nul']
    righe += [f'rmdir /s /q "{lav}"', f'start "" "{radice}\\{eseguibile}" {" ".join(chr(34) + x + chr(34) for x in sys.argv[1:])}', 'del "%~f0"']
    with open(bat, 'w') as fh:
        fh.write('\r\n'.join(righe) + '\r\n')
    subprocess.Popen(['cmd', '/c', bat], creationflags=0x00000008)      # DETACHED_PROCESS
    os._exit(0)
