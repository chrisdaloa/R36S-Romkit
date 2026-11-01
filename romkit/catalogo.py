"""Genera data.js, le descrizioni e le miniature del catalogo leggendo l'archivio (sola lettura).

Uso: romkit catalogo   (rilanciabile: le miniature gia' fatte e aggiornate si saltano)
"""
import json, os, re, hashlib, xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

MEDIA = {'images', 'videos', 'media', 'manuals', 'image', 'video', 'snaps', 'boxart', 'marquees', 'covers', 'thumbnails'}
NOT_GAME = ('.png', '.jpg', '.jpeg', '.mp4', '.xml', '.txt', '.bak', '.pdf', '.srm', '.state', '.sav', '.cfg',
            '.db', '.ini', '.sh', '.gif', '.mp3', '.ogg', '.m3u', '.sub', '.ccd', '.img')
IMG_TAGS = ('image', 'thumbnail', 'boxart', 'titleshot', 'screenshot', 'marquee', 'wheel', 'mix', 'fanart')
THUMB = 220

def pulisci(f):
    b = os.path.splitext(f)[0]
    b = re.sub(r'\s*[\(\[].*?[\)\]]', '', b)
    return re.sub(r'^\d+\s*[-.]?\s*(?=\D)', '', b).lstrip('. ').strip() or f

CATEGORIE = [
    ('Piattaforma', r'platform|plataforma|piattaforma'),
    ('Sparatutto', r'shoot|tiro|sparo|sparatutto|gallery'),
    ('Combattimento', r'combattimento|luta|fight|beat.em|briga|lotta'),
    ('Corse e guida', r'corsa|corrida|\brace\b|racing|driving|pilotagem'),
    ('Sport', r'sport|esporte|calcio|futebol|baseball|tennis|golf|basket|pallacanestro|boxe|boxing|hóquei|natação|skate|\bsci\b|football|soccer|multisport'),
    ('Puzzle', r'puzzle|quebra|rompicapo'),
    ('Ruolo (RPG)', r'ruolo|rpg'),
    ('Avventura', r'avventura|aventura|adventure'),
    ('Azione', r'azione|ação|action|labirinto|maze|breakout|rompi'),
    ('Strategia', r'strat'),
    ('Simulazione', r'simula'),
    ('Carte, tavolo e casinò', r'societ|tavolo|tabuleiro|carte|mahjong|casin|cassino'),
    ('Quiz ed educativi', r'quiz|educativ'),
    ('Flipper', r'flipper|pinball'),
    ('Compilation', r'compila'),
    ('Adulti', r'adult'),
]

def categorie(v):
    c = [n for n, rx in CATEGORIE if re.search(rx, v, re.I)]
    return c or ['Altro']

LINGUE = {'en': 'en', 'fr': 'fr', 'de': 'de', 'es': 'es', 'it': 'it', 'nl': 'nl', 'pt': 'pt', 'sv': 'sv',
          'no': 'no', 'da': 'da', 'fi': 'fi', 'ja': 'ja', 'jp': 'ja', 'zh': 'zh', 'cn': 'zh', 'ko': 'ko', 'kr': 'ko',
          'ru': 'ru', 'pl': 'pl', 'br': 'pt', 'ca': 'ca', 'cs': 'cs', 'el': 'el', 'tr': 'tr', 'hu': 'hu'}
TAG_LINGUA = {'usa': 'en', 'world': 'en', 'australia': 'en', 'canada': 'en', 'uk': 'en', 'europe': 'en',
              'japan': 'ja', 'germany': 'de', 'france': 'fr', 'spain': 'es', 'italy': 'it', 'ita': 'it',
              'china': 'zh', 'taiwan': 'zh', 'korea': 'ko', 'brazil': 'pt', 'pt-br': 'pt', 'russia': 'ru',
              'netherlands': 'nl', 'sweden': 'sv', 'chinese version': 'zh', 'ch': 'zh', 'j': 'ja', 'u': 'en',
              'e': 'en', 'f': 'fr', 'g': 'de', 'i': 'it', 's': 'es', 'k': 'ko', 'c': 'zh', 'hong kong': 'zh'}

def lingue(nome_file, lang_xml=''):
    ls = set()
    for grp in re.findall(r'[\(\[]([^)\]]*)[\)\]]', nome_file):
        for tok in re.split(r'[,/+]\s*', grp):
            t = tok.strip().lower()
            if t in TAG_LINGUA:
                ls.add(TAG_LINGUA[t])
            elif re.fullmatch(r'[a-z]{2}', t) and t in LINGUE and ',' in grp:
                ls.add(LINGUE[t])
            elif t in ('en', 'fr', 'de', 'es', 'it', 'nl', 'pt', 'sv', 'ja', 'zh', 'ko', 'ru'):
                ls.add(t)
    for t in re.split(r'[,\s]+', (lang_xml or '').lower()):
        if t in LINGUE:
            ls.add(LINGUE[t])
    return sorted(ls)

def ita(*s):
    t = ' '.join(s)
    return bool(re.search(r'\b(ita|italy|italiano|italian)\b|\(it\)|\(i\)', t, re.I))

def thumb(args):
    src, dst = args
    try:
        if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
            return True
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with Image.open(src) as im:
            im = im.convert('RGB')
            im.thumbnail((THUMB, THUMB))
            im.save(dst, 'JPEG', quality=78)
        return True
    except Exception:
        return False

def genera(cfg):
    root, out = cfg.archivio, cfg.dati
    os.makedirs(out, exist_ok=True)
    skip = set(cfg['catalogo']['ignora'])
    dir_sys = set(cfg['catalogo']['sistemi_cartelle'])
    sottocart = cfg['catalogo']['sottocartelle']
    solo_ext = {k: v.lower() for k, v in cfg['catalogo']['solo_estensione'].items()}
    giocabili = cfg['gioca']['sistemi'] if cfg['gioca']['abilitato'] else []
    games, jobs, descr = [], [], {}
    for s in sorted(os.listdir(root)):
        d = os.path.join(root, s)
        if s in skip or s.startswith(('.', '_')) or not os.path.isdir(d):
            continue
        if s in sottocart and os.path.isdir(os.path.join(d, sottocart[s])):
            d = os.path.join(d, sottocart[s])
        voci = {}
        gl = os.path.join(d, 'gamelist.xml')
        if os.path.exists(gl):
            try:
                for g in ET.parse(gl).getroot().findall('game'):
                    p = os.path.normpath(g.findtext('path') or '')
                    voci[p] = g
            except ET.ParseError:
                pass
        nomi = set(os.listdir(d))
        elementi = []
        for f in nomi:
            if f.startswith('.') or f.lower() in MEDIA or f.lower().startswith('gamelist.xml') or re.search(r'\.(state\d*|torrent|sqlite|auto|a1\.bin|b1\.bin)$', f.lower()):
                continue
            p = os.path.join(d, f)
            if os.path.isdir(p):
                if s in dir_sys:
                    elementi.append(f)
            elif (f.lower().endswith(solo_ext[s]) if s in solo_ext else not f.lower().endswith(NOT_GAME)):
                if f.lower().endswith('.bin') and os.path.splitext(f)[0] + '.cue' in nomi:
                    continue
                elementi.append(f)
        for f in sorted(elementi):
            p = os.path.join(d, f)
            g = voci.get(os.path.normpath(f))
            titolo = (g.findtext('name') if g is not None else None) or pulisci(f)
            img = None
            if g is not None:
                for tag in IMG_TAGS:
                    r = (g.findtext(tag) or '').strip()
                    if r and os.path.exists(os.path.join(d, r)):
                        img = os.path.join(d, r)
                        break
            try:
                dim = os.path.getsize(p) if os.path.isfile(p) else 0
            except OSError:
                dim = 0
            riga = {'s': s, 't': titolo, 'f': f, 'sz': dim, 'it': ita(f, titolo)}
            lg = lingue(f, g.findtext('lang') if g is not None else '')
            if riga['it'] and 'it' not in lg:
                lg = sorted(lg + ['it'])
            if lg:
                riga['l'] = lg
            if g is not None:
                m = re.match(r'(\d{4})', g.findtext('releasedate') or '')
                if m and m.group(1) != '0000':
                    riga['y'] = int(m.group(1))
                try:
                    r = float(g.findtext('rating') or 0)
                    if r > 0:
                        riga['r'] = round(min(r, 1) * 5 * 2) / 2
                except ValueError:
                    pass
                for k, tag in (('g', 'genre'), ('p', 'players'), ('d', 'developer'), ('e', 'publisher')):
                    v = (g.findtext(tag) or '').strip()
                    if v:
                        riga[k] = v
                        if k == 'g':
                            riga['c'] = categorie(v)
                ds = (g.findtext('desc') or '').strip()
                if ds:
                    descr.setdefault(s, {})[f] = ds
            if img:
                h = hashlib.md5((s + f).encode()).hexdigest()[:12]
                riga['i'] = f'thumbs/{s}/{h}.jpg'
                jobs.append((img, os.path.join(out, riga['i'])))
            games.append(riga)

    with ThreadPoolExecutor(8) as ex:
        ok = list(ex.map(thumb, jobs))
    perse = {j[1] for j, o in zip(jobs, ok) if not o}
    for g in games:
        if g.get('i') and os.path.join(out, g['i']) in perse:
            del g['i']
    with open(os.path.join(out, 'data.json'), 'w') as fh:
        json.dump(games, fh, ensure_ascii=False, separators=(',', ':'))
    for sis, dd in descr.items():
        with open(os.path.join(out, f'desc_{sis}.js'), 'w') as fh:
            fh.write('window.DESC=window.DESC||{};window.DESC[' + json.dumps(sis) + ']=' + json.dumps(dd, ensure_ascii=False, separators=(',', ':')) + ';')
    # data.js permette di aprire index.html con doppio clic (file:// non consente fetch)
    with open(os.path.join(out, 'data.js'), 'w') as fh:
        fh.write('window.CONFIG=' + json.dumps({'giocabili': giocabili}) + ';window.GIOCHI=' + json.dumps(games, ensure_ascii=False, separators=(',', ':')) + ';')
    return len(games), sum(1 for g in games if 'i' in g), len(perse)
