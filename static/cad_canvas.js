/**
 * CAD Canvas & Panzoom Integration Script for DWG Viewer
 * Provides 60 FPS smooth pan, cursor wheel zoom, Tavole bounding-box framing,
 * instantaneous CSS layer toggling, and marquee area selection with CAD coordinate transforms.
 */
(function() {
  window.cadViewer = {
    panzoom: null,
    svgW: 1000000,
    svgH: 478805,
    cadExtents: [0, 0, 1, 1],
    tavole: {},
    selectionMode: false,
    currentSelection: null,
    isDraggingSelection: false,
    dragStart: { x: 0, y: 0, clientX: 0, clientY: 0 },

    init: function(svgW, svgH, cadExtents, tavole) {
      this.svgW = svgW || 1000000;
      this.svgH = svgH || 478805;
      this.cadExtents = cadExtents || [0, 0, 1, 1];
      this.tavole = tavole || {};

      const viewport = document.getElementById('cad-viewport');
      if (!viewport) return;

      const svg = document.getElementById('cad-svg') || viewport.querySelector('svg');
      if (!svg) return;
      if (!svg.id) svg.id = 'cad-svg';

      // Ensure SVG is a direct child of the viewport so Panzoom captures all pointer events
      if (svg.parentElement && svg.parentElement !== viewport) {
        viewport.insertBefore(svg, viewport.firstChild);
      }

      svg.style.width = '100%';
      svg.style.height = '100%';
      svg.style.display = 'block';

      // Initialize Panzoom
      if (typeof Panzoom !== 'undefined') {
        if (this.panzoom) {
          try { this.panzoom.destroy(); } catch(e) {}
        }
        this.panzoom = Panzoom(svg, {
          maxScale: 60,
          minScale: 0.1,
          step: 0.25,
          canvas: true,
          cursor: 'grab',
        });

        // Wheel zoom centered on cursor
        viewport.onwheel = (e) => {
          if (!this.selectionMode && this.panzoom) {
            this.panzoom.zoomWithWheel(e);
          }
        };

        // Double click fit / reset
        viewport.ondblclick = (e) => {
          if (!this.selectionMode && this.panzoom) {
            this.panzoom.reset({ animate: true });
          }
        };
      }

      this.setupSelectionMarquee(viewport, svg);
      this.setupActionPopup();
    },

    ensureInitialized: function() {
      if (!this.panzoom) {
        if (window.__CAD_VIEWER_CONFIG__) {
          const c = window.__CAD_VIEWER_CONFIG__;
          this.init(c.svgW, c.svgH, c.cadExtents, c.tavole);
        } else {
          this.init(this.svgW, this.svgH, this.cadExtents, this.tavole);
        }
      }
    },

    initFromGlobalConfig: function() {
      if (window.__CAD_VIEWER_CONFIG__) {
        const c = window.__CAD_VIEWER_CONFIG__;
        this.init(c.svgW, c.svgH, c.cadExtents, c.tavole);
      }
    },

    zoomToTavola: function(tavolaKey) {
      this.ensureInitialized();
      if (!this.panzoom) return;
      if (tavolaKey === 'Globale') {
        const svg = document.getElementById('cad-svg');
        if (svg) svg.style.transition = 'transform 0.35s cubic-bezier(0.25, 1, 0.5, 1)';
        this.panzoom.reset({ animate: false });
        if (svg) setTimeout(() => { svg.style.transition = ''; }, 360);
        return;
      }
      const tavola = this.tavole[tavolaKey];
      if (!tavola || !tavola.bbox) return;
      this.zoomToCadBbox(tavola.bbox);
    },

    zoomToCadBbox: function(bbox) {
      const minX = bbox[0], minY = bbox[1], maxX = bbox[2], maxY = bbox[3];
      const extMinX = this.cadExtents[0], extMinY = this.cadExtents[1];
      const extMaxX = this.cadExtents[2], extMaxY = this.cadExtents[3];
      const cadW = extMaxX - extMinX;
      const cadH = extMaxY - extMinY;

      // Transform CAD bbox to SVG rect
      const sx1 = (minX - extMinX) / cadW * this.svgW;
      const sx2 = (maxX - extMinX) / cadW * this.svgW;
      const sy1 = (extMaxY - maxY) / cadH * this.svgH; // top in SVG
      const sy2 = (extMaxY - minY) / cadH * this.svgH; // bottom in SVG

      const rx = Math.min(sx1, sx2);
      const ry = Math.min(sy1, sy2);
      const rw = Math.abs(sx2 - sx1);
      const rh = Math.abs(sy2 - sy1);

      this.zoomToSvgRect(rx, ry, rw, rh);
    },

    zoomToSvgRect: function(rx, ry, rw, rh) {
      this.ensureInitialized();
      if (!this.panzoom) return;
      const viewport = document.getElementById('cad-viewport');
      if (!viewport) return;

      const cw = viewport.clientWidth;
      const ch = viewport.clientHeight;
      if (cw === 0 || ch === 0) return;

      const scaleFactor = Math.min(cw / this.svgW, ch / this.svgH);
      const renderedW = this.svgW * scaleFactor;
      const renderedH = this.svgH * scaleFactor;
      const offsetX = (cw - renderedW) / 2;
      const offsetY = (ch - renderedH) / 2;

      // Target box in unscaled container coordinates
      const boxW = Math.max(rw * scaleFactor, 10);
      const boxH = Math.max(rh * scaleFactor, 10);
      const boxCX = offsetX + (rx + rw / 2) * scaleFactor;
      const boxCY = offsetY + (ry + rh / 2) * scaleFactor;

      const targetScale = Math.min((cw * 0.92) / boxW, (ch * 0.92) / boxH);
      const panX = cw / 2 - boxCX;
      const panY = ch / 2 - boxCY;

      const svg = document.getElementById('cad-svg') || viewport.querySelector('svg');
      if (svg) {
        svg.style.transition = 'transform 0.35s cubic-bezier(0.25, 1, 0.5, 1)';
        this.panzoom.zoom(targetScale, { animate: false });
        this.panzoom.pan(panX, panY, { animate: false });
        setTimeout(() => {
          if (svg) svg.style.transition = '';
        }, 360);
      } else {
        this.panzoom.zoom(targetScale, { animate: true });
        this.panzoom.pan(panX, panY, { animate: true });
      }
    },

    zoomIn: function() {
      this.ensureInitialized();
      if (this.panzoom) this.panzoom.zoomIn({ animate: true });
    },

    zoomOut: function() {
      this.ensureInitialized();
      if (this.panzoom) this.panzoom.zoomOut({ animate: true });
    },

    reset: function() {
      this.ensureInitialized();
      if (this.panzoom) this.panzoom.reset({ animate: true });
    },

    setTheme: function(isDark) {
      const vp = document.getElementById('cad-viewport');
      if (!vp) return;
      if (isDark) {
        vp.classList.remove('theme-light');
        vp.style.backgroundColor = '#12151b';
      } else {
        vp.classList.add('theme-light');
        vp.style.backgroundColor = '#f1f5f9';
      }
    },

    toggleLayerVisibility: function(cleanName, isVisible) {
      // 1. Direct DOM manipulation on matching layer groups
      const selector = `.layer-${cleanName}, [data-layer="${cleanName}"]`;
      const elements = document.querySelectorAll(selector);
      elements.forEach(function(el) {
        if (isVisible) {
          el.classList.remove('hidden');
          el.style.display = '';
        } else {
          el.classList.add('hidden');
          el.style.display = 'none';
        }
      });

      // 2. Dynamic stylesheet rule fallback
      let styleTag = document.getElementById('cad-dynamic-layer-styles');
      if (!styleTag) {
        styleTag = document.createElement('style');
        styleTag.id = 'cad-dynamic-layer-styles';
        document.head.appendChild(styleTag);
      }
      const rule = `.layer-${cleanName} { display: none !important; }`;
      let text = styleTag.textContent || '';
      if (!isVisible) {
        if (!text.includes(rule)) {
          styleTag.textContent = (text + '\n' + rule).trim();
        }
      } else {
        styleTag.textContent = text.replaceAll(rule, '').trim();
      }
    },

    hideAllLayers: function() {
      document.querySelectorAll('.cad-layer').forEach(function(el) {
        el.classList.add('hidden');
        el.style.display = 'none';
      });
      let styleTag = document.getElementById('cad-dynamic-layer-styles');
      if (!styleTag) {
        styleTag = document.createElement('style');
        styleTag.id = 'cad-dynamic-layer-styles';
        document.head.appendChild(styleTag);
      }
      styleTag.textContent = '.cad-layer { display: none !important; }';
    },

    showAllLayers: function() {
      document.querySelectorAll('.cad-layer').forEach(function(el) {
        el.classList.remove('hidden');
        el.style.display = '';
      });
      const styleTag = document.getElementById('cad-dynamic-layer-styles');
      if (styleTag) {
        styleTag.textContent = '';
      }
    },

    setSelectionMode: function(active) {
      this.selectionMode = !!active;
      const viewport = document.getElementById('cad-viewport');
      if (viewport) {
        viewport.style.cursor = this.selectionMode ? 'crosshair' : 'default';
      }
      if (this.panzoom) {
        this.panzoom.setOptions({ disablePan: this.selectionMode });
      }
      if (!this.selectionMode) {
        this.clearSelection();
      }
    },

    clearSelection: function() {
      const box = document.getElementById('cad-selection-box');
      if (box) box.style.display = 'none';
      const popup = document.getElementById('cad-selection-popup');
      if (popup) popup.style.display = 'none';
      this.currentSelection = null;
    },

    setupActionPopup: function() {
      const btnZoom = document.getElementById('btn-zoom-selection');
      const btnExport = document.getElementById('btn-export-selection');
      const btnClose = document.getElementById('btn-close-selection');

      if (btnZoom) {
        btnZoom.onclick = () => {
          if (this.currentSelection && this.currentSelection.svg_rect) {
            const r = this.currentSelection.svg_rect;
            this.zoomToSvgRect(r.x, r.y, r.width, r.height);
          }
        };
      }

      if (btnExport) {
        btnExport.onclick = () => {
          if (this.currentSelection && this.currentSelection.cad_bbox) {
            // Trigger custom event or NiceGUI backend callback
            const bbox = this.currentSelection.cad_bbox;
            const inputEl = document.getElementById('cad-selected-bbox-input');
            if (inputEl) {
              inputEl.value = JSON.stringify(bbox);
              inputEl.dispatchEvent(new Event('change', { bubbles: true }));
            }
            const exportBtn = document.getElementById('btn-trigger-bbox-pdf');
            if (exportBtn) exportBtn.click();
          }
        };
      }

      if (btnClose) {
        btnClose.onclick = () => {
          this.clearSelection();
        };
      }
    },

    setupSelectionMarquee: function(viewport, svg) {
      const box = document.getElementById('cad-selection-box');
      const popup = document.getElementById('cad-selection-popup');

      viewport.addEventListener('mousedown', (e) => {
        if (!this.selectionMode || e.button !== 0) return;
        if (popup && popup.contains(e.target)) return;

        this.isDraggingSelection = true;
        const rect = viewport.getBoundingClientRect();
        this.dragStart = {
          x: e.clientX - rect.left,
          y: e.clientY - rect.top,
          clientX: e.clientX,
          clientY: e.clientY,
        };

        if (box) {
          box.style.left = `${this.dragStart.x}px`;
          box.style.top = `${this.dragStart.y}px`;
          box.style.width = '0px';
          box.style.height = '0px';
          box.style.display = 'block';
        }
        if (popup) popup.style.display = 'none';
      });

      window.addEventListener('mousemove', (e) => {
        if (!this.selectionMode || !this.isDraggingSelection) return;
        const rect = viewport.getBoundingClientRect();
        const curX = e.clientX - rect.left;
        const curY = e.clientY - rect.top;

        const left = Math.min(curX, this.dragStart.x);
        const top = Math.min(curY, this.dragStart.y);
        const width = Math.abs(curX - this.dragStart.x);
        const height = Math.abs(curY - this.dragStart.y);

        if (box) {
          box.style.left = `${left}px`;
          box.style.top = `${top}px`;
          box.style.width = `${width}px`;
          box.style.height = `${height}px`;
        }
      });

      window.addEventListener('mouseup', (e) => {
        if (!this.selectionMode || !this.isDraggingSelection) return;
        this.isDraggingSelection = false;

        const rect = viewport.getBoundingClientRect();
        const curX = e.clientX - rect.left;
        const curY = e.clientY - rect.top;
        const width = Math.abs(curX - this.dragStart.x);
        const height = Math.abs(curY - this.dragStart.y);

        if (width < 10 || height < 10) {
          if (box) box.style.display = 'none';
          return;
        }

        try {
          const pt1 = svg.createSVGPoint();
          pt1.x = this.dragStart.clientX;
          pt1.y = this.dragStart.clientY;
          const svgPt1 = pt1.matrixTransform(svg.getScreenCTM().inverse());

          const pt2 = svg.createSVGPoint();
          pt2.x = e.clientX;
          pt2.y = e.clientY;
          const svgPt2 = pt2.matrixTransform(svg.getScreenCTM().inverse());

          const svgRx = Math.min(svgPt1.x, svgPt2.x);
          const svgRy = Math.min(svgPt1.y, svgPt2.y);
          const svgRw = Math.abs(svgPt2.x - svgPt1.x);
          const svgRh = Math.abs(svgPt2.y - svgPt1.y);

          const extMinX = this.cadExtents[0], extMinY = this.cadExtents[1];
          const extMaxX = this.cadExtents[2], extMaxY = this.cadExtents[3];
          const cadW = extMaxX - extMinX;
          const cadH = extMaxY - extMinY;

          const cadX1 = extMinX + (svgRx / this.svgW) * cadW;
          const cadX2 = extMinX + ((svgRx + svgRw) / this.svgW) * cadW;
          const cadY1 = extMaxY - ((svgRy + svgRh) / this.svgH) * cadH;
          const cadY2 = extMaxY - (svgRy / this.svgH) * cadH;

          const cadBbox = [
            Math.min(cadX1, cadX2),
            Math.min(cadY1, cadY2),
            Math.max(cadX1, cadX2),
            Math.max(cadY1, cadY2)
          ];

          this.currentSelection = {
            svg_rect: { x: svgRx, y: svgRy, width: svgRw, height: svgRh },
            cad_bbox: cadBbox,
          };

          if (popup) {
            const popupLeft = Math.max(10, Math.min(viewport.clientWidth - 280, Math.min(curX, this.dragStart.x)));
            const popupTop = Math.max(10, Math.min(curY, this.dragStart.y) - 50);
            popup.style.left = `${popupLeft}px`;
            popup.style.top = `${popupTop}px`;
            popup.style.display = 'flex';
          }

          const inputEl = document.getElementById('cad-selected-bbox-input');
          if (inputEl) {
            inputEl.value = JSON.stringify(cadBbox);
            inputEl.dispatchEvent(new Event('change', { bubbles: true }));
          }
        } catch (err) {
          console.error('Error calculating selection coords:', err);
        }
      });
    }
  };

  // Auto-init on script load if global config is already available or poll for it
  function autoInitCheck(attempts) {
    if (window.__CAD_VIEWER_CONFIG__ && typeof Panzoom !== 'undefined') {
      const vp = document.getElementById('cad-viewport');
      if (vp) {
        window.cadViewer.initFromGlobalConfig();
        return;
      }
    }
    if (attempts < 120) {
      setTimeout(function() { autoInitCheck(attempts + 1); }, 50);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() { autoInitCheck(0); });
  } else {
    autoInitCheck(0);
  }
})();
