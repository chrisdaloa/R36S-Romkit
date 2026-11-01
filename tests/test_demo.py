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

    def test_sorgenti_salvate(self):
        from romkit import sorgenti
        with tempfile.TemporaryDirectory() as t:
            lav = os.path.join(t, 'lav')
            cli.main(['demo', lav])
            cfg = config.carica(os.path.join(lav, 'config.toml'))
            with self.assertRaises(ValueError):
                sorgenti.aggiungi(cfg, 'X', '/etc')          # non e' un volume rilevato
            sorgenti.volumi = lambda c: [os.path.join(t, 'sd')]
            sorgenti._scrivi(cfg, {'A': '/x'})
            self.assertEqual(sorgenti.tutte(cfg)['A'], '/x')
            sorgenti.aggiungi(cfg, 'B', os.path.join(t, 'sd'))
            self.assertIn('B', sorgenti.salvate(cfg))
            sorgenti.rimuovi(cfg, 'B')
            self.assertNotIn('B', sorgenti.salvate(cfg))
            with self.assertRaises(ValueError):
                sorgenti.aggiungi(cfg, '../x', os.path.join(t, 'sd'))


if __name__ == '__main__':
    unittest.main()
