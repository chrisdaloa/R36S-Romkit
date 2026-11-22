"""Versione del programma: numero di rilascio e, in una copia git, il commit in uso."""
import os, re, sys, subprocess, time, glob

NUMERO = '0.5.11'
CONGELATO = bool(getattr(sys, 'frozen', False))      # True nell'eseguibile autonomo (PyInstaller)
RADICE = os.path.dirname(sys.executable) if CONGELATO else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _git(*a):
    try:
        r = subprocess.run(['git', '-C', RADICE, *a], capture_output=True, text=True, timeout=5)
        return r.stdout.strip() if r.returncode == 0 else ''
    except (OSError, subprocess.SubprocessError):
        return ''


def commit():
    """Commit breve della copia sul disco ('' se non e' una copia git); '+' se ci sono modifiche ai file del programma."""
    c = _git('rev-parse', '--short', 'HEAD')
    if c and _git('status', '--porcelain', '--', 'romkit', 'web'):
        c += '+'
    return c


AVVIO = commit()     # commit al momento dell'avvio
T_AVVIO = time.time()


def _python_cambiato():
    """True se un file Python del programma e' stato modificato dopo l'avvio: il server gira con codice vecchio."""
    return any(os.path.getmtime(f) > T_AVVIO for f in glob.glob(os.path.join(RADICE, 'romkit', '*.py')))


def _num(v):
    return tuple(int(x) for x in re.findall(r'\d+', v)[:4])


def novita_su_disco():
    """(versione sul disco, testo del CHANGELOG delle versioni piu' recenti di quella in esecuzione)."""
    try:
        disco = re.search(r"NUMERO = '([^']+)'", open(os.path.join(RADICE, 'romkit', 'versione.py'), encoding='utf-8').read()).group(1)
        parti = re.split(r'^## ', open(os.path.join(RADICE, 'CHANGELOG.md'), encoding='utf-8').read(), flags=re.M)[1:]
    except (OSError, AttributeError):
        return '', ''
    nuove = [p.strip() for p in parti if re.match(r'\d', p) and _num(p.split()[0]) > _num(NUMERO)]
    return disco, '\n'.join('## ' + p for p in nuove)


def info():
    ora, da = commit(), _python_cambiato()
    r = {'versione': NUMERO, 'commit': AVVIO, 'su_disco': ora, 'da_riavviare': da}
    if da:
        r['versione_su_disco'], r['novita'] = novita_su_disco()
    return r


def testo():
    return f'{NUMERO} ({AVVIO})' if AVVIO else NUMERO
