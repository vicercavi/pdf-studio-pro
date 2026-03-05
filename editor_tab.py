# editor_tab.py  –  Editor interactivo de PDF con edición inline y estilos por span
import os
import copy
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk
import customtkinter as ctk
from PIL import Image, ImageOps, ImageTk, ImageDraw
import fitz  # PyMuPDF

try:
    from rapidocr_onnxruntime import RapidOCR
    import numpy as np
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

try:
    from tkinterdnd2 import DND_FILES
    DND_AVAILABLE = True
except Exception:
    DND_AVAILABLE = False
    DND_FILES = None

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
ZOOM_STEPS = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 4.0]

FONT_MAP = {"Helvetica": "helv", "Times Roman": "tiro", "Courier": "cour"}
FONT_DISPLAY = {"helv": "Helvetica", "tiro": "Times Roman", "cour": "Courier"}
COLOR_MAP = {
    "Negro": (0, 0, 0), "Rojo": (1, 0, 0), "Azul": (0, 0, 1),
    "Verde": (0, 0.5, 0), "Naranja": (1, 0.5, 0), "Blanco": (1, 1, 1),
}


# ── helpers ──────────────────────────────────────────────────────────
def _fit(img, mw, mh):
    w, h = img.size
    if w <= 0 or h <= 0:
        return img
    s = min(mw / w, mh / h, 1.0)
    return img.resize((max(1, int(w * s)), max(1, int(h * s))), Image.Resampling.LANCZOS)


def _square_thumb(im, size=76, bg="#1d2433"):
    c = Image.new("RGB", (size, size), bg)
    t = _fit(im, size - 8, size - 8)
    c.paste(t, ((size - t.size[0]) // 2, (size - t.size[1]) // 2))
    return c


def _parse_dropped(widget, data):
    try:
        paths = list(widget.tk.splitlist(data))
    except Exception:
        paths = [data]
    out = []
    for p in paths:
        p = p.strip()
        if p.startswith("{") and p.endswith("}"):
            p = p[1:-1]
        if p:
            out.append(p)
    return out


def _pdf_font_to_builtin(name):
    n = name.lower()
    if any(k in n for k in ("arial", "helv", "sans")):
        return "helv"
    if any(k in n for k in ("times", "roman", "serif")):
        return "tiro"
    if any(k in n for k in ("courier", "mono", "consol")):
        return "cour"
    return "helv"


def _pdf_font_to_tk(name):
    n = name.lower()
    if any(k in n for k in ("courier", "mono", "consol", "cour")):
        return "Courier New"
    if any(k in n for k in ("times", "roman", "serif", "tiro")):
        return "Times New Roman"
    return "Arial"


def _pdf_color_to_rgb(c):
    if c is None:
        return (0, 0, 0)
    if isinstance(c, int):
        r = ((c >> 16) & 0xFF) / 255.0
        g = ((c >> 8) & 0xFF) / 255.0
        b = (c & 0xFF) / 255.0
        return (r, g, b)
    if isinstance(c, float):
        v = max(0.0, min(1.0, c))
        return (v, v, v)
    if isinstance(c, (list, tuple)) and len(c) >= 3:
        return tuple(max(0.0, min(1.0, float(x))) for x in c[:3])
    return (0, 0, 0)


def _rgb01_to_hex(c):
    r = max(0, min(255, int(c[0] * 255)))
    g = max(0, min(255, int(c[1] * 255)))
    b = max(0, min(255, int(c[2] * 255)))
    return "#{:02x}{:02x}{:02x}".format(r, g, b)


def _closest_color_name(rgb):
    best, best_d = "Negro", 999.0
    for name, val in COLOR_MAP.items():
        d = sum((a - b) ** 2 for a, b in zip(rgb, val))
        if d < best_d:
            best_d, best = d, name
    return best


def _resolve_font_with_flags(font_base, flags):
    bold = bool(flags & 16)
    italic = bool(flags & 2)
    v = {
        "helv": {(0, 0): "helv", (1, 0): "hebo", (0, 1): "heit", (1, 1): "hebi"},
        "tiro": {(0, 0): "tiro", (1, 0): "tibo", (0, 1): "tiit", (1, 1): "tibi"},
        "cour": {(0, 0): "cour", (1, 0): "cobo", (0, 1): "coit", (1, 1): "cobi"},
    }
    return v.get(font_base, {}).get((int(bold), int(italic)), font_base)


# ── class ────────────────────────────────────────────────────────────
class EditPdfTab(ctk.CTkFrame):

    def __init__(self, master):
        super().__init__(master)
        self.doc = None
        self.pdf_path = None
        self.current_page = 0
        self.page_thumbs = []
        self.scale = 1.0
        self.manual_zoom = None
        self.offset_x = 0
        self.offset_y = 0
        self.canvas_img_ref = None

        self.text_lines = []
        self.added_objects = []
        self.page_states = {}

        self.selected = None
        self.mode = "select"

        # inline edit state
        self._edit_widget = None
        self._edit_win_id = None
        self._editing_line = None
        self._style_bar_win = None
        self._resize_handle_id = None
        self._resize_origin = None
        self._format_tags = {}
        self._default_edit_fmt = {}
        self._updating_toolbar = False

        # drag state
        self._drag_data = None
        self._drag_threshold = 5
        self._is_dragging = False
        self._draw_start = None
        self._draw_rect_id = None
        self._render_pending = None
        self._img_previews = []

        # resize state (for selected objects)
        self._resizing = False
        self._resize_data = None
        self._sel_rz_bbox = None

        # OCR reader (lazy init)
        self._ocr_reader = None

        # undo / redo (per page)
        self._undo_stacks = {}   # {page_idx: [snapshots]}
        self._redo_stacks = {}

        self._build_ui()
        self._build_style_toolbar()
        self._register_dnd_if_available()

    # ─── UI ──────────────────────────────────────────────────────────
    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)
        bold = ctk.CTkFont(weight="bold")
        small = ctk.CTkFont(size=12)

        # top bar
        top = ctk.CTkFrame(self, fg_color="#161b26")
        top.grid(row=0, column=0, columnspan=3, sticky="ew", padx=12, pady=(12, 8))
        ctk.CTkButton(top, text="Abrir PDF", width=100, command=self.open_pdf).grid(row=0, column=0, padx=6, pady=8)
        ctk.CTkButton(top, text="Guardar", width=80, command=self.save_pdf).grid(row=0, column=1, padx=6, pady=8)
        ctk.CTkButton(top, text="Guardar como", width=110, command=self.save_pdf_as).grid(row=0, column=2, padx=6, pady=8)
        ctk.CTkFrame(top, width=2, height=28, fg_color="#2a3040").grid(row=0, column=3, padx=8, pady=8)
        ctk.CTkLabel(top, text="Modo:", font=small).grid(row=0, column=4, padx=(4, 2), pady=8)
        self.mode_seg = ctk.CTkSegmentedButton(
            top, values=["Seleccionar", "Agregar Texto", "Agregar Imagen", "Resaltar"],
            command=self._on_mode_change)
        self.mode_seg.set("Seleccionar")
        self.mode_seg.grid(row=0, column=5, padx=6, pady=8)

        # left – thumbnails
        left = ctk.CTkFrame(self, fg_color="#121722", width=190)
        left.grid(row=1, column=0, sticky="nsw", padx=(12, 4), pady=(0, 12))
        left.grid_rowconfigure(1, weight=1)
        left.grid_propagate(False)
        ctk.CTkLabel(left, text="Páginas", font=bold).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 4))
        tf = ctk.CTkFrame(left, fg_color="#121722")
        tf.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))
        tf.grid_rowconfigure(0, weight=1)
        tf.grid_columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(tf, show="tree", selectmode="browse", style="Dark.Treeview", height=12)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scr = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        scr.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scr.set)
        self.tree.bind("<<TreeviewSelect>>", self._on_page_select)

        # center – canvas + zoom + scrollbars
        center = ctk.CTkFrame(self, fg_color="#0f1420", corner_radius=12)
        center.grid(row=1, column=1, sticky="nsew", padx=4, pady=(0, 12))
        center.grid_rowconfigure(1, weight=1)
        center.grid_columnconfigure(0, weight=1)

        zoom_bar = ctk.CTkFrame(center, fg_color="#161b26", height=32)
        zoom_bar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=6, pady=(6, 0))
        ctk.CTkButton(zoom_bar, text="\u2212", width=30, height=26, command=self._zoom_out).pack(side="left", padx=2, pady=2)
        self.zoom_label = ctk.CTkLabel(zoom_bar, text="Ajustar", width=60, font=small)
        self.zoom_label.pack(side="left", padx=2)
        ctk.CTkButton(zoom_bar, text="+", width=30, height=26, command=self._zoom_in).pack(side="left", padx=2, pady=2)
        ctk.CTkButton(zoom_bar, text="Ajustar", width=60, height=26, command=self._zoom_fit).pack(side="left", padx=6, pady=2)

        self.canvas = tk.Canvas(center, bg="#0f1420", highlightthickness=0, cursor="arrow")
        self.v_scroll = ttk.Scrollbar(center, orient="vertical", command=self.canvas.yview)
        self.h_scroll = ttk.Scrollbar(center, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(xscrollcommand=self.h_scroll.set, yscrollcommand=self.v_scroll.set)
        self.canvas.grid(row=1, column=0, sticky="nsew", padx=(6, 0), pady=(4, 0))
        self.v_scroll.grid(row=1, column=1, sticky="ns", pady=(4, 0))
        self.h_scroll.grid(row=2, column=0, sticky="ew", padx=(6, 0))

        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Double-Button-1>", self._on_double_click)
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.canvas.bind("<Delete>", self._on_delete_key)
        self.canvas.bind("<BackSpace>", self._on_delete_key)
        self.canvas.bind("<Control-MouseWheel>", self._on_ctrl_mousewheel)
        self.canvas.bind("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        self.canvas.bind("<Control-z>", self._undo)
        self.canvas.bind("<Control-y>", self._redo)

        # right – tools (no "Texto nuevo" – click directly to create)
        right = ctk.CTkScrollableFrame(self, fg_color="#121722", width=260,
                                        label_text="Herramientas", label_font=bold)
        right.grid(row=1, column=2, sticky="nse", padx=(4, 12), pady=(0, 12))

        ctk.CTkLabel(right, text="Página", font=bold, text_color="#8cb0ff").pack(anchor="w", padx=10, pady=(10, 4))
        rf = ctk.CTkFrame(right, fg_color="transparent")
        rf.pack(fill="x", padx=10, pady=2)
        ctk.CTkButton(rf, text="Rotar 90\u00b0 \u2192", width=110, command=lambda: self._rotate(90)).pack(side="left", padx=(0, 4))
        ctk.CTkButton(rf, text="Rotar 90\u00b0 \u2190", width=110, command=lambda: self._rotate(-90)).pack(side="right")
        ctk.CTkButton(right, text="Eliminar página", fg_color="#8b2020", hover_color="#a52a2a",
                       command=self._delete_page).pack(fill="x", padx=10, pady=(6, 4))

        ctk.CTkFrame(right, height=2, fg_color="#2a3040").pack(fill="x", padx=10, pady=8)

        ctk.CTkLabel(right, text="OCR / Texto", font=bold, text_color="#8cb0ff").pack(anchor="w", padx=10, pady=(4, 4))
        of = ctk.CTkFrame(right, fg_color="transparent")
        of.pack(fill="x", padx=10, pady=2)
        ctk.CTkButton(of, text="Extraer texto", width=110, command=self._extract_text_to_box).pack(side="left", padx=(0, 4))
        ctk.CTkButton(of, text="OCR Página", width=110, command=self._ocr_page).pack(side="right")
        ctk.CTkButton(right, text="Copiar al portapapeles", command=self._copy_ocr, height=28).pack(fill="x", padx=10, pady=(4, 4))
        self.ocr_box = ctk.CTkTextbox(right, height=140, fg_color="#1a2030", text_color="#e4e9f5", corner_radius=8)
        self.ocr_box.pack(fill="x", padx=10, pady=(4, 10))

        # bottom
        bot = ctk.CTkFrame(self, fg_color="#161b26")
        bot.grid(row=2, column=0, columnspan=3, sticky="ew", padx=12, pady=(0, 12))
        bot.grid_columnconfigure(1, weight=1)
        self.status_lbl = ctk.CTkLabel(bot, text="Sin documento", font=small)
        self.status_lbl.grid(row=0, column=0, padx=10, pady=8, sticky="w")
        self.hint_lbl = ctk.CTkLabel(bot, text="Arrastra un PDF o haz click en Abrir PDF", font=small, text_color="#93a1ba")
        self.hint_lbl.grid(row=0, column=1, padx=10, pady=8, sticky="e")

    # ─── Style toolbar (floating) ────────────────────────────────────
    def _build_style_toolbar(self):
        self._style_bar = ctk.CTkFrame(self.canvas, fg_color="#1a2030", corner_radius=8, height=36)
        sm = ctk.CTkFont(size=11)
        self._edit_font_var = tk.StringVar(value="Helvetica")
        ctk.CTkOptionMenu(self._style_bar, variable=self._edit_font_var, width=110,
                           values=list(FONT_MAP.keys()), font=sm,
                           command=lambda _: self._on_font_change()).pack(side="left", padx=2, pady=2)
        self._edit_size_var = tk.StringVar(value="12")
        se = ctk.CTkEntry(self._style_bar, textvariable=self._edit_size_var, width=40, font=sm)
        se.pack(side="left", padx=2, pady=2)
        se.bind("<Return>", lambda _: self._on_size_change())
        se.bind("<FocusOut>", lambda _: self._on_size_change())
        self._bold_btn = ctk.CTkButton(self._style_bar, text="B", width=28, height=26,
                                        font=ctk.CTkFont(weight="bold", size=12), command=self._toggle_bold)
        self._bold_btn.pack(side="left", padx=1, pady=2)
        self._italic_btn = ctk.CTkButton(self._style_bar, text="I", width=28, height=26,
                                          font=ctk.CTkFont(slant="italic", size=12), command=self._toggle_italic)
        self._italic_btn.pack(side="left", padx=1, pady=2)
        self._underline_btn = ctk.CTkButton(self._style_bar, text="U", width=28, height=26,
                                             font=ctk.CTkFont(underline=True, size=12), command=self._toggle_underline)
        self._underline_btn.pack(side="left", padx=1, pady=2)
        self._edit_color_var = tk.StringVar(value="Negro")
        ctk.CTkOptionMenu(self._style_bar, variable=self._edit_color_var, width=85,
                           values=list(COLOR_MAP.keys()), font=sm,
                           command=lambda _: self._on_color_change()).pack(side="left", padx=2, pady=2)

    # ─── DnD ─────────────────────────────────────────────────────────
    def _register_dnd_if_available(self):
        if not DND_AVAILABLE:
            return
        for w in [self, self.canvas]:
            try:
                w.drop_target_register(DND_FILES)
                w.dnd_bind("<<Drop>>", self._on_drop_files)
            except Exception:
                pass

    def _on_drop_files(self, event):
        dropped = _parse_dropped(self, event.data)
        pdf_files = [p for p in dropped if p.lower().endswith(".pdf") and os.path.isfile(p)]
        if pdf_files:
            self._load_pdf_file(pdf_files[0])

    # ─── Modes ───────────────────────────────────────────────────────
    def _on_mode_change(self, val):
        m = {"Seleccionar": "select", "Agregar Texto": "add_text",
             "Agregar Imagen": "add_image", "Resaltar": "highlight"}
        self.mode = m.get(val, "select")
        cursors = {"select": "arrow", "add_text": "xterm",
                   "add_image": "crosshair", "highlight": "crosshair"}
        self.canvas.config(cursor=cursors.get(self.mode, "arrow"))
        hints = {"select": "Click: seleccionar | Doble-click: editar | Arrastrar: mover",
                 "add_text": "Click en la página para crear un cuadro de texto",
                 "add_image": "Dibuja un rectángulo donde colocar la imagen",
                 "highlight": "Dibuja un rectángulo para resaltar"}
        self.hint_lbl.configure(text=hints.get(self.mode, ""))
        self._commit_edit()
        self._deselect()

    # ─── Zoom ────────────────────────────────────────────────────────
    def _zoom_in(self):
        cur = self.manual_zoom if self.manual_zoom else self.scale
        for z in ZOOM_STEPS:
            if z > cur + 0.01:
                self.manual_zoom = z
                self._render()
                return

    def _zoom_out(self):
        cur = self.manual_zoom if self.manual_zoom else self.scale
        for z in reversed(ZOOM_STEPS):
            if z < cur - 0.01:
                self.manual_zoom = z
                self._render()
                return

    def _zoom_fit(self):
        self.manual_zoom = None
        self._render()

    def _on_ctrl_mousewheel(self, event):
        if event.delta > 0:
            self._zoom_in()
        else:
            self._zoom_out()
        return "break"

    # ─── Undo / Redo (per page) ──────────────────────────────────────
    def _snapshot(self):
        return {
            "text_lines": copy.deepcopy(self.text_lines),
            "added_objects": copy.deepcopy(self.added_objects),
        }

    def _push_undo(self):
        p = self.current_page
        if p not in self._undo_stacks:
            self._undo_stacks[p] = []
        self._undo_stacks[p].append(self._snapshot())
        self._redo_stacks.pop(p, None)
        if len(self._undo_stacks[p]) > 50:
            self._undo_stacks[p].pop(0)

    def _undo(self, event=None):
        if self._editing_line:
            return  # let tk.Text handle its own undo
        p = self.current_page
        stack = self._undo_stacks.get(p, [])
        if not stack:
            return "break"
        if p not in self._redo_stacks:
            self._redo_stacks[p] = []
        self._redo_stacks[p].append(self._snapshot())
        state = stack.pop()
        self.text_lines = state["text_lines"]
        self.added_objects = state["added_objects"]
        self.selected = None
        self._render()
        return "break"

    def _redo(self, event=None):
        if self._editing_line:
            return  # let tk.Text handle its own redo
        p = self.current_page
        stack = self._redo_stacks.get(p, [])
        if not stack:
            return "break"
        if p not in self._undo_stacks:
            self._undo_stacks[p] = []
        self._undo_stacks[p].append(self._snapshot())
        state = stack.pop()
        self.text_lines = state["text_lines"]
        self.added_objects = state["added_objects"]
        self.selected = None
        self._render()
        return "break"

    # ─── Files ───────────────────────────────────────────────────────
    def open_pdf(self):
        path = filedialog.askopenfilename(title="Abrir PDF", filetypes=[("PDF", "*.pdf")])
        if path:
            self._load_pdf_file(path)

    def _load_pdf_file(self, path):
        self._commit_edit()
        if self.doc:
            self.doc.close()
        try:
            self.doc = fitz.open(path)
            self.pdf_path = path
            self.current_page = 0
            self.page_states.clear()
            self.text_lines = []
            self.added_objects = []
            self.selected = None
            self.manual_zoom = None
            self._undo_stacks.clear()
            self._redo_stacks.clear()
            self._build_thumbs()
            self._load_page(0)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir.\n\n{e}")

    def save_pdf(self):
        if not self.doc:
            return
        if not self.pdf_path:
            self.save_pdf_as()
            return
        self._commit_edit()
        self._store_page_state()
        try:
            self._apply_all_changes()
            tmp = self.pdf_path + ".tmp"
            self.doc.save(tmp, garbage=4, deflate=True)
            self.doc.close()
            os.replace(tmp, self.pdf_path)
            self.doc = fitz.open(self.pdf_path)
            self.page_states.clear()
            self._build_thumbs()
            self._load_page(self.current_page)
            messagebox.showinfo("Éxito", "PDF guardado.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar.\n\n{e}")

    def save_pdf_as(self):
        if not self.doc:
            return
        path = filedialog.asksaveasfilename(title="Guardar como", defaultextension=".pdf",
                                             filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        self._commit_edit()
        self._store_page_state()
        try:
            self._apply_all_changes()
            self.doc.save(path, garbage=4, deflate=True)
            self.doc.close()
            self.doc = fitz.open(path)
            self.pdf_path = path
            self.page_states.clear()
            self._build_thumbs()
            self._load_page(self.current_page)
            messagebox.showinfo("Éxito", f"Guardado:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar.\n\n{e}")

    # ─── Thumbnails ──────────────────────────────────────────────────
    def _build_thumbs(self):
        self.page_thumbs.clear()
        self.tree.delete(*self.tree.get_children())
        if not self.doc:
            return
        for i in range(self.doc.page_count):
            pg = self.doc[i]
            pix = pg.get_pixmap(matrix=fitz.Matrix(0.22, 0.22), alpha=False)
            im = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            tk_img = ImageTk.PhotoImage(_square_thumb(im))
            self.page_thumbs.append(tk_img)
            self.tree.insert("", "end", iid=str(i), text=f"  Pág. {i+1}", image=tk_img)
        if self.doc.page_count > 0:
            idx = min(self.current_page, self.doc.page_count - 1)
            self.tree.selection_set(str(idx))
            self.tree.see(str(idx))

    def _rebuild_thumb(self, idx):
        if not self.doc or idx >= self.doc.page_count:
            return
        pg = self.doc[idx]
        pix = pg.get_pixmap(matrix=fitz.Matrix(0.22, 0.22), alpha=False)
        im = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        tk_img = ImageTk.PhotoImage(_square_thumb(im))
        self.page_thumbs[idx] = tk_img
        self.tree.item(str(idx), image=tk_img)

    def _on_page_select(self, _=None):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if idx != self.current_page:
            self._commit_edit()
            self._store_page_state()
            self._load_page(idx)

    # ─── Page state ──────────────────────────────────────────────────
    def _store_page_state(self):
        if self.doc is None:
            return
        self.page_states[self.current_page] = {
            "text_lines": [dict(l) for l in self.text_lines],
            "added_objects": [dict(o) for o in self.added_objects],
        }

    def _load_page(self, idx):
        self.current_page = idx
        self.selected = None
        if idx in self.page_states:
            st = self.page_states[idx]
            self.text_lines = st["text_lines"]
            self.added_objects = st["added_objects"]
        else:
            self._extract_lines()
            self.added_objects = []
        self._render()

    # ─── Extract text LINE by LINE with SPANS ────────────────────────
    def _extract_lines(self):
        self.text_lines = []
        if not self.doc:
            return
        page = self.doc[self.current_page]
        d = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        for block in d.get("blocks", []):
            if block["type"] != 0:
                continue
            for line in block.get("lines", []):
                raw_spans = line.get("spans", [])
                if not raw_spans:
                    continue
                spans = []
                for sp in raw_spans:
                    t = sp.get("text", "")
                    if not t:
                        continue
                    spans.append({
                        "text": t,
                        "font_name": sp.get("font", ""),
                        "font": _pdf_font_to_builtin(sp.get("font", "")),
                        "size": sp.get("size", 12),
                        "color": _pdf_color_to_rgb(sp.get("color", 0)),
                        "flags": sp.get("flags", 0),
                    })
                # strip trailing whitespace from last span
                if spans:
                    spans[-1]["text"] = spans[-1]["text"].rstrip()
                    if not spans[-1]["text"]:
                        spans.pop()
                if not spans:
                    continue
                text = "".join(s["text"] for s in spans)
                first = spans[0]
                bb = list(line["bbox"])
                self.text_lines.append({
                    "bbox": list(bb), "bbox_orig": list(bb),
                    "text": text, "orig_text": text,
                    "spans": [dict(s) for s in spans],
                    "font_name": first["font_name"], "font": first["font"],
                    "size": first["size"], "color": first["color"], "flags": first["flags"],
                    "modified": False, "moved": False, "deleted": False,
                })

    # ─── Font helpers ────────────────────────────────────────────────
    def _get_tk_font(self, data):
        family = _pdf_font_to_tk(data.get("font_name", data.get("font", "")))
        px = max(8, int(data["size"] * self.scale))
        flags = data.get("flags", 0)
        w = "bold" if flags & 16 else "normal"
        sl = "italic" if flags & 2 else "roman"
        return (family, -px, w) if sl == "roman" else (family, -px, w, sl)

    def _get_tk_font_span(self, span):
        family = _pdf_font_to_tk(span.get("font_name", span.get("font", "")))
        px = max(8, int(span["size"] * self.scale))
        flags = span.get("flags", 0)
        w = "bold" if flags & 16 else "normal"
        sl = "italic" if flags & 2 else "roman"
        return (family, -px, w) if sl == "roman" else (family, -px, w, sl)

    # ─── Render ──────────────────────────────────────────────────────
    def _render(self):
        if not self.doc or self.current_page >= self.doc.page_count:
            self.canvas.delete("all")
            self.status_lbl.configure(text="Sin documento")
            return

        page = self.doc[self.current_page]
        cw = max(100, self.canvas.winfo_width())
        ch = max(100, self.canvas.winfo_height())
        pw, ph = page.rect.width, page.rect.height

        if self.manual_zoom is not None:
            self.scale = self.manual_zoom
        else:
            self.scale = min((cw - 16) / pw, (ch - 16) / ph, 4.0)

        mat = fitz.Matrix(self.scale, self.scale)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        im = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        draw = ImageDraw.Draw(im)
        for ln in self.text_lines:
            if ln.get("modified") or ln.get("deleted") or ln.get("moved"):
                bb = ln["bbox_orig"]
                x0 = int(bb[0] * self.scale) - 3
                y0 = int(bb[1] * self.scale) - 5
                x1 = int(bb[2] * self.scale) + 3
                y1 = int(bb[3] * self.scale) + 5
                draw.rectangle([x0, y0, x1, y1], fill="white")
        # Blank areas under OCR overlays so scanned image text doesn't show
        for obj in self.added_objects:
            if obj.get("ocr"):
                bb = obj["bbox"]
                x0 = int(bb[0] * self.scale) - 2
                y0 = int(bb[1] * self.scale) - 2
                x1 = int(bb[2] * self.scale) + 2
                y1 = int(bb[3] * self.scale) + 2
                draw.rectangle([x0, y0, x1, y1], fill="white")

        self.offset_x = max(0, (cw - pix.width) // 2) if self.manual_zoom is None else 8
        self.offset_y = max(0, (ch - pix.height) // 2) if self.manual_zoom is None else 8

        self.canvas.delete("all")
        self._img_previews.clear()
        self.canvas_img_ref = ImageTk.PhotoImage(im)
        self.canvas.create_image(self.offset_x, self.offset_y, anchor="nw",
                                  image=self.canvas_img_ref, tags="bg")
        self.canvas.configure(scrollregion=(0, 0,
                                            pix.width + self.offset_x * 2,
                                            pix.height + self.offset_y * 2))
        self._draw_overlays()
        ztext = "Ajustar" if self.manual_zoom is None else f"{self.scale*100:.0f}%"
        self.zoom_label.configure(text=ztext)
        self.status_lbl.configure(
            text=f"Pág. {self.current_page+1}/{self.doc.page_count}  |  "
                 f"{pw:.0f}\u00d7{ph:.0f} pt  |  Zoom {self.scale*100:.0f}%")
        self.canvas.focus_set()

    def _draw_overlays(self):
        self._sel_rz_bbox = None

        for i, ln in enumerate(self.text_lines):
            if ln["deleted"]:
                continue
            x0, y0, x1, y1 = self._pdf_to_canvas_rect(ln["bbox"])

            if ln.get("modified") or ln.get("moved"):
                self._draw_spans_on_canvas(ln, x0, y0, y1)

            is_sel = ln is self.selected
            if is_sel:
                self.canvas.create_rectangle(x0 - 1, y0 - 1, x1 + 1, y1 + 1,
                                              outline="#3c7bff", width=2, fill="", tags="sel")
                self._sel_rz_bbox = (x1 - 4, y1 - 4, x1 + 4, y1 + 4)
                self.canvas.create_rectangle(*self._sel_rz_bbox,
                    fill="#3c7bff", outline="#1a50cc", tags="sel_rz")
            else:
                self.canvas.create_rectangle(x0, y0, x1, y1, outline="", fill="", tags=f"hit_{i}")

        for j, obj in enumerate(self.added_objects):
            x0, y0, x1, y1 = self._pdf_to_canvas_rect(obj["bbox"])
            is_sel = obj is self.selected
            if obj["type"] == "text":
                self._draw_spans_on_canvas(obj, x0, y0, y1)
                if is_sel:
                    border = "#3c7bff"
                elif obj.get("ocr"):
                    border = "#00bcd4"
                else:
                    border = "#00aa55"
                self.canvas.create_rectangle(x0, y0, x1, y1,
                    outline=border,
                    width=2 if is_sel else 1, dash=() if is_sel else (3, 2),
                    fill="", tags=f"abox_{j}")
            elif obj["type"] == "image":
                self._draw_image_preview(obj, x0, y0, x1, y1, is_sel)
            if is_sel:
                self._sel_rz_bbox = (x1 - 4, y1 - 4, x1 + 4, y1 + 4)
                self.canvas.create_rectangle(*self._sel_rz_bbox,
                    fill="#3c7bff", outline="#1a50cc", tags="sel_rz")

    def _draw_spans_on_canvas(self, item, x0, y0, y1):
        spans = item.get("spans", [])
        if not spans:
            font = self._get_tk_font(item)
            self.canvas.create_text(x0 + 1, (y0 + y1) / 2, text=item["text"],
                                     font=font, fill=_rgb01_to_hex(item["color"]),
                                     anchor="w", tags="overlay")
            return
        xpos = x0 + 1
        for sp in spans:
            font = self._get_tk_font_span(sp)
            color = _rgb01_to_hex(sp["color"])
            self.canvas.create_text(xpos, (y0 + y1) / 2, text=sp["text"],
                                     font=font, fill=color, anchor="w", tags="overlay")
            try:
                tf = tkfont.Font(font=font)
                tw = tf.measure(sp["text"])
            except Exception:
                tw = len(sp["text"]) * max(6, int(sp["size"] * self.scale)) * 0.6
            if sp.get("flags", 0) & 1:
                uy = y1 - 1
                self.canvas.create_line(xpos, uy, xpos + tw, uy,
                                         fill=color, width=1, tags="overlay")
            xpos += tw

    def _draw_image_preview(self, obj, x0, y0, x1, y1, is_sel):
        w = max(4, int(x1 - x0))
        h = max(4, int(y1 - y0))
        try:
            with Image.open(obj["image_path"]) as raw:
                preview = _fit(raw.convert("RGB"), w, h)
                tk_img = ImageTk.PhotoImage(preview)
                self._img_previews.append(tk_img)
                self.canvas.create_image((x0 + x1) / 2, (y0 + y1) / 2, image=tk_img, tags="overlay")
        except Exception:
            self.canvas.create_text((x0 + x1) / 2, (y0 + y1) / 2,
                                     text=os.path.basename(obj.get("image_path", "?")),
                                     font=("Arial", 9), fill="#999", tags="overlay")
        self.canvas.create_rectangle(x0, y0, x1, y1,
            outline="#3c7bff" if is_sel else "#cc6600",
            width=2 if is_sel else 1, fill="", tags="overlay")

    def _on_canvas_resize(self, _):
        if not self.doc:
            return
        if self._render_pending:
            self.after_cancel(self._render_pending)
        self._render_pending = self.after(120, self._render)

    # ─── Coordinates ─────────────────────────────────────────────────
    def _pdf_to_canvas(self, px, py):
        return px * self.scale + self.offset_x, py * self.scale + self.offset_y

    def _canvas_to_pdf(self, cx, cy):
        cx = self.canvas.canvasx(cx)
        cy = self.canvas.canvasy(cy)
        return (cx - self.offset_x) / self.scale, (cy - self.offset_y) / self.scale

    def _canvas_to_pdf_raw(self, cx, cy):
        return (cx - self.offset_x) / self.scale, (cy - self.offset_y) / self.scale

    def _pdf_to_canvas_rect(self, bbox):
        x0, y0 = self._pdf_to_canvas(bbox[0], bbox[1])
        x1, y1 = self._pdf_to_canvas(bbox[2], bbox[3])
        return x0, y0, x1, y1

    # ─── Hit test ────────────────────────────────────────────────────
    def _find_at(self, cx, cy):
        px, py = self._canvas_to_pdf(cx, cy)
        for obj in reversed(self.added_objects):
            b = obj["bbox"]
            if b[0] <= px <= b[2] and b[1] <= py <= b[3]:
                return obj
        for ln in reversed(self.text_lines):
            if ln["deleted"]:
                continue
            b = ln["bbox"]
            if b[0] <= px <= b[2] and b[1] <= py <= b[3]:
                return ln
        return None

    # ─── Selection ───────────────────────────────────────────────────
    def _select(self, item):
        if self.selected is item:
            return
        self.selected = item
        self._render()

    def _deselect(self):
        if self.selected is not None:
            self.selected = None
            self._render()

    # ─── Canvas events ───────────────────────────────────────────────
    def _on_press(self, event):
        if not self.doc:
            return
        self._commit_edit()

        # Check resize handle first
        if self.selected and self._sel_rz_bbox:
            cx = self.canvas.canvasx(event.x)
            cy = self.canvas.canvasy(event.y)
            rx0, ry0, rx1, ry1 = self._sel_rz_bbox
            if rx0 - 3 <= cx <= rx1 + 3 and ry0 - 3 <= cy <= ry1 + 3:
                self._push_undo()
                self._resizing = True
                self._resize_data = {
                    "item": self.selected,
                    "orig_bbox": list(self.selected["bbox"]),
                }
                return

        if self.mode == "select":
            hit = self._find_at(event.x, event.y)
            if hit:
                self._select(hit)
                sx = self.canvas.canvasx(event.x)
                sy = self.canvas.canvasy(event.y)
                self._drag_data = {"item": hit, "sx": sx, "sy": sy, "orig_bbox": list(hit["bbox"])}
                self._is_dragging = False
            else:
                self._deselect()
        elif self.mode == "add_text":
            px, py = self._canvas_to_pdf(event.x, event.y)
            self._create_text_box(px, py)
        elif self.mode in ("add_image", "highlight"):
            self._draw_start = (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))

    def _on_motion(self, event):
        if self._resizing and self._resize_data:
            cx = self.canvas.canvasx(event.x)
            cy = self.canvas.canvasy(event.y)
            px, py = self._canvas_to_pdf_raw(cx, cy)
            item = self._resize_data["item"]
            ob = self._resize_data["orig_bbox"]
            min_w = 10 / self.scale
            min_h = 10 / self.scale
            item["bbox"] = [ob[0], ob[1], max(ob[0] + min_w, px), max(ob[1] + min_h, py)]
            self._render()
            return
        if self.mode == "select" and self._drag_data:
            cx = self.canvas.canvasx(event.x)
            cy = self.canvas.canvasy(event.y)
            dx = abs(cx - self._drag_data["sx"])
            dy = abs(cy - self._drag_data["sy"])
            if dx > self._drag_threshold or dy > self._drag_threshold:
                if not self._is_dragging:
                    self._push_undo()
                self._is_dragging = True
            if self._is_dragging:
                self._do_drag(event)
        elif self.mode in ("add_image", "highlight") and self._draw_start:
            if self._draw_rect_id:
                self.canvas.delete(self._draw_rect_id)
            x0, y0 = self._draw_start
            cx = self.canvas.canvasx(event.x)
            cy = self.canvas.canvasy(event.y)
            colors = {"add_image": "#ff8800", "highlight": "#ffff00"}
            self._draw_rect_id = self.canvas.create_rectangle(
                x0, y0, cx, cy, outline=colors.get(self.mode, "#fff"), width=2, dash=(5, 3))

    def _on_release(self, event):
        if self._resizing:
            if self._resize_data:
                item = self._resize_data["item"]
                if item in self.text_lines:
                    item["modified"] = True
                    item["moved"] = True
            self._resizing = False
            self._resize_data = None
            return
        if self.mode == "select" and self._drag_data:
            if self._is_dragging:
                self._end_drag()
            self._drag_data = None
            self._is_dragging = False
        elif self.mode in ("add_image", "highlight") and self._draw_start:
            x0, y0 = self._draw_start
            cx = self.canvas.canvasx(event.x)
            cy = self.canvas.canvasy(event.y)
            self._draw_start = None
            if self._draw_rect_id:
                self.canvas.delete(self._draw_rect_id)
                self._draw_rect_id = None
            if abs(cx - x0) < 10 or abs(cy - y0) < 10:
                return
            px0, py0 = self._canvas_to_pdf_raw(min(x0, cx), min(y0, cy))
            px1, py1 = self._canvas_to_pdf_raw(max(x0, cx), max(y0, cy))
            rect = [px0, py0, px1, py1]
            if self.mode == "add_image":
                self._place_image(rect)
            elif self.mode == "highlight":
                self._apply_highlight(rect)

    def _on_double_click(self, event):
        if self.mode != "select" or not self.doc:
            return
        hit = self._find_at(event.x, event.y)
        if hit:
            self._select(hit)
            self._start_inline_edit(hit)

    def _on_delete_key(self, event):
        if self._editing_line:
            return
        if self.selected:
            self._push_undo()
            if self.selected in self.text_lines:
                self.selected["deleted"] = True
                self.selected["modified"] = True
            elif self.selected in self.added_objects:
                self.added_objects.remove(self.selected)
            self.selected = None
            self._render()

    # ─── Drag to move ────────────────────────────────────────────────
    def _do_drag(self, event):
        d = self._drag_data
        item = d["item"]
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        dx = (cx - d["sx"]) / self.scale
        dy = (cy - d["sy"]) / self.scale
        ob = d["orig_bbox"]
        item["bbox"] = [ob[0] + dx, ob[1] + dy, ob[2] + dx, ob[3] + dy]
        self._render()

    def _end_drag(self):
        d = self._drag_data
        item = d["item"]
        if item["bbox"] != d["orig_bbox"] and item in self.text_lines:
            item["moved"] = True
            item["modified"] = True

    # ─── Format tag helpers ──────────────────────────────────────────
    def _fmt_tag_key(self, fmt):
        f = fmt.get("font", "helv")
        s = int(fmt.get("size", 12))
        fl = fmt.get("flags", 0) & 19
        c = fmt.get("color", (0, 0, 0))
        return f"fmt_{f}_{s}_{fl}_{int(c[0]*255)}_{int(c[1]*255)}_{int(c[2]*255)}"

    def _get_or_create_fmt_tag(self, fmt):
        tag = self._fmt_tag_key(fmt)
        if tag not in self._format_tags:
            self._format_tags[tag] = {
                "font": fmt.get("font", "helv"),
                "font_name": fmt.get("font_name", "Helvetica"),
                "size": fmt.get("size", 12),
                "color": fmt.get("color", (0, 0, 0)),
                "flags": fmt.get("flags", 0) & 19,
            }
            # configure on widget
            if self._edit_widget:
                family = _pdf_font_to_tk(fmt.get("font_name", fmt.get("font", "")))
                px = max(6, int(fmt.get("size", 12) * self.scale))
                flags = fmt.get("flags", 0)
                wt = "bold" if flags & 16 else "normal"
                sl = "italic" if flags & 2 else "roman"
                ul = bool(flags & 1)
                ft = (family, -px, wt) if sl == "roman" else (family, -px, wt, sl)
                fg = _rgb01_to_hex(fmt.get("color", (0, 0, 0)))
                self._edit_widget.tag_configure(tag, font=ft, foreground=fg, underline=ul)
        return tag

    def _get_fmt_at(self, idx_str):
        tags = self._edit_widget.tag_names(idx_str)
        for t in tags:
            if t.startswith("fmt_") and t in self._format_tags:
                return dict(self._format_tags[t])
        return dict(self._default_edit_fmt)

    def _get_edit_sel(self):
        try:
            s = self._edit_widget.index("sel.first")
            e = self._edit_widget.index("sel.last")
            return s, e
        except tk.TclError:
            return "1.0", self._edit_widget.index("end-1c")

    def _remove_fmt_tags_in_range(self, start, end):
        for t in list(self._format_tags.keys()):
            self._edit_widget.tag_remove(t, start, end)

    # ─── Inline editing with tk.Text + per-span tags ─────────────────
    def _start_inline_edit(self, line_data):
        if self._editing_line:
            self._commit_edit()
        self._editing_line = line_data
        self._format_tags = {}

        spans = line_data.get("spans", [])
        if not spans:
            spans = [{"text": line_data.get("text", ""),
                      "font": line_data.get("font", "helv"),
                      "font_name": line_data.get("font_name", ""),
                      "size": line_data.get("size", 12),
                      "color": line_data.get("color", (0, 0, 0)),
                      "flags": line_data.get("flags", 0)}]
        # Store original spans for change detection
        line_data["_orig_spans"] = [dict(s) for s in spans]
        self._default_edit_fmt = {
            "font": spans[0].get("font", "helv"),
            "font_name": spans[0].get("font_name", ""),
            "size": spans[0].get("size", 12),
            "color": spans[0].get("color", (0, 0, 0)),
            "flags": spans[0].get("flags", 0),
        }

        bb = line_data["bbox"]
        x0, y0 = self._pdf_to_canvas(bb[0], bb[1])
        x1, y1 = self._pdf_to_canvas(bb[2], bb[3])
        w = max(200, int(x1 - x0) + 40)
        h = max(28, int(y1 - y0) + 8)

        self._edit_widget = tk.Text(
            self.canvas, wrap="none", bg="#fffde8",
            insertbackground="#000000", selectbackground="#3c7bff",
            bd=1, relief="solid", undo=True, height=1)

        for sp in spans:
            tag = self._get_or_create_fmt_tag(sp)
            self._edit_widget.insert("end", sp["text"], tag)

        self._edit_widget.focus_set()
        self._edit_widget.tag_add("sel", "1.0", "end-1c")
        self._edit_widget.bind("<Escape>", lambda e: self._cancel_edit())
        self._edit_widget.bind("<Tab>", lambda e: (self._commit_edit(), "break")[1])
        self._edit_widget.bind("<ButtonRelease-1>", lambda e: self._update_toolbar_from_cursor())
        self._edit_widget.bind("<KeyRelease>", self._on_edit_key_release)

        self._edit_win_id = self.canvas.create_window(
            x0, y0, anchor="nw", window=self._edit_widget, width=w, height=h)

        self._show_style_toolbar(x0, y0)
        self._show_resize_handle(x0, y0, w, h)

    def _on_edit_key_release(self, event):
        self._ensure_chars_tagged()
        self._update_toolbar_from_cursor()

    def _ensure_chars_tagged(self):
        if not self._edit_widget:
            return
        text = self._edit_widget.get("1.0", "end-1c")
        if not text:
            return
        default_tag = None
        for i in range(len(text)):
            idx = f"1.{i}"
            tags = self._edit_widget.tag_names(idx)
            if any(t.startswith("fmt_") and t in self._format_tags for t in tags):
                continue
            if default_tag is None:
                for check in [i - 1, i + 1]:
                    if 0 <= check < len(text):
                        ct = self._edit_widget.tag_names(f"1.{check}")
                        ft = next((t for t in ct if t.startswith("fmt_") and t in self._format_tags), None)
                        if ft:
                            default_tag = ft
                            break
                if default_tag is None:
                    default_tag = self._get_or_create_fmt_tag(self._default_edit_fmt)
            self._edit_widget.tag_add(default_tag, idx, f"1.{i+1}")

    # ─── Style toolbar show/hide ─────────────────────────────────────
    def _show_style_toolbar(self, x0, y0):
        self._update_toolbar_from_cursor()
        toolbar_y = max(0, y0 - 40)
        self._style_bar_win = self.canvas.create_window(
            x0, toolbar_y, anchor="nw", window=self._style_bar)

    def _hide_style_toolbar(self):
        if self._style_bar_win:
            self.canvas.delete(self._style_bar_win)
            self._style_bar_win = None

    def _show_resize_handle(self, x0, y0, w, h):
        rx, ry = x0 + w - 4, y0 + h - 4
        self._resize_handle_id = self.canvas.create_rectangle(
            rx, ry, rx + 8, ry + 8, fill="#3c7bff", outline="#1a50cc", tags="rz")
        self._resize_origin = (x0, y0, w, h)
        self.canvas.tag_bind("rz", "<B1-Motion>", self._on_resize_drag)

    def _hide_resize_handle(self):
        if self._resize_handle_id:
            self.canvas.delete(self._resize_handle_id)
            self._resize_handle_id = None
            self._resize_origin = None

    def _on_resize_drag(self, event):
        if not self._edit_win_id or not self._resize_origin:
            return
        x0, y0 = self._resize_origin[0], self._resize_origin[1]
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        nw = max(100, int(cx - x0))
        nh = max(24, int(cy - y0))
        self.canvas.itemconfigure(self._edit_win_id, width=nw, height=nh)
        self.canvas.coords(self._resize_handle_id, cx - 4, cy - 4, cx + 4, cy + 4)
        if self._editing_line:
            px0, py0 = self._canvas_to_pdf_raw(x0, y0)
            px1, py1 = self._canvas_to_pdf_raw(x0 + nw, y0 + nh)
            self._editing_line["bbox"] = [px0, py0, px1, py1]

    # ─── Toolbar ↔ cursor sync ───────────────────────────────────────
    def _update_toolbar_from_cursor(self):
        if not self._edit_widget:
            return
        self._updating_toolbar = True
        try:
            fmt = self._get_fmt_at(self._edit_widget.index("insert"))
            self._edit_font_var.set(FONT_DISPLAY.get(fmt.get("font", "helv"), "Helvetica"))
            self._edit_size_var.set(str(int(fmt.get("size", 12))))
            flags = fmt.get("flags", 0)
            self._bold_btn.configure(fg_color="#3c7bff" if flags & 16 else "#2b2b2b")
            self._italic_btn.configure(fg_color="#3c7bff" if flags & 2 else "#2b2b2b")
            self._underline_btn.configure(fg_color="#3c7bff" if flags & 1 else "#2b2b2b")
            self._edit_color_var.set(_closest_color_name(fmt.get("color", (0, 0, 0))))
        finally:
            self._updating_toolbar = False

    # ─── Style modification (per-selection) ──────────────────────────
    def _modify_selection(self, updates):
        if not self._edit_widget:
            return
        s, e = self._get_edit_sel()
        si = int(s.split(".")[1])
        ei = int(e.split(".")[1])
        if si >= ei:
            return
        i = si
        while i < ei:
            fmt = self._get_fmt_at(f"1.{i}")
            j = i + 1
            while j < ei:
                nf = self._get_fmt_at(f"1.{j}")
                if nf != fmt:
                    break
                j += 1
            fmt.update(updates)
            new_tag = self._get_or_create_fmt_tag(fmt)
            self._remove_fmt_tags_in_range(f"1.{i}", f"1.{j}")
            self._edit_widget.tag_add(new_tag, f"1.{i}", f"1.{j}")
            i = j

    def _toggle_flag(self, bit):
        if not self._edit_widget:
            return
        s, e = self._get_edit_sel()
        si = int(s.split(".")[1])
        ei = int(e.split(".")[1])
        if si >= ei:
            return
        i = si
        while i < ei:
            fmt = self._get_fmt_at(f"1.{i}")
            j = i + 1
            while j < ei:
                nf = self._get_fmt_at(f"1.{j}")
                if nf != fmt:
                    break
                j += 1
            fmt["flags"] = fmt.get("flags", 0) ^ bit
            new_tag = self._get_or_create_fmt_tag(fmt)
            self._remove_fmt_tags_in_range(f"1.{i}", f"1.{j}")
            self._edit_widget.tag_add(new_tag, f"1.{i}", f"1.{j}")
            i = j
        self._update_toolbar_from_cursor()

    def _toggle_bold(self):
        self._toggle_flag(16)

    def _toggle_italic(self):
        self._toggle_flag(2)

    def _toggle_underline(self):
        self._toggle_flag(1)

    def _on_font_change(self):
        if self._updating_toolbar or not self._edit_widget:
            return
        f = FONT_MAP.get(self._edit_font_var.get(), "helv")
        fn = {"helv": "Helvetica", "tiro": "TimesRoman", "cour": "Courier"}.get(f, "Helvetica")
        self._modify_selection({"font": f, "font_name": fn})

    def _on_size_change(self):
        if self._updating_toolbar or not self._edit_widget:
            return
        try:
            sz = max(1, int(self._edit_size_var.get()))
        except ValueError:
            return
        self._modify_selection({"size": sz})

    def _on_color_change(self):
        if self._updating_toolbar or not self._edit_widget:
            return
        c = COLOR_MAP.get(self._edit_color_var.get(), (0, 0, 0))
        self._modify_selection({"color": c})

    # ─── Commit / Cancel ─────────────────────────────────────────────
    def _commit_edit(self):
        if not self._editing_line or not self._edit_widget:
            return
        self._push_undo()
        text = self._edit_widget.get("1.0", "end-1c")
        ln = self._editing_line

        if not text.strip():
            ln["deleted"] = True
            ln["modified"] = True
        else:
            # read spans from tags
            spans = []
            i = 0
            while i < len(text):
                fmt = self._get_fmt_at(f"1.{i}")
                j = i + 1
                while j < len(text):
                    nf = self._get_fmt_at(f"1.{j}")
                    if nf != fmt:
                        break
                    j += 1
                spans.append({
                    "text": text[i:j],
                    "font": fmt.get("font", "helv"),
                    "font_name": fmt.get("font_name", "Helvetica"),
                    "size": fmt.get("size", 12),
                    "color": fmt.get("color", (0, 0, 0)),
                    "flags": fmt.get("flags", 0),
                })
                i = j
            ln["text"] = text
            ln["spans"] = spans
            if spans:
                first = spans[0]
                ln["font"] = first["font"]
                ln["font_name"] = first["font_name"]
                ln["size"] = first["size"]
                ln["color"] = first["color"]
                ln["flags"] = first["flags"]
            # Detect text OR format changes
            changed = text != ln.get("orig_text", text)
            if not changed:
                orig_spans = ln.get("_orig_spans", [])
                if len(spans) != len(orig_spans):
                    changed = True
                else:
                    for ns, os_ in zip(spans, orig_spans):
                        if (ns["text"] != os_["text"] or ns["font"] != os_["font"] or
                            abs(ns["size"] - os_["size"]) > 0.5 or
                            ns["flags"] != os_["flags"] or ns["color"] != os_["color"]):
                            changed = True
                            break
            if changed:
                ln["modified"] = True

        self.canvas.delete(self._edit_win_id)
        self._edit_widget.destroy()
        self._edit_widget = None
        self._edit_win_id = None
        self._editing_line = None
        self._format_tags = {}
        self._hide_style_toolbar()
        self._hide_resize_handle()
        self._render()

    def _cancel_edit(self):
        if self._edit_widget:
            self.canvas.delete(self._edit_win_id)
            self._edit_widget.destroy()
            self._edit_widget = None
            self._edit_win_id = None
            self._editing_line = None
            self._format_tags = {}
        self._hide_style_toolbar()
        self._hide_resize_handle()

    # ─── Create text box (Agregar Texto mode) ────────────────────────
    def _create_text_box(self, px, py):
        self._push_undo()
        sz = 14
        obj = {
            "type": "text",
            "bbox": [px, py, px + 150, py + sz * 1.4],
            "text": "", "orig_text": "",
            "spans": [{"text": "", "font": "helv", "font_name": "Helvetica",
                        "size": sz, "color": (0, 0, 0), "flags": 0}],
            "font": "helv", "font_name": "Helvetica",
            "size": sz, "color": (0, 0, 0), "flags": 0,
        }
        self.added_objects.append(obj)
        self._select(obj)
        self._start_inline_edit(obj)

    # ─── Place image ─────────────────────────────────────────────────
    def _place_image(self, rect):
        self._push_undo()
        path = filedialog.askopenfilename(
            title="Seleccionar imagen",
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.bmp *.tiff *.webp"), ("Todos", "*.*")])
        if not path:
            return
        obj = {"type": "image", "bbox": rect, "image_path": path}
        self.added_objects.append(obj)
        self._select(obj)
        self._render()

    # ─── Highlight ───────────────────────────────────────────────────
    def _apply_highlight(self, rect):
        self._push_undo()
        page = self.doc[self.current_page]
        try:
            a = page.add_highlight_annot(fitz.Rect(rect))
            a.set_colors(stroke=(1, 1, 0))
            a.update()
        except Exception as e:
            messagebox.showerror("Error", str(e))
        if self.current_page in self.page_states:
            del self.page_states[self.current_page]
        self._extract_lines()
        self._rebuild_thumb(self.current_page)
        self._render()

    # ─── Rotate / Delete page ────────────────────────────────────────
    def _rotate(self, angle):
        if not self.doc:
            return
        page = self.doc[self.current_page]
        page.set_rotation((page.rotation + angle) % 360)
        if self.current_page in self.page_states:
            del self.page_states[self.current_page]
        self._extract_lines()
        self.added_objects = []
        self._rebuild_thumb(self.current_page)
        self._render()

    def _delete_page(self):
        if not self.doc or self.doc.page_count <= 1:
            messagebox.showwarning("Atención", "No se puede eliminar la única página.")
            return
        if not messagebox.askyesno("Confirmar", f"¿Eliminar página {self.current_page+1}?"):
            return
        if self.current_page in self.page_states:
            del self.page_states[self.current_page]
        self.doc.delete_page(self.current_page)
        if self.current_page >= self.doc.page_count:
            self.current_page = self.doc.page_count - 1
        new_states = {}
        for k, v in self.page_states.items():
            nk = k - 1 if k > self.current_page else k
            if nk >= 0:
                new_states[nk] = v
        self.page_states = new_states
        self._build_thumbs()
        self._load_page(self.current_page)

    # ─── OCR ─────────────────────────────────────────────────────────
    def _extract_text_to_box(self):
        if not self.doc:
            return
        text = self.doc[self.current_page].get_text()
        self.ocr_box.delete("1.0", "end")
        self.ocr_box.insert("1.0", text.strip() or "(Sin texto embebido)")

    def _ocr_page(self):
        if not self.doc:
            return
        if not OCR_AVAILABLE:
            messagebox.showinfo("OCR",
                "Para usar OCR, instala rapidocr-onnxruntime:\n\n"
                "pip install rapidocr-onnxruntime\n\n"
                "Usa ONNX Runtime (liviano, sin PyTorch).")
            return

        self.hint_lbl.configure(text="Procesando OCR...")
        self.update_idletasks()

        pix = self.doc[self.current_page].get_pixmap(dpi=300, alpha=False)
        im = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        img_np = np.array(im)
        ocr_scale = 300.0 / 72.0

        def do_ocr():
            try:
                if self._ocr_reader is None:
                    self._ocr_reader = RapidOCR()
                results, _ = self._ocr_reader(img_np)
                self.after(0, lambda r=results: self._apply_ocr_results(r, ocr_scale))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error OCR", str(e)))
                self.after(0, lambda: self.hint_lbl.configure(text="Error en OCR"))

        threading.Thread(target=do_ocr, daemon=True).start()

    def _apply_ocr_results(self, results, ocr_scale):
        self._push_undo()
        # Remove previous OCR objects
        self.added_objects = [o for o in self.added_objects if not o.get("ocr")]

        # Build list of native text bboxes to skip overlap
        native_bboxes = []
        for ln in self.text_lines:
            if not ln.get("deleted"):
                native_bboxes.append(ln["bbox"])

        lines = []
        if results:
            for bbox, text, _conf in results:
                xs = [p[0] for p in bbox]
                ys = [p[1] for p in bbox]
                x0 = min(xs) / ocr_scale
                y0 = min(ys) / ocr_scale
                x1 = max(xs) / ocr_scale
                y1 = max(ys) / ocr_scale

                # Skip if this OCR region overlaps significantly with native text
                skip = False
                for nb in native_bboxes:
                    ox0 = max(x0, nb[0])
                    oy0 = max(y0, nb[1])
                    ox1 = min(x1, nb[2])
                    oy1 = min(y1, nb[3])
                    if ox0 < ox1 and oy0 < oy1:
                        overlap_area = (ox1 - ox0) * (oy1 - oy0)
                        ocr_area = max(1, (x1 - x0) * (y1 - y0))
                        if overlap_area / ocr_area > 0.3:
                            skip = True
                            break
                if skip:
                    continue

                sz = max(8, (y1 - y0) * 0.85)
                obj = {
                    "type": "text", "ocr": True,
                    "bbox": [x0, y0, x1, y1],
                    "text": text, "orig_text": text,
                    "spans": [{"text": text, "font": "helv", "font_name": "Helvetica",
                               "size": sz, "color": (0, 0, 0), "flags": 0}],
                    "font": "helv", "font_name": "Helvetica",
                    "size": sz, "color": (0, 0, 0), "flags": 0,
                }
                self.added_objects.append(obj)
                lines.append(text)
        full_text = "\n".join(lines) if lines else "(OCR no detectó texto)"
        self.ocr_box.delete("1.0", "end")
        self.ocr_box.insert("1.0", full_text)
        self.hint_lbl.configure(text=f"OCR completado — {len(lines)} bloques detectados (cyan)")
        self._render()

    def _ocr_image(self):
        if not OCR_AVAILABLE:
            messagebox.showinfo("OCR",
                "Para usar OCR, instala rapidocr-onnxruntime:\n\n"
                "pip install rapidocr-onnxruntime")
            return
        path = filedialog.askopenfilename(
            title="Seleccionar imagen para OCR",
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.bmp *.tiff *.webp"), ("Todos", "*.*")])
        if not path:
            return
        self.hint_lbl.configure(text="Procesando OCR de imagen...")
        self.update_idletasks()
        try:
            im = Image.open(path).convert("RGB")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir la imagen.\n\n{e}")
            return
        img_np = np.array(im)

        def do_ocr():
            try:
                if self._ocr_reader is None:
                    self._ocr_reader = RapidOCR()
                results, _ = self._ocr_reader(img_np)
                if results:
                    text = "\n".join(r[1] for r in results)
                else:
                    text = ""
                self.after(0, lambda t=text: self._show_ocr_text(t, path))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error OCR", str(e)))
                self.after(0, lambda: self.hint_lbl.configure(text="Error en OCR"))

        threading.Thread(target=do_ocr, daemon=True).start()

    def _show_ocr_text(self, text, path):
        self.ocr_box.delete("1.0", "end")
        self.ocr_box.insert("1.0", text.strip() or "(OCR no detectó texto)")
        name = os.path.basename(path)
        self.hint_lbl.configure(text=f"OCR de {name} completado")

    def _copy_ocr(self):
        text = self.ocr_box.get("1.0", "end").strip()
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.hint_lbl.configure(text="Texto copiado al portapapeles")

    # ─── Apply all changes to PDF (on save) ──────────────────────────
    def _apply_all_changes(self):
        self._store_page_state()
        for page_idx, state in self.page_states.items():
            if page_idx >= self.doc.page_count:
                continue
            page = self.doc[page_idx]
            lines = state["text_lines"]
            added = state["added_objects"]

            needs_redact = False
            for ln in lines:
                if ln.get("deleted") or ln.get("modified") or ln.get("moved"):
                    page.add_redact_annot(fitz.Rect(ln["bbox_orig"]), fill=(1, 1, 1))
                    needs_redact = True
            if needs_redact:
                page.apply_redactions()

            for ln in lines:
                if ln.get("deleted"):
                    continue
                if ln.get("modified") or ln.get("moved"):
                    bb = ln["bbox"]
                    spans = ln.get("spans", [])
                    if spans:
                        x_pos = bb[0]
                        for sp in spans:
                            fn = _resolve_font_with_flags(sp.get("font", "helv"), sp.get("flags", 0))
                            pt = fitz.Point(x_pos, bb[1] + sp["size"])
                            try:
                                page.insert_text(pt, sp["text"], fontsize=sp["size"],
                                                 fontname=fn, color=sp["color"], overlay=True)
                                tw = fitz.get_text_length(sp["text"], fontname=fn, fontsize=sp["size"])
                                x_pos += tw
                            except Exception:
                                x_pos += len(sp["text"]) * sp["size"] * 0.5
                    else:
                        fn = _resolve_font_with_flags(ln["font"], ln.get("flags", 0))
                        pt = fitz.Point(bb[0], bb[1] + ln["size"])
                        try:
                            page.insert_text(pt, ln["text"], fontsize=ln["size"],
                                             fontname=fn, color=ln["color"], overlay=True)
                        except Exception:
                            pass

            # Redact areas under OCR objects so original scanned image is blanked
            ocr_redact = False
            for obj in added:
                if obj.get("ocr") and obj["type"] == "text":
                    bb = obj["bbox"]
                    page.add_redact_annot(fitz.Rect(bb), fill=(1, 1, 1))
                    ocr_redact = True
            if ocr_redact:
                page.apply_redactions()

            for obj in added:
                if obj["type"] == "text":
                    bb = obj["bbox"]
                    spans = obj.get("spans", [])
                    if spans:
                        x_pos = bb[0]
                        for sp in spans:
                            if not sp.get("text", "").strip():
                                continue
                            fn = _resolve_font_with_flags(sp.get("font", "helv"), sp.get("flags", 0))
                            pt = fitz.Point(x_pos, bb[1] + sp.get("size", 14))
                            try:
                                page.insert_text(pt, sp["text"], fontsize=sp.get("size", 14),
                                                 fontname=fn, color=sp.get("color", (0, 0, 0)), overlay=True)
                                tw = fitz.get_text_length(sp["text"], fontname=fn, fontsize=sp.get("size", 14))
                                x_pos += tw
                            except Exception:
                                x_pos += len(sp["text"]) * sp.get("size", 14) * 0.5
                elif obj["type"] == "image":
                    try:
                        page.insert_image(fitz.Rect(obj["bbox"]), filename=obj["image_path"])
                    except Exception:
                        pass
