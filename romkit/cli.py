"""Riga di comando: romkit <comando> [--config config.toml]."""
import argparse, os, sys
from . import config as C


def _cfg(a):
    f = a.config
    if not os.path.exists(f):
        sys.exit(f'Config non trovata: {f}. Avvia "romkit serve" per la configurazione guidata, oppure copia config.example.toml in config.toml.')
    c = C.carica(f)
    if getattr(a, 'archivio', None):
        c.archivio = os.path.abspath(os.path.expanduser(a.archivio))
    if not c.archivio or not os.path.isdir(c.archivio):
        sys.exit(f'Archivio non raggiungibile: {c.archivio!r} (imposta [archivio].percorso)')
    return c


def main(argv=None):
    p = argparse.ArgumentParser(prog='romkit', description='Catalogo web e pack per schede SD di console portatili.')
    p.add_argument('--config', default='config.toml')
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('catalogo', help='genera i dati del catalogo dall\'archivio')
    sv = sub.add_parser('serve', help='avvia il server del catalogo')
    sv.add_argument('--setup', action='store_true', help='riapre la configurazione guidata anche se config.toml esiste')
    sv.add_argument('--porta', type=int, default=8765, help='porta della configurazione guidata (predefinita 8765)')
    sv.add_argument('--archivio', help='usa questa cartella al posto di [archivio].percorso')
    d = sub.add_parser('demo', help='crea un archivio finto e una config di prova')
    d.add_argument('cartella', nargs='?', default='demo-lavoro')
    sd = sub.add_parser('sd', help='riepiloga e confronta una SD (montata o via SSH), in sola lettura')
    sds = sd.add_subparsers(dest='az', required=True)
    sr = sds.add_parser('riepilogo'); sr.add_argument('dove', nargs='?', help='cartella o utente@host:/percorso')
    sc = sds.add_parser('confronta'); sc.add_argument('dove', nargs='?'); sc.add_argument('--pack')
    sc.add_argument('--dettagli', action='store_true')
    pk = sub.add_parser('pack', help='prepara o copia un pack')
    ps = pk.add_subparsers(dest='az', required=True)
    pp = ps.add_parser('prepara'); pp.add_argument('nome'); pp.add_argument('cartella')
    pc = ps.add_parser('copia'); pc.add_argument('cartella'); pc.add_argument('--applica', action='store_true')
    pc.add_argument('--destinazione')
    a = p.parse_args(argv)

    if a.cmd == 'demo':
        from . import demo
        return demo.crea(a.cartella)
    if a.cmd == 'serve' and (a.setup or not os.path.exists(a.config)):
        from . import server
        return server.serve_setup(os.path.abspath(a.config), porta=a.porta)
    cfg = _cfg(a)
    if a.cmd == 'catalogo':
        from . import catalogo
        catalogo.genera(cfg)
    elif a.cmd == 'serve':
        from . import server
        server.serve(cfg)
    elif a.cmd == 'sd':
        from . import sd
        dove = a.dove or cfg['sd']['destinazione']
        if not dove:
            sys.exit('Indica la SD: romkit sd riepilogo <cartella|utente@host:/percorso> oppure imposta [sd].destinazione')
        sd.riepilogo(cfg, dove) if a.az == 'riepilogo' else sd.confronta(cfg, dove, a.pack, a.dettagli)
    elif a.cmd == 'pack':
        from . import packs
        if a.az == 'prepara':
            r = packs.prepara(cfg, a.nome, a.cartella)
            print(open(os.path.join(r['dest'], 'report.txt')).read()[:4000])
        else:
            packs.copia(cfg, a.cartella, a.applica, a.destinazione)


if __name__ == '__main__':
    main()
