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
    create_header,
    create_canvas,
    create_floating_hud,
    create_layer_drawer,
    create_export_dialog,
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
    """Verify that all NiceGUI CAD UI components can be instantiated directly without runtime errors."""
    from nicegui import Client, ui
    from renderer import render_to_svg
    from ui_components import (
        create_canvas,
        create_export_dialog,
        create_floating_hud,
        create_header,
        create_layer_drawer,
    )

    model = load_cad_file("Tavole.dwg")
    state = CadViewerState(model=model)
    svg_content = render_to_svg(model)

    with Client(ui.page("/test_page")):
        # 1. Header and quick-navigation chips
        header, chips = create_header(state)
        assert header is not None
        assert "Globale" in chips
        assert "Tavola 1" in chips
        assert "Tavola 4" in chips

        # 2. Export dialog
        dialog = create_export_dialog(state)
        assert dialog is not None
        assert hasattr(dialog, "mode_radio")

        # 3. Canvas container with embedded SVG and dialog reference
        canvas = create_canvas(state, svg_content, export_dialog=dialog)
        assert canvas is not None

        # 4. Layer drawer
        drawer = create_layer_drawer(state)
        assert drawer is not None


def test_export_dialog_dynamic_options():
    """Verify export dialog refreshes options dynamically when tavola or custom bbox changes."""
    from nicegui import Client, ui

    model = load_cad_file("Tavole.dwg")
    state = CadViewerState(model=model)

    with Client(ui.page("/test_dialog")):
        dialog = create_export_dialog(state)

        # Initially no custom area
        assert "custom" not in dialog.mode_radio.options
        assert "all_tavole" in dialog.mode_radio.options
        assert "Tavola Corrente (Globale)" in dialog.mode_radio.options["current"]

        # Change active tavola -> label for current should update
        state.set_active_tavola("Tavola 2")
        assert "Tavola Corrente (Tavola 2)" in dialog.mode_radio.options["current"]

        # Select custom bbox -> should dynamically add 'custom' option and select it
        custom_box = (3700.0, 1600.0, 3800.0, 1700.0)
        state.set_selected_bbox(custom_box)
        assert "custom" in dialog.mode_radio.options
        assert dialog.mode_radio.value == "custom"
        assert "Area Selezionata" in dialog.mode_radio.options["custom"]

        # Clear custom bbox -> should remove 'custom' option and fall back
        state.set_selected_bbox(None)
        assert "custom" not in dialog.mode_radio.options
        assert dialog.mode_radio.value == "current"


def test_theme_toggle_handler():
    """Verify theme toggle properly flips state and button icon."""
    from nicegui import Client, ui
    from ui_components import _handle_theme_toggle

    model = load_cad_file("Tavole.dwg")
    state = CadViewerState(model=model, dark_mode=True)

    with Client(ui.page("/test_theme")):
        btn = ui.button(icon="dark_mode")
        called = []

        def callback():
            called.append(True)

        _handle_theme_toggle(state, theme_btn=btn, callback=callback)
        assert not state.dark_mode
        assert btn.props.get("icon") == "light_mode"
        assert len(called) == 1

        _handle_theme_toggle(state, theme_btn=btn, callback=callback)
        assert state.dark_mode
        assert btn.props.get("icon") == "dark_mode"
        assert len(called) == 2


def test_layer_bulk_toggle_handlers():
    """Verify bulk layer toggle functions correctly modify state."""
    from nicegui import Client, ui
    from ui_components import _show_all_layers, _hide_all_layers

    model = load_cad_file("Tavole.dwg")
    state = CadViewerState(model=model)

    with Client(ui.page("/test_layer_bulk")):
        cb1 = ui.checkbox(value=True)
        cb2 = ui.checkbox(value=True)
        checkbox_refs = {"0": cb1, "A-WALL": cb2}

        # Hide all
        _hide_all_layers(state, checkbox_refs, None)
        assert not cb1.value
        assert not cb2.value
        assert len(state.visible_layers) == 0

        # Show all
        _show_all_layers(state, checkbox_refs, None)
        assert cb1.value
        assert cb2.value
        assert len(state.visible_layers) == len(model.layers)


def test_safe_run_javascript_execution():
    """Verify safe_run_javascript does not pass invalid keyword arguments to ui.run_javascript."""
    from nicegui import Client, ui
    from ui_components import safe_run_javascript

    with Client(ui.page("/test_js")):
        # Should not raise TypeError: run_javascript() got an unexpected keyword argument 'respond'
        safe_run_javascript("console.log('test');")


@pytest.mark.asyncio
async def test_save_uploaded_file():
    """Verify save_uploaded_file extracts filename and saves bytes properly."""
    from nicegui.elements.upload_files import SmallFileUpload
    from nicegui.events import UploadEventArguments
    from ui_components import save_uploaded_file

    file_item = SmallFileUpload("my_custom_plan.dxf", "application/dxf", b"DXF_TEST_DATA")
    event = UploadEventArguments(file=file_item, sender=None, client=None)
    saved = await save_uploaded_file(event, upload_dir=".cache/test_uploads")
    try:
        assert os.path.exists(saved)
        assert os.path.basename(saved) == "my_custom_plan.dxf"
        with open(saved, "rb") as f:
            assert f.read() == b"DXF_TEST_DATA"
    finally:
        if os.path.exists(saved):
            os.remove(saved)
        if os.path.exists(".cache/test_uploads"):
            os.rmdir(".cache/test_uploads")





