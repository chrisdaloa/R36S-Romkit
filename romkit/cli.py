"""Riga di comando: romkit <comando> [--config config.toml]."""
import argparse, os, sys
from . import config as C


def _cfg(a):
    f = a.config
    if not os.path.exists(f):
        sys.exit(f'Config non trovata: {f}. Copia config.example.toml in config.toml e adattala.')
    c = C.carica(f)
    if not c.archivio or not os.path.isdir(c.archivio):
        sys.exit(f'Archivio non raggiungibile: {c.archivio!r} (imposta [archivio].percorso)')
    return c


def main(argv=None):
    p = argparse.ArgumentParser(prog='romkit', description='Catalogo web e pack per schede SD di console portatili.')
    p.add_argument('--config', default='config.toml')
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('catalogo', help='genera i dati del catalogo dall\'archivio')
    sub.add_parser('serve', help='avvia il server del catalogo')
    d = sub.add_parser('demo', help='crea un archivio finto e una config di prova')
    d.add_argument('cartella', nargs='?', default='demo-lavoro')
    pk = sub.add_parser('pack', help='prepara o copia un pack')
    ps = pk.add_subparsers(dest='az', required=True)
    pp = ps.add_parser('prepara'); pp.add_argument('nome'); pp.add_argument('cartella')
    pc = ps.add_parser('copia'); pc.add_argument('cartella'); pc.add_argument('--applica', action='store_true')
    pc.add_argument('--destinazione')
    a = p.parse_args(argv)

    if a.cmd == 'demo':
        from . import demo
        return demo.crea(a.cartella)
    cfg = _cfg(a)
    if a.cmd == 'catalogo':
        from . import catalogo
        catalogo.genera(cfg)
    elif a.cmd == 'serve':
        from . import server
        server.serve(cfg)
    elif a.cmd == 'pack':
        from . import packs
        if a.az == 'prepara':
            r = packs.prepara(cfg, a.nome, a.cartella)
            print(open(os.path.join(r['dest'], 'report.txt')).read()[:4000])
        else:
            packs.copia(cfg, a.cartella, a.applica, a.destinazione)


if __name__ == '__main__':
    main()
