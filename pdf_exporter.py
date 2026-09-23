"""Vector PDF Exporter Engine for architectural CAD drawings (single sheets & multi-page tavole)."""

import io
import os
from typing import Optional, Sequence

import matplotlib
import matplotlib.pyplot as plt
import pypdf
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.config import BackgroundPolicy, ColorPolicy, Configuration
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from ezdxf.addons.drawing.properties import LayoutProperties

from cad_engine import CadModel

# Standard ISO 216 paper dimensions in millimeters: (long_edge, short_edge)
PAPER_SIZES_MM: dict[str, tuple[float, float]] = {
    "A4": (297.0, 210.0),
    "A3": (420.0, 297.0),
    "A2": (594.0, 420.0),
    "A1": (841.0, 594.0),
    "A0": (1189.0, 841.0),
}

DEFAULT_MARGIN_MM: float = 10.0


def calculate_page_geometry(
    bbox: tuple[float, float, float, float],
    paper_size: str = "A3",
    margin_mm: float = DEFAULT_MARGIN_MM,
) -> tuple[float, float, tuple[float, float, float, float]]:
    """Calculate optimal page orientation, dimensions (in inches), and normalized axes rect with margins.

    Args:
        bbox: Bounding box as (min_x, min_y, max_x, max_y).
        paper_size: Paper size standard ("A4", "A3", "A2", "A1", "A0").
        margin_mm: Page margin in millimeters.

    Returns:
        (fig_width_in, fig_height_in, (left, bottom, width, height))
    """
    key = paper_size.upper().strip()
    if key not in PAPER_SIZES_MM:
        raise ValueError(
            f"Unsupported paper size: '{paper_size}'. Supported sizes: {list(PAPER_SIZES_MM.keys())}"
        )

    long_edge, short_edge = PAPER_SIZES_MM[key]
    min_x, min_y, max_x, max_y = bbox
    dx = abs(max_x - min_x)
    dy = abs(max_y - min_y)

    # Automatically calculate optimal page orientation based on aspect ratio
    if dx >= dy:
        pw_mm, ph_mm = long_edge, short_edge  # Landscape
    else:
        pw_mm, ph_mm = short_edge, long_edge  # Portrait

    printable_w_mm = max(pw_mm - 2 * margin_mm, 1.0)
    printable_h_mm = max(ph_mm - 2 * margin_mm, 1.0)

    left = margin_mm / pw_mm
    bottom = margin_mm / ph_mm
    width = printable_w_mm / pw_mm
    height = printable_h_mm / ph_mm

    fig_w_in = pw_mm / 25.4
    fig_h_in = ph_mm / 25.4

    return fig_w_in, fig_h_in, (left, bottom, width, height)


def _setup_render_context_and_config(
    cad_model: CadModel,
    visible_layers: Optional[set[str]] = None,
) -> tuple[RenderContext, Configuration, LayoutProperties]:
    """Configure ezdxf drawing context with white background and print-ready high-contrast lines."""
    ctx = RenderContext(cad_model.dxf_doc)
    config = Configuration(
        background_policy=BackgroundPolicy.CUSTOM,
        custom_bg_color="#ffffff",
        color_policy=ColorPolicy.COLOR,
        min_lineweight=0.20,
        lineweight_scaling=1.2,
    )
    layout_props = LayoutProperties.modelspace()
    layout_props.set_colors("#ffffff", "#000000")

    if visible_layers is not None:
        visible_set_lower = {name.lower() for name in visible_layers}
        for name, layer_prop in ctx.layers.items():
            layer_prop.is_visible = name.lower() in visible_set_lower
    else:
        for layer_prop in ctx.layers.values():
            layer_prop.is_visible = True

    return ctx, config, layout_props


def _apply_bbox_to_axes(
    ax: plt.Axes,
    bbox: tuple[float, float, float, float],
    title: str = "",
) -> None:
    """Apply bounding box limits and aspect ratio to axes."""
    min_x, min_y, max_x, max_y = bbox
    if min_x >= max_x:
        min_x, max_x = min_x - 1.0, max_x + 1.0
    if min_y >= max_y:
        min_y, max_y = min_y - 1.0, max_y + 1.0

    ax.set_xlim(min_x, max_x)
    ax.set_ylim(min_y, max_y)
    ax.set_aspect("equal", "box")

    if title:
        ax.set_title(title, fontsize=11, pad=8, color="#12151b")
    else:
        ax.set_title("")


def export_custom_bbox_to_pdf(
    cad_model: CadModel,
    bbox: tuple[float, float, float, float],
    output_path: str,
    paper_size: str = "A3",
    title: str = "",
    visible_layers: Optional[Sequence[str] | set[str]] = None,
) -> str:
    """Export custom CAD bounding box to a high quality vector PDF with optimal page orientation.

    Args:
        cad_model: Loaded CadModel.
        bbox: Bounding box tuple (min_x, min_y, max_x, max_y).
        output_path: Destination PDF file path.
        paper_size: Target paper standard ("A3", "A4", etc.).
        title: Optional title drawn on page and embedded into PDF metadata.
        visible_layers: Optional set of visible layer names.

    Returns:
        The written output_path.
    """
    output_dir = os.path.dirname(os.path.abspath(output_path))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    fig_w, fig_h, (left, bottom, w, h) = calculate_page_geometry(bbox, paper_size=paper_size)

    fig = plt.figure(figsize=(fig_w, fig_h))
    try:
        fig.patch.set_facecolor("#ffffff")
        ax = fig.add_axes([left, bottom, w, h])
        ax.set_facecolor("#ffffff")

        layers_set = set(visible_layers) if visible_layers is not None else None
        ctx, config, layout_props = _setup_render_context_and_config(cad_model, layers_set)

        backend = MatplotlibBackend(ax, adjust_figure=False)
        frontend = Frontend(ctx, backend, config=config)

        msp = cad_model.dxf_doc.modelspace()
        frontend.draw_layout(msp, finalize=False, layout_properties=layout_props)

        _apply_bbox_to_axes(ax, bbox, title=title)

        metadata = {"Title": title} if title else None
        fig.savefig(output_path, format="pdf", facecolor="#ffffff", edgecolor="none", metadata=metadata)
        return output_path
    finally:
        plt.close(fig)


def export_tavola_to_pdf(
    cad_model: CadModel,
    tavola_key: str,
    output_path: str,
    paper_size: str = "A3",
    visible_layers: Optional[Sequence[str] | set[str]] = None,
) -> str:
    """Export an architectural Tavola sheet to vector PDF.

    Args:
        cad_model: Loaded CadModel containing tavole definitions.
        tavola_key: Sheet identifier, e.g. 'Tavola 1'.
        output_path: Destination PDF file path.
        paper_size: Target paper standard ("A3", "A4", etc.).
        visible_layers: Optional set of visible layer names.

    Returns:
        The written output_path.
    """
    tavola = cad_model.get_tavola(tavola_key)
    if not tavola:
        # Fallback to case-insensitive match
        for k, t in cad_model.tavole.items():
            if k.lower() == tavola_key.lower():
                tavola = t
                break

    if not tavola:
        raise KeyError(
            f"Tavola '{tavola_key}' not found in CadModel. Available tavole: {list(cad_model.tavole.keys())}"
        )

    return export_custom_bbox_to_pdf(
        cad_model=cad_model,
        bbox=tavola.bbox,
        output_path=output_path,
        paper_size=paper_size,
        title=tavola.title or tavola.name,
        visible_layers=visible_layers,
    )


def export_all_tavole_multipage_pdf(
    cad_model: CadModel,
    output_path: str,
    paper_size: str = "A3",
    visible_layers: Optional[Sequence[str] | set[str]] = None,
) -> str:
    """Collate all 4 architectural tavole into a single multi-page vector PDF with bookmarks/outlines.

    Generates pages in strict order (Tavola 1, Tavola 2, Tavola 3, Tavola 4) and collates
    using pypdf.PdfWriter with navigation bookmarks.

    Args:
        cad_model: Loaded CadModel containing tavole definitions.
        output_path: Destination multi-page PDF file path.
        paper_size: Target paper standard ("A3", "A4", etc.).
        visible_layers: Optional set of visible layer names.

    Returns:
        The written output_path.
    """
    output_dir = os.path.dirname(os.path.abspath(output_path))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    tavole_order = ["Tavola 1", "Tavola 2", "Tavola 3", "Tavola 4"]
    available_keys = [k for k in tavole_order if k in cad_model.tavole]
    if not available_keys:
        available_keys = [k for k in cad_model.tavole.keys() if k != "Globale"]
    if not available_keys:
        available_keys = list(cad_model.tavole.keys())
    if not available_keys:
        raise ValueError("No tavole found to export in CadModel")

    layers_set = set(visible_layers) if visible_layers is not None else None
    ctx, config, layout_props = _setup_render_context_and_config(cad_model, layers_set)

    # Optimization: Render modelspace once and re-project viewports per sheet
    first_tavola = cad_model.tavole[available_keys[0]]
    init_w, init_h, (init_l, init_b, init_w_rect, init_h_rect) = calculate_page_geometry(
        first_tavola.bbox, paper_size=paper_size
    )

    fig = plt.figure(figsize=(init_w, init_h))
    fig.patch.set_facecolor("#ffffff")
    ax = fig.add_axes([init_l, init_b, init_w_rect, init_h_rect])
    ax.set_facecolor("#ffffff")

    backend = MatplotlibBackend(ax, adjust_figure=False)
    frontend = Frontend(ctx, backend, config=config)
    msp = cad_model.dxf_doc.modelspace()
    frontend.draw_layout(msp, finalize=False, layout_properties=layout_props)

    writer = pypdf.PdfWriter()

    try:
        for key in available_keys:
            tavola_info = cad_model.tavole[key]
            fig_w, fig_h, (left, bottom, w, h) = calculate_page_geometry(
                tavola_info.bbox, paper_size=paper_size
            )
            fig.set_size_inches(fig_w, fig_h, forward=True)
            ax.set_position([left, bottom, w, h])

            _apply_bbox_to_axes(ax, tavola_info.bbox, title="")

            page_buffer = io.BytesIO()
            fig.savefig(
                page_buffer,
                format="pdf",
                facecolor="#ffffff",
                edgecolor="none",
                metadata={"Title": tavola_info.title or key},
            )
            page_buffer.seek(0)

            bookmark_title = tavola_info.title if tavola_info.title else key
            writer.append(page_buffer, outline_item=bookmark_title)

        with open(output_path, "wb") as f_out:
            writer.write(f_out)
    finally:
        plt.close(fig)

    return output_path
