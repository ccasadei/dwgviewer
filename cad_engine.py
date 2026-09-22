import os
import shutil


def find_dwg2dxf() -> str | None:
    path = shutil.which("dwg2dxf")
    if path:
        return path
    conda_paths = [
        "/opt/miniconda3/envs/cad_env/bin/dwg2dxf",
        os.path.expanduser("~/miniconda3/envs/cad_env/bin/dwg2dxf"),
    ]
    for p in conda_paths:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None
