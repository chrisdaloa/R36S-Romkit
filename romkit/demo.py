"""Archivio finto per provare romkit senza ROM vere: file vuoti, gamelist e immagini generate."""
import os, json
from xml.sax.saxutils import escape

GIOCHI = {
    'nes': ['Super Demo Bros (Italy)', 'Quest of Pixels (USA)', 'Block Runner (Europe)'],
    'snes': ['Space Test World (Italy)', 'Pixel Kart (USA)'],
    'gba': ['Advance Demo (Italy)', 'Tiny Hero (Europe)', 'Puzzle Land (USA)'],
    'megadrive': ['Speedy Blue (Europe)', 'Demo Fighter (USA)'],
}
EST = {'nes': 'zip', 'snes': 'zip', 'gba': 'zip', 'megadrive': 'zip'}


def crea(cartella, avviso=True):
    from PIL import Image, ImageDraw
    arch = os.path.join(cartella, 'EASYROMS')
    for s, titoli in GIOCHI.items():
        d = os.path.join(arch, s)
        os.makedirs(os.path.join(d, 'downloaded_images'), exist_ok=True)
        righe = ['<?xml version="1.0"?>', '<gameList>']
        for i, t in enumerate(titoli):
            f = f'{t}.{EST[s]}'
            with open(os.path.join(d, f), 'wb') as fh:
                fh.write(b'PK' + bytes(100))
            im = Image.new('RGB', (320, 240), ((i * 70) % 255, (len(s) * 40) % 255, 120))
            ImageDraw.Draw(im).text((10, 110), t, fill='white')
            im.save(os.path.join(d, 'downloaded_images', f'{t}.png'))
            righe.append(f'<game><path>./{escape(f)}</path><name>{escape(t)}</name>'
                         f'<desc>Gioco di prova per {s}.</desc><image>./downloaded_images/{escape(t)}.png</image>'
                         f'<genre>Platform</genre><players>1-2</players><releasedate>199{i}0101T000000</releasedate></game>')
        righe.append('</gameList>')
        open(os.path.join(d, 'gamelist.xml'), 'w').write('\n'.join(righe))
    os.makedirs(os.path.join(arch, 'bios'), exist_ok=True)
    open(os.path.join(arch, 'bios', 'finto.bin'), 'wb').write(bytes(64))
    cfgf = os.path.join(cartella, 'config.toml')
    open(cfgf, 'w').write(f'[archivio]\npercorso = "./EASYROMS"\n[uscite]\ndati = "./dati"\npack = "./packs"\n'
                           f'[sd]\ndestinazione = "./SD-finta"\n')
    os.makedirs(os.path.join(cartella, 'SD-finta'), exist_ok=True)
    if avviso:
        print(f'Demo creata in {cartella}. Prova:\n  romkit --config {cfgf} catalogo\n  romkit --config {cfgf} serve')
    return cartella
