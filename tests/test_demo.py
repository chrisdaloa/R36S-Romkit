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
