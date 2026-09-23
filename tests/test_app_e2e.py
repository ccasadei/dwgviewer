import pytest
from nicegui.testing import User
import main


@pytest.mark.asyncio
async def test_app_loads_and_displays_canvas(user: User):
    """Verify that opening with ?file=Tavole.dwg loads the drawing and displays CAD workspace UI."""
    await user.open("/?file=Tavole.dwg")
    # Verify header title/filename badge
    await user.should_see("Tavole.dwg")
    # Verify Tavole chips are visible
    await user.should_see("Tavola 1")
    await user.should_see("Tavola 4")
    # Verify export button is present
    await user.should_see("Stampa / PDF")


@pytest.mark.asyncio
async def test_app_first_launch_prompts_file_selection(user: User):
    """Verify that opening the home page without a file prompts file selection dialog."""
    await user.open("/")
    await user.should_see("Carica File CAD")
    await user.should_see("Nessun file aperto")
    await user.should_see("Carica file DWG / DXF")


def test_cli_argument_parsing():
    """Verify that CLI parser parses defaults and custom options correctly."""
    parser = main.build_parser()
    args = parser.parse_args([])
    assert args.file is None
    assert args.port == 8080
    assert args.host == "0.0.0.0"
    assert args.reload is False
    assert args.native is False

    custom_args = parser.parse_args([
        "--file", "sample.dwg",
        "--port", "9090",
        "--host", "127.0.0.1",
        "--reload",
        "--native",
    ])
    assert custom_args.file == "sample.dwg"
    assert custom_args.port == 9090
    assert custom_args.host == "127.0.0.1"
    assert custom_args.reload is True
    assert custom_args.native is True


@pytest.mark.asyncio
async def test_app_upload_dialog_present(user: User):
    """Verify that file upload / import option is accessible in the UI."""
    await user.open("/")
    await user.should_see("Carica")


@pytest.mark.asyncio
async def test_app_graceful_missing_file(user: User):
    """Verify that opening with a nonexistent file displays an error banner and upload interface."""
    await user.open("/?file=nonexistent_file.dwg")
    await user.should_see("non trovato")
    await user.should_see("Carica")


def test_get_cad_model_caching():
    """Verify in-memory model caching returns the cached CadModel instance."""
    m1 = main.get_cad_model("Tavole.dwg")
    m2 = main.get_cad_model("Tavole.dwg")
    assert m1 is m2


def test_get_cad_model_nonexistent():
    """Verify FileNotFoundError is raised when file does not exist."""
    with pytest.raises(FileNotFoundError):
        main.get_cad_model("nonexistent_model.dwg")

