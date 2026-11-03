"""Pulizia dei titoli mostrati: toglie i numeri d'ordine davanti al nome, non i numeri veri."""
import re

_NUM = re.compile(r'^(\d+)\s+(?=\S)')


def senza_numero(sistema, titolo, file):
    """«0001 Rockman 1» -> «Rockman 1»; restano 1942, 720 Degrees, 007, 1000 Miglia.

    E' un numero d'ordine se: zero-padded a 3+ cifre (tranne 007), codice PSP a 5+ cifre,
    oppure 3 cifre uguali a quelle che aprono il nome di un file non compresso."""
    m = _NUM.match(titolo or '')
    if not m:
        return titolo
    n, resto = m.group(1), titolo[m.end():]
    indice = n != '007' and (
        (n[0] == '0' and len(n) >= 3)
        or (sistema == 'psp' and len(n) >= 5)
        or (len(n) == 3 and file.startswith(n + ' ') and not file.lower().endswith(('.zip', '.7z'))))
    return resto if indice and resto else titolo
