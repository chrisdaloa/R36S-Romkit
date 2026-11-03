"""Piano di sincronizzazione di una SD con un pack: cosa aggiungere, aggiornare, togliere. Solo lettura."""
import os, fnmatch, subprocess
from . import packs

SALVATAGGI = ('.srm', '.sav', '.state', '.auto', '.rtc', '.mcr', '.mcd', '.eep', '.fla', '.sra', '.nv')


def _remoto(dove):
    return ':' in dove and not os.path.isabs(dove)


def _file_sd(dove, escludi, ignora):
    """{percorso relativo: dimensione} dei file nelle cartelle dei sistemi della SD."""
    out = {}
    if _remoto(dove):
        host, _, path = dove.partition(':')
        cmd = f"cd {path!r} && find . -mindepth 2 -type f -printf '%s\\t%P\\n'"
        r = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', host, cmd],
                           capture_output=True, text=True, timeout=600)
        if r.returncode:
            raise SystemExit(f'SSH fallito verso {host}: {r.stderr.strip()[:200]}')
        for riga in r.stdout.splitlines():
            sz, p = riga.split('\t', 1)
            out[p] = int(sz)
    else:
        for s in os.listdir(dove):
            if s.startswith(('.', '_')) or not os.path.isdir(os.path.join(dove, s)):
                continue
            for r, dd, ff in os.walk(os.path.join(dove, s)):
                for f in ff:
                    p = os.path.join(r, f)
                    out[os.path.relpath(p, dove)] = os.path.getsize(p)
    return {p: n for p, n in out.items()
            if p.split('/', 1)[0] not in ignora and not any(fnmatch.fnmatch(os.path.basename(p), e) for e in escludi)}


def piano(cfg, dove, pack, cartella='_anteprima'):
    """Confronta file per file la SD con la lista di copia del pack.

    Si toglie solo cio' che sta in un sistema del pack, esiste anche nell'archivio con lo stesso percorso e non e' nel pack:
    salvataggi, cartelle di servizio, sistemi fuori dal pack e file estranei all'archivio non vengono mai proposti."""
    r = packs.prepara(cfg, pack, cartella)
    with open(os.path.join(r['dest'], 'lista-copia.txt')) as fh:
        voluto = {x for x in fh.read().split('\n') if x}
    arch = cfg.archivio
    sistemi = {i.split('/', 1)[0] for i in packs.carica_packs(cfg)[pack]['ids']} - set(cfg['sync']['non_toccare'])
    ignora = set(cfg['catalogo']['ignora']) | set(cfg['pack']['servizio'])
    sd = _file_sd(dove, cfg['pack']['escludi'], ignora)
    sd_tutti = sd
    agg, upd, tog = [], [], []
    for p in sorted(voluto):
        try:
            n = os.path.getsize(os.path.join(arch, p))
        except OSError:
            continue
        if p.split('/', 1)[0] in ignora:
            continue                                   # file di servizio: non fanno parte del confronto
        if p not in sd:
            agg.append((p, n))
        elif sd[p] != n:
            upd.append((p, n))
    for p, n in sorted(sd.items()):
        b = os.path.basename(p).lower()
        if p.split('/', 1)[0] not in sistemi or p in voluto or b.startswith('gamelist.xml') or b.endswith(SALVATAGGI) or '.state' in b:
            continue
        if os.path.isfile(os.path.join(arch, p)):
            tog.append((p, n))
    def somma(l):
        return sum(n for _, n in l)
    per = {}
    for k, l in (('aggiungi', agg), ('aggiorna', upd), ('togli', tog)):
        for p, n in l:
            x = per.setdefault(p.split('/', 1)[0], {'aggiungi': [0, 0], 'aggiorna': [0, 0], 'togli': [0, 0]})[k]
            x[0] += 1
            x[1] += n
    return {'pack': pack, 'cartella': r['dest'], 'anomalie': r['anomalie'],
            'aggiungi': agg, 'aggiorna': upd, 'togli': tog,
            'byte': {'aggiungi': somma(agg), 'aggiorna': somma(upd), 'togli': somma(tog)},
            'per_sistema': per, 'file_sd': len(sd_tutti)}
