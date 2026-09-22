import os
import re
import pytest
import ezdxf
from cad_engine import load_cad_file, CadModel
from renderer import render_to_svg, sanitize_layer_name, get_svg_cache_path


def test_render_to_svg():
    """Verify basic SVG rendering from Tavole.dwg per task brief."""
    model = load_cad_file("Tavole.dwg")
    svg_content = render_to_svg(model, dark_mode=True)

    assert svg_content.startswith("<svg") or "<svg" in svg_content
    assert "</svg>" in svg_content
    assert "viewBox=" in svg_content
    # Verify layer classes exist in SVG for CSS toggling
    assert "cad-layer" in svg_content
    assert "layer-" in svg_content


def test_render_to_svg_layer_tagging():
    """Verify layer wrapping with both class and data-layer attributes."""
    model = load_cad_file("Tavole.dwg")
    svg_content = render_to_svg(model, dark_mode=True)

    # Check for layer container group syntax
    assert 'class="cad-layer layer-' in svg_content
    assert 'data-layer="' in svg_content

    # Specific known layers in Tavole.dwg
    assert 'data-layer="0"' in svg_content
    assert 'data-layer="Muri"' in svg_content
    assert 'data-layer="ALBERI - Trees"' in svg_content
    assert 'layer-Muri' in svg_content
    assert 'layer-0' in svg_content


def test_render_to_svg_themes():
    """Verify dark mode and light mode produce appropriate background styles."""
    model = load_cad_file("Tavole.dwg")

    dark_svg = render_to_svg(model, dark_mode=True, force_refresh=True)
    assert "#12151b" in dark_svg.lower()

    light_svg = render_to_svg(model, dark_mode=False, force_refresh=True)
    assert "#ffffff" in light_svg.lower()


def test_render_to_svg_caching(tmp_path):
    """Verify SVG caching behavior and instant reload."""
    model = load_cad_file("Tavole.dwg")
    cache_dir = str(tmp_path / "cache")

    # First call generates and caches
    svg1 = render_to_svg(model, dark_mode=True, cache_dir=cache_dir)
    cache_file = get_svg_cache_path(model.file_path, dark_mode=True, cache_dir=cache_dir)
    assert os.path.exists(cache_file)
    assert os.path.getsize(cache_file) > 0

    # Second call returns from cache
    svg2 = render_to_svg(model, dark_mode=True, cache_dir=cache_dir)
    assert svg1 == svg2

    # Invalidate cache by forcing refresh
    svg3 = render_to_svg(model, dark_mode=True, cache_dir=cache_dir, force_refresh=True)
    assert "</svg>" in svg3


def test_sanitize_layer_name():
    """Verify layer name sanitization for CSS classes."""
    assert sanitize_layer_name("0") == "0"
    assert sanitize_layer_name("Muri") == "Muri"
    assert sanitize_layer_name("STATO DI FATTO") == "STATO_DI_FATTO"
    assert sanitize_layer_name("ALBERI - Trees") == "ALBERI_-_Trees"
    assert sanitize_layer_name("PROSPETTO/SEZIONE") == "PROSPETTO_SEZIONE"
    assert sanitize_layer_name("") == "0"
    # Class names should not contain invalid CSS characters
    for name in ["0", "Muri", "STATO DI FATTO", "A/B:C.D#E*F"]:
        clean = sanitize_layer_name(name)
        assert re.match(r"^[a-zA-Z0-9_\-]+$", clean)


def test_render_empty_drawing():
    """Verify renderer handles empty DXF drawing gracefully."""
    doc = ezdxf.new()
    empty_model = CadModel(
        file_path="empty.dxf",
        dxf_doc=doc,
        extents=(0.0, 0.0, 0.0, 0.0),
    )
    svg = render_to_svg(empty_model, dark_mode=True, force_refresh=True)
    assert "<svg" in svg
    assert "</svg>" in svg
    assert "cad-layer" in svg
