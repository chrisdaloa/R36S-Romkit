"""Server locale del catalogo: pagina web, dati generati, pack e (solo se abilitato) ROM in sola lettura."""
import os, json, posixpath, tempfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit, parse_qs
from . import sd, sorgenti

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'web')
MAX_PACKS = 20 * 1024 * 1024
DATI = ('data.js', 'data.json')


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
            # sola lettura; il browser indica solo il nome di una sorgente configurata
            sorg = sorgenti.tutte(cfg)
            if not q.get('sorgente'):
                return self._json(json.dumps(list(sorg)).encode())
            nome = q['sorgente'][0]
            if nome not in sorg:
                return self.send_error(404, 'Sorgente sconosciuta')
            try:
                r = sd.analizza(cfg, sorg[nome], (q.get('pack') or [None])[0] or None)
            except (OSError, KeyError, SystemExit) as e:
                return self.send_error(502, str(e)[:200] or 'SD non raggiungibile')
            r['dettagli'] = r['dettagli'][:2000]
            r.pop('dove', None)
            self._json(json.dumps(r, ensure_ascii=False).encode())

        def do_GET(self):
            ru = urlsplit(self.path)
            if ru.path == '/api/volumi':
                return self._json(json.dumps({'volumi': sorgenti.volumi(cfg), 'salvate': sorgenti.salvate(cfg),
                                              'modificabile': locale}).encode())
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
            if self.path.split('?', 1)[0] != '/api/packs':
                return self.send_error(405)
            orig = self.headers.get('Origin')
            if orig and orig.split('://', 1)[-1] != self.headers.get('Host'):
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

        def _origine_ok(self):
            orig = self.headers.get('Origin')
            return bool(locale) and not (orig and orig.split('://', 1)[-1] != self.headers.get('Host'))

        def _sorgente(self, agg):
            # il browser indica un nome e un percorso tra i volumi rilevati, mai un percorso libero
            if urlsplit(self.path).path != '/api/sorgenti':
                return self.send_error(405)
            if not self._origine_ok():
                return self.send_error(403)
            n = int(self.headers.get('Content-Length') or 0)
            if not 0 < n <= 4096:
                return self.send_error(413)
            try:
                d = json.loads(self.rfile.read(n))
                if agg:
                    sorgenti.aggiungi(cfg, d['nome'], d['percorso'])
                else:
                    sorgenti.rimuovi(cfg, d['nome'])
            except (ValueError, KeyError, TypeError) as e:
                return self.send_error(400, str(e)[:100])
            self.send_response(204)
            self.end_headers()

        def do_POST(self):
            self._sorgente(True)

        def do_DELETE(self):
            self._sorgente(False)

    return H


def serve(cfg):
    host, porta = cfg['server']['host'], cfg['server']['porta']
    os.makedirs(cfg.pack, exist_ok=True)
    print(f'Catalogo su http://{host}:{porta}/index.html  (Ctrl+C per fermare)')
    if host not in ('127.0.0.1', 'localhost', '::1'):
        print('ATTENZIONE: server raggiungibile dalla rete, senza autenticazione.')
    ThreadingHTTPServer((host, porta), crea(cfg)).serve_forever()
