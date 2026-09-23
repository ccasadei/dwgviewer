"""CAD DWG Viewer - Main Application Entry Point.

Interactive Web CAD DWG & DXF Viewer built with NiceGUI, ezdxf, and Panzoom.
Provides high-performance vector rendering, per-layer CSS toggling,
Tavole architectural sheet navigation, marquee area selection, and vector PDF export.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from nicegui import app, ui

from cad_engine import CadModel, load_cad_file
from renderer import render_to_svg
from ui_components import (
    CadViewerState,
    create_canvas,
    create_export_dialog,
    create_header,
    create_layer_drawer,
    create_upload_dialog,
)

# Global in-memory cache for parsed CadModel instances to speed up page loads and testing
_MODEL_CACHE: Dict[str, Tuple[float, CadModel]] = {}

# Default CAD file to load
DEFAULT_FILE: str = "./Tavole.dwg"

# Mount static asset directory for Panzoom and CAD helper scripts
_STATIC_DIR = Path(__file__).parent / "static"
if _STATIC_DIR.is_dir():
    try:
        app.add_static_files("/static", str(_STATIC_DIR))
    except Exception:
        pass


def get_cad_model(file_path: str, cache_dir: str = ".cache") -> CadModel:
    """Retrieve parsed CadModel from memory cache or load from disk.

    Args:
        file_path: Relative or absolute path to DWG or DXF file.
        cache_dir: Directory used for DXF and SVG file caching.

    Returns:
        Loaded and parsed CadModel.

    Raises:
        FileNotFoundError: If the CAD file does not exist on disk.
        ValueError: If the file format is unsupported.
    """
    abs_path = os.path.abspath(file_path)
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"File CAD non trovato: '{file_path}'")

    mtime = os.path.getmtime(abs_path)
    if abs_path in _MODEL_CACHE:
        cached_mtime, cached_model = _MODEL_CACHE[abs_path]
        if cached_mtime >= mtime:
            return cached_model

    model = load_cad_file(abs_path, cache_dir=cache_dir)
    _MODEL_CACHE[abs_path] = (mtime, model)
    return model


def build_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser for the CAD DWG viewer application.

    Returns:
        argparse.ArgumentParser configured with file, port, host, reload, and native options.
    """
    parser = argparse.ArgumentParser(
        description="CAD DWG Viewer - Visualizzatore Web CAD DWG/DXF ad alte prestazioni"
    )
    parser.add_argument(
        "--file",
        type=str,
        default="./Tavole.dwg",
        help="Percorso del file CAD (.dwg o .dxf) da visualizzare (default: ./Tavole.dwg)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Porta TCP su cui avviare il server web (default: 8080)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Indirizzo host di binding per il server web (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        default=False,
        help="Attiva il ricaricamento automatico al salvataggio del codice (sviluppo)",
    )
    parser.add_argument(
        "--native",
        action="store_true",
        default=False,
        help="Avvia come applicazione desktop nativa con pywebview (se disponibile)",
    )
    return parser


@ui.page("/")
def index_page(file: Optional[str] = None) -> None:
    """Render the primary CAD workspace viewport or error recovery view."""
    target_file = file or DEFAULT_FILE

    # Configure dark mode and CAD page layout styling
    ui.dark_mode().enable()
    ui.query("body").classes("bg-[#12151b] text-slate-100 overflow-hidden m-0 p-0 select-none")
    ui.page_title(f"CAD DWG Viewer - {os.path.basename(target_file)}")

    # 1. Attempt loading and rendering CAD model
    try:
        model = get_cad_model(target_file)
        state = CadViewerState(model=model, dark_mode=True)
        svg_content = render_to_svg(model, dark_mode=state.dark_mode)
    except Exception as err:
        # Graceful error state with error banner, notification, and dynamic upload interface
        upload_dialog = create_upload_dialog(
            on_file_loaded=lambda p: ui.navigate.to(f"/?file={p}")
        )

        with ui.header().classes(
            "bg-slate-900 border-b border-slate-800 text-white px-4 py-2 flex items-center justify-between shadow-md z-30"
        ):
            with ui.row().classes("items-center gap-3"):
                ui.icon("architecture", size="md").classes("text-cyan-400")
                ui.label("CAD DWG Viewer").classes("text-sm font-bold tracking-wider uppercase text-slate-100")
                ui.badge(os.path.basename(target_file), color="red-900").classes(
                    "text-xs text-red-200 font-mono px-2 py-0.5 border border-red-700"
                )

            ui.button(
                "Carica",
                icon="upload_file",
                on_click=upload_dialog.open,
            ).props("dense no-caps color=cyan-7").classes(
                "text-xs font-semibold px-3 py-1 text-white shadow-sm rounded"
            ).tooltip("Carica un altro file DWG o DXF")

        with ui.column().classes(
            "w-full max-w-xl mx-auto my-16 p-8 bg-slate-900/90 border border-red-500/30 rounded-2xl shadow-2xl items-center text-center gap-4"
        ):
            ui.icon("error_outline", size="xl").classes("text-red-400")
            ui.label("File CAD non trovato o non valido").classes("text-lg font-bold text-slate-100")
            ui.label(str(err)).classes(
                "text-xs text-red-300 font-mono bg-red-950/60 p-3 rounded w-full border border-red-900/40 text-left"
            )
            ui.label("Carica un file DWG o DXF per iniziare la visualizzazione:").classes(
                "text-sm text-slate-300 mt-2"
            )

            async def _handle_direct_upload(e: Any) -> None:
                clean_name = os.path.basename(e.name)
                upload_dir = os.path.join(".cache", "uploads")
                os.makedirs(upload_dir, exist_ok=True)
                saved_path = os.path.join(upload_dir, clean_name)
                content = e.content.read() if hasattr(e.content, "read") else e.content
                with open(saved_path, "wb") as f:
                    f.write(content)
                ui.notify(f"File {clean_name} caricato con successo!", type="positive")
                ui.navigate.to(f"/?file={saved_path}")

            ui.upload(
                label="Carica file DWG / DXF",
                auto_upload=True,
                max_files=1,
                on_upload=_handle_direct_upload,
            ).props('accept=".dwg,.dxf" color=cyan-6 dark').classes("w-full")

        ui.notify(f"Impossibile aprire '{target_file}': {err}", type="negative", position="top")
        return

    # 2. Render normal CAD viewer workspace
    export_dialog = create_export_dialog(state)
    upload_dialog = create_upload_dialog(
        on_file_loaded=lambda p: ui.navigate.to(f"/?file={p}")
    )
    drawer = create_layer_drawer(state)

    header, chips = create_header(
        state,
        on_export_click=export_dialog.open,
        on_drawer_toggle=drawer.toggle,
        on_upload_click=upload_dialog.open,
    )

    canvas = create_canvas(
        state,
        svg_content,
        export_dialog=export_dialog,
    )


def main() -> None:
    """CLI execution entry point."""
    global DEFAULT_FILE
    parser = build_parser()
    args, _ = parser.parse_known_args()
    DEFAULT_FILE = args.file

    ui.run(
        host=args.host,
        port=args.port,
        reload=args.reload,
        native=args.native,
        title="CAD DWG Viewer",
        favicon="📐",
    )


if __name__ == "__main__":
    main()
