import os
import ezdxf
import pytest
from cad_engine import (
    CadModel,
    convert_dwg_to_dxf,
    load_cad_file,
)


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


def test_tavole_definitions():
    dwg_path = "Tavole.dwg"
    model = load_cad_file(dwg_path)

    # Verify Tavola titles and coordinate bounds
    t1 = model.tavole["Tavola 1"]
    assert "Prospetti" in t1.title
    assert t1.bbox == (3678.5, 1724.0, 3910.5, 1755.0)

    t2 = model.tavole["Tavola 2"]
    assert "Planimetria" in t2.title
    assert t2.bbox == (3678.5, 1673.5, 3928.0, 1717.0)

    t3 = model.tavole["Tavola 3"]
    assert "Variante" in t3.title
    assert t3.bbox == (3678.5, 1624.0, 3928.0, 1667.2)

    t4 = model.tavole["Tavola 4"]
    assert "Servoscala" in t4.title
    assert t4.bbox == (3677.0, 1535.8, 3759.0, 1579.2)

    tg = model.tavole["Globale"]
    # Globale must encompass full extents with 2% margin
    min_x, min_y, max_x, max_y = model.extents
    assert tg.bbox[0] < min_x
    assert tg.bbox[1] < min_y
    assert tg.bbox[2] > max_x
    assert tg.bbox[3] > max_y


def test_layer_info_properties():
    dwg_path = "Tavole.dwg"
    model = load_cad_file(dwg_path)

    assert len(model.layers) > 0
    muri_layer = next((l for l in model.layers if l.name == "Muri"), None)
    assert muri_layer is not None
    assert muri_layer.count > 0
    assert muri_layer.entity_count == muri_layer.count
    assert muri_layer.color.startswith("#")
    assert isinstance(muri_layer.color_aci, int)


def test_load_dxf_direct(tmp_path):
    dxf_file = str(tmp_path / "test_sample.dxf")
    doc = ezdxf.new("R2000")
    doc.layers.add("CUSTOM_LAYER", color=1)  # Red
    msp = doc.modelspace()
    msp.add_line((0, 0), (100, 200), dxfattribs={"layer": "CUSTOM_LAYER"})
    doc.saveas(dxf_file)

    model = load_cad_file(dxf_file)
    assert isinstance(model, CadModel)
    assert model.dxf_doc is not None
    assert "Globale" in model.tavole
    layer_names = [l.name for l in model.layers]
    assert "CUSTOM_LAYER" in layer_names
    custom_layer = next(l for l in model.layers if l.name == "CUSTOM_LAYER")
    assert custom_layer.count == 1
    assert custom_layer.color == "#ff0000"


def test_dwg_caching(tmp_path):
    dwg_path = "Tavole.dwg"
    custom_cache = str(tmp_path / "cache")
    
    # First conversion creates cached DXF
    cached_dxf = convert_dwg_to_dxf(dwg_path, cache_dir=custom_cache)
    assert os.path.exists(cached_dxf)
    initial_mtime = os.path.getmtime(cached_dxf)

    # Second call should reuse cached DXF without rewriting
    cached_dxf_2 = convert_dwg_to_dxf(dwg_path, cache_dir=custom_cache)
    assert cached_dxf == cached_dxf_2
    assert os.path.getmtime(cached_dxf_2) == initial_mtime


def test_load_nonexistent_file():
    with pytest.raises(FileNotFoundError):
        load_cad_file("nonexistent_drawing.dwg")


def test_invalid_extension():
    with pytest.raises(ValueError, match="Unsupported file format"):
        load_cad_file("drawing.txt")
