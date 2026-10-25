# NameReforge

Rinomina molti file in una volta sola, con anteprima in tempo reale e possibilità di annullare.
Alternativa moderna e multipiattaforma ad Ant Renamer. Funziona su Linux, Windows e macOS.

Scritto in Python con PySide6 (Qt6, stile Fusion). I tag audio sono letti con `mutagen`, i metadati delle foto con Pillow.

## Avvio da sorgente

Serve Python 3.12 o più recente.

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"        # su Windows: .venv\Scripts\pip
.venv/bin/python -m nameforge
```

## Come si usa

1. **Files**: trascina file o cartelle nella finestra, oppure usa «Aggiungi file…» e «Aggiungi cartella…».
2. **Actions**: scegli un'azione e imposta i parametri. La colonna «Nuovo nome» si aggiorna da sola.
   I nomi che cambieranno sono in evidenza; le righe in rosso sono in conflitto (nome duplicato, già esistente o non valido) e bloccano la rinomina.
3. **Batch** (facoltativo): con «Aggiungi al batch» impili più azioni, eseguite a cascata nell'ordine mostrato. Si riordinano trascinandole e si possono salvare come profilo JSON.
4. **Reforge** (Ctrl+Invio) applica le nuove denominazioni sul disco. Fino a quel momento non viene scritto nulla.
5. **Log** elenca ogni operazione e gli errori. **Ctrl+Z** annulla l'ultima rinomina, anche dopo aver chiuso il programma.

### Azioni

Sostituisci stringa · Cambia estensione · Maiuscole/minuscole · Enumerazione · Inserisci, sposta e cancella caratteri ·
Nome casuale · Espressione regolare · Data e ora · Tag audio · Metadati EXIF · Nomi da file (.txt o .csv).

Tag audio e EXIF usano un modello di testo, ad esempio `{artist} - {title}` o `{date:%Y-%m-%d_%H%M%S}`.
Campi audio: artist, title, album, albumartist, genre, track, disc, year (MP3, FLAC, OGG, Opus, M4A).
Campi EXIF: date, make, model, width, height.

### Sicurezza

- Niente viene mai sovrascritto: se il nome di destinazione esiste già, quel file non viene toccato e l'errore va nel Log.
- Scambi (a↔b), catene e cambi di sole maiuscole sono gestiti con nomi temporanei.
- Prima di scrivere sul disco viene salvato un manifest, in modo che l'annullamento funzioni anche dopo un arresto improvviso.
- L'annullamento guarda lo stato reale del disco: i file spostati o cancellati nel frattempo sono saltati e segnalati.

I dati dell'applicazione (profili, manifest, impostazioni) stanno nella cartella dati dell'utente del sistema operativo, sotto `NameReforge`.

## Sviluppo

```bash
.venv/bin/pytest -q            # i test della GUI girano senza schermo: QT_QPA_PLATFORM=offscreen
.venv/bin/ruff check .
QT_QPA_PLATFORM=offscreen .venv/bin/python tools/bench_files.py   # prestazioni con 50.000 file
```

Il motore di ridenominazione (`src/nameforge/core/`) non dipende da Qt.

## Pacchetti

```bash
pip install -e ".[build]"
cd packaging && pyinstaller nameforge.spec --noconfirm --distpath ../dist --workpath ../build
dist/NameReforge/NameReforge --selftest      # controlla che il pacchetto sia completo
```

Su Windows l'installer si crea con Inno Setup (`packaging/installer.iss`); su macOS il `.dmg` con `hdiutil`.
La pipeline `.github/workflows/release.yml` fa tutto su ogni tag `v*`.
