"""Vector SVG Renderer with Client-Side Layer Tagging for CAD drawings."""

import os
import re
from xml.etree import ElementTree as ET
from typing import Optional

from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.config import BackgroundPolicy, ColorPolicy, Configuration
from ezdxf.addons.drawing.layout import Page, Settings
from ezdxf.addons.drawing.properties import BackendProperties, LayoutProperties
from ezdxf.addons.drawing.svg import SVGBackend, SVGRenderBackend

from cad_engine import CadModel

DARK_BG_COLOR = "#12151b"
LIGHT_BG_COLOR = "#ffffff"


def sanitize_layer_name(name: str) -> str:
    """Sanitize CAD layer name for use in CSS class names."""
    if not name:
        return "0"
    # Replace any character other than ASCII alphanumeric, underscore, or hyphen with underscore
    cleaned = re.sub(r"[^a-zA-Z0-9_\-]", "_", name.strip())
    cleaned = re.sub(r"_+", "_", cleaned)
    return cleaned.strip("_") or "0"


def get_svg_cache_path(file_path: str, dark_mode: bool, cache_dir: str = ".cache") -> str:
    """Generate deterministic cache file path based on source file name and theme."""
    base_name = os.path.splitext(os.path.basename(file_path))[0] or "drawing"
    theme_suffix = "dark" if dark_mode else "light"
    return os.path.join(cache_dir, f"{base_name}_{theme_suffix}.svg")


def is_cache_valid(cache_path: str, source_files: list[str]) -> bool:
    """Check if cache file exists and is strictly newer than all source files."""
    if not os.path.exists(cache_path) or os.path.getsize(cache_path) == 0:
        return False
    try:
        cache_mtime = os.path.getmtime(cache_path)
        for src in source_files:
            if src and os.path.exists(src):
                if cache_mtime < os.path.getmtime(src):
                    return False
        return True
    except OSError:
        return False


class LayerTaggedSVGRenderBackend(SVGRenderBackend):
    """Custom SVGRenderBackend that wraps entities into per-layer <g> groups."""

    def __init__(
        self,
        page: Page,
        settings: Settings,
        dark_mode: bool = True,
        initial_layers: Optional[list[str]] = None,
    ) -> None:
        super().__init__(page, settings)
        self.dark_mode = dark_mode
        self.layer_groups: dict[str, ET.Element] = {}

        bg_color = DARK_BG_COLOR if dark_mode else LIGHT_BG_COLOR
        self.set_background(bg_color)

        # Enhance background rect with ID and class for CSS targeting
        self.background.set("id", "cad-background")
        self.background.set("class", "cad-background")

        # Set root SVG styling and attributes
        theme_name = "dark" if dark_mode else "light"
        self.root.set("data-theme", theme_name)
        self.root.set("class", f"cad-svg cad-theme-{theme_name}")
        self.root.set("style", f"background-color: {bg_color};")

        # Inject custom CSS styles for CAD layers and themes
        defs = self.root.find("defs")
        if defs is None:
            defs = ET.SubElement(self.root, "defs")
        style_elem = ET.SubElement(defs, "style")
        style_elem.set("id", "cad-custom-styles")
        style_elem.text = (
            f"\n  :root {{\n"
            f"    --cad-bg: {bg_color};\n"
            f"  }}\n"
            f"  svg.cad-svg {{\n"
            f"    background-color: {bg_color};\n"
            f"  }}\n"
            f"  .cad-background {{\n"
            f"    pointer-events: none;\n"
            f"  }}\n"
            f"  .cad-layer {{\n"
            f"    display: inline;\n"
            f"  }}\n"
            f"  .cad-layer.hidden {{\n"
            f"    display: none !important;\n"
            f"  }}\n"
        )

        # Pre-populate layer groups if known
        if initial_layers:
            for layer_name in initial_layers:
                self.get_or_create_layer_group(layer_name)

    def get_or_create_layer_group(self, layer_name: str) -> ET.Element:
        """Retrieve existing or create new <g> group for the specified layer."""
        clean_name = sanitize_layer_name(layer_name)
        if clean_name not in self.layer_groups:
            group = ET.SubElement(
                self.entities,
                "g",
                attrib={
                    "class": f"cad-layer layer-{clean_name}",
                    "data-layer": layer_name,
                },
            )
            self.layer_groups[clean_name] = group
        return self.layer_groups[clean_name]

    def add_strokes(self, d: str, properties: BackendProperties) -> None:
        """Add stroked path inside the entity's layer group."""
        if not d:
            return
        group = self.get_or_create_layer_group(properties.layer)
        element = ET.SubElement(group, "path", d=d)
        stroke_width = self.resolve_stroke_width(properties.lineweight)
        stroke_color, stroke_opacity = self.resolve_color(properties.color)

        # Ensure high-contrast strokes against theme background
        if self.dark_mode and stroke_color.lower() in ("#000000", "#12151b"):
            stroke_color = "#ffffff"
        elif not self.dark_mode and stroke_color.lower() in ("#ffffff", "#fefefe"):
            stroke_color = "#000000"

        cls = self.styles.get_class(
            stroke=stroke_color,
            stroke_width=stroke_width,
            stroke_opacity=stroke_opacity,
        )
        element.set("class", cls)

    def add_filling(self, d: str, properties: BackendProperties) -> None:
        """Add filled path inside the entity's layer group."""
        if not d:
            return
        group = self.get_or_create_layer_group(properties.layer)
        element = ET.SubElement(group, "path", d=d)
        fill_color, fill_opacity = self.resolve_color(properties.color)

        # Ensure high-contrast fills against theme background
        if self.dark_mode and fill_color.lower() in ("#000000", "#12151b"):
            fill_color = "#ffffff"
        elif not self.dark_mode and fill_color.lower() in ("#ffffff", "#fefefe"):
            fill_color = "#000000"

        cls = self.styles.get_class(fill=fill_color, fill_opacity=fill_opacity)
        element.set("class", cls)


class LayerTaggedSVGBackend(SVGBackend):
    """Custom SVGBackend that supplies LayerTaggedSVGRenderBackend."""

    def __init__(
        self,
        dark_mode: bool = True,
        initial_layers: Optional[list[str]] = None,
    ) -> None:
        super().__init__()
        self.dark_mode = dark_mode
        self.initial_layers = initial_layers or []

    def make_backend(self, page: Page, settings: Settings) -> LayerTaggedSVGRenderBackend:
        return LayerTaggedSVGRenderBackend(
            page,
            settings,
            dark_mode=self.dark_mode,
            initial_layers=self.initial_layers,
        )


def render_to_svg(
    cad_model: CadModel,
    dark_mode: bool = True,
    cache_dir: str = ".cache",
    force_refresh: bool = False,
) -> str:
    """Render CadModel ModelSpace to a vector SVG string with per-layer tagging and caching."""
    cache_file = get_svg_cache_path(cad_model.file_path, dark_mode=dark_mode, cache_dir=cache_dir)
    source_files = [cad_model.file_path]
    dxf_filename = getattr(cad_model.dxf_doc, "filename", None)
    if dxf_filename and dxf_filename != cad_model.file_path:
        source_files.append(str(dxf_filename))

    # 1. Attempt reading from cache
    if not force_refresh and is_cache_valid(cache_file, source_files):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return f.read()
        except OSError:
            pass

    # 2. Configure rendering context and theme policies
    bg_color = DARK_BG_COLOR if dark_mode else LIGHT_BG_COLOR
    fg_color = "#ffffff" if dark_mode else "#000000"

    config = Configuration(
        background_policy=BackgroundPolicy.CUSTOM,
        custom_bg_color=bg_color,
        color_policy=ColorPolicy.COLOR if dark_mode else ColorPolicy.COLOR_SWAP_BW,
    )

    layout_props = LayoutProperties.modelspace()
    layout_props.set_colors(bg_color, fg_color)

    context = RenderContext(cad_model.dxf_doc)
    # Ensure all layers are visible so they are emitted into the SVG for CSS toggling
    for layer_prop in context.layers.values():
        layer_prop.is_visible = True

    initial_layers = [l.name for l in cad_model.layers] if cad_model.layers else []
    backend = LayerTaggedSVGBackend(dark_mode=dark_mode, initial_layers=initial_layers)

    frontend = Frontend(context, backend, config=config)
    msp = cad_model.dxf_doc.modelspace()
    frontend.draw_layout(msp, layout_properties=layout_props)

    # 3. Handle empty drawing gracefully
    if not backend.player().bbox().has_data:
        svg_content = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1000" class="cad-svg cad-theme-{"dark" if dark_mode else "light"}" style="background-color: {bg_color};">\n'
            f'  <defs>\n'
            f'    <style id="cad-custom-styles">\n'
            f'      .cad-layer {{ display: inline; }}\n'
            f'      .cad-layer.hidden {{ display: none !important; }}\n'
            f'    </style>\n'
            f'  </defs>\n'
            f'  <rect width="1000" height="1000" fill="{bg_color}" class="cad-background" id="cad-background"/>\n'
            f'  <g class="cad-layer layer-0" data-layer="0"></g>\n'
            f'</svg>'
        )
    else:
        # Auto-detect page dimensions from content bounding box
        page = Page(0, 0)
        svg_content = backend.get_string(page)

    # 4. Save to cache
    try:
        os.makedirs(cache_dir, exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            f.write(svg_content)
    except OSError:
        pass

    return svg_content
