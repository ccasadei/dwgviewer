# Specifica di Progetto: Modern Web DWG/CAD Viewer & Multi-Page PDF Exporter

**Data:** 2026-09-22  
**Stato:** In revisione  
**Tecnologie:** Python 3.10+, NiceGUI, ezdxf, LibreDWG (dwg2dxf), Panzoom (SVG), Matplotlib/PyPDF, uv  

---

## 1. Obiettivo del Progetto
Realizzare un'applicazione web moderna e reattiva in Python per la visualizzazione, navigazione e stampa vettoriale in PDF del file CAD binario `./Tavole.dwg` (e facoltativamente di altri file DWG/DXF).

### Requisiti Chiave
1. **Supporto DWG binario**: lettura diretta di `Tavole.dwg` (formato AutoCAD AC1015) tramite pipeline automatica con `dwg2dxf` (GNU LibreDWG) e caching DXF/SVG.
2. **Interfaccia Web Moderna (NiceGUI)**:
   - Canvas vettoriale SVG interattivo con pan fluido e zoom con rotellina (60 FPS).
   - Tema Dark CAD ad alto contrasto (con possibilità di switch su tema chiaro).
   - Selettore rapido delle 4 Tavole con zoom animato sulle coordinate della singola tavola.
   - Pannello a scomparsa per gestione/visibilità dei Layer con indicatori di colore e conteggio elementi.
   - Strumento di selezione libera a rettangolo per ingrandire o stampare porzioni personalizzate.
3. **Stampa ed Esportazione PDF**:
   - **Tutte le Tavole (PDF Multi-pagina)**: 4 pagine distinte e ordinate (Tavola 1, Tavola 2, Tavola 3, Tavola 4) in formato standard (A3/A4) con orientamento appropriato.
   - **Tavola Singola**: esportazione della sola tavola attiva.
   - **Disegno Completo**: esportazione panoramica dell'intero modelspace.
   - **Ritaglio Personalizzato**: esportazione dell'area selezionata interattivamente sul canvas.
4. **Gestione del Progetto**: ambiente virtuale e pacchetti gestiti interamente con `uv` (`pyproject.toml`).

---

## 2. Architettura del Sistema

```
┌────────────────────────────────────────────────────────┐
│                   Browser Client                       │
│  ┌─────────────────┐ ┌───────────────┐ ┌────────────┐  │
│  │ Panzoom Toolbar │ │ Quick Tavole  │ │ Layer Box  │  │
│  └────────┬────────┘ └───────┬───────┘ └──────┬─────┘  │
│           │                  │                │        │
│           ▼                  ▼                ▼        │
│          Interactive SVG Vector Canvas (DOM / CSS)     │
└───────────────────────────▲────────────────────────────┘
                            │ WebSocket / HTTP
┌───────────────────────────┴────────────────────────────┐
│              NiceGUI App Backend (Python)              │
│  ┌──────────────────────────────────────────────────┐  │
│  │ main.py & ui_components.py                       │  │
│  │ (Quasar/Tailwind UI, state, event handlers)      │  │
│  └────────┬─────────────────────────────────┬───────┘  │
│           │                                 │          │
│           ▼                                 ▼          │
│  ┌──────────────────┐             ┌─────────────────┐  │
│  │ cad_engine.py    │             │ pdf_exporter.py │  │
│  │ - dwg2dxf bridge │             │ - single Tavola │  │
│  │ - ezdxf parser   │             │ - multi-page PDF│  │
│  │ - tavole detector│             │ - custom bbox   │  │
│  │ - layer stats    │             │ - vector output │  │
│  └────────┬─────────┘             └─────────────────┘  │
│           ▼                                            │
│  ┌──────────────────┐                                  │
│  │ renderer.py      │                                  │
│  │ - ezdxf drawing  │                                  │
│  │ - SVG generator  │                                  │
│  │ - group tagging  │                                  │
│  └──────────────────┘                                  │
└────────────────────────────────────────────────────────┘
```

---

## 3. Componenti Dettagliati

### 3.1 `cad_engine.py`
* **Localizzazione Converter**: cerca l'eseguibile `dwg2dxf` nel PATH di sistema o nell'ambiente `cad_env` (`/opt/miniconda3/envs/cad_env/bin/dwg2dxf`).
* **Conversione & Cache**:
  * Se riceve `.dwg`, controlla se esiste una copia `.dxf` recente in `.cache/`. Se non esiste o il DWG è più recente, esegue `dwg2dxf`.
  * Legge il DXF tramite `ezdxf.readfile()`.
* **Riconoscimento Tavole**:
  * Rileva le 4 tavole architettoniche presenti nel disegno in base alle fasce di coordinate Y e ai cartigli:
    * **Tavola 1**: Y `[1700, 1760]`, X `[3670, 3930]` (Prospetti, Sezioni, Copertura)
    * **Tavola 2**: Y `[1660, 1715]`, X `[3670, 3930]` (Planimetria 1:2000, Stato di fatto)
    * **Tavola 3**: Y `[1610, 1665]`, X `[3670, 3930]` (Variante, Demolizioni/Costruzioni)
    * **Tavola 4**: Y `[1530, 1600]`, X `[3670, 3930]` (Inserimento servoscala, Abbattimento barriere)
    * **Globale**: Bounding box dell'intero disegno.
* **Estrazione Layer**:
  * Elenco di tutti i layer, colore RGB o indice ACI, stato visibile predefinito e conteggio entità.

### 3.2 `renderer.py`
* Genera la grafica SVG ottimizzata utilizzando `ezdxf.addons.drawing.Frontend` e `ezdxf.addons.drawing.svg.SVGBackend`.
* Inserisce identificatori di classe/id per ogni layer all'interno dell'albero SVG (`data-layer="NOME_LAYER"`).
* Applica stili per garantire contrasto ottimale:
  * In Dark Mode: sfondo scuro `#12151b`, linee chiare/colorate.
  * In Light Mode: sfondo bianco `#ffffff`, linee scure.

### 3.3 `pdf_exporter.py`
* Generazione di file PDF vettoriali per qualsiasi Bounding Box `(min_x, min_y, max_x, max_y)`.
* Supporto per:
  * **Singola Tavola**: calcolo proporzioni ottimali (A3 orizzontale / A4), margini di 10mm, rendering ad alta risoluzione vettoriale.
  * **Multi-pagina**: genera i PDF delle 4 tavole e li assembla in un unico file `Tavole_Architettoniche_Complete.pdf` tramite `pypdf`.
  * **Selezione Personalizzata**: prende le coordinate min/max selezionate dall'utente nel browser e stampa l'area ritagliata.

### 3.4 Interfaccia Web (`ui_components.py` & `main.py`)
* **Header / Toolbar**:
  * Logo CAD e nome file attivo.
  * Tasti selezione rapida: `[ Vista Globale ]`, `[ Tavola 1 ]`, `[ Tavola 2 ]`, `[ Tavola 3 ]`, `[ Tavola 4 ]`.
  * Menu Stampa / PDF: "Tutte le 4 Tavole (PDF Multi-pagina)", "Tavola Corrente (PDF)", "Vista Completa (PDF)", "Area Selezionata (PDF)".
  * Strumento Selezione: toggle per attivare la selezione rettangolare su canvas.
  * Tasto Layer Drawer (pannello laterale).
  * Toggle Tema Chiaro / Scuro.
* **Canvas Vettoriale Interattivo**:
  * Libreria Panzoom integrata via HTML5/JavaScript per consentire pan fluido con mouse/touch e zoom con rotella centrato sulle coordinate del mouse.
  * Mini-mappa / controlli rapidi flottanti (Zoom +, Zoom -, Fit, Reset).
* **Layer Drawer**:
  * Drawer laterale destro con elenco layer, switch on/off per ciascuno, opzioni "Tutti / Nessuno".

---

## 4. Gestione Errori e Casi Limite
1. **File DWG non valido o mancante**: messaggio descrittivo con form di upload drag-and-drop.
2. **Entità o font CAD non riconosciuti**: gestione graziosa con font universali sans-serif e skip di entità binarie non standard senza bloccare il rendering.
3. **Tempi di elaborazione**: il primo caricamento produce una barra di progresso / spinner animato, mentre i caricamenti successivi usano la cache istantanea.

---

## 5. Strategia di Test e Verifica
1. **Test del Backend (`test_cad_engine.py`)**:
   - Verifica della conversione DWG -> DXF.
   - Verifica del rilevamento delle 4 tavole e delle loro coordinate.
   - Verifica della generazione SVG e della presenza dei tag layer.
2. **Test dell'Esportazione PDF (`test_pdf_export.py`)**:
   - Generazione di una tavola singola in PDF (controllo validità file e dimensioni).
   - Generazione del PDF multi-pagina (controllo che contenga esattamente 4 pagine non vuote).
3. **Test End-to-End Interfaccia**:
   - Avvio dell'app su porta locale, verifica che risponda con codice 200 HTTP, che il canvas carichi l'SVG e che gli endpoint di download PDF funzionino correttamente.
