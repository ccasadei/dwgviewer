"""Interactive Web UI Components & Panzoom Integration for CAD DWG Viewer.

Provides NiceGUI-based CAD workspace with:
- High-performance vector canvas embedding Panzoom (smooth drag, wheel zoom, double-click fit)
- Quick Tavole navigation chips ([ Vista Globale ], [ Tavola 1 ] .. [ Tavola 4 ])
- Layer manager drawer with instantaneous client-side CSS layer toggling
- Marquee rectangular area selection tool with CAD coordinate transformation
- Floating HUD (Zoom In, Zoom Out, Fit Screen, Reset)
- Vector PDF export dialog with multi-page collation, single sheet, and custom selection
"""

import json
import os
import re
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

from nicegui import app, core, ui

from cad_engine import CadModel, LayerInfo, TavolaInfo
from pdf_exporter import (
    export_all_tavole_multipage_pdf,
    export_custom_bbox_to_pdf,
    export_tavola_to_pdf,
)
from renderer import sanitize_layer_name


def safe_run_javascript(code: str, **kwargs: Any) -> None:
    """Execute JavaScript safely, ignoring errors when no active client or event loop is available."""
    try:
        kwargs.setdefault("respond", False)
        if core.loop is not None:
            ui.run_javascript(code, **kwargs)
    except Exception:
        pass


def format_layer_data(layers: Sequence[LayerInfo]) -> List[Dict[str, Any]]:
    """Format CAD model layers into structured dictionary records for UI rendering.

    Args:
        layers: Sequence of LayerInfo objects from CadModel.

    Returns:
        List of dicts with name, clean_name, color, count, and visibility properties.
    """
    formatted = []
    for l in layers:
        formatted.append(
            {
                "name": l.name,
                "clean_name": sanitize_layer_name(l.name),
                "color": l.color,
                "color_aci": l.color_aci,
                "count": l.count,
                "entity_count": l.count,
                "visible": not l.is_off,
                "is_frozen": l.is_frozen,
                "is_locked": l.is_locked,
            }
        )
    return formatted


def get_tavole_options(model: CadModel) -> Dict[str, Dict[str, Any]]:
    """Extract ordered Tavole sheets and global view options with metadata for UI chips.

    Args:
        model: Loaded CadModel.

    Returns:
        Dict mapping sheet key to title, bounding box, and description.
    """
    options: Dict[str, Dict[str, Any]] = {}

    # 1. Global panoramic view
    if "Globale" in model.tavole:
        g = model.tavole["Globale"]
        options["Globale"] = {
            "name": "Globale",
            "title": g.title or "Vista Globale (Tutto il Disegno)",
            "bbox": g.bbox,
            "description": g.description or "Panoramica completa del modello CAD",
        }
    else:
        options["Globale"] = {
            "name": "Globale",
            "title": "Vista Globale",
            "bbox": model.extents,
            "description": "Panoramica completa del disegno",
        }

    # 2. Sequential architectural sheets (Tavola 1 to 4)
    standard_sheets = ["Tavola 1", "Tavola 2", "Tavola 3", "Tavola 4"]
    for sheet_key in standard_sheets:
        if sheet_key in model.tavole:
            t = model.tavole[sheet_key]
            options[sheet_key] = {
                "name": t.name,
                "title": t.title or sheet_key,
                "bbox": t.bbox,
                "description": t.description or "",
            }

    # 3. Any additional custom sheets
    for key, t in model.tavole.items():
        if key not in options:
            options[key] = {
                "name": t.name,
                "title": t.title or key,
                "bbox": t.bbox,
                "description": t.description or "",
            }

    return options


def cad_bbox_to_svg_rect(
    cad_bbox: Tuple[float, float, float, float],
    model_extents: Tuple[float, float, float, float],
    svg_bounds: Tuple[float, float, float, float],
) -> Dict[str, float]:
    """Map CAD coordinate bounding box to SVG viewBox rectangle.

    Args:
        cad_bbox: (min_x, min_y, max_x, max_y) in CAD space.
        model_extents: (ext_min_x, ext_min_y, ext_max_x, ext_max_y) of full drawing.
        svg_bounds: (svg_x0, svg_y0, svg_width, svg_height) of SVG viewBox.

    Returns:
        Dict with "x", "y", "width", "height" in SVG coordinate space.
    """
    min_x, min_y, max_x, max_y = cad_bbox
    ext_min_x, ext_min_y, ext_max_x, ext_max_y = model_extents
    svg_x0, svg_y0, svg_w, svg_h = svg_bounds

    cad_dx = max(ext_max_x - ext_min_x, 1e-6)
    cad_dy = max(ext_max_y - ext_min_y, 1e-6)

    scale_x = svg_w / cad_dx
    scale_y = svg_h / cad_dy

    left = svg_x0 + (min_x - ext_min_x) * scale_x
    right = svg_x0 + (max_x - ext_min_x) * scale_x
    # Invert Y: CAD max_y is SVG top (svg_y0)
    top = svg_y0 + (ext_max_y - max_y) * scale_y
    bottom = svg_y0 + (ext_max_y - min_y) * scale_y

    x = min(left, right)
    y = min(top, bottom)
    width = abs(right - left)
    height = abs(bottom - top)

    return {"x": x, "y": y, "width": width, "height": height}


def svg_rect_to_cad_bbox(
    svg_rect: Dict[str, float],
    model_extents: Tuple[float, float, float, float],
    svg_bounds: Tuple[float, float, float, float],
) -> Tuple[float, float, float, float]:
    """Map SVG viewBox rectangle back to CAD coordinate bounding box.

    Args:
        svg_rect: Dict with "x", "y", "width", "height" in SVG coordinate space.
        model_extents: (ext_min_x, ext_min_y, ext_max_x, ext_max_y) of full drawing.
        svg_bounds: (svg_x0, svg_y0, svg_width, svg_height) of SVG viewBox.

    Returns:
        (min_x, min_y, max_x, max_y) in CAD coordinate space.
    """
    ext_min_x, ext_min_y, ext_max_x, ext_max_y = model_extents
    svg_x0, svg_y0, svg_w, svg_h = svg_bounds

    cad_dx = max(ext_max_x - ext_min_x, 1e-6)
    cad_dy = max(ext_max_y - ext_min_y, 1e-6)

    scale_x = svg_w / cad_dx
    scale_y = svg_h / cad_dy

    sx = svg_rect["x"]
    sy = svg_rect["y"]
    sw = svg_rect["width"]
    sh = svg_rect["height"]

    cad_min_x = ext_min_x + (sx - svg_x0) / scale_x
    cad_max_x = ext_min_x + (sx + sw - svg_x0) / scale_x

    # SVG sy is top (higher CAD Y), sy + sh is bottom (lower CAD Y)
    cad_max_y = ext_max_y - (sy - svg_y0) / scale_y
    cad_min_y = ext_max_y - (sy + sh - svg_y0) / scale_y

    return (
        min(cad_min_x, cad_max_x),
        min(cad_min_y, cad_max_y),
        max(cad_min_x, cad_max_x),
        max(cad_min_y, cad_max_y),
    )


def extract_svg_viewbox(svg_content: str) -> Tuple[float, float, float, float]:
    """Extract viewBox (x, y, w, h) from an SVG document string."""
    m = re.search(r'viewBox=["\']([-\d. ]+)["\']', svg_content)
    if m:
        parts = [float(p) for p in m.group(1).split()]
        if len(parts) == 4:
            return (parts[0], parts[1], parts[2], parts[3])
    return (0.0, 0.0, 1000000.0, 478805.0)


def generate_layer_toggle_css(hidden_layer_names: Sequence[str]) -> str:
    """Generate dynamic CSS rule to hide inactive CAD layers instantly.

    Args:
        hidden_layer_names: Collection of layer names to hide.

    Returns:
        CSS rule string (or empty string if none are hidden).
    """
    if not hidden_layer_names:
        return ""
    classes = [f".layer-{sanitize_layer_name(name)}" for name in hidden_layer_names]
    selector = ", ".join(classes)
    return f"{selector} {{ display: none !important; }}"


class CadViewerState:
    """Central state management container for the interactive CAD web application."""

    def __init__(self, model: CadModel, dark_mode: bool = True) -> None:
        self.model = model
        self.active_tavola: str = "Globale"
        self.dark_mode: bool = dark_mode
        self.visible_layers: Set[str] = {l.name for l in model.layers if not l.is_off}
        self.selection_active: bool = False
        self.selected_bbox: Optional[Tuple[float, float, float, float]] = None
        self.paper_size: str = "A3"
        self._listeners: List[Callable[[], None]] = []
        self._bulk_updating: bool = False
        self.export_dialog: Optional[ui.dialog] = None

    def set_active_tavola(self, name: str) -> None:
        """Update active sheet selection."""
        if name in self.model.tavole or name == "Globale":
            self.active_tavola = name
            self._notify()

    def toggle_layer(self, layer_name: str, visible: bool) -> None:
        """Toggle visibility for a single CAD layer."""
        if visible:
            self.visible_layers.add(layer_name)
        else:
            self.visible_layers.discard(layer_name)
        self._notify()

    def hide_all_layers(self) -> None:
        """Hide all CAD layers."""
        self.visible_layers.clear()
        self._notify()

    def show_all_layers(self) -> None:
        """Make all CAD layers visible."""
        self.visible_layers = {l.name for l in self.model.layers}
        self._notify()

    def toggle_dark_mode(self) -> bool:
        """Toggle between Dark CAD theme and Light theme."""
        self.dark_mode = not self.dark_mode
        self._notify()
        return self.dark_mode

    def set_selected_bbox(self, bbox: Optional[Tuple[float, float, float, float]]) -> None:
        """Set or clear the user-selected marquee bounding box."""
        self.selected_bbox = bbox
        self._notify()

    def get_hidden_layers(self) -> List[str]:
        """Return list of currently hidden layer names."""
        all_layers = {l.name for l in self.model.layers}
        return list(all_layers - self.visible_layers)

    def add_listener(self, callback: Callable[[], None]) -> None:
        """Register state change notification callback."""
        self._listeners.append(callback)

    def _notify(self) -> None:
        for cb in self._listeners:
            try:
                cb()
            except Exception:
                pass

    def export_pdf(
        self,
        mode: str = "current",
        bbox: Optional[Tuple[float, float, float, float]] = None,
        output_dir: str = ".cache",
        paper_size: Optional[str] = None,
        use_layer_filter: bool = True,
    ) -> str:
        """Export drawing geometry to vector PDF based on requested mode.

        Args:
            mode: 'all_tavole' (4-sheet collation), 'current' (active sheet),
                  'globale' (full drawing), or 'custom' (marquee rectangle).
            bbox: Explicit bounding box for custom mode (falls back to selected_bbox).
            output_dir: Directory where the generated PDF will be stored.
            paper_size: Target paper standard ("A3", "A4", etc.).
            use_layer_filter: Whether to respect currently visible layer settings.

        Returns:
            Path to the generated PDF file.
        """
        os.makedirs(output_dir, exist_ok=True)
        psize = paper_size or self.paper_size
        layers = self.visible_layers if use_layer_filter else None

        if mode == "all_tavole":
            out_file = os.path.join(output_dir, "Tavole_Architettoniche_Complete.pdf")
            return export_all_tavole_multipage_pdf(
                self.model, out_file, paper_size=psize, visible_layers=layers
            )
        elif mode == "custom":
            target_bbox = bbox or self.selected_bbox
            if not target_bbox:
                raise ValueError("No bounding box provided for custom selection export")
            out_file = os.path.join(output_dir, "CAD_Area_Selezionata.pdf")
            return export_custom_bbox_to_pdf(
                self.model, target_bbox, out_file, paper_size=psize, visible_layers=layers
            )
        elif mode == "current":
            tavola_key = self.active_tavola
            clean_key = tavola_key.replace(" ", "_")
            out_file = os.path.join(output_dir, f"{clean_key}.pdf")
            return export_tavola_to_pdf(
                self.model, tavola_key, out_file, paper_size=psize, visible_layers=layers
            )
        elif mode == "globale":
            out_file = os.path.join(output_dir, "Disegno_Completo_Globale.pdf")
            return export_tavola_to_pdf(
                self.model, "Globale", out_file, paper_size=psize, visible_layers=layers
            )
        else:
            raise ValueError(f"Unknown PDF export mode: {mode}")





def inject_panzoom_head_scripts() -> None:
    """Inject Panzoom and local CAD helper scripts into page head."""
    # Local scripts mounted under /static
    ui.add_head_html('<script src="/static/panzoom.min.js"></script>')
    ui.add_head_html('<script src="/static/cad_canvas.js"></script>')
    # Dynamic layer style element placeholder
    ui.add_head_html('<style id="cad-dynamic-layer-styles"></style>')


def create_header(
    state: CadViewerState,
    on_tavola_select: Optional[Callable[[str], None]] = None,
    on_export_click: Optional[Callable[[], None]] = None,
    on_drawer_toggle: Optional[Callable[[], None]] = None,
    on_selection_toggle: Optional[Callable[[bool], None]] = None,
    on_theme_toggle: Optional[Callable[[], None]] = None,
    on_upload_click: Optional[Callable[[], None]] = None,
) -> Tuple[ui.header, Dict[str, ui.button]]:
    """Build modern dark CAD header bar with Tavole chips, export triggers, and layer toggle."""
    chip_buttons: Dict[str, ui.button] = {}

    with ui.header().classes(
        "bg-slate-900 border-b border-slate-800 text-white px-4 py-2 flex items-center justify-between shadow-md z-30"
    ) as header:
        # Left branding: Logo & Filename chip
        with ui.row().classes("items-center gap-3"):
            ui.icon("architecture", size="md").classes("text-cyan-400")
            with ui.column().classes("gap-0"):
                ui.label("CAD DWG Viewer").classes("text-sm font-bold tracking-wider uppercase text-slate-100")
                base_name = os.path.basename(state.model.file_path) or "Tavole.dwg"
                ui.badge(base_name, color="slate-800").classes(
                    "text-xs text-cyan-300 font-mono px-2 py-0.5 border border-cyan-800/40"
                )

        # Center: Tavole Quick-Navigation Chips
        tavole_opts = get_tavole_options(state.model)
        with ui.row().classes("items-center gap-2 flex-wrap justify-center"):
            for key in ["Globale", "Tavola 1", "Tavola 2", "Tavola 3", "Tavola 4"]:
                if key not in tavole_opts:
                    continue
                label_text = "Vista Globale" if key == "Globale" else key
                is_active = (key == state.active_tavola)

                btn = ui.button(
                    label_text,
                    on_click=(lambda k=key: _handle_tavola_click(k, state, chip_buttons, on_tavola_select)),
                ).props(
                    "dense no-caps unelevated " + ("color=cyan-7" if is_active else "color=slate-800")
                ).classes(
                    "text-xs font-medium px-3 py-1 transition-all rounded "
                    + ("text-white shadow-sm ring-1 ring-cyan-400" if is_active else "text-slate-300 hover:text-white")
                )
                chip_buttons[key] = btn

        # Right: Tools & Actions (Upload, Selection, Export PDF, Theme, Layers)
        with ui.row().classes("items-center gap-2"):
            # File Upload Dialog Trigger Button
            ui.button(
                "Carica",
                icon="upload_file",
                on_click=on_upload_click,
            ).props("dense no-caps outline color=cyan-400").classes(
                "text-xs rounded text-cyan-300 hover:text-white"
            ).tooltip("Carica file DWG o DXF")

            # Area Selection Marquee Toggle
            sel_btn = (
                ui.button(
                    "Seleziona Riquadro",
                    icon="crop_free",
                    on_click=lambda: _toggle_selection_mode(state, sel_btn, on_selection_toggle),
                )
                .props("dense no-caps outline color=slate-400")
                .classes("text-xs transition-colors rounded")
                .tooltip("Trascina un rettangolo sul disegno per zoomare o stampare in PDF")
            )

            # PDF Export Dialog Trigger Button
            ui.button(
                "Stampa / PDF",
                icon="picture_as_pdf",
                on_click=on_export_click,
            ).props("dense no-caps color=emerald-600").classes(
                "text-xs font-semibold px-3 py-1 text-white shadow-sm hover:bg-emerald-500 rounded"
            ).tooltip("Esporta Tavole o ritaglio personalizzato in PDF vettoriale")

            # Theme Toggle Button
            ui.button(
                icon="dark_mode" if state.dark_mode else "light_mode",
                on_click=lambda: _handle_theme_toggle(state, on_theme_toggle),
            ).props("dense round flat color=slate-300").classes("text-sm").tooltip("Cambia tema Chiaro / Scuro")

            # Layer Drawer Toggle
            ui.button(
                icon="layers",
                on_click=on_drawer_toggle,
            ).props("dense round flat color=cyan-400").classes("text-sm relative").tooltip("Gestisci Livelli CAD")

    return header, chip_buttons


def _handle_tavola_click(
    key: str,
    state: CadViewerState,
    chip_buttons: Dict[str, ui.button],
    callback: Optional[Callable[[str], None]],
) -> None:
    state.set_active_tavola(key)
    # Update button visual styling
    for k, btn in chip_buttons.items():
        if k == key:
            btn.props("color=cyan-7")
            btn.classes(add="text-white ring-1 ring-cyan-400 shadow-sm", remove="text-slate-300")
        else:
            btn.props("color=slate-800")
            btn.classes(add="text-slate-300", remove="text-white ring-1 ring-cyan-400 shadow-sm")

    # Trigger client-side smooth pan/zoom
    safe_run_javascript(f"if (window.cadViewer) window.cadViewer.zoomToTavola('{key}');")

    if callback:
        callback(key)


def _toggle_selection_mode(
    state: CadViewerState,
    btn: ui.button,
    callback: Optional[Callable[[bool], None]],
) -> None:
    state.selection_active = not state.selection_active
    if state.selection_active:
        btn.props("color=cyan-5 unelevated")
        btn.classes(add="bg-cyan-600 text-white ring-1 ring-cyan-300", remove="outline text-slate-400")
        btn.text = "Annulla Selezione"
        ui.notify("Modalità selezione attiva: trascina un rettangolo sul canvas", type="info", position="top")
    else:
        btn.props("outline color=slate-400")
        btn.classes(add="outline text-slate-400", remove="bg-cyan-600 text-white ring-1 ring-cyan-300")
        btn.text = "Seleziona Riquadro"

    safe_run_javascript(f"if (window.cadViewer) window.cadViewer.setSelectionMode({str(state.selection_active).lower()});")
    if callback:
        callback(state.selection_active)


def _handle_theme_toggle(
    state: CadViewerState,
    callback: Optional[Callable[[], None]],
) -> None:
    state.toggle_dark_mode()
    if callback:
        callback()


def create_canvas(
    state: CadViewerState,
    svg_content: str,
    on_export_custom_bbox: Optional[Callable[[Tuple[float, float, float, float]], None]] = None,
    export_dialog: Optional[ui.dialog] = None,
) -> ui.element:
    """Build the responsive CAD viewport container embedding SVG, Panzoom, and selection marquee."""
    inject_panzoom_head_scripts()

    cad_extents = list(state.model.extents)
    svg_bounds = list(extract_svg_viewbox(svg_content))
    tavole_data = {
        name: {"title": t["title"], "bbox": list(t["bbox"])}
        for name, t in get_tavole_options(state.model).items()
    }

    # Hidden input and button to sync custom marquee selections back to NiceGUI
    hidden_bbox_input = ui.input(value="").props("id=cad-selected-bbox-input").classes("hidden")

    def _on_bbox_synced(e: Any = None) -> None:
        try:
            val = hidden_bbox_input.value
            if val:
                coords = json.loads(val)
                if len(coords) == 4:
                    bbox = (float(coords[0]), float(coords[1]), float(coords[2]), float(coords[3]))
                    state.set_selected_bbox(bbox)
        except Exception:
            pass

    def _on_trigger_export_pdf() -> None:
        _on_bbox_synced()
        if state.selected_bbox:
            if on_export_custom_bbox:
                on_export_custom_bbox(state.selected_bbox)
            dlg = export_dialog or getattr(state, "export_dialog", None)
            if dlg:
                if hasattr(dlg, "refresh_options"):
                    dlg.refresh_options()
                dlg.open()

    hidden_bbox_input.on("change", _on_bbox_synced)

    # Hidden trigger button clicked by JS popup "Stampa PDF"
    ui.button("", on_click=_on_trigger_export_pdf).props("id=btn-trigger-bbox-pdf").classes("hidden")

    # Main viewport container
    bg_class = "bg-[#12151b]" if state.dark_mode else "bg-white"
    with ui.element("div").props("id=cad-viewport").classes(
        f"relative w-full h-[calc(100vh-56px)] overflow-hidden select-none {bg_class}"
    ) as viewport:
        # Embed the SVG drawing
        ui.html(svg_content).classes("w-full h-full block")

        # Marquee selection box overlay (dragged by user)
        ui.element("div").props("id=cad-selection-box style='display:none;'").classes(
            "absolute border-2 border-dashed border-cyan-400 bg-cyan-400/20 pointer-events-none z-20"
        )

        # Action popup shown upon completing rectangular selection
        with ui.element("div").props("id=cad-selection-popup style='display:none;'").classes(
            "absolute z-30 bg-slate-900/95 text-white backdrop-blur-md rounded-lg shadow-2xl p-2 flex items-center gap-2 border border-slate-700 ring-1 ring-cyan-500/30"
        ):
            ui.button(
                "Zoom",
                icon="zoom_in",
            ).props("id=btn-zoom-selection dense no-caps color=cyan-7").classes(
                "text-xs px-2 py-1 font-semibold rounded text-white"
            ).tooltip("Ingrandisci su quest'area")

            ui.button(
                "Stampa PDF",
                icon="picture_as_pdf",
            ).props("id=btn-export-selection dense no-caps color=emerald-600").classes(
                "text-xs px-2 py-1 font-semibold rounded text-white"
            ).tooltip("Esporta questa porzione in PDF")

            ui.button(
                icon="close",
            ).props("id=btn-close-selection dense flat round color=slate-400").classes("text-xs")

        # Floating HUD Controls (Zoom In, Zoom Out, Fit, Reset)
        create_floating_hud()

        # Active Sheet Indicator (bottom left)
        with ui.element("div").classes(
            "absolute bottom-4 left-4 z-10 bg-slate-900/80 backdrop-blur-sm text-slate-300 text-xs px-3 py-1.5 rounded-md border border-slate-800 shadow flex items-center gap-2"
        ):
            ui.icon("layers", size="xs").classes("text-cyan-400")
            ui.label().bind_text_from(
                state, "active_tavola", backward=lambda k: f"{k} - {state.model.tavole[k].title}" if k in state.model.tavole else k
            ).classes("font-mono font-medium")

    # Client-side initialization of Panzoom & coordinates after DOM mount
    init_script = f"""
    setTimeout(function() {{
        if (window.cadViewer) {{
            window.cadViewer.init({svg_bounds[2]}, {svg_bounds[3]}, {json.dumps(cad_extents)}, {json.dumps(tavole_data)});
        }}
    }}, 80);
    """
    safe_run_javascript(init_script)

    return viewport


def create_floating_hud() -> ui.element:
    """Build floating semi-transparent HUD toolbar with zoom and fit actions."""
    with ui.element("div").classes(
        "absolute bottom-4 right-4 z-20 flex flex-col gap-1 bg-slate-900/80 backdrop-blur-md p-1.5 rounded-lg border border-slate-700/80 shadow-xl ring-1 ring-white/10"
    ) as hud:
        ui.button(
            icon="add",
            on_click=lambda: safe_run_javascript("if(window.cadViewer) window.cadViewer.zoomIn();"),
        ).props("dense round flat color=slate-200").classes("text-sm hover:bg-slate-800").tooltip("Ingrandisci (Zoom +)")

        ui.button(
            icon="remove",
            on_click=lambda: safe_run_javascript("if(window.cadViewer) window.cadViewer.zoomOut();"),
        ).props("dense round flat color=slate-200").classes("text-sm hover:bg-slate-800").tooltip("Rimpicciolisci (Zoom -)")

        ui.button(
            icon="crop_free",
            on_click=lambda: safe_run_javascript("if(window.cadViewer) window.cadViewer.reset();"),
        ).props("dense round flat color=cyan-400").classes("text-sm hover:bg-slate-800").tooltip("Adatta a Schermo (Fit)")

        ui.button(
            icon="restart_alt",
            on_click=lambda: safe_run_javascript("if(window.cadViewer) window.cadViewer.reset();"),
        ).props("dense round flat color=slate-400").classes("text-sm hover:bg-slate-800").tooltip("Ripristina Vista (Reset)")

    return hud


def create_layer_drawer(
    state: CadViewerState,
    on_layer_toggle: Optional[Callable[[str, bool], None]] = None,
) -> ui.right_drawer:
    """Build right slide-over drawer for layer visibility management."""
    layer_data = format_layer_data(state.model.layers)
    checkbox_refs: Dict[str, ui.checkbox] = {}

    with ui.right_drawer(value=False).classes(
        "bg-slate-900 text-slate-100 border-l border-slate-800 p-4 shadow-2xl w-80 flex flex-col gap-3"
    ) as drawer:
        # Drawer Header
        with ui.row().classes("items-center justify-between w-full pb-2 border-b border-slate-800"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("layers", size="sm").classes("text-cyan-400")
                ui.label("Livelli CAD").classes("font-bold text-sm tracking-wide")
                ui.badge(f"{len(layer_data)}").props("color=slate-800").classes("text-xs text-cyan-300 font-mono")

            ui.button(icon="close", on_click=drawer.toggle).props("dense round flat color=slate-400").classes("text-xs")

        # Global Actions: Mostra Tutti / Nascondi Tutti
        with ui.row().classes("w-full gap-2 justify-between"):
            ui.button(
                "Mostra Tutti",
                icon="visibility",
                on_click=lambda: _show_all_layers(state, checkbox_refs, on_layer_toggle),
            ).props("dense no-caps outline color=cyan-400").classes("text-xs flex-1 rounded")

            ui.button(
                "Nascondi Tutti",
                icon="visibility_off",
                on_click=lambda: _hide_all_layers(state, checkbox_refs, on_layer_toggle),
            ).props("dense no-caps outline color=slate-500").classes("text-xs flex-1 rounded")

        # Layer Search Filter Input
        search_input = ui.input(placeholder="Cerca layer...").props(
            "dense outlined rounded dark color=cyan-5"
        ).classes("w-full text-xs")

        # Scrollable Layer List
        with ui.scroll_area().classes("flex-1 w-full pr-1"):
            layer_rows = []
            for item in layer_data:
                name = item["name"]
                clean_name = item["clean_name"]
                color_hex = item["color"]
                count = item["count"]
                is_checked = name in state.visible_layers

                with ui.row().classes(
                    "items-center justify-between w-full py-1.5 px-2 hover:bg-slate-800/60 rounded transition-colors border-b border-slate-800/40"
                ) as row:
                    with ui.row().classes("items-center gap-2 overflow-hidden flex-1"):
                        # Checkbox for instant visibility toggle
                        cb = ui.checkbox(
                            value=is_checked,
                            on_change=lambda e, n=name, cn=clean_name: _toggle_single_layer(
                                state, n, cn, e.value, on_layer_toggle
                            ),
                        ).props("dense color=cyan-5 dark")
                        checkbox_refs[name] = cb

                        # Color indicator pill
                        ui.element("span").classes("w-3 h-3 rounded-full flex-shrink-0 shadow-sm ring-1 ring-white/20").style(
                            f"background-color: {color_hex};"
                        )

                        # Layer Name
                        ui.label(name).classes(
                            "text-xs font-mono truncate text-slate-200 select-none cursor-pointer"
                        ).tooltip(name)

                    # Entity Count Badge
                    ui.label(str(count)).classes("text-[10px] font-mono text-slate-400 bg-slate-800 px-1.5 py-0.5 rounded")

                layer_rows.append((name.lower(), row))

            # Filter handler
            def _filter_layers(e: Any) -> None:
                query = (search_input.value or "").strip().lower()
                for lname, row in layer_rows:
                    row.visible = (query in lname) if query else True

            search_input.on("update:model-value", _filter_layers)

    return drawer


def _toggle_single_layer(
    state: CadViewerState,
    layer_name: str,
    clean_name: str,
    is_visible: bool,
    callback: Optional[Callable[[str, bool], None]],
) -> None:
    if getattr(state, "_bulk_updating", False):
        return
    state.toggle_layer(layer_name, is_visible)
    safe_run_javascript(
        f"if (window.cadViewer) window.cadViewer.toggleLayerVisibility('{clean_name}', {str(is_visible).lower()});"
    )
    if callback:
        callback(layer_name, is_visible)


def _show_all_layers(
    state: CadViewerState,
    checkbox_refs: Dict[str, ui.checkbox],
    callback: Optional[Callable[[str, bool], None]],
) -> None:
    state._bulk_updating = True
    try:
        state.show_all_layers()
        for cb in checkbox_refs.values():
            cb.value = True
    finally:
        state._bulk_updating = False
    safe_run_javascript("if (window.cadViewer) window.cadViewer.showAllLayers();")
    if callback:
        callback("*", True)


def _hide_all_layers(
    state: CadViewerState,
    checkbox_refs: Dict[str, ui.checkbox],
    callback: Optional[Callable[[str, bool], None]],
) -> None:
    state._bulk_updating = True
    try:
        state.hide_all_layers()
        for cb in checkbox_refs.values():
            cb.value = False
    finally:
        state._bulk_updating = False
    safe_run_javascript("if (window.cadViewer) window.cadViewer.hideAllLayers();")
    if callback:
        callback("*", False)


def create_export_dialog(state: CadViewerState) -> ui.dialog:
    """Build modal dialog for triggering vector PDF generation and downloads."""
    with ui.dialog() as dialog, ui.card().classes(
        "bg-slate-900 text-slate-100 p-6 rounded-xl border border-slate-800 shadow-2xl max-w-lg w-full"
    ):
        with ui.row().classes("items-center justify-between w-full pb-3 border-b border-slate-800"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("picture_as_pdf", size="md").classes("text-emerald-400")
                ui.label("Esportazione PDF Vettoriale").classes("font-bold text-base tracking-wide text-white")
            ui.button(icon="close", on_click=dialog.close).props("dense round flat color=slate-400")

        # Export Mode Selector
        ui.label("Seleziona Contenuto da Stampare:").classes("text-xs font-semibold text-slate-300 mt-2")

        initial_opts = {
            "all_tavole": "Tutte le 4 Tavole (PDF Multi-pagina ordinato)",
            "current": f"Tavola Corrente ({state.active_tavola})",
            "globale": "Disegno Completo (Vista Globale)",
        }
        if state.selected_bbox:
            initial_opts["custom"] = "Area Selezionata (Ritaglio rettangolare)"

        initial_val = "custom" if state.selected_bbox else ("all_tavole" if state.active_tavola == "Globale" else "current")

        mode_radio = ui.radio(
            options=initial_opts,
            value=initial_val,
        ).props("color=emerald-5 dark").classes("text-xs flex flex-col gap-1")

        def refresh_options() -> None:
            """Refresh export mode options and selection based on viewer state."""
            opts = {
                "all_tavole": "Tutte le 4 Tavole (PDF Multi-pagina ordinato)",
                "current": f"Tavola Corrente ({state.active_tavola})",
                "globale": "Disegno Completo (Vista Globale)",
            }
            if state.selected_bbox:
                opts["custom"] = "Area Selezionata (Ritaglio rettangolare)"
                mode_radio.options = opts
                mode_radio.value = "custom"
            else:
                mode_radio.options = opts
                if mode_radio.value == "custom":
                    mode_radio.value = "all_tavole" if state.active_tavola == "Globale" else "current"

        state.add_listener(refresh_options)
        dialog.on("open", refresh_options)
        dialog.refresh_options = refresh_options
        dialog.mode_radio = mode_radio
        state.export_dialog = dialog

        # Paper Size & Options
        with ui.row().classes("w-full items-center justify-between gap-4 mt-2 pt-3 border-t border-slate-800"):
            with ui.column().classes("gap-1 flex-1"):
                ui.label("Formato Carta:").classes("text-xs font-semibold text-slate-300")
                paper_select = ui.select(
                    options=["A4", "A3", "A2", "A1", "A0"],
                    value=state.paper_size,
                ).props("dense outlined dark color=emerald-5").classes("w-full text-xs")

            with ui.column().classes("gap-1 flex-1"):
                ui.label("Filtro Livelli:").classes("text-xs font-semibold text-slate-300")
                layer_filter_cb = ui.checkbox("Esporta solo layer visibili", value=True).props(
                    "dense color=emerald-5 dark"
                ).classes("text-xs")

        # Status & Action Buttons
        status_label = ui.label("").classes("text-xs font-mono text-cyan-400 min-h-[1.5rem] mt-2")

        with ui.row().classes("w-full justify-end gap-2 mt-4 pt-3 border-t border-slate-800"):
            ui.button("Annulla", on_click=dialog.close).props("dense flat color=slate-400").classes("text-xs")

            async def _perform_export() -> None:
                status_label.text = "Generazione PDF vettoriale in corso..."
                ui.notify("Avvio esportazione PDF vettoriale...", type="info")
                try:
                    mode = mode_radio.value
                    paper = paper_select.value
                    use_filter = layer_filter_cb.value

                    pdf_path = state.export_pdf(
                        mode=mode,
                        paper_size=paper,
                        use_layer_filter=use_filter,
                    )

                    status_label.text = "Completato! Download in avvio..."
                    ui.notify("PDF generato con successo!", type="positive")
                    filename = os.path.basename(pdf_path)
                    ui.download(pdf_path, filename=filename)
                    dialog.close()
                except Exception as err:
                    status_label.text = f"Errore: {err}"
                    ui.notify(f"Errore durante l'esportazione: {err}", type="negative")

            ui.button(
                "Genera e Scarica PDF",
                icon="download",
                on_click=_perform_export,
            ).props("dense color=emerald-600").classes(
                "text-xs font-semibold px-4 py-1.5 text-white shadow-md hover:bg-emerald-500 rounded"
            )

    return dialog


def create_upload_dialog(
    on_file_loaded: Optional[Callable[[str], None]] = None,
) -> ui.dialog:
    """Build modal dialog for uploading and loading new CAD DWG/DXF files."""
    with ui.dialog() as dialog, ui.card().classes(
        "bg-slate-900 text-slate-100 p-6 rounded-xl border border-slate-800 shadow-2xl max-w-md w-full"
    ):
        with ui.row().classes("items-center justify-between w-full pb-3 border-b border-slate-800"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("upload_file", size="md").classes("text-cyan-400")
                ui.label("Carica File CAD").classes("font-bold text-base tracking-wide text-white")
            ui.button(icon="close", on_click=dialog.close).props("dense round flat color=slate-400")

        ui.label("Seleziona o trascina un file DWG o DXF:").classes("text-xs text-slate-300 mt-2")

        status_label = ui.label("").classes("text-xs font-mono text-cyan-400 min-h-[1.2rem]")

        async def _handle_upload(e: Any) -> None:
            filename = os.path.basename(e.name)
            ext = os.path.splitext(filename)[1].lower()
            if ext not in (".dwg", ".dxf"):
                ui.notify(f"Estensione non supportata: {ext}. Seleziona un file .dwg o .dxf", type="negative")
                status_label.text = f"Errore: formato {ext} non supportato"
                return

            upload_dir = os.path.join(".cache", "uploads")
            os.makedirs(upload_dir, exist_ok=True)
            saved_path = os.path.join(upload_dir, filename)

            content = e.content.read() if hasattr(e.content, "read") else e.content
            with open(saved_path, "wb") as f:
                f.write(content)

            status_label.text = f"File {filename} caricato con successo!"
            ui.notify(f"File {filename} caricato!", type="positive")
            dialog.close()

            if on_file_loaded:
                on_file_loaded(saved_path)

        ui.upload(
            label="Carica file DWG / DXF",
            auto_upload=True,
            max_files=1,
            on_upload=_handle_upload,
        ).props('accept=".dwg,.dxf" color=cyan-6 dark').classes("w-full")

        with ui.row().classes("w-full justify-end mt-4"):
            ui.button("Chiudi", on_click=dialog.close).props("dense flat color=slate-400").classes("text-xs")

    return dialog

