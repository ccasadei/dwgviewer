# CAD DWG Viewer & Multi-Page PDF Exporter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a modern, high-performance web-based CAD viewer in Python (using NiceGUI, ezdxf, LibreDWG, and uv) to visualize `./Tavole.dwg` with smooth pan/zoom, layer management, interactive custom area selection, and multi-page/single-sheet vector PDF printing.

**Architecture:** 
1. `cad_engine.py`: DWG-to-DXF converter using LibreDWG with local caching; DXF entity parser that extracts layers and computes exact bounding boxes for Tavola 1, 2, 3, 4, and the full drawing.
2. `renderer.py`: Vector SVG generator using `ezdxf.addons.drawing` with embedded layer classes (`data-layer="..."`) for instant client-side toggling and crisp 60fps pan/zoom.
3. `pdf_exporter.py`: High-fidelity vector PDF generation engine with automatic paper sizing (A3/A4) and multi-page collation via `pypdf`.
4. `main.py` & `ui_components.py`: Modern NiceGUI single-page application with dark CAD theme, Panzoom integration, Tavole chips, floating HUD, layer drawer, and PDF export dialogs.

**Tech Stack:** Python 3.10+, uv, NiceGUI, ezdxf, matplotlib, pypdf, reportlab, GNU LibreDWG (`dwg2dxf`), pytest

**Spec:** `docs/superpowers/specs/2026-09-22-cad-dwg-viewer-design.md`

## Global Constraints
- Must use `uv` for dependency and environment management (`pyproject.toml`).
- Must handle binary AutoCAD DWG (`AC1015` format of `./Tavole.dwg`) via `dwg2dxf` bridge.
- All PDF output must be pure vector geometry (no raster downscaling).
- UI must be modern, responsive, and provide smooth 60fps pan/zoom.
- The 4 detected Tavole must be:
  - Tavola 1: Y `[1700, 1760]`, X `[3670, 3930]` (Prospetti, Sezioni, Copertura)
  - Tavola 2: Y `[1660, 1715]`, X `[3670, 3930]` (Planimetria 1:2000, Stato di fatto)
  - Tavola 3: Y `[1610, 1665]`, X `[3670, 3930]` (Variante, Demolizioni e Costruzioni)
  - Tavola 4: Y `[1530, 1600]`, X `[3670, 3930]` (Inserimento servoscala, Abbattimento barriere)
- All code must include thorough unit tests executed via `uv run pytest`.

---

### Task 1: Project Scaffolding and `uv` Environment Setup

**Files:**
- Create: `pyproject.toml`
- Test: `tests/test_environment.py`

**Interfaces:**
- Consumes: System Python & installed LibreDWG binary
- Produces: Working uv virtual environment with all pinned dependencies

- [ ] **Step 1: Write the failing environment test**

Create `tests/test_environment.py`:
```python
import shutil

def test_dependencies_importable():
    import ezdxf
    import nicegui
    import matplotlib
    import pypdf
    assert ezdxf is not None
    assert nicegui is not None
    assert matplotlib is not None
    assert pypdf is not None

def test_dwg2dxf_available():
    from cad_engine import find_dwg2dxf
    path = find_dwg2dxf()
    assert path is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_environment.py -v`  
Expected: FAIL (pyproject or cad_engine not yet created)

- [ ] **Step 3: Create `pyproject.toml` and minimal `cad_engine.py` stub**

Write `pyproject.toml`:
```toml
[project]
name = "dwgviewer"
version = "0.1.0"
description = "Modern Web DWG/CAD Viewer & Multi-Page PDF Exporter"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "nicegui>=3.0.0",
    "ezdxf>=1.4.0",
    "matplotlib>=3.10.0",
    "pypdf>=6.0.0",
    "reportlab>=4.0.0",
    "pillow>=10.0.0",
    "pytest>=8.0.0",
]

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"
```

Write stub in `cad_engine.py`:
```python
import os
import shutil

def find_dwg2dxf() -> str | None:
    path = shutil.which("dwg2dxf")
    if path:
        return path
    conda_paths = [
        "/opt/miniconda3/envs/cad_env/bin/dwg2dxf",
        os.path.expanduser("~/miniconda3/envs/cad_env/bin/dwg2dxf"),
    ]
    for p in conda_paths:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None
```

Run `uv sync` to install dependencies in `.venv`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_environment.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock cad_engine.py tests/test_environment.py
git commit -m "chore: setup uv project and dependency environment"
```

---

### Task 2: CAD Engine (DWG/DXF Loader, Tavole Detection, and Layer Stats)

**Files:**
- Create: `cad_engine.py`
- Test: `tests/test_cad_engine.py`

**Interfaces:**
- Consumes: `./Tavole.dwg` binary and `find_dwg2dxf()`
- Produces: `CadModel` dataclass with `extents`, `tavole: dict[str, TavolaInfo]`, `layers: list[LayerInfo]`, and `dxf_doc`

- [ ] **Step 1: Write the failing tests for CadEngine**

Create `tests/test_cad_engine.py`:
```python
import os
import pytest
from cad_engine import load_cad_file, CadModel

def test_load_tavole_dwg():
    dwg_path = "Tavole.dwg"
    assert os.path.exists(dwg_path), "Tavole.dwg must be present in root"
    
    model = load_cad_file(dwg_path)
    assert isinstance(model, CadModel)
    assert model.dxf_doc is not None
    
    # Check bounding box
    min_x, min_y, max_x, max_y = model.extents
    assert min_x < 3700 and max_x > 3900
    assert min_y < 1600 and max_y > 1700
    
    # Check 4 Tavole detection
    assert "Tavola 1" in model.tavole
    assert "Tavola 2" in model.tavole
    assert "Tavola 3" in model.tavole
    assert "Tavola 4" in model.tavole
    assert "Globale" in model.tavole
    
    t1 = model.tavole["Tavola 1"]
    assert 1700 <= t1.bbox[1] <= 1760
    assert 1700 <= t1.bbox[3] <= 1760
    
    # Check layers
    layer_names = [l.name for l in model.layers]
    assert "STATO DI FATTO" in layer_names
    assert "Muri" in layer_names
    assert "TESTI" in layer_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cad_engine.py -v`  
Expected: FAIL (`load_cad_file`, `CadModel` not implemented)

- [ ] **Step 3: Implement `cad_engine.py`**

Implement complete `cad_engine.py`:
- DWG to DXF conversion with `.cache/` directory storage. If the DXF is already cached and newer than the DWG, read the cached DXF directly.
- Read DXF via `ezdxf.readfile`.
- Compute global bounding box from ModelSpace entities.
- Identify the 4 Tavole bounding boxes:
  - Tavola 1: `(3670.0, 1715.0, 3935.0, 1760.0)`, title: "Tavola 1 - Prospetti, Sezioni e Copertura"
  - Tavola 2: `(3670.0, 1665.0, 3935.0, 1715.0)`, title: "Tavola 2 - Planimetria 1:2000 e Stato di Fatto"
  - Tavola 3: `(3670.0, 1605.0, 3935.0, 1665.0)`, title: "Tavola 3 - Variante, Demolizioni e Costruzioni"
  - Tavola 4: `(3670.0, 1530.0, 3935.0, 1605.0)`, title: "Tavola 4 - Inserimento Servoscala e Abbattimento Barriere"
  - Globale: full extents with 2% margin.
- Extract layer list with name, ACI color / hex color, and entity count.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cad_engine.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cad_engine.py tests/test_cad_engine.py
git commit -m "feat: implement cad_engine with dwg caching, tavole detection, and layer extraction"
```

---

### Task 3: Vector SVG Renderer with Client-Side Layer Tagging

**Files:**
- Create: `renderer.py`
- Test: `tests/test_renderer.py`

**Interfaces:**
- Consumes: `CadModel` from `cad_engine.py`
- Produces: `render_to_svg(cad_model: CadModel, dark_mode: bool = True) -> str`

- [ ] **Step 1: Write the failing tests for SvgRenderer**

Create `tests/test_renderer.py`:
```python
from cad_engine import load_cad_file
from renderer import render_to_svg

def test_render_to_svg():
    model = load_cad_file("Tavole.dwg")
    svg_content = render_to_svg(model, dark_mode=True)
    
    assert svg_content.startswith("<svg") or "<svg" in svg_content
    assert "</svg>" in svg_content
    assert "viewBox=" in svg_content
    # Verify layer classes exist in SVG for CSS toggling
    assert "cad-layer" in svg_content
    assert "layer-" in svg_content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_renderer.py -v`  
Expected: FAIL (`render_to_svg` not implemented)

- [ ] **Step 3: Implement `renderer.py`**

Implement `renderer.py`:
- Use `ezdxf.addons.drawing.Frontend` and `ezdxf.addons.drawing.svg.SVGBackend` (or custom SVG visitor) with layer tagging.
- Ensure layers are wrapped in `<g class="cad-layer layer-{clean_name}" data-layer="{layer_name}">`.
- Include SVG style definition for CAD colors and dark/light mode background (`#12151b` dark, `#ffffff` light).
- Cache generated SVG in `.cache/` for instant subsequent loads.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_renderer.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add renderer.py tests/test_renderer.py
git commit -m "feat: implement vector SVG renderer with layer tagging and theme support"
```

---

### Task 4: Vector PDF Exporter Engine (Single Sheet & Multi-Page Tavole)

**Files:**
- Create: `pdf_exporter.py`
- Test: `tests/test_pdf_exporter.py`

**Interfaces:**
- Consumes: `CadModel` from `cad_engine.py`
- Produces: 
  - `export_tavola_to_pdf(cad_model: CadModel, tavola_key: str, output_path: str) -> str`
  - `export_custom_bbox_to_pdf(cad_model: CadModel, bbox: tuple, output_path: str) -> str`
  - `export_all_tavole_multipage_pdf(cad_model: CadModel, output_path: str) -> str`

- [ ] **Step 1: Write the failing tests for PdfExporter**

Create `tests/test_pdf_exporter.py`:
```python
import os
import pypdf
from cad_engine import load_cad_file
from pdf_exporter import export_tavola_to_pdf, export_all_tavole_multipage_pdf

def test_export_single_tavola_pdf(tmp_path):
    model = load_cad_file("Tavole.dwg")
    out_file = str(tmp_path / "tavola1.pdf")
    
    export_tavola_to_pdf(model, "Tavola 1", out_file)
    assert os.path.exists(out_file)
    assert os.path.getsize(out_file) > 10000 # Non-trivial PDF
    
    reader = pypdf.PdfReader(out_file)
    assert len(reader.pages) == 1

def test_export_all_tavole_multipage_pdf(tmp_path):
    model = load_cad_file("Tavole.dwg")
    out_file = str(tmp_path / "all_tavole.pdf")
    
    export_all_tavole_multipage_pdf(model, out_file)
    assert os.path.exists(out_file)
    
    reader = pypdf.PdfReader(out_file)
    assert len(reader.pages) == 4 # Exactly 4 tavole!
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_pdf_exporter.py -v`  
Expected: FAIL (`export_tavola_to_pdf` not implemented)

- [ ] **Step 3: Implement `pdf_exporter.py`**

Implement `pdf_exporter.py`:
- Use `matplotlib` with `ezdxf.addons.drawing.matplotlib.MatplotlibBackend` and `Frontend` to render vector PDF within exact bounding boxes `(min_x, min_y, max_x, max_y)`.
- Set figure dimensions according to aspect ratio (e.g. A3 landscape: 420mm x 297mm; A4: 297mm x 210mm).
- Set clean white background (`#ffffff`), crisp black/colored lines for print fidelity.
- Use `pypdf.PdfMerger` to combine the 4 Tavole (Tavola 1, Tavola 2, Tavola 3, Tavola 4) into a single cohesive document with bookmark outlines.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_pdf_exporter.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pdf_exporter.py tests/test_pdf_exporter.py
git commit -m "feat: implement vector PDF export engine with multi-page collation"
```

---

### Task 5: Interactive Web UI Components & Panzoom Integration

**Files:**
- Create: `ui_components.py`
- Create: `static/panzoom.js` / canvas script helper
- Test: `tests/test_ui_components.py`

**Interfaces:**
- Consumes: `CadModel`, `render_to_svg`, `pdf_exporter`
- Produces: NiceGUI interactive web interface components

- [ ] **Step 1: Write unit tests for UI helper structures**

Create `tests/test_ui_components.py`:
```python
from ui_components import format_layer_data, get_tavole_options
from cad_engine import load_cad_file

def test_ui_helpers():
    model = load_cad_file("Tavole.dwg")
    layers_data = format_layer_data(model.layers)
    assert len(layers_data) > 0
    assert "name" in layers_data[0]
    assert "color" in layers_data[0]
    
    tavole_opts = get_tavole_options(model)
    assert "Tavola 1" in tavole_opts
    assert "Tavola 4" in tavole_opts
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ui_components.py -v`  
Expected: FAIL

- [ ] **Step 3: Implement `ui_components.py` and client-side scripts**

Implement `ui_components.py`:
- Header bar with file info, Tavole chips `[ Vista Globale ]` `[ Tavola 1 ]` `[ Tavola 2 ]` `[ Tavola 3 ]` `[ Tavola 4 ]`.
- Interactive SVG canvas embedding Panzoom (smooth mouse drag, wheel zoom, double-click fit).
- Layer drawer with checkboxes dynamically showing/hiding layers instantly via CSS classes (`.layer-{name} { display: none; }`).
- Interactive selection tool: allows dragging a marquee rectangle on canvas, converting screen coordinates back to CAD coordinates, and triggering custom area zoom or PDF export.
- Floating HUD (Zoom In, Zoom Out, Fit to Screen, Reset).
- PDF export dialog / direct download trigger via `ui.download`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ui_components.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ui_components.py tests/test_ui_components.py
git commit -m "feat: implement web UI components, panzoom canvas, and layer controls"
```

---

### Task 6: Application Assembly, End-to-End Testing & Run Script

**Files:**
- Create: `main.py`
- Create: `README.md`
- Test: `tests/test_app_e2e.py`

**Interfaces:**
- Consumes: All modules (`cad_engine`, `renderer`, `pdf_exporter`, `ui_components`)
- Produces: Complete running NiceGUI application launched with `uv run python main.py`

- [ ] **Step 1: Write End-to-End integration test**

Create `tests/test_app_e2e.py`:
```python
import pytest
from nicegui.testing import User
import main

@pytest.mark.asyncio
async def test_app_loads_and_displays_canvas(user: User):
    await user.open('/')
    # Verify header title
    await user.should_see('Tavole.dwg')
    # Verify Tavole chips are visible
    await user.should_see('Tavola 1')
    await user.should_see('Tavola 4')
    # Verify export button is present
    await user.should_see('Stampa / PDF')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_app_e2e.py -v`  
Expected: FAIL (`main.py` not configured)

- [ ] **Step 3: Implement `main.py` and documentation**

Implement `main.py`:
- Entry point with argument parsing (`--file`, `--port`, `--reload`).
- Auto-loads `./Tavole.dwg` on startup.
- Full layout assembly with dark CAD theme by default.
- Create comprehensive `README.md` explaining how to run with `uv run python main.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_app_e2e.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add main.py README.md tests/test_app_e2e.py
git commit -m "feat: complete application assembly, documentation, and E2E verification"
```

---

### Task 7: Full Test Suite Verification & Quality Polish

**Files:**
- Modify/Polish any UI or performance details.
- Run complete test suite.

- [ ] **Step 1: Run complete test suite**

Run: `uv run pytest -v`  
Expected: ALL PASS

- [ ] **Step 2: Smoke test NiceGUI live execution**

Run background task: `uv run python main.py --port 8080`  
Verify HTTP 200 on `http://127.0.0.1:8080` with `curl -I http://127.0.0.1:8080`.

- [ ] **Step 3: Final Commit**

```bash
git add .
git commit -m "chore: final quality checks and test suite verification"
```
