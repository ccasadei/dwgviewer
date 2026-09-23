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
