import os
import pytest
import pypdf
from cad_engine import load_cad_file
from pdf_exporter import (
    export_tavola_to_pdf,
    export_custom_bbox_to_pdf,
    export_all_tavole_multipage_pdf,
)


def test_export_single_tavola_pdf(tmp_path):
    model = load_cad_file("Tavole.dwg")
    out_file = str(tmp_path / "tavola1.pdf")

    result = export_tavola_to_pdf(model, "Tavola 1", out_file)
    assert result == out_file
    assert os.path.exists(out_file)
    assert os.path.getsize(out_file) > 10000  # Non-trivial PDF

    reader = pypdf.PdfReader(out_file)
    assert len(reader.pages) == 1
    page = reader.pages[0]
    # A3 landscape: ~1190 x ~842 pt
    width = float(page.mediabox.width)
    height = float(page.mediabox.height)
    assert width > height  # Landscape orientation
    assert 1180 < width < 1200
    assert 830 < height < 850


def test_export_all_tavole_multipage_pdf(tmp_path):
    model = load_cad_file("Tavole.dwg")
    out_file = str(tmp_path / "all_tavole.pdf")

    result = export_all_tavole_multipage_pdf(model, out_file)
    assert result == out_file
    assert os.path.exists(out_file)

    reader = pypdf.PdfReader(out_file)
    assert len(reader.pages) == 4  # Exactly 4 tavole!

    # Verify bookmarks/outlines exist for each Tavola
    assert len(reader.outline) == 4
    for i, item in enumerate(reader.outline, 1):
        title = item.title if hasattr(item, "title") else str(item)
        assert f"Tavola {i}" in title


def test_export_custom_bbox_to_pdf(tmp_path):
    model = load_cad_file("Tavole.dwg")
    out_file = str(tmp_path / "custom_bbox.pdf")
    custom_bbox = (3700.0, 1720.0, 3850.0, 1750.0)

    result = export_custom_bbox_to_pdf(
        model,
        custom_bbox,
        out_file,
        paper_size="A4",
        title="Dettaglio Scala",
    )
    assert result == out_file
    assert os.path.exists(out_file)
    assert os.path.getsize(out_file) > 5000

    reader = pypdf.PdfReader(out_file)
    assert len(reader.pages) == 1
    page = reader.pages[0]
    # A4 landscape: ~842 x ~595 pt
    width = float(page.mediabox.width)
    height = float(page.mediabox.height)
    assert width > height
    assert 830 < width < 850
    assert 585 < height < 605


def test_export_custom_bbox_portrait(tmp_path):
    model = load_cad_file("Tavole.dwg")
    out_file = str(tmp_path / "custom_portrait.pdf")
    # Taller than wide bounding box to trigger portrait orientation
    portrait_bbox = (3700.0, 1500.0, 3750.0, 1750.0)

    result = export_custom_bbox_to_pdf(
        model,
        portrait_bbox,
        out_file,
        paper_size="A4",
        title="Sezione Verticale",
    )
    assert result == out_file
    assert os.path.exists(out_file)

    reader = pypdf.PdfReader(out_file)
    assert len(reader.pages) == 1
    page = reader.pages[0]
    width = float(page.mediabox.width)
    height = float(page.mediabox.height)
    assert height > width  # Portrait orientation
    assert 585 < width < 605
    assert 830 < height < 850


def test_export_tavola_invalid_key(tmp_path):
    model = load_cad_file("Tavole.dwg")
    out_file = str(tmp_path / "invalid.pdf")
    with pytest.raises(KeyError):
        export_tavola_to_pdf(model, "Tavola 99", out_file)


def test_export_invalid_paper_size(tmp_path):
    model = load_cad_file("Tavole.dwg")
    out_file = str(tmp_path / "invalid_size.pdf")
    with pytest.raises(ValueError):
        export_tavola_to_pdf(model, "Tavola 1", out_file, paper_size="B5")


def test_render_context_color_policy_and_lineweights():
    """Verify PDF export configuration uses ColorPolicy.COLOR and legible lineweights."""
    from pdf_exporter import _setup_render_context_and_config
    from ezdxf.addons.drawing.config import ColorPolicy

    model = load_cad_file("Tavole.dwg")
    ctx, config, layout_props = _setup_render_context_and_config(model)

    assert config.color_policy == ColorPolicy.COLOR
    assert config.min_lineweight >= 0.18
    assert config.lineweight_scaling >= 1.0
    assert layout_props.background_color == "#ffffff"


def test_render_context_visible_layers_case_insensitivity():
    """Verify visible_layers matching is case-insensitive against ezdxf RenderContext lowercase keys."""
    from pdf_exporter import _setup_render_context_and_config

    model = load_cad_file("Tavole.dwg")
    original_layer_names = [l.name for l in model.layers]  # contains 'TESTI', 'Muri', etc.
    ctx, _, _ = _setup_render_context_and_config(model, visible_layers=original_layer_names)

    # Every layer that exists in model should be marked visible in RenderContext
    visible_count = sum(1 for p in ctx.layers.values() if p.is_visible)
    assert visible_count == len(ctx.layers)

