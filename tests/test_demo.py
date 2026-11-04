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
