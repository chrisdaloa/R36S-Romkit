# Cronologia delle versioni

Il numero di versione sta in `romkit/versione.py` (`NUMERO`). Si vede nella pagina, accanto al nome, e con `romkit --version`.

## 0.4.0 — 2026-11-04
- Cestino della scheda: dalla scheda collegata si vedono le sincronizzazioni con i giochi tolti (`_rimossi`), con numero di file, dimensione e sistemi.
- «Rimetti a posto» rimette i file dove stavano, senza sovrascrivere quelli già presenti sulla scheda; «Cancella definitivamente» libera lo spazio (con doppia conferma).
- Funziona solo su schede montate su questo PC e solo dal PC che ospita il catalogo.

## 0.3.1 — 2026-11-04
- Versione di prova per verificare l'aggiornamento dall'app (nessuna modifica funzionale).

## 0.3.0 — 2026-11-04
- Eseguibile autonomo per Linux e Windows (macOS in preparazione): si scarica, si decomprime e si avvia con un doppio clic.
- Aggiornamento dall'app: la versione in alto mostra le novità e, dal PC che ospita il catalogo, scarica, verifica e installa la release.
- Il nome del programma nella pagina è «R36S-Romkit».
- Windows: la sincronizzazione con la scheda non è ancora disponibile (serve `rsync`).

## 0.2.0 — 2026-11-04
- Configurazione guidata al primo avvio, con la scelta «Provo con una demo».
- Interfaccia in italiano e inglese.
- Nuova interfaccia: barra superiore, filtri laterali, pannello Pack a cassetto, vista griglia/elenco.
- Schede della console riconosciute per UUID, con stato collegata/non collegata e spazio libero.
- Sincronizzazione SD/pack: anteprima, applicazione con cestino `_rimossi`, conferma oltre il 20%, registro.
- Avanzamento della sincronizzazione su una riga, anche per cartelle di servizio e scrittura di lista e report.
- Cache dell'anteprima di sincronizzazione (esito della preparazione e dimensioni dei file).
- Opzione `[server].pack_da_rete` per salvare i pack da altri PC della rete locale.
- Gioca: altri sistemi nel browser, schermo intero, preset grafici.
- Supporto di base per Windows (non provato).
- La scheda SD collegata è selezionata di default; indicatore di versione e avviso «da riavviare».

## 0.1.0 — 2026-11-01
- Primo rilascio: catalogo web, pack, server e CLI.
