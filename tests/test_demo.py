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


if __name__ == '__main__':
    unittest.main()
