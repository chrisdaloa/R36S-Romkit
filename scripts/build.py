"""Costruisce l'eseguibile autonomo e lo impacchetta in dist/ (zip su Windows e macOS, tar.gz su Linux).

Uso: python scripts/build.py     (richiede: pip install pyinstaller pillow)"""
import os, sys, shutil, platform, tarfile, zipfile, subprocess, hashlib

RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RADICE)
from romkit import versione

NOME = 'R36S-Romkit'
SISTEMA = {'Windows': 'windows', 'Linux': 'linux', 'Darwin': 'macos'}[platform.system()]
EXTRA = ['web', 'config.example.toml', 'README.md', 'README.en.md', 'LICENSE', 'CHANGELOG.md']


def main():
    dist, lavoro = os.path.join(RADICE, 'dist'), os.path.join(RADICE, 'build')
    for d in (dist, lavoro):
        shutil.rmtree(d, ignore_errors=True)
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--name', NOME, '--onedir', '--console',
                    '--distpath', dist, '--workpath', lavoro, '--specpath', lavoro, os.path.join(RADICE, 'avvia.py')],
                   check=True, cwd=RADICE)
    cart = os.path.join(dist, NOME)
    for x in EXTRA:                      # accanto all'eseguibile, cosi' l'aggiornamento puo' sostituirli
        src = os.path.join(RADICE, x)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(cart, x))
        elif os.path.exists(src):
            shutil.copy2(src, cart)
    with open(os.path.join(cart, 'VERSIONE'), 'w') as fh:
        fh.write(versione.NUMERO + '\n')
    base = f'{NOME}-{versione.NUMERO}-{SISTEMA}'
    if SISTEMA == 'linux':
        pacco = os.path.join(dist, base + '.tar.gz')
        with tarfile.open(pacco, 'w:gz') as t:
            t.add(cart, arcname=NOME)
    else:
        pacco = os.path.join(dist, base + '.zip')
        with zipfile.ZipFile(pacco, 'w', zipfile.ZIP_DEFLATED) as z:
            for r, _, ff in os.walk(cart):
                for f in ff:
                    p = os.path.join(r, f)
                    z.write(p, os.path.join(NOME, os.path.relpath(p, cart)))
    h = hashlib.sha256(open(pacco, 'rb').read()).hexdigest()
    with open(pacco + '.sha256', 'w') as fh:
        fh.write(f'{h}  {os.path.basename(pacco)}\n')
    print(pacco, f'{os.path.getsize(pacco) / 1e6:.1f} MB', h)


if __name__ == '__main__':
    main()
