# romkit (working name)

Web catalogue and «pack» management for SD cards of ArkOS/EmulationStation handhelds (R36S and similar).

It works on **your own** ROM collection (one folder per system, with `gamelist.xml` and images). It ships and downloads no ROMs.

## Features
- **Catalogue**: search, filters (system, language, genre, year, rating, players), grid or list view, details.
- **Packs**: pick games for an SD card (e.g. 128 GB); size is computed and reduced gamelists, a copy list and a report are produced.
- **Copy**: `rsync` to the card (dry-run by default).
- **Play** (optional, off by default): in-browser play with EmulatorJS, trusted LAN only.

## Quick start (no ROMs, fake collection)
```
pip install -e .
romkit demo demo-work
romkit --config demo-work/config.toml catalogo
romkit --config demo-work/config.toml serve      # http://127.0.0.1:8765/index.html
```

## With your collection
1. `cp config.example.toml config.toml`, set `[archivio].percorso`.
2. `romkit catalogo`, then `romkit serve`.
3. Create a pack in the web page, then `romkit pack prepara "Pack name" FOLDER` and read `report.txt`.
4. `romkit pack copia FOLDER` (dry-run), then add `--applica`.

## Security
The server listens on `127.0.0.1` only by default and has no authentication. Never expose it to the Internet. «Play» serves ROMs: keep it off outside a trusted home network.

Requires Python ≥ 3.11, Pillow, `rsync`. Linux/macOS for now. MIT licence.
