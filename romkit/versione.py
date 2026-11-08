"""Versione del programma: numero di rilascio e, in una copia git, il commit in uso."""
import os, sys, subprocess, time, glob

NUMERO = '0.5.0'
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


def info():
    ora = commit()
    return {'versione': NUMERO, 'commit': AVVIO, 'su_disco': ora, 'da_riavviare': _python_cambiato()}


def testo():
    return f'{NUMERO} ({AVVIO})' if AVVIO else NUMERO
