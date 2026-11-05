"""Server locale del catalogo: pagina web, dati generati, pack e (solo se abilitato) ROM in sola lettura."""
import os, json, subprocess, webbrowser, ipaddress, posixpath, tempfile, threading, time, uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit, parse_qs
from . import sd, sorgenti, sync, packs, guidata, versione, aggiorna

WEB = os.path.join(versione.RADICE, 'web')
MAX_PACKS = 20 * 1024 * 1024
DATI = ('data.js', 'data.json')


LAVORI = {}                    # id -> stato dei calcoli di sincronizzazione in corso o finiti
LAVORI_LOCK = threading.Lock()


def _lancia_piano(cfg, nome, dove, pack):
    chiave = (nome, pack)
    with LAVORI_LOCK:
        for j, v in LAVORI.items():
            if v['chiave'] == chiave and v['stato'] == 'in corso':
                return j
        j = uuid.uuid4().hex[:12]
        LAVORI[j] = {'chiave': chiave, 'stato': 'in corso', 'inizio': time.time()}

    def corri():
        try:
            p = sync.piano(cfg, dove, pack, stato=LAVORI[j])
            elenco = {k: p[k][:3000] for k in ('aggiungi', 'aggiorna', 'togli')}
            n = {k: len(p[k]) for k in ('aggiungi', 'aggiorna', 'togli')}
            LAVORI[j]['piano'] = p
            r = {'stato': 'finito', 'byte': p['byte'], 'n': n, 'per_sistema': p['per_sistema'],
                 'elenco': elenco, 'anomalie': p['anomalie'][:50]}
        except (OSError, KeyError, SystemExit) as e:
            r = {'stato': 'errore', 'errore': str(e)[:200] or 'Calcolo non riuscito'}
        with LAVORI_LOCK:
            LAVORI[j].update(r)
    threading.Thread(target=corri, daemon=True).start()
    return j


def _setup_api(h, metodo, file):
    """Rotte /api/setup/*: navigatore cartelle, controllo archivio, schede, salvataggio, primo catalogo.
    Solo da questo PC (loopback, stessa origine): scrivono la configurazione e leggono l'elenco delle cartelle."""
    ru = urlsplit(h.path)
    q = parse_qs(ru.query)
    azione = ru.path[len('/api/setup/'):]
    if not h._origine_ok():
        return h.send_error(403)
    corpo = {}
    if metodo == 'POST':
        n = int(h.headers.get('Content-Length') or 0)
        if not 0 <= n <= 65536:
            return h.send_error(413)
        try:
            corpo = json.loads(h.rfile.read(n) or b'{}')
        except ValueError:
            return h.send_error(400)
    try:
        if metodo == 'GET' and azione == 'attuale':
            r = guidata.attuale(file)
        elif metodo == 'GET' and azione == 'cartelle':
            r = guidata.cartelle((q.get('p') or [''])[0])
        elif metodo == 'GET' and azione == 'scansione':
            r = guidata.scansiona((q.get('p') or [''])[0])
        elif metodo == 'GET' and azione == 'volumi':
            r = {'schede': guidata.volumi((q.get('p') or [''])[0])}
        elif metodo == 'GET' and azione == 'lavoro':
            r = dict(guidata.LAVORO)
        elif metodo == 'POST' and azione == 'salva':
            r = guidata.salva(file, corpo)
            guidata.costruisci(file)
        elif metodo == 'POST' and azione == 'demo':
            r = guidata.demo(file)
        elif metodo == 'POST' and azione == 'fine':
            r = {'ok': True}
            guidata.riavvia(['--config', file, 'serve'] if versione.CONGELATO else ['-m', 'romkit.cli', '--config', file, 'serve'])
        else:
            return h.send_error(404)
    except (ValueError, KeyError, TypeError, OSError) as e:
        return h.send_error(400, str(e)[:150] or 'Richiesta non valida')
    h._json(json.dumps(r, ensure_ascii=False).encode())


def crea_setup(file):
    """Handler della sola configurazione guidata, usato quando config.toml non esiste ancora."""
    class S(SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=WEB, **k)

        def end_headers(self):
            self.send_header('Cache-Control', 'no-cache')
            super().end_headers()

        def _json(self, dati):
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(dati)))
            self.end_headers()
            self.wfile.write(dati)

        def _da_qui(self):
            return self.client_address[0] in ('127.0.0.1', '::1')

        def _origine_ok(self):
            orig = self.headers.get('Origin')
            return self._da_qui() and not (orig and orig.split('://', 1)[-1] != self.headers.get('Host'))

        def do_GET(self):
            if self.path.startswith('/api/setup/'):
                return _setup_api(self, 'GET', file)
            if self.path.split('?', 1)[0] in ('/', '/index.html'):
                self.path = '/setup.html'
            elif self.path.split('?', 1)[0] != '/setup.html':
                return self.send_error(404)
            super().do_GET()

        def do_POST(self):
            if self.path.startswith('/api/setup/'):
                return _setup_api(self, 'POST', file)
            self.send_error(405)
    return S


def _apri_browser(url):
    """Apre la pagina nel browser predefinito, poco dopo l'avvio del server."""
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()


def serve_setup(file, host='127.0.0.1', porta=8765, apri=False):
    print(f'Prima configurazione: apri http://{host}:{porta}/ nel browser  (Ctrl+C per fermare)')
    if apri:
        _apri_browser(f'http://{host}:{porta}/')
    ThreadingHTTPServer((host, porta), crea_setup(file)).serve_forever()


def crea(cfg):
    packs_file = os.path.join(cfg.pack, 'packs.json')
    pack_rete = bool(cfg['server'].get('pack_da_rete'))
    locale = cfg['server']['host'] in ('127.0.0.1', 'localhost', '::1')
    giocabili = set(cfg['gioca']['sistemi']) if cfg['gioca']['abilitato'] else set()

    class H(SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=WEB, **k)

        def translate_path(self, path):
            p = posixpath.normpath(unquote(path.split('?', 1)[0].split('#', 1)[0]))
            parti = [x for x in p.split('/') if x]
            if parti and parti[0] == 'rom':
                if len(parti) != 3 or parti[1] not in giocabili or parti[2].startswith('.'):
                    return os.path.join(WEB, '_negato')
                return os.path.join(cfg.archivio, parti[1], parti[2])
            if parti and (parti[0] in ('thumbs',) or parti[0] in DATI or parti[0].startswith('desc_')):
                return os.path.join(cfg.dati, *parti)
            return super().translate_path(path)

        def end_headers(self):
            self.send_header('Cache-Control', 'no-cache')
            super().end_headers()

        def _json(self, dati):
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(dati)))
            self.end_headers()
            self.wfile.write(dati)

        def _sd(self, q):
            # sola lettura; il browser indica solo il nome di una sorgente registrata
            if not q.get('sorgente'):
                return self._json(json.dumps(sorgenti.elenco(cfg), ensure_ascii=False).encode())
            nome = q['sorgente'][0]
            risolte = sorgenti.risolte(cfg)
            if nome not in risolte:
                return self.send_error(404, 'Sorgente sconosciuta')
            if risolte[nome] is None:
                return self.send_error(503, 'Scheda non collegata')
            if q.get('cestino'):
                try:
                    return self._json(json.dumps(sync.cestino(risolte[nome])).encode())
                except (OSError, SystemExit) as e:
                    return self.send_error(502, str(e)[:200] or 'SD non raggiungibile')
            if q.get('spazio'):
                try:
                    return self._json(json.dumps(sd.spazio(risolte[nome]) or {}).encode())
                except (OSError, SystemExit) as e:
                    return self.send_error(502, str(e)[:200] or 'SD non raggiungibile')
            try:
                r = sd.analizza(cfg, risolte[nome], (q.get('pack') or [None])[0] or None)
            except (OSError, KeyError, SystemExit) as e:
                return self.send_error(502, str(e)[:200] or 'SD non raggiungibile')
            r['dettagli'] = r['dettagli'][:2000]
            r.pop('dove', None)
            self._json(json.dumps(r, ensure_ascii=False).encode())

        def _sync_stato(self, q):
            j = (q.get('id') or [''])[0]
            with LAVORI_LOCK:
                v = LAVORI.get(j)
                v = dict(v) if v else None
            if not v:
                return self.send_error(404)
            v.pop('chiave', None)
            v.pop('piano', None)
            self._json(json.dumps(v, ensure_ascii=False).encode())

        def _sync_avvia(self):
            if not self._origine_ok():
                return self.send_error(403)
            n = int(self.headers.get('Content-Length') or 0)
            if not 0 < n <= 4096:
                return self.send_error(413)
            try:
                d = json.loads(self.rfile.read(n))
                nome, pack = d['sorgente'], d['pack']
                dove = sorgenti.risolte(cfg).get(nome)
                if dove is None:
                    return self.send_error(503, 'Scheda non collegata o sconosciuta')
                if pack not in packs.carica_packs(cfg):
                    return self.send_error(404, 'Pack sconosciuto')
            except (ValueError, KeyError, TypeError, OSError):
                return self.send_error(400)
            self._json(json.dumps({'id': _lancia_piano(cfg, nome, dove, pack)}).encode())

        def _aggiorna_installa(self):
            if not self._origine_ok():
                return self.send_error(403)
            if aggiorna.LAVORO.get('stato') in ('scarico', 'verifico', 'estraggo', 'sostituisco', 'riavvio'):
                return self.send_error(409, 'Aggiornamento gia\' in corso')
            aggiorna.LAVORO.clear()
            aggiorna.LAVORO.update(stato='scarico', fatti=0, totale=0)
            def corri():
                try:
                    nuova = aggiorna.installa(cfg, lambda: guidata.riavvia(['--config', cfg.file, 'serve']))
                    aggiorna.LAVORO.update(stato='riavvio', versione=nuova)
                except SystemExit as e:
                    aggiorna.LAVORO.update(stato='errore', errore=str(e)[:300])
                except Exception as e:
                    aggiorna.LAVORO.update(stato='errore', errore=(str(e) or type(e).__name__)[:300])
            threading.Thread(target=corri, daemon=True).start()
            self._json(b'{"ok": true}')

        def _sync_applica(self):
            if not self._origine_ok():
                return self.send_error(403)
            n = int(self.headers.get('Content-Length') or 0)
            if not 0 < n <= 65536:
                return self.send_error(413)
            try:
                d = json.loads(self.rfile.read(n))
                with LAVORI_LOCK:
                    v = LAVORI.get(d['id'])
                    piano = v and v.get('piano')
                    if not piano or v['stato'] != 'finito':
                        return self.send_error(404, 'Piano non disponibile: rifai l\'anteprima')
                    nome, pack = v['chiave']
                    if any(x['stato'] == 'in corso' and x['chiave'][0] == nome for x in LAVORI.values()):
                        return self.send_error(409, 'Un\'altra operazione su questa scheda e\' in corso')
                sistemi = set(d['sistemi']) if d.get('sistemi') is not None else None
                agg, tog = bool(d.get('aggiungi', True)), bool(d.get('togli', True))
                dove = sorgenti.risolte(cfg).get(nome)
                if dove is None:
                    return self.send_error(503, 'Scheda non collegata')
                if tog and sync.richiede_conferma(piano, sistemi) and not d.get('conferma_soglia'):
                    return self.send_error(409, 'Le rimozioni superano il 20% della scheda: serve la conferma esplicita')
            except (ValueError, KeyError, TypeError):
                return self.send_error(400)
            j = uuid.uuid4().hex[:12]
            with LAVORI_LOCK:
                v.pop('piano', None)          # il piano vale una volta sola: dopo si rifà l'anteprima
                LAVORI[j] = {'chiave': (nome, pack), 'stato': 'in corso', 'tipo': 'applica', 'fase': 'avvio', 'inizio': time.time()}

            def corri():
                try:
                    r = sync.applica(cfg, dove, piano, agg, tog, sistemi, LAVORI[j])
                    r['stato'] = 'finito'
                except (OSError, SystemExit) as e:
                    r = {'stato': 'errore', 'errore': str(e)[:300] or 'Sincronizzazione non riuscita'}
                with LAVORI_LOCK:
                    LAVORI[j].update(r)
                    LAVORI[j].pop('piano', None)
            threading.Thread(target=corri, daemon=True).start()
            self._json(json.dumps({'id': j}).encode())

        def _cestino_azione(self):
            if not self._origine_ok():
                return self.send_error(403)
            n = int(self.headers.get('Content-Length') or 0)
            if not 0 < n <= 4096:
                return self.send_error(413)
            try:
                d = json.loads(self.rfile.read(n))
                nome, data, azione = d['sorgente'], d['data'], d['azione']
                if azione not in ('ripristina', 'svuota'):
                    return self.send_error(400)
                dove = sorgenti.risolte(cfg).get(nome)
                if dove is None:
                    return self.send_error(503, 'Scheda non collegata o sconosciuta')
            except (ValueError, KeyError, TypeError):
                return self.send_error(400)
            with LAVORI_LOCK:
                if any(x['stato'] == 'in corso' and x['chiave'][0] == nome for x in LAVORI.values()):
                    return self.send_error(409, 'Un\'altra operazione su questa scheda e\' in corso')
            try:
                r = sync.ripristina(dove, data) if azione == 'ripristina' else sync.svuota(dove, data)
            except (OSError, SystemExit) as e:
                return self.send_error(502, str(e)[:200] or 'Operazione sul cestino non riuscita')
            self._json(json.dumps(r).encode())

        def _sd_smonta(self):
            if not self._origine_ok():
                return self.send_error(403)
            n = int(self.headers.get('Content-Length') or 0)
            if not 0 < n <= 4096:
                return self.send_error(413)
            try:
                nome = json.loads(self.rfile.read(n))['sorgente']
                if not isinstance(nome, str):
                    raise TypeError
            except (ValueError, KeyError, TypeError):
                return self.send_error(400)
            with LAVORI_LOCK:
                if any(x['stato'] == 'in corso' and x['chiave'][0] == nome for x in LAVORI.values()):
                    return self.send_error(409, 'Un\'altra operazione su questa scheda e\' in corso')
            try:
                r = sorgenti.smonta(cfg, nome)
            except (OSError, subprocess.SubprocessError, SystemExit) as e:
                return self.send_error(502, str(e)[:200] or 'Smontaggio non riuscito')
            self._json(json.dumps(r).encode())

        def do_GET(self):
            ru = urlsplit(self.path)
            if ru.path.startswith('/api/setup/'):
                return _setup_api(self, 'GET', cfg.file)
            if ru.path == '/api/sync':
                return self._sync_stato(parse_qs(ru.query))
            if ru.path == '/api/aggiornamento':
                r = aggiorna.pubblico(aggiorna.controlla(cfg, forza=bool(parse_qs(ru.query).get('forza')) and self._da_qui()))
                r['modificabile'] = self._da_qui()
                return self._json(json.dumps(r).encode())
            if ru.path == '/api/aggiornamento/stato':
                return self._json(json.dumps(aggiorna.LAVORO).encode())
            if ru.path == '/api/versione':
                return self._json(json.dumps(versione.info()).encode())
            if ru.path == '/api/volumi':
                return self._json(json.dumps({'schede': sorgenti.schede(cfg), 'salvate': sorgenti.salvate(cfg),
                                              'modificabile': self._da_qui()}).encode())
            if ru.path == '/api/sd':
                return self._sd(parse_qs(ru.query))
            if self.path.split('?', 1)[0] == '/api/packs':
                if not os.path.isdir(cfg.pack):
                    return self.send_error(503, 'Cartella dei pack non raggiungibile')
                try:
                    with open(packs_file, 'rb') as fh:
                        return self._json(fh.read())
                except FileNotFoundError:
                    return self._json(b'{}')
            super().do_GET()

        def do_PUT(self):
            # i pack si salvano solo dalla pagina stessa (stessa origine)
            if self.path.split('?', 1)[0] == '/api/sorgenti':
                return self._sorgente('rinomina')
            if self.path.split('?', 1)[0] != '/api/packs':
                return self.send_error(405)
            if not self._origine_ok(rete=True):
                return self.send_error(403)
            if not os.path.isdir(cfg.pack):
                return self.send_error(503, 'Cartella dei pack non raggiungibile')
            n = int(self.headers.get('Content-Length') or 0)
            if not 0 < n <= MAX_PACKS:
                return self.send_error(413)
            try:
                dati = json.loads(self.rfile.read(n))
                if not isinstance(dati, dict):
                    raise ValueError
            except ValueError:
                return self.send_error(400)
            fd, tmp = tempfile.mkstemp(dir=cfg.pack, prefix='.packs-')
            with os.fdopen(fd, 'w') as fh:
                json.dump(dati, fh, ensure_ascii=False, separators=(',', ':'))
            os.replace(tmp, packs_file)
            self.send_response(204)
            self.end_headers()

        def _da_qui(self):
            # si scrive solo con il server in locale o da questo stesso PC (loopback), mai dalla rete
            return bool(locale) or self.client_address[0] in ('127.0.0.1', '::1')

        def _origine_ok(self, rete=False):
            orig = self.headers.get('Origin')
            stessa = not (orig and orig.split('://', 1)[-1] != self.headers.get('Host'))
            return (self._da_qui() or (rete and pack_rete and self._rete_privata())) and stessa

        def _rete_privata(self):
            try:
                ip = ipaddress.ip_address(self.client_address[0].split('%')[0])
                if getattr(ip, 'ipv4_mapped', None):
                    ip = ip.ipv4_mapped
                return ip.is_private and not ip.is_loopback
            except ValueError:
                return False

        def _sorgente(self, azione):
            # il browser indica un nome e l'UUID di una scheda rilevata, mai un percorso
            if urlsplit(self.path).path != '/api/sorgenti':
                return self.send_error(405)
            if not self._origine_ok():
                return self.send_error(403)
            n = int(self.headers.get('Content-Length') or 0)
            if not 0 < n <= 4096:
                return self.send_error(413)
            try:
                d = json.loads(self.rfile.read(n))
                if azione == 'aggiungi':
                    sorgenti.aggiungi(cfg, d['nome'], d['uuid'])
                elif azione == 'rinomina':
                    sorgenti.rinomina(cfg, d['nome'], d['nuovo'])
                else:
                    sorgenti.rimuovi(cfg, d['nome'])
            except (ValueError, KeyError, TypeError) as e:
                return self.send_error(400, str(e)[:100])
            self.send_response(204)
            self.end_headers()

        def do_POST(self):
            if self.path.startswith('/api/setup/'):
                return _setup_api(self, 'POST', cfg.file)
            if urlsplit(self.path).path == '/api/aggiornamento/installa':
                return self._aggiorna_installa()
            if urlsplit(self.path).path == '/api/sync':
                return self._sync_avvia()
            if urlsplit(self.path).path == '/api/sync/applica':
                return self._sync_applica()
            if urlsplit(self.path).path == '/api/sd/cestino':
                return self._cestino_azione()
            if urlsplit(self.path).path == '/api/sd/smonta':
                return self._sd_smonta()
            self._sorgente('aggiungi')

        def do_DELETE(self):
            self._sorgente('rimuovi')

    return H


def serve(cfg, apri=False):
    host, porta = cfg['server']['host'], cfg['server']['porta']
    os.makedirs(cfg.pack, exist_ok=True)
    print(f'Catalogo su http://{host}:{porta}/index.html  (Ctrl+C per fermare)')
    if host not in ('127.0.0.1', 'localhost', '::1'):
        print('ATTENZIONE: server raggiungibile dalla rete, senza autenticazione.')
    if apri:
        _apri_browser(f'http://127.0.0.1:{porta}/index.html')
    ThreadingHTTPServer((host, porta), crea(cfg)).serve_forever()
