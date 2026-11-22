import os, json, tempfile, unittest
from romkit import cli, config, packs


class Fumo(unittest.TestCase):
    def test_demo_catalogo_pack(self):
        with tempfile.TemporaryDirectory() as t:
            lav = os.path.join(t, 'lav')
            cli.main(['demo', lav])
            cf = os.path.join(lav, 'config.toml')
            cli.main(['--config', cf, 'catalogo'])
            cfg = config.carica(cf)
            self.assertTrue(os.path.exists(os.path.join(cfg.dati, 'data.json')))
            dati = json.load(open(os.path.join(cfg.dati, 'data.json')))
            self.assertEqual(len(dati), 10)
            os.makedirs(cfg.pack)
            ids = [f"{g['s']}/{g['f']}" for g in dati if g['s'] in ('nes', 'gba')]
            json.dump({'P': {'cap': 1, 'ris': 0, 'ids': ids}}, open(os.path.join(cfg.pack, 'packs.json'), 'w'))
            r = packs.prepara(cfg, 'P', 'P1')
            self.assertEqual(r['anomalie'], [])
            lista = open(os.path.join(r['dest'], 'lista-copia.txt')).read().split('\n')
            self.assertIn('nes/Super Demo Bros (Italy).zip', lista)
            self.assertNotIn('snes/Pixel Kart (USA).zip', lista)
            self.assertIn('bios/finto.bin', lista)
            # SD finta: una copia parziale del pack, piu' un gioco non previsto
            from romkit import sd
            sdp = os.path.join(t, 'sd')
            os.makedirs(os.path.join(sdp, 'nes'))
            os.makedirs(os.path.join(sdp, 'snes'))
            for f in ('Super Demo Bros (Italy).zip', 'Quest of Pixels (USA).zip'):
                open(os.path.join(sdp, 'nes', f), 'wb').write(b'PK' + bytes(100))
            open(os.path.join(sdp, 'snes', 'Pixel Kart (USA).zip'), 'wb').write(b'x')
            dett = sd.confronta(cfg, sdp, pack='P')
            self.assertIn(('+', 'nes', 'Block Runner (Europe).zip'), dett)
            self.assertIn(('+', 'gba', 'Tiny Hero (Europe).zip'), dett)
            self.assertIn(('-', 'snes', 'Pixel Kart (USA).zip'), dett)

    def test_cestino_scheda(self):
        from romkit import sync
        with tempfile.TemporaryDirectory() as t:
            def scrivi(rel, txt='x'):
                p = os.path.join(t, rel)
                os.makedirs(os.path.dirname(p), exist_ok=True)
                open(p, 'w').write(txt)
            scrivi('_rimossi/2026-11-04_134314/nes/a.nes', 'aaa')
            scrivi('_rimossi/2026-11-04_134314/snes/b.sfc', 'bb')
            scrivi('_rimossi/2026-11-04_134314/snes/c.sfc', 'cc')
            scrivi('_rimossi/non-una-data/nes/z.nes')
            scrivi('snes/c.sfc', 'nuovo')                      # gia' presente: non va sovrascritto
            c = sync.cestino(t)
            self.assertEqual([(x['data'], x['file'], x['byte']) for x in c], [('2026-11-04_134314', 3, 7)])
            self.assertEqual(c[0]['sistemi'], {'nes': 1, 'snes': 2})
            for brutta in ('../x', 'non-una-data', '2026-11-04_000000'):
                with self.assertRaises(SystemExit):
                    sync.ripristina(t, brutta)
            r = sync.ripristina(t, '2026-11-04_134314')
            self.assertEqual(r, {'ripristinati': 2, 'rimasti': 1})
            self.assertEqual(open(os.path.join(t, 'nes/a.nes')).read(), 'aaa')
            self.assertEqual(open(os.path.join(t, 'snes/c.sfc')).read(), 'nuovo')
            self.assertEqual(os.listdir(os.path.join(t, '_rimossi/2026-11-04_134314/snes')), ['c.sfc'])
            self.assertEqual(sync.svuota(t, '2026-11-04_134314'), {'cancellati': 1, 'byte': 2})
            self.assertEqual(sync.cestino(t), [])
            self.assertTrue(os.path.isdir(os.path.join(t, '_rimossi/non-una-data')))

    def test_smonta_scheda(self):
        from types import SimpleNamespace as R
        from romkit import sorgenti
        with tempfile.TemporaryDirectory() as t:
            lav = os.path.join(t, 'lav')
            cli.main(['demo', lav])
            cfg = config.carica(os.path.join(lav, 'config.toml'))
            sdp = os.path.join(t, 'media', 'EASYROMS')
            os.makedirs(sdp)
            cfg['sd']['sorgenti']['SD'] = sdp
            def disco(rm=True, extra=None):
                ch = [{'name': 'sdx1', 'path': '/dev/sdx1', 'mountpoints': [None]},
                      {'name': 'sdx3', 'path': '/dev/sdx3', 'mountpoints': [sdp]}] + (extra or [])
                return {'blockdevices': [{'name': 'sdx', 'path': '/dev/sdx', 'rm': rm, 'hotplug': rm, 'children': ch}]}
            chiamate = []
            def ok(cmd):
                chiamate.append(cmd)
                return R(returncode=0, stdout='', stderr='')
            cfg_ = cfg
            self.addCleanup(setattr, sorgenti, 'RADICI', sorgenti.RADICI)
            sorgenti.RADICI = (os.path.realpath(t),)
            # sorgenti.smonta usa il percorso reale: la sorgente del config qui coincide con il mount
            r = sorgenti.smonta(cfg_, 'SD', disco(), ok)
            self.assertEqual(r, {'smontate': 1, 'spenta': True})
            self.assertIn(['udisksctl', 'unmount', '-b', '/dev/sdx3'], chiamate)
            self.assertEqual(chiamate[-1], ['udisksctl', 'power-off', '-b', '/dev/sdx'])
            with self.assertRaises(SystemExit):                   # disco non rimovibile
                sorgenti.smonta(cfg_, 'SD', disco(rm=False), ok)
            with self.assertRaises(SystemExit):                   # partizione di sistema sullo stesso disco
                sorgenti.smonta(cfg_, 'SD', disco(extra=[{'name': 'sdx2', 'path': '/dev/sdx2', 'mountpoints': ['/boot']}]), ok)
            def occupato(cmd):
                return R(returncode=1 if cmd[1:2] == ['unmount'] else 0, stdout='', stderr='target is busy')
            with self.assertRaises(SystemExit) as e:
                sorgenti.smonta(cfg_, 'SD', disco(), occupato)
            self.assertIn('busy', str(e.exception))
            with self.assertRaises(SystemExit):                   # sorgente sconosciuta
                sorgenti.smonta(cfg_, 'altra', disco(), ok)

    def test_sync_cartelle_di_servizio(self):
        from romkit import sync
        with tempfile.TemporaryDirectory() as t:
            lav = os.path.join(t, 'lav')
            cli.main(['demo', lav])
            cf = os.path.join(lav, 'config.toml')
            cli.main(['--config', cf, 'catalogo'])
            cfg = config.carica(cf)
            dati = json.load(open(os.path.join(cfg.dati, 'data.json')))
            os.makedirs(cfg.pack)
            json.dump({'P': {'cap': 1, 'ris': 0, 'ids': [f"{g['s']}/{g['f']}" for g in dati if g['s'] == 'nes']}},
                      open(os.path.join(cfg.pack, 'packs.json'), 'w'))
            sdp = os.path.join(t, 'sd')
            os.makedirs(sdp)
            p = sync.piano(cfg, sdp, 'P')                     # scheda vuota: il bios arriva
            self.assertIn(('bios/finto.bin', 64), p['aggiungi'])
            self.assertEqual(p['per_sistema']['bios']['aggiungi'], [1, 64])
            os.makedirs(os.path.join(sdp, 'bios'))
            open(os.path.join(sdp, 'bios', 'finto.bin'), 'wb').write(b'diverso e piu lungo')
            open(os.path.join(sdp, 'bios', 'mio.bin'), 'wb').write(b'x')
            p = sync.piano(cfg, sdp, 'P')                     # gia' presente (anche diverso): non si tocca, non si toglie
            self.assertFalse([x for x in p['aggiungi'] + p['aggiorna'] + p['togli'] if x[0].startswith('bios/')])

    def test_sorgenti_per_uuid(self):
        from romkit import sorgenti
        with tempfile.TemporaryDirectory() as t:
            lav = os.path.join(t, 'lav')
            cli.main(['demo', lav])
            cfg = config.carica(os.path.join(lav, 'config.toml'))
            sdp = os.path.join(t, 'media', 'EASYROMS')
            os.makedirs(sdp)
            def lsb(mount):
                return {'blockdevices': [
                    {'name': 'sdx', 'type': 'disk', 'children': [
                        {'name': 'sdx1', 'label': 'BOOT', 'uuid': 'AAAA-0001', 'fstype': 'vfat', 'size': 1, 'mountpoints': [None]},
                        {'name': 'sdx3', 'label': 'EASYROMS', 'uuid': 'BBBB-0002', 'fstype': 'exfat', 'size': 5, 'mountpoints': [mount]}]},
                    {'name': 'sdy', 'type': 'disk', 'children': [
                        {'name': 'sdy1', 'label': 'CHIAVETTA', 'uuid': 'CCCC-0003', 'fstype': 'vfat', 'size': 1, 'mountpoints': ['/mnt/chiavetta']}]}]}
            # scheda vuota ma con la firma BOOT+EASYROMS: riconosciuta anche se non montata
            s = sorgenti.schede(cfg, lsb(None))
            self.assertEqual([x['uuid'] for x in s], ['BBBB-0002'])
            self.assertEqual(s[0]['forza'], 'forte')
            self.assertIsNone(s[0]['percorso'])
            with self.assertRaises(ValueError):
                sorgenti.aggiungi(cfg, '../x', 'BBBB-0002')
            with self.assertRaises(ValueError):
                sorgenti.aggiungi(cfg, 'X', 'CCCC-0003')       # non e' una scheda della console
            sorgenti.schede = lambda c, dati=None: s
            sorgenti.aggiungi(cfg, 'SD prova', 'BBBB-0002')
            self.assertIsNone(sorgenti.risolte(cfg, lsb(None))['SD prova'])        # non collegata
            sorgenti.schede = lambda c, dati=None: [dict(s[0], percorso=sdp)]
            self.assertEqual(sorgenti.risolte(cfg)['SD prova'], sdp)               # cambia il mount, resta la stessa
            self.assertIn({'nome': 'SD prova', 'stato': 'collegata'}, sorgenti.elenco(cfg))
            with self.assertRaises(ValueError):
                sorgenti.aggiungi(cfg, 'Altra', 'BBBB-0002')    # gia' registrata
            sorgenti.rinomina(cfg, 'SD prova', 'SD 64 GB')
            self.assertEqual(sorgenti.salvate(cfg)['SD 64 GB']['uuid'], 'BBBB-0002')
            self.assertNotIn('SD prova', sorgenti.salvate(cfg))
            with self.assertRaises(ValueError):
                sorgenti.rinomina(cfg, 'SD 64 GB', '../x')
            sorgenti.rimuovi(cfg, 'SD 64 GB')
            self.assertNotIn('SD prova', sorgenti.salvate(cfg))


if __name__ == '__main__':
    unittest.main()


class Guidata(unittest.TestCase):
    def test_prima_configurazione(self):
        from romkit import guidata
        with tempfile.TemporaryDirectory() as t:
            lav = os.path.join(t, 'lav')
            cli.main(['demo', lav])
            os.remove(os.path.join(lav, 'config.toml'))
            arch = os.path.join(lav, 'EASYROMS')
            s = guidata.scansiona(arch)
            self.assertEqual((s['sistemi'], s['giochi'], s['valido']), (4, 10, True))
            self.assertFalse(guidata.scansiona(os.path.join(arch, 'bios'))['valido'])
            cf = os.path.join(t, 'config.toml')
            with self.assertRaises(ValueError):
                guidata.salva(cf, {'archivio': arch, 'dati': arch, 'pack': os.path.join(t, 'p')})
            guidata.salva(cf, {'archivio': arch, 'dati': os.path.join(t, 'd'), 'pack': os.path.join(t, 'p'), 'porta': 8800, 'gioca': True})
            c = config.carica(cf)
            self.assertEqual((c.archivio, c['server']['host'], c['server']['porta'], c['gioca']['abilitato']),
                             (arch, '127.0.0.1', 8800, True))
            # rifacendo la procedura le impostazioni a mano restano e si crea la copia .bak
            open(cf, 'a').write('\n[catalogo.sottocartelle]\n"pico-8" = "carts"\n')
            guidata.salva(cf, {'archivio': arch, 'dati': os.path.join(t, 'd'), 'pack': os.path.join(t, 'p'), 'rete': True})
            c = config.carica(cf)
            self.assertEqual(c['catalogo']['sottocartelle'], {'pico-8': 'carts'})
            self.assertEqual(c['server']['host'], '0.0.0.0')
            self.assertTrue(os.path.exists(cf + '.bak'))
            guidata.costruisci(cf)
            import time
            for _ in range(100):
                if guidata.LAVORO['stato'] != 'in corso':
                    break
                time.sleep(0.1)
            self.assertEqual((guidata.LAVORO['stato'], guidata.LAVORO['giochi']), ('finito', 10))


class SbiCache(unittest.TestCase):
    def prepara_demo(self, t):
        lav = os.path.join(t, 'lav')
        cli.main(['demo', lav])
        cfg = config.carica(os.path.join(lav, 'config.toml'))
        psx = os.path.join(cfg.archivio, 'psx')
        os.makedirs(psx, exist_ok=True)
        for f in ('Gioco (Europe) (Disc 1).chd', 'Gioco (Europe) (Disc 1).sbi', 'Gioco (Europe) (Disc 2).chd',
                  'Gioco (Europe) (Disc 2).sbi', 'Gioco (Europe).m3u', 'Altro (Europe).chd', 'Altro (Europe).sbi'):
            open(os.path.join(psx, f), 'w').write('Gioco (Europe) (Disc 1).chd\nGioco (Europe) (Disc 2).chd\n' if f.endswith('.m3u') else 'x')
        os.makedirs(cfg.pack, exist_ok=True)
        json.dump({'P': {'cap': 1, 'ris': 0, 'ids': ['psx/Gioco (Europe).m3u', 'psx/Altro (Europe).chd', 'nes/Super Demo Bros (Italy).zip']}},
                  open(os.path.join(cfg.pack, 'packs.json'), 'w'))
        return cfg

    def test_sbi_inclusi(self):
        with tempfile.TemporaryDirectory() as t:
            cfg = self.prepara_demo(t)
            r = packs.prepara(cfg, 'P', 'P1')
            lista = open(os.path.join(r['dest'], 'lista-copia.txt')).read().split('\n')
            for f in ('Gioco (Europe) (Disc 1).sbi', 'Gioco (Europe) (Disc 2).sbi', 'Altro (Europe).sbi'):
                self.assertIn('psx/' + f, lista)

    def test_cache_per_sistema_identica(self):
        with tempfile.TemporaryDirectory() as t:
            cfg = self.prepara_demo(t)
            def leggi(r):
                d = r['dest']
                return (open(os.path.join(d, 'lista-copia.txt')).read(), open(os.path.join(d, 'report.txt')).read().split('\n', 1)[1],
                        sorted((os.path.relpath(os.path.join(a, f), d), open(os.path.join(a, f), 'rb').read()) for a, _, ff in os.walk(os.path.join(d, 'gamelist')) for f in ff))
            pieno = leggi(packs.prepara(cfg, 'P', 'A'))
            primo = packs.prepara(cfg, 'P', 'B', cache=True)
            self.assertTrue(primo['ricalcolati'])
            self.assertEqual(leggi(primo), pieno)
            # un solo sistema cambia: gli altri vengono dalla cache e il risultato resta identico al calcolo completo
            ids = json.load(open(os.path.join(cfg.pack, 'packs.json')))
            ids['P']['ids'].append('psx/Gioco (Europe) (Disc 1).chd')
            json.dump(ids, open(os.path.join(cfg.pack, 'packs.json'), 'w'))
            pieno2 = leggi(packs.prepara(cfg, 'P', 'C'))
            nuovo = packs.prepara(cfg, 'P', 'B', cache=True)
            self.assertEqual(leggi(nuovo), pieno2)
            ancora = packs.prepara(cfg, 'P', 'D', cache=True)
            self.assertEqual(ancora['ricalcolati'], [])

    def test_dischi_nascosti_con_m3u_completo(self):
        import xml.etree.ElementTree as ET
        with tempfile.TemporaryDirectory() as t:
            cfg = self.prepara_demo(t)
            psx = os.path.join(cfg.archivio, 'psx')
            open(os.path.join(psx, 'Rotto (Europe).m3u'), 'w').write('Rotto (Europe) (Disc 1).chd\nRotto (Europe) (Disc 2).chd\n')
            open(os.path.join(psx, 'Rotto (Europe) (Disc 1).chd'), 'w').write('x')       # il disco 2 non esiste
            def voce(p, extra=''):
                return f'<game><path>./{p}</path><name>{p}</name>{extra}</game>'
            open(os.path.join(psx, 'gamelist.xml'), 'w').write(
                '<gameList>' + voce('Gioco (Europe).m3u', '<genre>RPG</genre>')
                + voce('Gioco (Europe) (Disc 1).chd', '<desc>Trama</desc><image>./images/g1.png</image><genre>Altro</genre>')
                + voce('Gioco (Europe) (Disc 2).chd') + voce('Altro (Europe).chd')
                + voce('Rotto (Europe).m3u') + voce('Rotto (Europe) (Disc 1).chd') + '</gameList>')
            os.makedirs(os.path.join(psx, 'images'), exist_ok=True)
            open(os.path.join(psx, 'images', 'g1.png'), 'w').write('png')
            json.dump({'P': {'cap': 1, 'ris': 0, 'ids': [f'psx/{x}' for x in (
                'Gioco (Europe).m3u', 'Gioco (Europe) (Disc 1).chd', 'Gioco (Europe) (Disc 2).chd', 'Altro (Europe).chd',
                'Rotto (Europe).m3u', 'Rotto (Europe) (Disc 1).chd')]}}, open(os.path.join(cfg.pack, 'packs.json'), 'w'))
            r = packs.prepara(cfg, 'P', 'P1')
            voci = {g.findtext('path'): g for g in ET.parse(os.path.join(r['dest'], 'gamelist', 'psx', 'gamelist.xml')).getroot().findall('game')}
            nasc = lambda p: voci['./' + p].findtext('hidden')
            self.assertIsNone(nasc('Gioco (Europe).m3u'))
            self.assertEqual(nasc('Gioco (Europe) (Disc 1).chd'), 'true')
            self.assertEqual(nasc('Gioco (Europe) (Disc 2).chd'), 'true')
            self.assertIsNone(nasc('Altro (Europe).chd'))
            m = voci['./Gioco (Europe).m3u']                       # prende info e immagine dal disco, ma tiene il proprio genere
            self.assertEqual((m.findtext('desc'), m.findtext('image'), m.findtext('genre')), ('Trama', './images/g1.png', 'RPG'))
            self.assertIsNone(nasc('Rotto (Europe).m3u'))
            self.assertIsNone(nasc('Rotto (Europe) (Disc 1).chd'))   # .m3u incompleto: niente nascosto
            self.assertTrue(any(a.startswith('M3U INCOMPLETO') and 'Rotto' in a for a in r['anomalie']))


class Scraper(unittest.TestCase):
    def test_cerca_e_applica_con_risposte_finte(self):
        import zipfile, xml.etree.ElementTree as ET
        from romkit import scraper
        with tempfile.TemporaryDirectory() as t:
            lav = os.path.join(t, 'lav')
            cli.main(['demo', lav])
            cfg = config.carica(os.path.join(lav, 'config.toml'))
            nes = os.path.join(cfg.archivio, 'nes')
            for f in ('Gioco Nuovo.zip', 'Ignoto.zip', 'Terzo.zip'):
                with zipfile.ZipFile(os.path.join(nes, f), 'w') as z:
                    z.writestr('rom.nes', f.encode())
            gl = os.path.join(nes, 'gamelist.xml')
            prima = open(gl).read() if os.path.exists(gl) else None
            chiamate = []
            def finto(url):
                chiamate.append(url)
                if url.startswith('http://img/'):
                    return 200, b'PNG'
                if 'Gioco+Nuovo' in url:
                    j = {'response': {'jeu': {'noms': [{'region': 'wor', 'text': 'Gioco Nuovo'}],
                         'synopsis': [{'langue': 'en', 'text': 'Eng'}, {'langue': 'it', 'text': 'Trama'}],
                         'genres': [{'noms': [{'langue': 'it', 'text': 'Azione'}]}], 'dates': [{'region': 'wor', 'text': '1994-03-02'}],
                         'note': {'text': '15'}, 'developpeur': {'text': 'Dev'},
                         'medias': [{'type': 'box-2D', 'url': 'http://img/box', 'format': 'png'}]}}}
                    return 200, json.dumps(j).encode()
                if 'Terzo' in url:
                    return 430, b'quota'
                return 404, b'Erreur : Jeu non trouvee'
            with self.assertRaises(SystemExit):
                scraper.cerca(cfg, 'nes', http=finto, pausa=0)           # senza credenziali
            cfg['scraper'].update(devid='d', devpassword='p')
            with self.assertRaises(SystemExit) as e:
                scraper.cerca(cfg, 'nes', http=lambda u: (403, b'Erreur de login'), pausa=0)
            self.assertIn('devid', str(e.exception))
            cerc, trov, resto = scraper.cerca(cfg, 'nes', http=finto, pausa=0, avanza=lambda *a: None)
            self.assertIn('crc=', chiamate[0])
            self.assertEqual((trov, resto > 0), (1, True))                 # il terzo ha fermato la ricerca per quota
            n = len(chiamate)
            scraper.cerca(cfg, 'nes', http=finto, pausa=0, avanza=lambda *a: None)
            self.assertLess(len(chiamate) - n, n)                          # i gia' cercati non si richiedono
            self.assertEqual(open(gl).read() if os.path.exists(gl) else None, prima)   # la ricerca non scrive nell'archivio
            w = scraper.applica(cfg, 'nes', http=finto)
            self.assertEqual((w['scritte'], w['media']), (1, 1))
            voce = [g for g in ET.parse(gl).getroot().findall('game') if g.findtext('path') == './Gioco Nuovo.zip'][0]
            self.assertEqual((voce.findtext('desc'), voce.findtext('genre'), voce.findtext('releasedate'), voce.findtext('rating')),
                             ('Trama', 'Azione', '19940302T000000', '0.75'))
            self.assertTrue(os.path.exists(os.path.join(nes, voce.findtext('image'))))


class NovitaSuDisco(unittest.TestCase):
    def test_changelog_delle_versioni_piu_recenti(self):
        from romkit import versione
        with tempfile.TemporaryDirectory() as t:
            os.makedirs(os.path.join(t, 'romkit'))
            open(os.path.join(t, 'romkit', 'versione.py'), 'w').write("NUMERO = '9.9.9'\n")
            open(os.path.join(t, 'CHANGELOG.md'), 'w').write('# x\n\n## 9.9.9 — d\n- nuovo\n\n## 0.0.1 — d\n- vecchio\n')
            vecchia, versione.RADICE = versione.RADICE, t
            try:
                d, n = versione.novita_su_disco()
            finally:
                versione.RADICE = vecchia
            self.assertEqual(d, '9.9.9')
            self.assertIn('- nuovo', n)
            self.assertNotIn('vecchio', n)
