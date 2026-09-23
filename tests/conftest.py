import os
import pytest

pytest_plugins = ["nicegui.testing.user_plugin"]


@pytest.fixture(autouse=True, scope="session")
def ensure_test_cad_files():
    """Ensure test CAD files exist for test fixtures by creating temporary symlinks if needed."""
    created_links = []
    if not os.path.exists("Tavole.dwg") and os.path.exists("sTavole.dwg"):
        os.symlink("sTavole.dwg", "Tavole.dwg")
        created_links.append("Tavole.dwg")
    if not os.path.exists("Tavole.dxf") and os.path.exists("sTavole.dxf"):
        os.symlink("sTavole.dxf", "Tavole.dxf")
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

