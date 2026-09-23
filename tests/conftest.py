import os
import shutil
import subprocess
import tempfile
import pytest

pytest_plugins = ["nicegui.testing.user_plugin"]


def find_dwgwrite() -> str | None:
    """Locate LibreDWG dwgwrite or dxf2dwg executable."""
    for tool in ("dwgwrite", "dxf2dwg"):
        path = shutil.which(tool)
        if path:
            return path
        conda_paths = [
            f"/opt/miniconda3/envs/cad_env/bin/{tool}",
            os.path.expanduser(f"~/miniconda3/envs/cad_env/bin/{tool}"),
        ]
        for p in conda_paths:
            if os.path.isfile(p) and os.access(p, os.X_OK):
                return p
    return None


def generate_test_dxf(target_dxf_path: str) -> None:
    """Generate a clean synthetic DXF with layers and geometry expected by tests."""
    import ezdxf

    doc = ezdxf.new("R2000")
    msp = doc.modelspace()
    test_layers = [
        ("0", 7),
        ("STATO DI FATTO", 3),
        ("Muri", 1),
        ("TESTI", 2),
        ("QUOTE", 4),
        ("ARREDI", 5),
        ("IMPIANTI", 6),
        ("ALBERI - Trees", 3),
    ]
    for layer_name, color in test_layers:
        if layer_name not in doc.layers:
            doc.layers.add(layer_name, color=color)

    # Geometry matching the extents expected by test suite:
    # min_x < 3700 and max_x > 3900; min_y < 1600 and max_y > 1700
    msp.add_line((3650.0, 1530.0), (3950.0, 1760.0), dxfattribs={"layer": "Muri"})
    msp.add_line((3678.5, 1724.0), (3910.5, 1755.0), dxfattribs={"layer": "STATO DI FATTO"})
    msp.add_text("Testo Tavola 1", dxfattribs={"layer": "TESTI"}).set_placement((3700.0, 1730.0))
    msp.add_line((3678.5, 1673.5), (3928.0, 1717.0), dxfattribs={"layer": "Muri"})
    msp.add_line((3678.5, 1624.0), (3928.0, 1667.2), dxfattribs={"layer": "QUOTE"})
    msp.add_line((3677.0, 1535.8), (3759.0, 1579.2), dxfattribs={"layer": "ARREDI"})
    msp.add_line((3700.0, 1600.0), (3720.0, 1620.0), dxfattribs={"layer": "ALBERI - Trees"})

    doc.saveas(target_dxf_path)


def generate_test_dwg(target_dwg_path: str, source_dxf_path: str) -> None:
    """Convert synthetic DXF to DWG using LibreDWG dwgwrite or dxf2dwg."""
    tool = find_dwgwrite()
    if not tool:
        raise RuntimeError("Neither dwgwrite nor dxf2dwg found to create test DWG file.")
    if "dwgwrite" in os.path.basename(tool):
        cmd = [tool, "-y", "-o", target_dwg_path, source_dxf_path]
    else:
        cmd = [tool, "-o", target_dwg_path, source_dxf_path]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Failed to generate test DWG ({res.returncode}): {res.stderr}")


@pytest.fixture(autouse=True, scope="session")
def ensure_test_cad_files():
    """Ensure test CAD files exist for test fixtures by creating temporary DWG/DXF files."""
    created_links = []
    tmp_dir = None

    if not os.path.exists("Tavole.dwg") or not os.path.exists("Tavole.dxf"):
        tmp_dir = tempfile.mkdtemp(prefix="cad_viewer_test_")
        tmp_dxf = os.path.join(tmp_dir, "Tavole.dxf")
        tmp_dwg = os.path.join(tmp_dir, "Tavole.dwg")
        generate_test_dxf(tmp_dxf)
        generate_test_dwg(tmp_dwg, tmp_dxf)

        if not os.path.exists("Tavole.dwg"):
            os.symlink(tmp_dwg, "Tavole.dwg")
            created_links.append("Tavole.dwg")
        if not os.path.exists("Tavole.dxf"):
            os.symlink(tmp_dxf, "Tavole.dxf")
            created_links.append("Tavole.dxf")

    try:
        yield
    finally:
        for link in created_links:
            if os.path.islink(link):
                try:
                    os.unlink(link)
                except OSError:
                    pass
            elif os.path.isfile(link):
                try:
                    os.remove(link)
                except OSError:
                    pass
        if tmp_dir and os.path.exists(tmp_dir):
            try:
                shutil.rmtree(tmp_dir)
            except OSError:
                pass

