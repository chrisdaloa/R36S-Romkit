# romkit (nome di lavoro)

Catalogo web e gestione di «pack» per le schede SD di console portatili con ArkOS/EmulationStation (R36S e simili).

*English version: [README.en.md](README.en.md)*

Il programma lavora sul **tuo** archivio di ROM (una cartella per sistema, con `gamelist.xml` e immagini).
Non include ROM, né le scarica.

## Cosa fa
- **Catalogo**: pagina web con ricerca, filtri (sistema, lingua, genere, anno, voto, giocatori), vista a griglia o lista, dettaglio.
- **Pack**: scegli dal catalogo i giochi per una SD (es. 128 GB); il programma calcola lo spazio e crea gamelist ridotti, elenco di copia e report.
- **Copia**: `rsync` verso la SD (dry-run di default).
- **Gioca** (opzionale, spento): prova i giochi nel browser con EmulatorJS, solo in rete fidata.

## Avvio rapido (senza ROM, con archivio di prova)
```
pip install -e .
romkit demo prova
romkit --config prova/config.toml catalogo
romkit --config prova/config.toml serve      # http://127.0.0.1:8765/index.html
```

## Con il tuo archivio
1. `cp config.example.toml config.toml` e imposta `[archivio].percorso`.
2. `romkit catalogo` per generare i dati.
3. `romkit serve` e apri il catalogo; crea un pack e seleziona i giochi.
4. `romkit pack prepara "Nome pack" CARTELLA` e controlla `report.txt`.
5. `romkit pack copia CARTELLA` (prova) poi `romkit pack copia CARTELLA --applica`.

## Sicurezza
Il server ascolta di default solo su `127.0.0.1` e non ha autenticazione. Non esporlo su Internet.
«Gioca» serve le ROM: tienilo spento salvo che in rete domestica.

## Requisiti
Python ≥ 3.11, Pillow, `rsync` (per la copia). Per ora Linux/macOS.

Licenza MIT.
