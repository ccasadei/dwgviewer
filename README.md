# CAD DWG Viewer 📐

**Visualizzatore Web CAD DWG/DXF ad alte prestazioni con navigazione interattiva e stampa PDF vettoriale multi-pagina.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![NiceGUI](https://img.shields.io/badge/NiceGUI-3.0%2B-emerald.svg)](https://nicegui.io/)
[![ezdxf](https://img.shields.io/badge/ezdxf-1.4%2B-orange.svg)](https://ezdxf.mozman.at/)
[![LibreDWG](https://img.shields.io/badge/LibreDWG-dwg2dxf-purple.svg)](https://www.gnu.org/software/libredwg/)
[![Vector PDF](https://img.shields.io/badge/PDF-Vector%20Export-red.svg)](https://pypdf.readthedocs.io/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 📖 Panoramica

**CAD DWG Viewer** è una moderna applicazione web per la visualizzazione e l'esportazione di elaborati tecnici architettonici e ingegneristici in formato AutoCAD DWG e DXF.

Sviluppata per offrire una navigazione fluida a 60 FPS senza richiedere software desktop proprietari pesanti, l'applicazione integra:
- Parsing e conversione automatica DWG via `LibreDWG` con cache incrementale.
- Rendering vettoriale puro in SVG con etichettatura dei layer CAD per una gestione istantanea della visibilità.
- Panoramica e zoom dinamici guidati da mouse e rotellina (Panzoom).
- Inquadratura immediata delle 4 tavole di progetto tramite chip dedicati.
- Selezione libera di aree rettangolari (marquee) con rimappatura precisa alle coordinate del modello CAD.
- Esportazione professionale in PDF vettoriale nativo (sia tavola singola, sia fascicolo completo multi-pagina in formato landscape, sia ritagli ad hoc).

---

## ✨ Funzionalità Principali

### 🔍 Viewport Vettoriale & Panzoom Interattivo
- **Pan & Zoom a 60 FPS**: trascina con il tasto sinistro per spostare il disegno, usa la rotellina per ingrandire esattamente sul punto puntato dal cursore.
- **Doppio Click & Tasti Rapidi**: doppio click o click sull'icona HUD per ripristinare e adattare l'intero disegno allo schermo (*Fit / Reset*).
- **HUD Flottante**: controlli touch-friendly semitrasparenti in basso a destra (Zoom In, Zoom Out, Adatta, Ripristina).

### 📑 Navigazione Rapida Tavole di Progetto
Pulsanti rapidi nell'header per passare istantaneamente tra le sezioni del progetto architettonico:
- **Vista Globale**: panoramica aerea dell'intero disegno CAD con margine di sicurezza.
- **Tavola 1**: Prospetti, Sezioni e Copertura.
- **Tavola 2**: Planimetria 1:2000 e Stato di Fatto.
- **Tavola 3**: Variante, Demolizioni e Costruzioni (gialli e rossi).
- **Tavola 4**: Inserimento Servoscala e Abbattimento Barriere Architettoniche.

### 🎨 Gestione Livelli CAD Istantanea (Zero-Latency)
- Drawer laterale scorrevole con l'elenco completo di tutti i layer CAD estratti.
- **Toggling Client-Side CSS**: attivazione e disattivazione istantanea senza ricaricamento del DOM né chiamate al server.
- **Filtro di Ricerca**: campo di ricerca in tempo reale per trovare velocemente i layer per nome.
- **Pillole di Colore & Statistiche**: indicatore visivo del colore originale AutoCAD (ACI) e badge con il conteggio delle entità grafiche per ciascun livello.
- **Pulsanti Globali**: *Mostra Tutti* e *Nascondi Tutti* in un solo click.


### 🖨️ Esportazione PDF Vettoriale Professionale
- **PDF 100% Vettoriale**: linee, testi e geometrie mantengono nitidezza perfetta a qualsiasi livello di ingrandimento.
- **Modalità di Esportazione**:
  1. *Fascicolo Completo*: genera un PDF multi-pagina con tutte le tavole ordinate consecutivamente (Tavola 1..4).
  2. *Tavola Corrente*: esporta la tavola attualmente inquadrata.
  3. *Vista Globale*: stampa l'intero foglio del modello.
  4. *Area Personalizzata*: ritaglia esattamente il rettangolo selezionato dall'utente.
- **Formati Carta Supportati**: A4, A3, A2, A1, A0 con orientamento automatico (Landscape / Portrait in base alle proporzioni dell'area).
- **Filtro Livelli in Stampa**: rispetta opzionalmente i layer visibili al momento della richiesta.

### 📁 Caricamento Dinamico & Tolleranza agli Errori
- Supporto per file sia **.dwg** che **.dxf**.
- Finestra di upload drag-and-drop per caricare e visualizzare altri file CAD al volo.
- Gestione trasparente degli errori: se il file specificato non esiste o è corrotto, l'applicazione mostra un banner informativo elegante e offre il caricamento diretto di un file sostitutivo.

---

## 🛠️ Requisiti di Sistema

- **Python**: Versione 3.10 o successiva (testato con Python 3.13).
- **uv** (consigliato per la gestione ultra-rapida di ambienti virtuali e dipendenze) oppure `pip`.
- **LibreDWG (`dwg2dxf`)**: necessario per la conversione automatica di file DWG binari proprietari in formato DXF testuale.
  - Verificare con: `which dwg2dxf`

---

## 🚀 Avvio Rapido con `uv`

### 1. Clonazione e configurazione
```bash
git clone <repository-url>
cd dwgviewer
```

### 2. Sincronizzazione dell'ambiente
Con `uv` installato sul sistema:
```bash
uv sync
```

### 3. Avvio dell'applicazione
Avvia il server web:
```bash
uv run python main.py
```

All'avvio, l'applicazione mostrerà automaticamente la finestra di dialogo per selezionare o caricare il file DWG o DXF desiderato.
L'interfaccia è accessibile nel browser all'indirizzo:  
👉 **`http://localhost:8080`** (o `http://127.0.0.1:8080`)

---

## ⚙️ Opzioni da Riga di Comando (CLI)

Il visualizzatore accetta parametri opzionali per specificare direttamente un file di avvio, porta di rete e modalità desktop:

```bash
uv run python main.py [OPZIONI]
```

| Parametro | Descrizione | Default |
| :--- | :--- | :--- |
| `--file FILE` | Percorso del file `.dwg` o `.dxf` da aprire all'avvio | `None` *(apre dialogo di selezione)* |
| `--port PORT` | Porta TCP di ascolto del server web | `8080` |
| `--host HOST` | Indirizzo host su cui effettuare il bind | `0.0.0.0` |
| `--reload` | Attiva il ricaricamento automatico al salvataggio (sviluppo) | `False` |
| `--native` | Avvia la finestra desktop nativa (richiede pywebview) | `False` |

### Esempi di Utilizzo

- **Aprire un file CAD specifico su una porta personalizzata**:
  ```bash
  uv run python main.py --file /percorso/mio_progetto.dwg --port 9000
  ```

- **Avvio in modalità sviluppo con ricaricamento automatico**:
  ```bash
  uv run python main.py --reload
  ```

---

## 🏗️ Architettura del Software

La base di codice è organizzata secondo principi di alta modularità e disaccoppiamento:

```
dwgviewer/
├── main.py               # Entry point dell'applicazione NiceGUI e parsing CLI
├── cad_engine.py         # Parsing DXF/DWG, calcolo estensioni, estrazione Tavole e layer
├── renderer.py           # Backend di rendering SVG vettoriale con etichette di layer
├── pdf_exporter.py       # Motore di generazione ed esportazione PDF vettoriale
├── ui_components.py      # Componenti UI (Header, Canvas, HUD, Drawer, Export Dialog)
├── static/               # Risorse statiche web
│   ├── panzoom.min.js    # Libreria Panzoom per navigazione fluida
│   └── cad_canvas.js     # Script client-side per coordinate, selezioni e CSS layer
├── tests/                # Suite completa di test automatizzati (E2E e unitari)
│   ├── conftest.py       # Configurazione fixture di test e plugin NiceGUI
│   ├── test_app_e2e.py   # Test di integrazione End-to-End
│   ├── test_cad_engine.py
│   ├── test_renderer.py
│   ├── test_pdf_exporter.py
│   └── test_ui_components.py
├── pyproject.toml        # Metadati del pacchetto e configurazione dipendenze
└── Tavole.dwg            # Disegno CAD architettonico dimostrativo
```

---

## 🧪 Esecuzione della Suite di Test

Tutti i moduli sono verificati da una suite completa di test automatizzati con `pytest`:

```bash
uv run pytest -v
```

Per eseguire solo i test end-to-end dell'interfaccia:
```bash
uv run pytest tests/test_app_e2e.py -v
```

---

## ☕ Sostieni il progetto

CAD DWG Viewer è gratuito e sviluppato nel tempo libero. Se ti è utile, puoi offrirmi qualcosa con PayPal:

- [☕ Un caffè — 3 €](https://paypal.me/ccasadei74/3EUR)
- [🍺 Una birra — 5 €](https://paypal.me/ccasadei74/5EUR)
- [🍕 Una pizza — 10 €](https://paypal.me/ccasadei74/10EUR)
- [💚 Importo libero](https://paypal.me/ccasadei74)

Gli importi sono solo suggerimenti: puoi sempre cambiarli prima di confermare. Grazie!

---

## 📄 Licenza

Rilasciato sotto licenza MIT. Per maggiori informazioni, consultare il file `LICENSE`.
