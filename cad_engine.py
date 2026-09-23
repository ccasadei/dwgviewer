import os
import shutil
import subprocess
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import ezdxf
from ezdxf import bbox
from ezdxf.colors import aci2rgb
from ezdxf.document import Drawing


@dataclass
class TavolaInfo:
    """Represents an architectural drawing sheet (Tavola) bounding box."""
    name: str
    title: str
    bbox: Tuple[float, float, float, float]
    description: str = ""


@dataclass
class LayerInfo:
    """Represents CAD layer metadata and statistics."""
    name: str
    color: str  # Hex RGB string, e.g. "#ffffff"
    color_aci: int = 7
    count: int = 0
    is_off: bool = False
    is_frozen: bool = False
    is_locked: bool = False

    @property
    def entity_count(self) -> int:
        return self.count


@dataclass
class CadModel:
    """Container for parsed CAD drawing, bounding box extents, sheets and layers."""
    file_path: str
    dxf_doc: Drawing
    extents: Tuple[float, float, float, float]
    tavole: Dict[str, TavolaInfo] = field(default_factory=dict)
    layers: List[LayerInfo] = field(default_factory=list)

    def get_tavola(self, name: str) -> Optional[TavolaInfo]:
        return self.tavole.get(name)


def find_dwg2dxf() -> str | None:
    """Locate LibreDWG dwg2dxf executable in PATH or known conda environment locations."""
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


def convert_dwg_to_dxf(dwg_path: str, cache_dir: str = ".cache") -> str:
    """Convert DWG file to DXF using dwg2dxf, storing result in cache_dir.
    Reuses cached DXF if it exists and is newer than the source DWG.
    """
    if not os.path.exists(dwg_path):
        raise FileNotFoundError(f"DWG file not found: {dwg_path}")

    os.makedirs(cache_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(dwg_path))[0]
    cached_dxf = os.path.join(cache_dir, f"{base_name}.dxf")

    dwg_mtime = os.path.getmtime(dwg_path)
    if os.path.exists(cached_dxf) and os.path.getsize(cached_dxf) > 0:
        dxf_mtime = os.path.getmtime(cached_dxf)
        if dxf_mtime >= dwg_mtime:
            return cached_dxf

    converter = find_dwg2dxf()
    if not converter:
        raise RuntimeError("dwg2dxf executable not found in PATH or conda environments")

    cmd = [converter, "-y", "-o", cached_dxf, dwg_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"dwg2dxf conversion failed (code {result.returncode}): {result.stderr}")

    if not os.path.exists(cached_dxf):
        raise FileNotFoundError(f"Converted DXF file not found at {cached_dxf}")

    return cached_dxf


def _aci_to_hex(aci: int) -> str:
    """Convert AutoCAD Color Index (ACI) to a hex string."""
    code = abs(aci)
    if 1 <= code <= 255:
        try:
            rgb = aci2rgb(code)
            return f"#{rgb.r:02x}{rgb.g:02x}{rgb.b:02x}"
        except Exception:
            return "#ffffff"
    return "#ffffff"


def load_cad_file(file_path: str, cache_dir: str = ".cache") -> CadModel:
    """Load DWG or DXF CAD file, parsing model extents, architectural tavole, and layers."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in (".dwg", ".dxf"):
        raise ValueError(f"Unsupported file format: '{ext}'. Expected .dwg or .dxf")

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    if ext == ".dwg":
        dxf_path = convert_dwg_to_dxf(file_path, cache_dir=cache_dir)
    else:
        dxf_path = file_path

    dxf_doc = ezdxf.readfile(dxf_path)
    msp = dxf_doc.modelspace()

    # Compute bounding box extents from ModelSpace entities
    box = bbox.extents(msp)
    if box.has_data:
        extents = (
            float(box.extmin[0]),
            float(box.extmin[1]),
            float(box.extmax[0]),
            float(box.extmax[1]),
        )
    else:
        extents = (0.0, 0.0, 0.0, 0.0)

    # Globale view: full extents with 2% margin
    min_x, min_y, max_x, max_y = extents
    dx = max_x - min_x
    dy = max_y - min_y
    margin_x = 0.02 * dx
    margin_y = 0.02 * dy
    globale_bbox = (
        min_x - margin_x,
        min_y - margin_y,
        max_x + margin_x,
        max_y + margin_y,
    )

    tavole: dict[str, TavolaInfo] = {}

    # Standard Tavole definitions with exact sheet frame perimeters
    tavole_specs = [
        ("Tavola 1", "Tavola 1 - Prospetti, Sezioni e Copertura", (3678.5, 1724.0, 3910.5, 1755.0)),
        ("Tavola 2", "Tavola 2 - Planimetria 1:2000 e Stato di Fatto", (3678.5, 1673.5, 3928.0, 1717.0)),
        ("Tavola 3", "Tavola 3 - Variante, Demolizioni e Costruzioni", (3678.5, 1624.0, 3928.0, 1667.2)),
        ("Tavola 4", "Tavola 4 - Inserimento Servoscala e Abbattimento Barriere", (3677.0, 1535.8, 3759.0, 1579.2)),
    ]

    is_tavole_doc = "tavole" in os.path.basename(file_path).lower() or (
        min_x <= 3700.0 and max_x >= 3900.0 and min_y <= 1600.0 and max_y >= 1700.0
    )

    if is_tavole_doc:
        for name, title, sheet_bbox in tavole_specs:
            tavole[name] = TavolaInfo(name=name, title=title, bbox=sheet_bbox)

    tavole["Globale"] = TavolaInfo(
        name="Globale",
        title="Vista Globale - Intero Disegno",
        bbox=globale_bbox,
    )

    # Count entities per layer in modelspace defensively
    entity_counts = Counter(getattr(e.dxf, "layer", "0") for e in msp)

    layers: list[LayerInfo] = []
    seen_layers = set()

    for layer in dxf_doc.layers:
        name = layer.dxf.name
        seen_layers.add(name)
        color_aci = abs(layer.dxf.color) if layer.dxf.hasattr("color") else 7
        hex_color = _aci_to_hex(color_aci)
        is_off = layer.is_off()
        is_frozen = layer.is_frozen()
        is_locked = layer.is_locked()
        count = entity_counts.get(name, 0)

        layers.append(
            LayerInfo(
                name=name,
                color=hex_color,
                color_aci=color_aci,
                count=count,
                is_off=is_off,
                is_frozen=is_frozen,
                is_locked=is_locked,
            )
        )

    # Handle layers present in entities but missing from layer table
    for layer_name, count in entity_counts.items():
        if layer_name not in seen_layers:
            layers.append(
                LayerInfo(
                    name=layer_name,
                    color="#ffffff",
                    color_aci=7,
                    count=count,
                    is_off=False,
                    is_frozen=False,
                    is_locked=False,
                )
            )

    return CadModel(
        file_path=file_path,
        dxf_doc=dxf_doc,
        extents=extents,
        tavole=tavole,
        layers=layers,
    )
