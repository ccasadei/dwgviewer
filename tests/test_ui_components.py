import os
import pytest
from cad_engine import load_cad_file
from ui_components import (
    format_layer_data,
    get_tavole_options,
    cad_bbox_to_svg_rect,
    svg_rect_to_cad_bbox,
    generate_layer_toggle_css,
    CadViewerState,
)


def test_ui_helpers():
    """Step 1 required test: format_layer_data and get_tavole_options."""
    model = load_cad_file("Tavole.dwg")
    layers_data = format_layer_data(model.layers)
    assert len(layers_data) > 0
    assert "name" in layers_data[0]
    assert "color" in layers_data[0]

    tavole_opts = get_tavole_options(model)
    assert "Tavola 1" in tavole_opts
    assert "Tavola 4" in tavole_opts


def test_format_layer_data_structure():
    """Verify detailed structure and properties of formatted layer data."""
    model = load_cad_file("Tavole.dwg")
    layers_data = format_layer_data(model.layers)
    assert len(layers_data) == len(model.layers)

    for item in layers_data:
        assert "name" in item
        assert "clean_name" in item
        assert "color" in item
        assert "count" in item
        assert "visible" in item
        assert isinstance(item["visible"], bool)
        assert isinstance(item["count"], int)
        assert item["clean_name"] != ""


def test_get_tavole_options():
    """Verify get_tavole_options includes all detected sheets and global view."""
    model = load_cad_file("Tavole.dwg")
    opts = get_tavole_options(model)

    assert "Globale" in opts
    assert "Tavola 1" in opts
    assert "Tavola 2" in opts
    assert "Tavola 3" in opts
    assert "Tavola 4" in opts

    for name in ["Tavola 1", "Tavola 2", "Tavola 3", "Tavola 4", "Globale"]:
        info = opts[name]
        assert "title" in info
        assert "bbox" in info
        bbox = info["bbox"]
        assert len(bbox) == 4
        assert bbox[0] < bbox[2]  # min_x < max_x
        assert bbox[1] < bbox[3]  # min_y < max_y


def test_cad_to_svg_coordinate_mapping():
    """Test coordinate transformations between CAD space and SVG viewBox space."""
    model = load_cad_file("Tavole.dwg")
    cad_bbox = model.extents
    svg_bounds = (0.0, 0.0, 1000000.0, 478805.0)

    # 1. Map whole model extent to SVG
    svg_rect = cad_bbox_to_svg_rect(cad_bbox, model.extents, svg_bounds)
    assert abs(svg_rect["x"]) < 1.0
    assert abs(svg_rect["y"]) < 1.0
    assert abs(svg_rect["width"] - 1000000.0) < 1.0
    assert abs(svg_rect["height"] - 478805.0) < 1.0

    # 2. Round-trip mapping: SVG rect back to CAD bbox
    recovered_cad = svg_rect_to_cad_bbox(svg_rect, model.extents, svg_bounds)
    for c_orig, c_rec in zip(cad_bbox, recovered_cad):
        assert abs(c_orig - c_rec) < 1e-2

    # 3. Map Tavola 1 to SVG rect
    t1 = model.tavole["Tavola 1"]
    t1_svg = cad_bbox_to_svg_rect(t1.bbox, model.extents, svg_bounds)
    assert t1_svg["x"] > 0
    assert abs(t1_svg["y"]) < 50000.0  # Near top margin of SVG canvas
    assert t1_svg["width"] > 0
    assert t1_svg["height"] > 0

    recovered_t1 = svg_rect_to_cad_bbox(t1_svg, model.extents, svg_bounds)
    for c_orig, c_rec in zip(t1.bbox, recovered_t1):
        assert abs(c_orig - c_rec) < 1e-2


def test_viewer_state_management():
    """Test state management container for CAD viewer."""
    model = load_cad_file("Tavole.dwg")
    state = CadViewerState(model=model)

    assert state.active_tavola == "Globale"
    assert state.dark_mode is True
    assert len(state.visible_layers) == len(model.layers)
    assert state.selection_active is False
    assert state.selected_bbox is None

    # Change active tavola
    state.set_active_tavola("Tavola 1")
    assert state.active_tavola == "Tavola 1"

    # Layer toggles
    first_layer = model.layers[0].name
    state.toggle_layer(first_layer, False)
    assert first_layer not in state.visible_layers
    state.toggle_layer(first_layer, True)
    assert first_layer in state.visible_layers

    # Hide all and show all
    state.hide_all_layers()
    assert len(state.visible_layers) == 0
    state.show_all_layers()
    assert len(state.visible_layers) == len(model.layers)

    # Theme toggle
    state.toggle_dark_mode()
    assert state.dark_mode is False
    state.toggle_dark_mode()
    assert state.dark_mode is True


def test_generate_layer_css():
    """Test generating dynamic CSS for hiding inactive layers."""
    css = generate_layer_toggle_css(["Muri", "STATO_DI_FATTO"])
    assert ".layer-Muri" in css
    assert "display: none !important" in css
    assert ".layer-STATO_DI_FATTO" in css

    empty_css = generate_layer_toggle_css([])
    assert empty_css == ""


def test_pdf_export_service(tmp_path):
    """Test PDF export service methods from CadViewerState."""
    model = load_cad_file("Tavole.dwg")
    state = CadViewerState(model=model)
    out_dir = str(tmp_path)

    # Export current tavola
    state.set_active_tavola("Tavola 1")
    pdf_path = state.export_pdf(mode="current", output_dir=out_dir)
    assert os.path.exists(pdf_path)
    assert os.path.getsize(pdf_path) > 1000

    # Export custom selection bbox
    custom_box = (3700.0, 1600.0, 3800.0, 1700.0)
    pdf_custom = state.export_pdf(mode="custom", bbox=custom_box, output_dir=out_dir)
    assert os.path.exists(pdf_custom)
    assert os.path.getsize(pdf_custom) > 1000

    # Export all tavole
    pdf_multi = state.export_pdf(mode="all_tavole", output_dir=out_dir)
    assert os.path.exists(pdf_multi)
    assert os.path.getsize(pdf_multi) > 1000


def test_extract_svg_viewbox():
    """Test extracting viewBox dimensions from SVG content."""
    from ui_components import extract_svg_viewbox
    vb = extract_svg_viewbox('<svg viewBox="0 0 1000000 478805"></svg>')
    assert vb == (0.0, 0.0, 1000000.0, 478805.0)

    # Fallback default viewBox
    fallback = extract_svg_viewbox('<svg></svg>')
    assert len(fallback) == 4
    assert fallback[2] > 0 and fallback[3] > 0


def test_export_pdf_error_handling(tmp_path):
    """Test invalid export modes and missing bbox errors."""
    model = load_cad_file("Tavole.dwg")
    state = CadViewerState(model=model)
    out_dir = str(tmp_path)

    with pytest.raises(ValueError, match="Unknown PDF export mode"):
        state.export_pdf(mode="nonexistent_mode", output_dir=out_dir)

    with pytest.raises(ValueError, match="No bounding box provided"):
        state.export_pdf(mode="custom", bbox=None, output_dir=out_dir)


def test_ui_components_page_construction():
    """Verify that all NiceGUI CAD UI components can be instantiated without runtime errors."""
    from nicegui import ui
    from renderer import render_to_svg
    from ui_components import (
        create_header,
        create_canvas,
        create_layer_drawer,
        create_export_dialog,
    )

    model = load_cad_file("Tavole.dwg")
    state = CadViewerState(model=model)
    svg_content = render_to_svg(model)

    @ui.page('/test_cad_page')
    def page():
        create_header(state)
        create_canvas(state, svg_content)
        create_layer_drawer(state)
        create_export_dialog(state)

    assert callable(page)

