"""Server locale del catalogo: pagina web, dati generati, pack e (solo se abilitato) ROM in sola lettura."""
import os, json, posixpath, tempfile, threading, time, uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit, parse_qs
from . import sd, sorgenti, sync, packs

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'web')
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
            p = sync.piano(cfg, dove, pack)
            elenco = {k: p[k][:3000] for k in ('aggiungi', 'aggiorna', 'togli')}
            n = {k: len(p[k]) for k in ('aggiungi', 'aggiorna', 'togli')}
            r = {'stato': 'finito', 'byte': p['byte'], 'n': n, 'per_sistema': p['per_sistema'],
                 'elenco': elenco, 'anomalie': p['anomalie'][:50]}
        except (OSError, KeyError, SystemExit) as e:
            r = {'stato': 'errore', 'errore': str(e)[:200] or 'Calcolo non riuscito'}
        with LAVORI_LOCK:
            LAVORI[j].update(r)
    threading.Thread(target=corri, daemon=True).start()
    return j


def crea(cfg):
    packs_file = os.path.join(cfg.pack, 'packs.json')
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

        def do_GET(self):
            ru = urlsplit(self.path)
            if ru.path == '/api/sync':
                return self._sync_stato(parse_qs(ru.query))
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
            if not self._origine_ok():
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

        def _origine_ok(self):
            orig = self.headers.get('Origin')
            return self._da_qui() and not (orig and orig.split('://', 1)[-1] != self.headers.get('Host'))

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
            if urlsplit(self.path).path == '/api/sync':
                return self._sync_avvia()
            self._sorgente('aggiungi')

        def do_DELETE(self):
            self._sorgente('rimuovi')

    return H


def serve(cfg):
    host, porta = cfg['server']['host'], cfg['server']['porta']
    os.makedirs(cfg.pack, exist_ok=True)
    print(f'Catalogo su http://{host}:{porta}/index.html  (Ctrl+C per fermare)')
    if host not in ('127.0.0.1', 'localhost', '::1'):
        print('ATTENZIONE: server raggiungibile dalla rete, senza autenticazione.')
    ThreadingHTTPServer((host, porta), crea(cfg)).serve_forever()
