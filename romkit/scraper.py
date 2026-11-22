"""Scraping opzionale da ScreenScraper per i giochi senza voce nel gamelist.xml dell'archivio.

Due fasi, entrambe riprendibili:
  1. cerca: per ogni gioco senza voce calcola il CRC (da un .zip singolo si legge dall'indice, senza leggere il file) e
     interroga ScreenScraper; l'esito si conserva in <dati>/scraper/<sistema>.json (anche «non trovato»).
  2. applica: scrive le voci nel gamelist.xml e scarica immagini e marquee nell'archivio, con copia di sicurezza prima.
Serve il programma registrato presso ScreenScraper (devid/devpassword in [scraper]); l'account utente e' facoltativo.
"""
import os, re, json, time, shutil, zipfile, zlib, datetime, urllib.request, urllib.parse, urllib.error
import xml.etree.ElementTree as ET
from .catalogo import MEDIA, NOT_GAME

API = 'https://api.screenscraper.fr/api2/jeuInfos.php'
# id dei sistemi in ScreenScraper; modificabili in [scraper.sistemi] del config
SISTEMI = {'nes': 3, 'famicom': 3, 'snes': 4, 'gb': 9, 'gbc': 10, 'gba': 12, 'mastersystem': 2, 'megadrive': 1,
           'gamegear': 21, 'atari2600': 26, 'msx': 113, 'n64': 14, 'psx': 57, 'pcengine': 31}
REGIONI = ('wor', 'eu', 'us', 'ss', 'jp')
LINGUE = ('it', 'en')
MAX_CRC_MB = 64


class Quota(Exception):
    """Quota giornaliera o limite di richieste raggiunti: ci si ferma e si riprende dopo."""


def scarica(url, timeout=60):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'R36S-Romkit'}), timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:300]


def _crc(percorso):
    """CRC32 del gioco; per uno .zip con un solo file e' quello del file contenuto (dall'indice, senza leggerlo)."""
    if percorso.lower().endswith('.zip'):
        try:
            with zipfile.ZipFile(percorso) as z:
                v = [i for i in z.infolist() if not i.is_dir()]
                if len(v) == 1:
                    return f'{v[0].CRC:08X}'
        except (zipfile.BadZipFile, OSError):
            return ''
    if os.path.getsize(percorso) > MAX_CRC_MB * 1048576:
        return ''
    c = 0
    with open(percorso, 'rb') as fh:
        for b in iter(lambda: fh.read(1 << 20), b''):
            c = zlib.crc32(b, c)
    return f'{c & 0xffffffff:08X}'


def senza_voce(cfg, s):
    """(cartella del sistema, file di gioco che non hanno una voce nel gamelist)."""
    sdir = os.path.join(cfg.archivio, s, cfg['catalogo']['sottocartelle'].get(s, ''))
    gl, voci = os.path.join(sdir, 'gamelist.xml'), set()
    if os.path.exists(gl):
        voci = {os.path.normpath(g.findtext('path') or '') for g in ET.parse(gl).getroot().findall('game')}
    out = [f for f in sorted(os.listdir(sdir))
           if os.path.isfile(os.path.join(sdir, f)) and not f.startswith('.') and f not in MEDIA
           and not f.lower().endswith(NOT_GAME) and os.path.normpath(f) not in voci]
    return sdir, out


def _scelta(lista, chiave, ordine):
    """Primo elemento di una lista di {chiave, text} secondo l'ordine delle preferenze, altrimenti il primo."""
    for o in ordine:
        for x in lista or []:
            if x.get(chiave) == o and x.get('text'):
                return x['text']
    return next((x['text'] for x in lista or [] if x.get('text')), '')


def _estrai(jeu):
    """Dati utili dalla risposta di jeuInfos (struttura difensiva: i campi mancanti restano vuoti)."""
    def t(k):
        v = jeu.get(k)
        return (v.get('text') if isinstance(v, dict) else v) or ''
    genere = ''
    for g in jeu.get('genres') or []:
        genere = _scelta(g.get('noms'), 'langue', LINGUE)
        if genere:
            break
    data = _scelta(jeu.get('dates'), 'region', REGIONI)
    m = re.match(r'(\d{4})(?:-(\d\d))?(?:-(\d\d))?', data)
    voto = ''
    try:
        voto = f'{min(1.0, float(t("note")) / 20):.2f}'.rstrip('0').rstrip('.') if t('note') else ''
    except ValueError:
        pass
    media = {}
    for x in jeu.get('medias') or []:
        if x.get('url') and x.get('type') in ('box-2D', 'ss', 'sstitle', 'screenmarquee', 'wheel') and x['type'] not in media:
            media[x['type']] = [x['url'], x.get('format') or 'png']
    return {'nome': _scelta(jeu.get('noms'), 'region', REGIONI), 'desc': _scelta(jeu.get('synopsis'), 'langue', LINGUE),
            'genere': genere, 'data': f'{m.group(1)}{m.group(2) or "01"}{m.group(3) or "01"}T000000' if m else '',
            'voto': voto, 'giocatori': t('joueurs'), 'sviluppatore': t('developpeur'), 'editore': t('editeur'), 'media': media}


def _url(cfg, sid, f, percorso):
    c = cfg['scraper']
    q = {'devid': c['devid'], 'devpassword': c['devpassword'], 'softname': c['softname'], 'output': 'json',
         'ssid': c['ssid'], 'sspassword': c['sspassword'], 'systemeid': sid, 'romtype': 'rom', 'romnom': f,
         'romtaille': os.path.getsize(percorso), 'crc': _crc(percorso)}
    return API + '?' + urllib.parse.urlencode({k: v for k, v in q.items() if v not in ('', None)})


def _cache(cfg, s):
    return os.path.join(cfg.dati, 'scraper', s + '.json')


def cerca(cfg, s, limite=None, http=scarica, pausa=None, avanza=print):
    """Interroga ScreenScraper per i giochi del sistema non ancora cercati. Restituisce (cercati, trovati, ancora_da_fare)."""
    c = cfg['scraper']
    if not (c['devid'] and c['devpassword']):
        raise SystemExit('Mancano le credenziali del programma: imposta devid e devpassword in [scraper] del config '
                         '(si chiedono a ScreenScraper registrando il programma come sviluppatore).')
    sid = c['sistemi'].get(s) or SISTEMI.get(s)
    if not sid:
        raise SystemExit(f'Sistema «{s}» sconosciuto per ScreenScraper: indica il suo id in [scraper.sistemi].')
    sdir, files = senza_voce(cfg, s)
    fc = _cache(cfg, s)
    try:
        cache = json.load(open(fc))
    except (OSError, ValueError):
        cache = {}
    da_fare = [f for f in files if f not in cache]
    pausa = c['pausa'] if pausa is None else pausa
    cercati = trovati = 0
    try:
        for k, f in enumerate(da_fare[:limite]):
            st, corpo = http(_url(cfg, sid, f, os.path.join(sdir, f)))
            if st in (429, 430, 431) or (st == 401 and b'API' in corpo):
                raise Quota(f'ScreenScraper ha risposto {st}: quota o limite raggiunti, riprendi piu\' tardi.')
            if st in (401, 403):
                raise SystemExit('ScreenScraper rifiuta le credenziali del programma: controlla devid e devpassword in [scraper] del config.')
            cercati += 1
            if st == 200:
                try:
                    cache[f] = _estrai(json.loads(corpo)['response']['jeu'])
                    trovati += 1
                except (ValueError, KeyError, TypeError):
                    cache[f] = None
            elif st == 404:
                cache[f] = None
            else:
                raise SystemExit(f'Risposta inattesa di ScreenScraper ({st}) per «{f}»: {corpo[:120]!r}')
            if avanza and (k + 1) % 10 == 0:
                avanza(f'{s}: {k + 1} di {len(da_fare[:limite])} cercati')
            time.sleep(pausa)
    except Quota as e:
        avanza(str(e))
    finally:
        os.makedirs(os.path.dirname(fc), exist_ok=True)
        with open(fc, 'w') as fh:
            json.dump(cache, fh, ensure_ascii=False)
    return cercati, trovati, len([f for f in files if f not in cache])


def riepilogo(cfg, s):
    sdir, files = senza_voce(cfg, s)
    try:
        cache = json.load(open(_cache(cfg, s)))
    except (OSError, ValueError):
        cache = {}
    trov = [f for f in files if cache.get(f)]
    return {'senza_voce': len(files), 'cercati': sum(f in cache for f in files), 'trovati': len(trov),
            'non_trovati': sum(f in cache and not cache[f] for f in files)}


def applica(cfg, s, http=scarica, avanza=print):
    """Scrive nel gamelist e scarica i media dei giochi trovati. Copia di sicurezza prima di toccare il gamelist."""
    sdir, files = senza_voce(cfg, s)
    try:
        cache = json.load(open(_cache(cfg, s)))
    except (OSError, ValueError):
        return {'scritte': 0, 'media': 0}
    scelti = [f for f in files if cache.get(f)]
    if not scelti:
        return {'scritte': 0, 'media': 0}
    gl = os.path.join(sdir, 'gamelist.xml')
    if os.path.exists(gl):
        shutil.copy2(gl, f'{gl}.bak-prima-scraper-{datetime.date.today():%Y%m%d}')
        tree = ET.parse(gl)
    else:
        tree = ET.ElementTree(ET.Element('gameList'))
    root, media = tree.getroot(), 0
    for f in scelti:
        d, stem = cache[f], os.path.splitext(f)[0]
        g = ET.SubElement(root, 'game')
        ET.SubElement(g, 'path').text = './' + f
        ET.SubElement(g, 'name').text = d['nome'] or stem
        for tipo, cartella, tag in (('box-2D', 'downloaded_images', 'image'), ('ss', 'downloaded_images', 'thumbnail'),
                                    ('screenmarquee', 'marquees', 'marquee')):
            if tipo not in d['media'] or (tag == 'thumbnail' and 'box-2D' in d['media']):
                continue
            url, fmt = d['media'][tipo]
            rel = f'{cartella}/{stem}.{fmt if re.fullmatch(r"\w{2,4}", fmt) else "png"}'
            st, corpo = http(url)
            if st == 200 and corpo:
                os.makedirs(os.path.join(sdir, cartella), exist_ok=True)
                with open(os.path.join(sdir, rel), 'wb') as fh:
                    fh.write(corpo)
                ET.SubElement(g, 'image' if tag == 'thumbnail' else tag).text = './' + rel
                media += 1
        for tag, k in (('desc', 'desc'), ('rating', 'voto'), ('releasedate', 'data'), ('developer', 'sviluppatore'),
                       ('publisher', 'editore'), ('genre', 'genere'), ('players', 'giocatori')):
            if d.get(k):
                ET.SubElement(g, tag).text = d[k]
    ET.indent(tree)
    tree.write(gl, encoding='utf-8', xml_declaration=True)
    return {'scritte': len(scelti), 'media': media}
