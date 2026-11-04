// Doppia lingua (italiano / inglese). Il testo italiano e' la chiave: T('testo') lo restituisce cosi' com'e'
// in italiano e lo traduce con EN in inglese. {nome} nei testi viene sostituito dai valori passati.
(function(){
 const EN={
  // intestazione e filtri
  'Catalogo giochi':'Game catalogue','catalogo giochi':'game catalogue','Cerca un titolo':'Search a title','Cerca':'Search',
  'Filtri':'Filters','Ordina per':'Sort by','Ordine':'Order','Titolo':'Title','Anno (recenti)':'Year (newest)','Valutazione':'Rating',
  'Dimensione':'Size','Sistema':'System','Vista':'View','Griglia':'Grid','Elenco':'List','Pack':'Pack','Impostazioni':'Settings',
  'Cambia archivio, cartelle, accesso e Gioca':'Change collection, folders, access and Play',
  'Disponibile solo dal PC che ospita il catalogo':'Only available from the PC that hosts the catalogue',
  'Le impostazioni si cambiano solo dal PC che ospita il catalogo (indirizzo localhost).':'Settings can only be changed from the PC that hosts the catalogue (localhost address).',
  'Lingua dell\'interfaccia':'Interface language',
  'Da questo dispositivo i pack sono in sola consultazione: le modifiche restano in questo browser.':'On this device packs are read-only: changes stay in this browser.',
  'Pack non salvati sul NAS: il NAS non è raggiungibile. Le modifiche restano in questo browser.':'Packs not saved on the NAS: the NAS is unreachable. Changes stay in this browser.',
  'Azzera':'Reset','Genere':'Genre','Tutti i generi':'All genres','Lingua':'Language','Tutte le lingue':'All languages',
  'Giocatori':'Players','Voto minimo':'Minimum rating','Valutazione minima':'Minimum rating','Anno':'Year','Da':'From','A':'To','Anno da':'Year from','Anno a':'Year to',
  'Solo senza immagine':'Only without image','Nel pack':'In pack','Filtro pack':'Pack filter','Tutti':'All','Fuori':'Not in pack',
  'Tutti i sistemi':'All systems','{n} giochi':'{n} games','Lingua non indicata ({n})':'Language not given ({n})',
  'Nessun gioco corrisponde ai filtri. Prova ad azzerarli dal pannello a sinistra.':'No game matches the filters. Try resetting them from the left panel.',
  'Mostra altri':'Show more',
  // lingue dei giochi
  'Inglese':'English','Francese':'French','Tedesco':'German','Spagnolo':'Spanish','Italiano':'Italian','Olandese':'Dutch','Portoghese':'Portuguese',
  'Svedese':'Swedish','Norvegese':'Norwegian','Danese':'Danish','Finlandese':'Finnish','Giapponese':'Japanese','Cinese':'Chinese','Coreano':'Korean',
  'Russo':'Russian','Polacco':'Polish','Catalano':'Catalan','Ceco':'Czech','Greco':'Greek','Turco':'Turkish','Ungherese':'Hungarian',
  // dettaglio gioco
  'Voto':'Rating','Lingue':'Languages','Sviluppatore':'Developer','Editore':'Publisher','File':'File','Gioca':'Play',
  'Nel pack · togli':'In pack · remove','Aggiungi al pack':'Add to pack','Nel pack: {t}':'In pack: {t}','Chiudi':'Close',
  // pannello pack
  'Pack e schede':'Packs and cards','Chiudi il pannello':'Close the panel','Pack attivo':'Active pack','Nessun pack':'No pack',
  'Nome nuovo pack (es. SD 64 GB)':'New pack name (e.g. SD 64 GB)','Nome nuovo pack':'New pack name','Crea pack':'Create pack',
  'Spazio utile (GB)':'Usable space (GB)','Riserva (GB)':'Reserve (GB)',
  'Aggiungi i risultati':'Add the results','Togli i risultati':'Remove the results','Riepilogo':'Summary','Esporta elenco':'Export list',
  'Scegli prima un pack':'Choose a pack first','{n} giochi su {cap} GB':'{n} games on {cap} GB',
  'Sforato di {x} (con riserva di {r} GB).':'Over by {x} (with a {r} GB reserve).','Margine di {x}, con riserva di {r} GB.':'{x} to spare, with a {r} GB reserve.',
  'Elimina pack':'Delete pack','Conferma: elimina «{n}»':'Confirm: delete «{n}»',
  'Pack «{p}»: riepilogo per sistema':'Pack «{p}»: summary by system','Scelti':'Chosen','Su':'Of','Peso scelto':'Chosen size','Peso totale':'Total size',
  // schede
  'Scheda SD o console':'SD card or console','SD o console':'SD or console','Controlla rispetto al pack':'Check against the pack','Sincronizza con il pack':'Sync with the pack',
  'Calcola cosa aggiungere e cosa togliere per allineare la scheda al pack. Non scrive nulla.':'Works out what to add and what to remove to align the card with the pack. Writes nothing.',
  'Allinea la scheda al pack scelto. Prima vedi cosa cambierebbe, poi decidi.':'Aligns the card with the chosen pack. First you see what would change, then you decide.',
  'Come funziona':'How it works','Aggiungi scheda':'Add card','Registra una scheda della console collegata':'Register a connected console card',
  'Rinomina':'Rename','Cambia il nome della sorgente scelta (solo quelle aggiunte da qui)':'Change the name of the chosen source (only those added here)',
  'Rimuovi':'Remove','Toglie la sorgente dall\'elenco, non tocca la scheda':'Removes the source from the list, does not touch the card',
  'Volume rilevato':'Detected volume','Nome (es. SD 64 GB)':'Name (e.g. SD 64 GB)','Nome della scheda':'Card name','Salva scheda':'Save card',
  ' — collegata':' — connected',' — non collegata':' — not connected',
  'Nuovo nome per «{n}»':'New name for «{n}»','Non rinominata: {e}':'Not renamed: {e}','Non salvata: {e}':'Not saved: {e}',
  'Nessuna scheda nuova rilevata. Serve una scheda della console collegata e montata (partizioni BOOT e EASYROMS), oppure una partizione con le cartelle dei sistemi.':'No new card detected. You need a console card connected and mounted (BOOT and EASYROMS partitions), or a partition with the system folders.',
  'senza nome':'unnamed',' · non montata':' · not mounted',' · scheda della console':' · console card',' · da verificare':' · to be checked',
  'Rimuovere la sorgente «{n}» dall\'elenco? Non tocca la SD.':'Remove the source «{n}» from the list? The SD is not touched.',
  // controllo SD
  'Controllo di «{s}» rispetto al pack «{p}»…':'Checking «{s}» against the pack «{p}»…','SD non raggiungibile: {e}':'SD not reachable: {e}',
  '«{s}» rispetto al pack «{p}»':'«{s}» against the pack «{p}»','Spazio reale della SD: {u} usati, {l} liberi. ':'Actual SD space: {u} used, {l} free. ',
  '{sd} giochi sulla SD, {at} nel pack: {ma} da aggiungere, {ex} in più, {di} diversi.':'{sd} games on the SD, {at} in the pack: {ma} to add, {ex} extra, {di} different.',
  'SD':'SD','Mancano':'Missing','In più':'Extra','Diversi':'Different','Dettaglio (primi {n})':'Details (first {n})',
  // sincronizzazione
  'Sincronizzazione di «{s}» con «{p}»':'Syncing «{s}» with «{p}»','Calcolo in corso: confronto la scheda con il pack, può richiedere alcuni minuti.':'Working: comparing the card with the pack, this may take a few minutes.',
  'Non avviata: {e}':'Not started: {e}','Calcolo interrotto: {e}':'Calculation stopped: {e}','Non riuscito: {e}':'Failed: {e}',
  'Questa è solo un\'anteprima: sulla scheda non è stato modificato nulla. Variazione di spazio sulla scheda: {v}.':'This is only a preview: nothing on the card was changed. Change in card space: {v}.',
  'La scheda è già allineata al pack.':'The card is already aligned with the pack.',
  'Da aggiungere':'To add','Da aggiornare':'To update','Da togliere':'To remove',
  'Sono nel pack ma non sulla scheda':'In the pack but not on the card','Ci sono già, ma il file è diverso':'Already there, but the file is different',
  'Sono sulla scheda ma non nel pack: finiscono in «_rimossi», non vengono cancellati':'On the card but not in the pack: they go to «_rimossi», they are not deleted',
  'Aggiungi':'Add','Aggiorna':'Update','Togli':'Remove','Includi {s}':'Include {s}',' — primi {n}':' — first {n}',
  'Aggiungi e aggiorna ({n} file)':'Add and update ({n} files)',
  'Togli ({n} file): vengono spostati in «_rimossi» sulla scheda, non cancellati':'Remove ({n} files): moved to «_rimossi» on the card, not deleted',
  'Applica le modifiche':'Apply the changes','Conferma: copio i file scelti':'Confirm: copy the chosen files','Conferma: sposto i file in _rimossi':'Confirm: move the files to _rimossi',
  'Conferma: copio i file scelti e sposto i file in _rimossi':'Confirm: copy the chosen files and move the files to _rimossi','Avvio…':'Starting…',
  'Le rimozioni superano il 20% della scheda. Premi ancora per confermare.':'Removals exceed 20% of the card. Press again to confirm.',
  'Confermo: tolgo più del 20%':'I confirm: remove more than 20%','Collegamento perso: {e}':'Connection lost: {e}',
  'Interrotta: {e} Rifai l\'anteprima prima di riprovare.':'Stopped: {e} Redo the preview before trying again.',
  'Fatto: {a} file copiati, {t} spostati{c}. Rifai la sincronizzazione per verificare che la scheda sia allineata.':'Done: {a} files copied, {t} moved{c}. Run the sync again to check that the card is aligned.',
  ' in «{c}» sulla scheda':' to «{c}» on the card',
  'Sposto in «_rimossi» i file da togliere: {f} di {n}':'Moving the files to remove into «_rimossi»: {f} of {n}',
  'Copio sulla scheda: {p}%':'Copying to the card: {p}%',' · restano {r}':' · {r} left','Aggiorno i gamelist della scheda':'Updating the card\'s gamelists','Avvio':'Starting',
  ' (passo {k} di {n})':' (step {k} of {n})','Preparo il pack':'Preparing the pack','Preparo il pack: sistema «{s}» ({f} di {n})':'Preparing the pack: system «{s}» ({f} of {n})',
  'Leggo i file della scheda: {n} trovati':'Reading the card\'s files: {n} found','Confronto la scheda con il pack: {f} di {n} file':'Comparing the card with the pack: {f} of {n} files',
  'Avvio il calcolo':'Starting the calculation',': sistema «{s}» ({f} di {n})':': system «{s}» ({f} of {n})',
  // guida
  'Come sincronizzare una scheda':'How to sync a card','Cosa non succede mai':'What never happens',
  'Scegli il pack':'Choose the pack','In alto nel pannello scegli il pack che la scheda deve rispecchiare, oppure creane uno dal catalogo.':'At the top of the panel choose the pack the card must mirror, or create one from the catalogue.',
  'Scegli la scheda':'Choose the card','Seleziona la SD o la console. La scheda deve essere inserita in questo PC.':'Select the SD or the console. The card must be inserted in this PC.',
  'Guarda cosa cambierebbe':'See what would change','«Sincronizza con il pack» confronta scheda e pack e mostra quanti giochi verrebbero aggiunti, aggiornati o tolti. In questa fase non viene scritto nulla.':'«Sync with the pack» compares card and pack and shows how many games would be added, updated or removed. Nothing is written at this stage.',
  'Scegli e applica':'Choose and apply','Puoi escludere interi sistemi, oppure solo le aggiunte o solo le rimozioni. «Applica le modifiche» chiede una seconda conferma prima di scrivere.':'You can exclude whole systems, or only the additions or only the removals. «Apply the changes» asks for a second confirmation before writing.',
  'Controlla':'Check','Durante la copia vedi avanzamento, velocità e tempo residuo. A fine lavoro rifai la sincronizzazione: deve dire che la scheda è allineata.':'During the copy you see progress, speed and time left. Afterwards run the sync again: it should say the card is aligned.',
  'Niente viene cancellato: i giochi tolti vengono spostati in «_rimossi/data» sulla scheda e puoi rimetterli al loro posto.':'Nothing is deleted: removed games are moved to «_rimossi/date» on the card and you can put them back.',
  'Salvataggi, impostazioni, i Ports e i file di servizio non vengono toccati.':'Saves, settings, Ports and service files are never touched.',
  'Se le rimozioni superano il 20% della scheda ti viene chiesta una conferma in più.':'If removals exceed 20% of the card you are asked for an extra confirmation.',
  'Le modifiche si fanno solo dal PC su cui gira il programma; dalla rete si può solo consultare.':'Changes can only be made from the PC running the program; from the network you can only browse.',
  // errori del server
  'Archivio, catalogo e pack devono essere cartelle diverse':'Collection, catalogue and packs must be different folders',
  'Calcolo non riuscito':'Calculation failed','Cartella dei pack non raggiungibile':'Packs folder not reachable','Cartella non leggibile':'Folder not readable',
  'Cartella non trovata':'Folder not found','Costruzione non riuscita':'Build failed','Indica le cartelle per il catalogo e per i pack':'Give the folders for the catalogue and the packs',
  'La cartella dell\'archivio non contiene sistemi con giochi':'The collection folder contains no systems with games',
  'La sincronizzazione scrive solo su schede montate su questo PC':'Syncing only writes to cards mounted on this PC',
  'Le rimozioni superano il 20% della scheda: serve la conferma esplicita':'Removals exceed 20% of the card: explicit confirmation needed',
  'Nome gia\' in uso':'Name already in use','Nome non valido (lettere, numeri, spazi, max 40)':'Invalid name (letters, digits, spaces, max 40)',
  'Pack sconosciuto':'Unknown pack','Piano non disponibile: rifai l\'anteprima':'Plan not available: redo the preview',
  'Porta non valida (1024-65535)':'Invalid port (1024-65535)','Richiesta non valida':'Invalid request','Scheda gia\' registrata':'Card already registered',
  'Scheda non collegata':'Card not connected','Scheda non collegata o sconosciuta':'Card not connected or unknown','Scheda non tra quelle rilevate':'Card not among those detected',
  'SD non raggiungibile':'SD not reachable','Sincronizzazione non riuscita':'Sync failed','Sorgente non modificabile da qui':'Source cannot be changed from here',
  'Sorgente non rimovibile da qui':'Source cannot be removed from here','Sorgente sconosciuta':'Unknown source',
  'Un\'altra operazione su questa scheda e\' in corso':'Another operation on this card is in progress',
  // procedura guidata
  'Configurazione guidata':'Guided setup','configurazione guidata':'guided setup','impostazioni':'settings',
  'Non hai ancora un archivio? Puoi provare il programma con giochi finti.':'No collection yet? You can try the program with fake games.','Provo con una demo':'Try a demo','Creo l\'archivio di prova…':'Creating the sample collection…',
  'Dove sono i tuoi giochi?':'Where are your games?','Scegli la cartella dell\'archivio: quella che contiene una sottocartella per ogni sistema (nes, snes, psx…).':'Choose the collection folder: the one holding a subfolder for each system (nes, snes, psx…).',
  'Cartella dell\'archivio':'Collection folder','Sfoglia':'Browse','Controllo la cartella…':'Checking the folder…',
  'Trovati {s} sistemi e {g} file di gioco; {c} sistemi hanno già descrizioni e immagini (gamelist.xml).':'Found {s} systems and {g} game files; {c} systems already have descriptions and images (gamelist.xml).',
  'Dove manca il gamelist.xml il catalogo mostra i titoli ricavati dal nome del file, senza immagini.':'Where gamelist.xml is missing the catalogue shows titles taken from the file name, without images.',
  'In questa cartella non ci sono sistemi con giochi. Scegli quella che contiene le cartelle nes, snes, psx…':'This folder has no systems with games. Choose the one holding the nes, snes, psx… folders.',
  'Avanti':'Next','Indietro':'Back','Dove salvare il lavoro?':'Where to save the work?',
  'L\'archivio non viene mai modificato. Il programma scrive i suoi file in due cartelle a parte.':'The collection is never modified. The program writes its files in two separate folders.',
  'Catalogo (dati, descrizioni, miniature)':'Catalogue (data, descriptions, thumbnails)','Si può rigenerare in qualsiasi momento. Servono poche centinaia di MB.':'It can be rebuilt at any time. A few hundred MB are needed.',
  'Pack (elenchi delle schede, gamelist ridotti, report)':'Packs (card lists, reduced gamelists, reports)','Meglio vicino all\'archivio: contiene le scelte per ogni scheda SD.':'Best next to the collection: it holds the choices for each SD card.',
  'Indica entrambe le cartelle.':'Give both folders.','Le due cartelle devono essere diverse.':'The two folders must be different.','Non usare la cartella dell\'archivio.':'Do not use the collection folder.',
  'Vuoi collegare delle schede SD?':'Connect some SD cards?','Se una scheda è inserita ora, la riconosco e la ricorderò per nome: poi potrai confrontarla con i pack. Si può fare anche più tardi dal catalogo.':'If a card is inserted now, I recognise it and remember it by name, so you can compare it with the packs. You can also do this later from the catalogue.',
  'Cerco le schede…':'Looking for cards…','Collega':'Connect','Senza nome':'Unnamed','Nessuna scheda riconosciuta. Va bene: puoi collegarla più tardi dal catalogo.':'No card recognised. That is fine: you can connect it later from the catalogue.',
  'Chi può aprire il catalogo?':'Who can open the catalogue?','Il catalogo è una pagina web servita da questo computer.':'The catalogue is a web page served by this computer.',
  'Solo questo computer (consigliato)':'Only this computer (recommended)','Indirizzo http://localhost:{p}. Nessun altro può vederlo.':'Address http://localhost:{p}. Nobody else can see it.',
  'Anche gli altri dispositivi di casa':'Other devices at home too','Da telefono o da un altro PC si può solo consultare. Copiare sulle schede e cambiare le impostazioni resta possibile solo da questo computer. Non ha password: usalo solo in una rete fidata.':'From a phone or another PC you can only browse. Copying to cards and changing settings stays possible only from this computer. It has no password: use it only on a trusted network.',
  'Porta':'Port','Giocare dal browser?':'Play in the browser?','Il pulsante «Gioca» apre un gioco direttamente nella pagina, con un emulatore integrato (per i sistemi classici a 8 e 16 bit e per i portatili).':'The «Play» button opens a game right in the page, with a built-in emulator (for classic 8 and 16-bit systems and handhelds).',
  'No, per ora':'Not for now','Puoi attivarlo in seguito rifacendo questa procedura.':'You can turn it on later by redoing this setup.','Sì, attiva «Gioca»':'Yes, turn on «Play»',
  'Il server rende scaricabili i file delle ROM di quei sistemi.':'The server makes the ROM files of those systems downloadable.',
  'Hai scelto anche l\'accesso dalla rete: chiunque sia collegato alla tua rete potrà scaricare quelle ROM. Meglio attivarlo solo se la rete è fidata.':'You also chose network access: anyone on your network will be able to download those ROMs. Better to turn it on only if the network is trusted.',
  'Tutto pronto':'All set','Controlla i dati. Poi costruisco il catalogo: con un archivio grande può richiedere qualche minuto.':'Check the details. Then I build the catalogue: with a large collection it can take a few minutes.',
  'Archivio':'Collection','Catalogo':'Catalogue','Schede':'Cards','nessuna':'none','Accesso':'Access','attivo':'on','spento':'off',
  'dalla rete di casa (sola consultazione)':'from the home network (browse only)','solo questo computer':'only this computer','{a}, porta {p}':'{a}, port {p}',
  'Salva e costruisci il catalogo':'Save and build the catalogue','Salvo la configurazione…':'Saving the configuration…',
  'Costruzione del catalogo':'Building the catalogue','({f} di {n} cartelle)':'({f} of {n} folders)','{n} secondi trascorsi':'{n} seconds elapsed',
  'Catalogo pronto: {g} giochi, {i} con immagine.':'Catalogue ready: {g} games, {i} with image.','Apri il catalogo':'Open the catalogue','Avvio del catalogo…':'Starting the catalogue…','Riprova':'Try again',
  'Scegli una cartella':'Choose a folder','Annulla':'Cancel','Usa questa cartella':'Use this folder','‹ Cartella superiore':'‹ Parent folder','Nessuna sottocartella.':'No subfolders.',
  'Avanzamento':'Progress','← Catalogo':'← Catalogue','Schermo intero':'Full screen','Grafica':'Graphics','Nitido':'Sharp','Morbido':'Smooth','CRT leggero':'Light CRT','CRT classico':'Classic CRT','Tasto F':'F key','Comandi: frecce, Z/X = B/A, Invio = Start, Maiusc = Select':'Controls: arrows, Z/X = B/A, Enter = Start, Shift = Select','Errore {c}':'Error {c}',
 };
 // messaggi del server con valori dentro: [espressione, sostituzione]
 const RX=[
  [/^Spazio insufficiente: servono ([\d.]+) GB, disponibili ([\d.]+) GB$/,'Not enough space: $1 GB needed, $2 GB available'],
  [/^SSH fallito verso (.+)$/,'SSH failed towards $1'],
  [/^Copia interrotta: (.*)$/,'Copy interrupted: $1'],
  [/^Gamelist non aggiornati: (.*)$/,'Gamelists not updated: $1'],
  [/^Non posso scrivere in (.+)$/,'Cannot write in $1'],
 ];
 let lang='it';
 try{lang=localStorage.getItem('lingua')||''}catch(e){}
 if(lang!=='it'&&lang!=='en')lang=(navigator.language||'it').toLowerCase().startsWith('it')?'it':'en';
 window.LANG=lang;window.LOC=lang==='en'?'en':'it';
 window.T=function(s,v){
  let r=s;
  if(lang==='en'){
   if(EN[s]!==undefined)r=EN[s];
   else for(const [x,y] of RX)if(x.test(s)){r=s.replace(x,y);break}
  }
  return v?r.replace(/\{(\w+)\}/g,(m,k)=>v[k]!==undefined?v[k]:m):r;
 };
 // traduce il testo e gli attributi gia' presenti nella pagina
 window.tradDOM=function(root){
  document.documentElement.lang=lang;
  if(lang!=='en')return;
  const w=document.createTreeWalker(root,NodeFilter.SHOW_TEXT),nodi=[];
  while(w.nextNode())nodi.push(w.currentNode);
  nodi.forEach(n=>{if(n.parentElement&&n.parentElement.closest('[translate=no]'))return;const s=n.nodeValue.trim();if(s&&EN[s]!==undefined)n.nodeValue=n.nodeValue.replace(s,EN[s])});
  root.querySelectorAll('[placeholder],[aria-label],[title]').forEach(e=>['placeholder','aria-label','title'].forEach(a=>{
   const s=e.getAttribute(a);if(s&&EN[s]!==undefined)e.setAttribute(a,EN[s])}));
  document.title=T(document.title);
 };
 // selettore della lingua: ricorda la scelta e ricarica la pagina
 window.selettoreLingua=function(sel){
  sel.value=lang;
  sel.onchange=()=>{try{localStorage.setItem('lingua',sel.value)}catch(e){}location.reload()};
 };
})();
