# app_pdf_studio.py
APP_VERSION = "2.0.0"

import os
import threading
import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk
from PIL import Image, ImageOps, ImageTk, ImageDraw
import fitz  # PyMuPDF
from pypdf import PdfReader, PdfWriter

try:
    from rapidocr_onnxruntime import RapidOCR
    import numpy as np
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except Exception:
    DND_AVAILABLE = False
    DND_FILES = None
    TkinterDnD = None


# -------------------- Utilidades -------------------- #
def fit_to_box(pil_img: Image.Image, max_w: int, max_h: int) -> Image.Image:
    w, h = pil_img.size
    if w <= 0 or h <= 0:
        return pil_img
    scale = min(max_w / w, max_h / h, 1.0)
    size = (max(1, int(w * scale)), max(1, int(h * scale)))
    return pil_img.resize(size, Image.Resampling.LANCZOS)


def make_square_thumbnail(im: Image.Image, size=(72, 72), bg="#23293a") -> Image.Image:
    canvas = Image.new("RGB", size, bg)
    thumb = fit_to_box(im, size[0] - 8, size[1] - 8)
    x = (size[0] - thumb.size[0]) // 2
    y = (size[1] - thumb.size[1]) // 2
    canvas.paste(thumb, (x, y))
    return canvas


def normalize_image_for_pdf(im: Image.Image) -> Image.Image:
    im = ImageOps.exif_transpose(im)
    if im.mode in ("RGBA", "LA"):
        bg = Image.new("RGB", im.size, "white")
        bg.paste(im, mask=im.split()[-1])
        return bg
    if im.mode == "P":
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, "white")
        bg.paste(im, mask=im.split()[-1])
        return bg
    return im.convert("RGB")


def parse_dropped_files(widget, data: str):
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


def collect_files(paths, allowed_exts):
    allowed = {e.lower() for e in allowed_exts}
    results = []

    for p in paths:
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                for fn in files:
                    fp = os.path.join(root, fn)
                    if os.path.splitext(fp)[1].lower() in allowed:
                        results.append(fp)
        elif os.path.isfile(p) and os.path.splitext(p)[1].lower() in allowed:
            results.append(p)

    seen = set()
    unique = []
    for p in results:
        norm = os.path.normcase(os.path.abspath(p))
        if norm not in seen:
            seen.add(norm)
            unique.append(p)
    return unique


def create_default_logo(size=(44, 44)):
    w, h = size
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([1, 1, w - 2, h - 2], radius=10, fill="#2f6fed", outline="#8cb0ff", width=1)
    draw.rectangle([13, 10, 31, 34], fill="#ffffff")
    draw.rectangle([16, 13, 28, 18], fill="#2f6fed")
    draw.rectangle([16, 21, 28, 24], fill="#2f6fed")
    draw.rectangle([16, 27, 28, 30], fill="#2f6fed")
    return img.convert("RGB")


def load_logo_image():
    candidates = ["assets/logo.png", "logo.png"]
    for p in candidates:
        if os.path.exists(p):
            try:
                with Image.open(p) as im:
                    return fit_to_box(im.convert("RGB"), 44, 44)
            except Exception:
                pass
    return create_default_logo((44, 44))


def setup_treeview_dark_style(root):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    style.configure(
        "Dark.Treeview",
        background="#121722",
        foreground="#e4e9f5",
        fieldbackground="#121722",
        rowheight=84,
        borderwidth=0,
        relief="flat",
        font=("Segoe UI", 10),
    )
    style.map(
        "Dark.Treeview",
        background=[("selected", "#2f6fed")],
        foreground=[("selected", "#ffffff")]
    )


# -------------------- ZoomablePreview widget -------------------- #
class ZoomablePreview(ctk.CTkFrame):
    """Canvas-based preview with zoom controls and scrollbars."""

    ZOOM_LEVELS = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 4.0]

    def __init__(self, master, placeholder="Selecciona un archivo", **kwargs):
        super().__init__(master, fg_color="#0f1420", corner_radius=12, **kwargs)
        self._pil_image = None
        self._zoom = 1.0
        self._tk_img = None
        self._placeholder = placeholder
        self._build()

    def _build(self):
        small = ctk.CTkFont(size=11)

        # Zoom toolbar
        bar = ctk.CTkFrame(self, fg_color="#161b26", height=32)
        bar.pack(fill="x", padx=4, pady=(4, 0))
        ctk.CTkButton(bar, text="\u2212", width=30, height=26,
                       command=self.zoom_out).pack(side="left", padx=2, pady=2)
        self.zoom_label = ctk.CTkLabel(bar, text="Ajustar", width=55, font=small)
        self.zoom_label.pack(side="left", padx=2)
        ctk.CTkButton(bar, text="+", width=30, height=26,
                       command=self.zoom_in).pack(side="left", padx=2, pady=2)
        ctk.CTkButton(bar, text="Ajustar", width=60, height=26,
                       command=self.zoom_fit).pack(side="left", padx=6, pady=2)

        # Scrollable canvas
        container = ctk.CTkFrame(self, fg_color="#0f1420")
        container.pack(fill="both", expand=True, padx=4, pady=4)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(container, bg="#0f1420", highlightthickness=0)
        self.v_scroll = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.h_scroll = ttk.Scrollbar(container, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(xscrollcommand=self.h_scroll.set, yscrollcommand=self.v_scroll.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.v_scroll.grid(row=0, column=1, sticky="ns")
        self.h_scroll.grid(row=1, column=0, sticky="ew")

        self._placeholder_id = self.canvas.create_text(
            200, 150, text=self._placeholder, fill="#93a1ba", font=("Segoe UI", 12))

        self.canvas.bind("<Control-MouseWheel>", self._on_ctrl_scroll)
        self.canvas.bind("<MouseWheel>", self._on_scroll_plain)
        self.canvas.bind("<Configure>", self._on_resize)

    def set_image(self, pil_img):
        self._pil_image = pil_img
        self._zoom = self._calc_fit_zoom()
        self._refresh()

    def clear(self):
        self._pil_image = None
        self._tk_img = None
        self.canvas.delete("all")
        self._placeholder_id = self.canvas.create_text(
            200, 150, text=self._placeholder, fill="#93a1ba", font=("Segoe UI", 12))
        self.zoom_label.configure(text="Ajustar")

    def _calc_fit_zoom(self):
        if not self._pil_image:
            return 1.0
        cw = max(100, self.canvas.winfo_width())
        ch = max(100, self.canvas.winfo_height())
        w, h = self._pil_image.size
        if w <= 0 or h <= 0:
            return 1.0
        return min(cw / w, ch / h, 4.0)

    def _refresh(self):
        if not self._pil_image:
            return
        w, h = self._pil_image.size
        nw, nh = max(1, int(w * self._zoom)), max(1, int(h * self._zoom))
        resized = self._pil_image.resize((nw, nh), Image.Resampling.LANCZOS)
        self._tk_img = ImageTk.PhotoImage(resized)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self._tk_img)
        self.canvas.configure(scrollregion=(0, 0, nw, nh))
        self.zoom_label.configure(text=f"{self._zoom*100:.0f}%")

    def zoom_in(self):
        for z in self.ZOOM_LEVELS:
            if z > self._zoom + 0.01:
                self._zoom = z
                self._refresh()
                return

    def zoom_out(self):
        for z in reversed(self.ZOOM_LEVELS):
            if z < self._zoom - 0.01:
                self._zoom = z
                self._refresh()
                return

    def zoom_fit(self):
        self._zoom = self._calc_fit_zoom()
        self._refresh()

    def _on_ctrl_scroll(self, event):
        if event.delta > 0:
            self.zoom_in()
        else:
            self.zoom_out()
        return "break"

    def _on_scroll_plain(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_resize(self, _):
        # Re-fit only if image is smaller than canvas (auto-fit behavior)
        pass


# -------------------- Tab 1: Imágenes -> PDF -------------------- #
class ImagesToPdfTab(ctk.CTkFrame):
    IMG_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp")

    def __init__(self, master):
        super().__init__(master)
        self.records = []  # [{path, thumb_tk}]
        self._drag_from_index = None

        self._build_ui()
        self._register_dnd_if_available()

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Barra superior
        top = ctk.CTkFrame(self, fg_color="#161b26")
        top.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(12, 8))
        top.grid_columnconfigure(7, weight=1)

        ctk.CTkButton(top, text="Agregar imágenes", command=self.add_images).grid(row=0, column=0, padx=6, pady=8)
        ctk.CTkButton(top, text="Quitar", command=self.remove_selected).grid(row=0, column=1, padx=6, pady=8)
        ctk.CTkButton(top, text="Subir", width=70, command=self.move_up).grid(row=0, column=2, padx=6, pady=8)
        ctk.CTkButton(top, text="Bajar", width=70, command=self.move_down).grid(row=0, column=3, padx=6, pady=8)
        ctk.CTkButton(top, text="Limpiar", width=80, command=self.clear_all).grid(row=0, column=4, padx=6, pady=8)

        self.dnd_hint = ctk.CTkLabel(top, text="Arrastra imágenes desde el explorador")
        self.dnd_hint.grid(row=0, column=7, padx=10, sticky="e")

        # Panel izquierdo (lista con miniaturas)
        left = ctk.CTkFrame(self, fg_color="#121722")
        left.grid(row=1, column=0, sticky="nsw", padx=(12, 8), pady=(0, 12))
        left.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(left, text="Orden de páginas (miniaturas)", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(10, 6)
        )

        container = ctk.CTkFrame(left, fg_color="#121722")
        container.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(container, show="tree", selectmode="browse", style="Dark.Treeview", height=20)
        self.tree.grid(row=0, column=0, sticky="nsew")

        scroll = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll.set)

        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<ButtonPress-1>", self.on_drag_start)
        self.tree.bind("<B1-Motion>", self.on_drag_motion)

        # Panel derecho (preview con zoom)
        right = ctk.CTkFrame(self, fg_color="#121722")
        right.grid(row=1, column=1, sticky="nsew", padx=(8, 12), pady=(0, 12))
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(right, text="Vista previa", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w", padx=12, pady=(12, 6)
        )

        self.preview_widget = ZoomablePreview(right, placeholder="Selecciona una imagen")
        self.preview_widget.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        # Pie
        bottom = ctk.CTkFrame(self, fg_color="#161b26")
        bottom.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 12))
        bottom.grid_columnconfigure(1, weight=1)

        self.count_label = ctk.CTkLabel(bottom, text="0 imágenes")
        self.count_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")

        ctk.CTkButton(bottom, text="Convertir a PDF", height=40, command=self.convert_to_pdf).grid(
            row=0, column=2, padx=10, pady=10, sticky="e"
        )

    def _register_dnd_if_available(self):
        if not DND_AVAILABLE:
            self.dnd_hint.configure(text="Drag & Drop no disponible (instala tkinterdnd2)")
            return

        for w in [self, self.tree, self.preview_widget, self.preview_widget.canvas]:
            try:
                w.drop_target_register(DND_FILES)
                w.dnd_bind("<<Drop>>", self.on_drop_files)
            except Exception:
                pass

    def on_drop_files(self, event):
        dropped = parse_dropped_files(self, event.data)
        files = collect_files(dropped, self.IMG_EXTS)
        if not files:
            messagebox.showwarning("Sin archivos válidos", "Suelta imágenes válidas (png, jpg, webp, etc.).")
            return
        self.add_image_paths(files)

    def add_images(self):
        paths = filedialog.askopenfilenames(
            title="Seleccionar imágenes",
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp"), ("Todos", "*.*")]
        )
        if paths:
            self.add_image_paths(list(paths))

    def add_image_paths(self, paths):
        added = 0
        for path in paths:
            try:
                with Image.open(path) as im:
                    im = ImageOps.exif_transpose(im).convert("RGB")
                    thumb_pil = make_square_thumbnail(im, size=(76, 76), bg="#1d2433")
                thumb_tk = ImageTk.PhotoImage(thumb_pil)
                self.records.append({"path": path, "thumb": thumb_tk})
                added += 1
            except Exception:
                continue
        if added:
            self.refresh_tree(select_index=len(self.records) - 1)

    def refresh_tree(self, select_index=None):
        self.tree.delete(*self.tree.get_children())
        for i, rec in enumerate(self.records):
            label = f"{i + 1:03d}. {os.path.basename(rec['path'])}"
            self.tree.insert("", "end", iid=str(i), text=label, image=rec["thumb"])

        self.count_label.configure(text=f"{len(self.records)} imágenes")

        if self.records:
            if select_index is None:
                select_index = 0
            select_index = max(0, min(select_index, len(self.records) - 1))
            self.tree.selection_set(str(select_index))
            self.tree.focus(str(select_index))
            self.tree.see(str(select_index))
            self.show_preview(select_index)
        else:
            self.clear_preview()

    def get_selected_index(self):
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except Exception:
            return None

    def on_select(self, _=None):
        idx = self.get_selected_index()
        if idx is not None:
            self.show_preview(idx)

    def show_preview(self, idx):
        if not (0 <= idx < len(self.records)):
            self.clear_preview()
            return
        path = self.records[idx]["path"]
        try:
            with Image.open(path) as im:
                im = ImageOps.exif_transpose(im).convert("RGB")
                self.preview_widget.set_image(im.copy())
        except Exception:
            self.preview_widget.clear()

    def clear_preview(self):
        self.preview_widget.clear()

    def on_drag_start(self, event):
        row = self.tree.identify_row(event.y)
        self._drag_from_index = int(row) if row else None

    def on_drag_motion(self, event):
        if self._drag_from_index is None:
            return
        row = self.tree.identify_row(event.y)
        if not row:
            return
        to_index = int(row)
        frm = self._drag_from_index
        if to_index == frm:
            return
        item = self.records.pop(frm)
        self.records.insert(to_index, item)
        self._drag_from_index = to_index
        self.refresh_tree(select_index=to_index)

    def remove_selected(self):
        idx = self.get_selected_index()
        if idx is None:
            return
        self.records.pop(idx)
        self.refresh_tree(select_index=max(0, idx - 1))

    def move_up(self):
        idx = self.get_selected_index()
        if idx is None or idx == 0:
            return
        self.records[idx - 1], self.records[idx] = self.records[idx], self.records[idx - 1]
        self.refresh_tree(select_index=idx - 1)

    def move_down(self):
        idx = self.get_selected_index()
        if idx is None or idx >= len(self.records) - 1:
            return
        self.records[idx + 1], self.records[idx] = self.records[idx], self.records[idx + 1]
        self.refresh_tree(select_index=idx + 1)

    def clear_all(self):
        self.records.clear()
        self.refresh_tree()

    def convert_to_pdf(self):
        if not self.records:
            messagebox.showwarning("Atención", "Agrega imágenes primero.")
            return

        out = filedialog.asksaveasfilename(
            title="Guardar PDF",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")]
        )
        if not out:
            return

        try:
            pil_images = []
            for rec in self.records:
                with Image.open(rec["path"]) as im:
                    pil_images.append(normalize_image_for_pdf(im).copy())

            first, rest = pil_images[0], pil_images[1:]
            first.save(out, "PDF", save_all=True, append_images=rest)

            for im in pil_images:
                im.close()

            messagebox.showinfo("Éxito", f"PDF creado:\n{out}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo crear PDF.\n\n{e}")


# -------------------- Tab 2: Fusionar PDFs por página -------------------- #
class MergePdfTab(ctk.CTkFrame):
    PDF_EXTS = (".pdf",)

    def __init__(self, master):
        super().__init__(master)
        self.records = []  # [{pdf_path,page_idx,label,thumb}]
        self._drag_from_index = None

        self._build_ui()
        self._register_dnd_if_available()

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(self, fg_color="#161b26")
        top.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(12, 8))
        top.grid_columnconfigure(7, weight=1)

        ctk.CTkButton(top, text="Agregar PDF(s)", command=self.add_pdfs).grid(row=0, column=0, padx=6, pady=8)
        ctk.CTkButton(top, text="Quitar página", command=self.remove_selected).grid(row=0, column=1, padx=6, pady=8)
        ctk.CTkButton(top, text="Subir", width=70, command=self.move_up).grid(row=0, column=2, padx=6, pady=8)
        ctk.CTkButton(top, text="Bajar", width=70, command=self.move_down).grid(row=0, column=3, padx=6, pady=8)
        ctk.CTkButton(top, text="Limpiar", width=80, command=self.clear_all).grid(row=0, column=4, padx=6, pady=8)

        self.dnd_hint = ctk.CTkLabel(top, text="Arrastra PDF(s) desde el explorador")
        self.dnd_hint.grid(row=0, column=7, padx=10, sticky="e")

        left = ctk.CTkFrame(self, fg_color="#121722")
        left.grid(row=1, column=0, sticky="nsw", padx=(12, 8), pady=(0, 12))
        left.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(left, text="Orden final de páginas (miniaturas)", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(10, 6)
        )

        container = ctk.CTkFrame(left, fg_color="#121722")
        container.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(container, show="tree", selectmode="browse", style="Dark.Treeview", height=20)
        self.tree.grid(row=0, column=0, sticky="nsew")

        scroll = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll.set)

        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<ButtonPress-1>", self.on_drag_start)
        self.tree.bind("<B1-Motion>", self.on_drag_motion)

        right = ctk.CTkFrame(self, fg_color="#121722")
        right.grid(row=1, column=1, sticky="nsew", padx=(8, 12), pady=(0, 12))
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(right, text="Vista previa de página", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w", padx=12, pady=(12, 6)
        )

        self.preview_widget = ZoomablePreview(right, placeholder="Selecciona una página")
        self.preview_widget.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        bottom = ctk.CTkFrame(self, fg_color="#161b26")
        bottom.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 12))
        bottom.grid_columnconfigure(1, weight=1)

        self.count_label = ctk.CTkLabel(bottom, text="0 páginas")
        self.count_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")

        ctk.CTkButton(bottom, text="Fusionar PDF", height=40, command=self.merge_pdf).grid(
            row=0, column=2, padx=10, pady=10, sticky="e"
        )

    def _register_dnd_if_available(self):
        if not DND_AVAILABLE:
            self.dnd_hint.configure(text="Drag & Drop no disponible (instala tkinterdnd2)")
            return

        for w in [self, self.tree, self.preview_widget, self.preview_widget.canvas]:
            try:
                w.drop_target_register(DND_FILES)
                w.dnd_bind("<<Drop>>", self.on_drop_files)
            except Exception:
                pass

    def on_drop_files(self, event):
        dropped = parse_dropped_files(self, event.data)
        files = collect_files(dropped, self.PDF_EXTS)
        if not files:
            messagebox.showwarning("Sin archivos válidos", "Suelta archivos PDF.")
            return
        self.add_pdf_paths(files)

    def add_pdfs(self):
        paths = filedialog.askopenfilenames(title="Seleccionar PDF(s)", filetypes=[("PDF", "*.pdf")])
        if paths:
            self.add_pdf_paths(list(paths))

    def add_pdf_paths(self, paths):
        for pdf_path in paths:
            try:
                doc = fitz.open(pdf_path)
                base = os.path.basename(pdf_path)

                for page_idx in range(doc.page_count):
                    page = doc.load_page(page_idx)

                    pix = page.get_pixmap(matrix=fitz.Matrix(0.30, 0.30), alpha=False)
                    im = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    thumb_pil = make_square_thumbnail(im, size=(76, 76), bg="#1d2433")
                    thumb_tk = ImageTk.PhotoImage(thumb_pil)

                    label = f"{base} | pág. {page_idx + 1}"
                    self.records.append({
                        "pdf_path": pdf_path,
                        "page_idx": page_idx,
                        "label": label,
                        "thumb": thumb_tk
                    })

                doc.close()
            except Exception as e:
                messagebox.showwarning("Advertencia", f"No se pudo abrir:\n{pdf_path}\n\n{e}")

        self.refresh_tree(select_index=max(0, len(self.records) - 1))

    def refresh_tree(self, select_index=None):
        self.tree.delete(*self.tree.get_children())
        for i, rec in enumerate(self.records):
            txt = f"{i + 1:03d}. {rec['label']}"
            self.tree.insert("", "end", iid=str(i), text=txt, image=rec["thumb"])

        self.count_label.configure(text=f"{len(self.records)} páginas")

        if self.records:
            if select_index is None:
                select_index = 0
            select_index = max(0, min(select_index, len(self.records) - 1))
            self.tree.selection_set(str(select_index))
            self.tree.focus(str(select_index))
            self.tree.see(str(select_index))
            self.show_preview(select_index)
        else:
            self.clear_preview()

    def get_selected_index(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def on_select(self, _=None):
        idx = self.get_selected_index()
        if idx is not None:
            self.show_preview(idx)

    def show_preview(self, idx):
        if not (0 <= idx < len(self.records)):
            self.clear_preview()
            return

        rec = self.records[idx]
        try:
            doc = fitz.open(rec["pdf_path"])
            page = doc.load_page(rec["page_idx"])
            pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), alpha=False)
            doc.close()

            im = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            self.preview_widget.set_image(im)
        except Exception:
            self.preview_widget.clear()

    def clear_preview(self):
        self.preview_widget.clear()

    def on_drag_start(self, event):
        row = self.tree.identify_row(event.y)
        self._drag_from_index = int(row) if row else None

    def on_drag_motion(self, event):
        if self._drag_from_index is None:
            return
        row = self.tree.identify_row(event.y)
        if not row:
            return

        to_index = int(row)
        frm = self._drag_from_index
        if to_index == frm:
            return

        item = self.records.pop(frm)
        self.records.insert(to_index, item)
        self._drag_from_index = to_index
        self.refresh_tree(select_index=to_index)

    def remove_selected(self):
        idx = self.get_selected_index()
        if idx is None:
            return
        self.records.pop(idx)
        self.refresh_tree(select_index=max(0, idx - 1))

    def move_up(self):
        idx = self.get_selected_index()
        if idx is None or idx == 0:
            return
        self.records[idx - 1], self.records[idx] = self.records[idx], self.records[idx - 1]
        self.refresh_tree(select_index=idx - 1)

    def move_down(self):
        idx = self.get_selected_index()
        if idx is None or idx >= len(self.records) - 1:
            return
        self.records[idx + 1], self.records[idx] = self.records[idx], self.records[idx + 1]
        self.refresh_tree(select_index=idx + 1)

    def clear_all(self):
        self.records.clear()
        self.refresh_tree()

    def merge_pdf(self):
        if not self.records:
            messagebox.showwarning("Atención", "Agrega PDF(s) primero.")
            return

        out = filedialog.asksaveasfilename(
            title="Guardar PDF fusionado",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")]
        )
        if not out:
            return

        try:
            writer = PdfWriter()
            cache = {}

            for rec in self.records:
                path, idx = rec["pdf_path"], rec["page_idx"]
                if path not in cache:
                    cache[path] = PdfReader(path)
                writer.add_page(cache[path].pages[idx])

            with open(out, "wb") as f:
                writer.write(f)

            messagebox.showinfo("Éxito", f"PDF fusionado:\n{out}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo fusionar el PDF.\n\n{e}")



# -------------------- Tab 3: Editor de PDF (modulo externo) -------- #
from editor_tab import EditPdfTab  # noqa: E402


# -------------------- Tab 4: PDF -> JPG/PNG -------------------- #
class PdfToImageTab(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self.doc = None
        self.pdf_path = None
        self.current_page = 0
        self.page_thumbs = []

        self._build_ui()
        self._register_dnd_if_available()

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        bold = ctk.CTkFont(weight="bold")
        small = ctk.CTkFont(size=12)

        # ---- Barra superior ----
        top = ctk.CTkFrame(self, fg_color="#161b26")
        top.grid(row=0, column=0, columnspan=3, sticky="ew", padx=12, pady=(12, 8))

        ctk.CTkButton(top, text="Abrir PDF", width=110, command=self.open_pdf).grid(
            row=0, column=0, padx=6, pady=8)

        sep = ctk.CTkFrame(top, width=2, height=28, fg_color="#2a3040")
        sep.grid(row=0, column=1, padx=8, pady=8)

        ctk.CTkLabel(top, text="DPI:", font=small).grid(row=0, column=2, padx=(6, 2), pady=8)
        self.dpi_var = tk.StringVar(value="300")
        ctk.CTkOptionMenu(top, variable=self.dpi_var, width=80,
                           values=["72", "150", "300", "600"]).grid(
            row=0, column=3, padx=4, pady=8)

        ctk.CTkLabel(top, text="Formato:", font=small).grid(row=0, column=4, padx=(10, 2), pady=8)
        self.format_var = tk.StringVar(value="JPG")
        ctk.CTkOptionMenu(top, variable=self.format_var, width=80,
                           values=["JPG", "PNG"]).grid(row=0, column=5, padx=4, pady=8)

        ctk.CTkLabel(top, text="Calidad JPG:", font=small).grid(
            row=0, column=6, padx=(10, 2), pady=8)
        self.quality_var = tk.StringVar(value="95")
        ctk.CTkOptionMenu(top, variable=self.quality_var, width=80,
                           values=["70", "80", "90", "95", "100"]).grid(
            row=0, column=7, padx=4, pady=8)

        self.dnd_hint = ctk.CTkLabel(top, text="Arrastra un PDF")
        self.dnd_hint.grid(row=0, column=8, padx=10, sticky="e")

        # ---- Panel izquierdo: miniaturas ----
        left = ctk.CTkFrame(self, fg_color="#121722", width=200)
        left.grid(row=1, column=0, sticky="nsw", padx=(12, 4), pady=(0, 12))
        left.grid_rowconfigure(1, weight=1)
        left.grid_propagate(False)

        ctk.CTkLabel(left, text="Páginas", font=bold).grid(
            row=0, column=0, sticky="w", padx=10, pady=(10, 6))

        tree_frame = ctk.CTkFrame(left, fg_color="#121722")
        tree_frame.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(tree_frame, show="tree", selectmode="browse",
                                 style="Dark.Treeview", height=14)
        self.tree.grid(row=0, column=0, sticky="nsew")

        scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.bind("<<TreeviewSelect>>", self._on_page_select)

        # ---- Panel central: vista previa con zoom ----
        center = ctk.CTkFrame(self, fg_color="#121722")
        center.grid(row=1, column=1, sticky="nsew", padx=4, pady=(0, 12))
        center.grid_rowconfigure(1, weight=1)
        center.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(center, text="Vista previa", font=bold).grid(
            row=0, column=0, sticky="w", padx=12, pady=(12, 6))

        self.preview_widget = ZoomablePreview(center, placeholder="Abre un PDF para ver la vista previa")
        self.preview_widget.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        # ---- Panel derecho: exportar ----
        right = ctk.CTkFrame(self, fg_color="#121722", width=220)
        right.grid(row=1, column=2, sticky="nse", padx=(4, 12), pady=(0, 12))
        right.grid_propagate(False)

        ctk.CTkLabel(right, text="Exportar", font=bold).pack(
            anchor="w", padx=12, pady=(16, 8))

        ctk.CTkButton(right, text="Exportar página actual",
                       command=self.export_current_page, height=38).pack(
            fill="x", padx=12, pady=6)

        ctk.CTkButton(right, text="Exportar todas las páginas",
                       command=self.export_all_pages, height=38).pack(
            fill="x", padx=12, pady=6)

        ctk.CTkFrame(right, height=2, fg_color="#2a3040").pack(
            fill="x", padx=12, pady=10)

        ctk.CTkLabel(right, text="Rango personalizado", font=bold).pack(
            anchor="w", padx=12, pady=(4, 4))

        range_frame = ctk.CTkFrame(right, fg_color="transparent")
        range_frame.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(range_frame, text="Desde:", font=small).pack(side="left")
        self.range_from_var = tk.StringVar(value="1")
        ctk.CTkEntry(range_frame, textvariable=self.range_from_var, width=50).pack(
            side="left", padx=4)
        ctk.CTkLabel(range_frame, text="Hasta:", font=small).pack(side="left", padx=(8, 0))
        self.range_to_var = tk.StringVar(value="1")
        ctk.CTkEntry(range_frame, textvariable=self.range_to_var, width=50).pack(
            side="left", padx=4)

        ctk.CTkButton(right, text="Exportar rango",
                       command=self.export_range, height=38).pack(
            fill="x", padx=12, pady=(8, 6))

        ctk.CTkFrame(right, height=2, fg_color="#2a3040").pack(
            fill="x", padx=12, pady=10)

        self.info_label = ctk.CTkLabel(right, text="", font=small, text_color="#93a1ba",
                                        wraplength=190, justify="left")
        self.info_label.pack(anchor="w", padx=12, pady=4)

        # ---- Barra inferior ----
        bottom = ctk.CTkFrame(self, fg_color="#161b26")
        bottom.grid(row=2, column=0, columnspan=3, sticky="ew", padx=12, pady=(0, 12))
        bottom.grid_columnconfigure(1, weight=1)

        self.page_label = ctk.CTkLabel(bottom, text="Sin documento", font=small)
        self.page_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")

    def _register_dnd_if_available(self):
        if not DND_AVAILABLE:
            return
        for w in [self, self.tree, self.preview_widget, self.preview_widget.canvas]:
            try:
                w.drop_target_register(DND_FILES)
                w.dnd_bind("<<Drop>>", self._on_drop)
            except Exception:
                pass

    def _on_drop(self, event):
        dropped = parse_dropped_files(self, event.data)
        files = collect_files(dropped, (".pdf",))
        if files:
            self._load_pdf(files[0])

    # ---- Abrir PDF ----
    def open_pdf(self):
        path = filedialog.askopenfilename(
            title="Abrir PDF",
            filetypes=[("PDF", "*.pdf")]
        )
        if path:
            self._load_pdf(path)

    def _load_pdf(self, path):
        if self.doc:
            self.doc.close()

        try:
            self.doc = fitz.open(path)
            self.pdf_path = path
            self.current_page = 0
            self.range_to_var.set(str(self.doc.page_count))
            self._build_thumbnails()
            self._show_preview(0)
            self.info_label.configure(
                text=f"Archivo: {os.path.basename(path)}\n"
                     f"Páginas: {self.doc.page_count}"
            )
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el PDF.\n\n{e}")

    def _build_thumbnails(self):
        self.page_thumbs.clear()
        self.tree.delete(*self.tree.get_children())

        if not self.doc:
            return

        for i in range(self.doc.page_count):
            page = self.doc[i]
            pix = page.get_pixmap(matrix=fitz.Matrix(0.25, 0.25), alpha=False)
            im = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            thumb = make_square_thumbnail(im, size=(76, 76), bg="#1d2433")
            thumb_tk = ImageTk.PhotoImage(thumb)
            self.page_thumbs.append(thumb_tk)
            self.tree.insert("", "end", iid=str(i), text=f"  Página {i + 1}", image=thumb_tk)

        if self.doc.page_count > 0:
            self.tree.selection_set("0")
            self.tree.focus("0")

    def _on_page_select(self, _=None):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        self.current_page = idx
        self._show_preview(idx)

    def _show_preview(self, idx):
        if not self.doc or idx >= self.doc.page_count:
            return

        page = self.doc[idx]
        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), alpha=False)
        im = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        self.preview_widget.set_image(im)
        self.page_label.configure(
            text=f"Página {idx + 1} de {self.doc.page_count}  |  "
                 f"{page.rect.width:.0f} x {page.rect.height:.0f} pt")

    # ---- Helpers de exportación ----
    def _get_dpi(self):
        try:
            return max(36, int(self.dpi_var.get()))
        except ValueError:
            return 300

    def _get_quality(self):
        try:
            return max(1, min(100, int(self.quality_var.get())))
        except ValueError:
            return 95

    def _get_format(self):
        return self.format_var.get().upper()

    def _export_page(self, page_idx, output_path):
        page = self.doc[page_idx]
        dpi = self._get_dpi()
        scale = dpi / 72.0
        mat = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        im = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        fmt = self._get_format()
        if fmt == "JPG":
            im.save(output_path, "JPEG", quality=self._get_quality())
        else:
            im.save(output_path, "PNG")

    def _pdf_base_name(self):
        return os.path.splitext(os.path.basename(self.pdf_path))[0] if self.pdf_path else "pdf"

    # ---- Exportar página actual ----
    def export_current_page(self):
        if not self.doc:
            messagebox.showwarning("Atención", "Abre un PDF primero.")
            return

        fmt = self._get_format()
        ext = ".jpg" if fmt == "JPG" else ".png"
        base = self._pdf_base_name()
        default_name = f"{base}_pag_{self.current_page + 1}{ext}"

        path = filedialog.asksaveasfilename(
            title="Exportar página como imagen",
            initialfile=default_name,
            defaultextension=ext,
            filetypes=[(fmt, f"*{ext}")]
        )
        if not path:
            return

        try:
            self._export_page(self.current_page, path)
            messagebox.showinfo("Éxito", f"Página exportada:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo exportar.\n\n{e}")

    # ---- Exportar todas las páginas ----
    def export_all_pages(self):
        if not self.doc:
            messagebox.showwarning("Atención", "Abre un PDF primero.")
            return

        folder = filedialog.askdirectory(title="Seleccionar carpeta de destino")
        if not folder:
            return

        fmt = self._get_format()
        ext = ".jpg" if fmt == "JPG" else ".png"
        base = self._pdf_base_name()
        out_folder = os.path.join(folder, base)
        os.makedirs(out_folder, exist_ok=True)

        try:
            for i in range(self.doc.page_count):
                out_path = os.path.join(out_folder, f"{base}_pag_{i + 1}{ext}")
                self._export_page(i, out_path)

            messagebox.showinfo(
                "Éxito",
                f"{self.doc.page_count} páginas exportadas en:\n{out_folder}"
            )
        except Exception as e:
            messagebox.showerror("Error", f"Error al exportar.\n\n{e}")

    # ---- Exportar rango ----
    def export_range(self):
        if not self.doc:
            messagebox.showwarning("Atención", "Abre un PDF primero.")
            return

        try:
            from_page = max(1, int(self.range_from_var.get()))
            to_page = min(self.doc.page_count, int(self.range_to_var.get()))
        except ValueError:
            messagebox.showwarning("Atención", "Ingresa números válidos para el rango.")
            return

        if from_page > to_page:
            messagebox.showwarning("Atención", "El rango 'Desde' debe ser menor o igual a 'Hasta'.")
            return

        folder = filedialog.askdirectory(title="Seleccionar carpeta de destino")
        if not folder:
            return

        fmt = self._get_format()
        ext = ".jpg" if fmt == "JPG" else ".png"
        base = self._pdf_base_name()
        total = to_page - from_page + 1

        if total > 1:
            out_folder = os.path.join(folder, base)
            os.makedirs(out_folder, exist_ok=True)
        else:
            out_folder = folder

        try:
            count = 0
            for i in range(from_page - 1, to_page):
                out_path = os.path.join(out_folder, f"{base}_pag_{i + 1}{ext}")
                self._export_page(i, out_path)
                count += 1

            messagebox.showinfo(
                "Éxito",
                f"{count} páginas exportadas ({from_page}-{to_page}) en:\n{out_folder}"
            )
        except Exception as e:
            messagebox.showerror("Error", f"Error al exportar.\n\n{e}")


# -------------------- App Base (con/sin DnD) -------------------- #
class BaseApp(ctk.CTk):
    pass


if DND_AVAILABLE:
    class BaseApp(TkinterDnD.DnDWrapper, ctk.CTk):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.TkdndVersion = TkinterDnD._require(self)


# -------------------- Tab 5: OCR Imagen -------------------- #
class OcrImageTab(ctk.CTkFrame):
    """OCR de imágenes sueltas (PNG, JPG, etc.) sin necesidad de PDF."""

    def __init__(self, master):
        super().__init__(master)
        self._ocr_reader = None
        self._img_ref = None
        self._build_ui()
        self._register_dnd_if_available()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        bold = ctk.CTkFont(weight="bold")
        small = ctk.CTkFont(size=12)

        # ---- Top bar ----
        top = ctk.CTkFrame(self, fg_color="#161b26")
        top.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))

        ctk.CTkButton(top, text="Abrir imagen", width=130, command=self._open_image).grid(
            row=0, column=0, padx=6, pady=8)
        ctk.CTkButton(top, text="Ejecutar OCR", width=130,
                       fg_color="#1a5c2a", hover_color="#237a38",
                       command=self._run_ocr).grid(row=0, column=1, padx=6, pady=8)
        ctk.CTkButton(top, text="Copiar texto", width=110, command=self._copy_text).grid(
            row=0, column=2, padx=6, pady=8)

        self.dnd_hint = ctk.CTkLabel(top, text="Arrastra una imagen aquí",
                                      font=small, text_color="#93a1ba")
        self.dnd_hint.grid(row=0, column=3, padx=10, sticky="e")
        top.grid_columnconfigure(3, weight=1)

        # ---- Main area: preview + text ----
        main = ctk.CTkFrame(self, fg_color="#0f1420")
        main.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        main.grid_columnconfigure(0, weight=3)
        main.grid_columnconfigure(1, weight=2)
        main.grid_rowconfigure(0, weight=1)

        # Left: image preview with zoom
        prev_frame = ctk.CTkFrame(main, fg_color="#121722")
        prev_frame.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)
        prev_frame.grid_rowconfigure(1, weight=1)
        prev_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(prev_frame, text="Vista previa de imagen", font=bold).grid(
            row=0, column=0, sticky="w", padx=12, pady=(10, 6))

        self.preview_widget = ZoomablePreview(prev_frame,
                                               placeholder="Selecciona o arrastra una imagen")
        self.preview_widget.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

        # Right: OCR text output
        text_frame = ctk.CTkFrame(main, fg_color="#121722")
        text_frame.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=8)
        text_frame.grid_rowconfigure(1, weight=1)
        text_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(text_frame, text="Texto reconocido (OCR)", font=bold).grid(
            row=0, column=0, sticky="w", padx=12, pady=(10, 6))

        self.ocr_box = ctk.CTkTextbox(text_frame, fg_color="#1a2030",
                                       text_color="#e4e9f5", corner_radius=8,
                                       font=ctk.CTkFont(size=13))
        self.ocr_box.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

        # ---- Bottom bar ----
        bot = ctk.CTkFrame(self, fg_color="#161b26")
        bot.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))
        bot.grid_columnconfigure(0, weight=1)
        self.status_lbl = ctk.CTkLabel(bot, text="Sin imagen cargada", font=small,
                                        text_color="#93a1ba")
        self.status_lbl.grid(row=0, column=0, padx=10, pady=8, sticky="w")

        self._current_image = None
        self._current_path = None

    def _register_dnd_if_available(self):
        if not DND_AVAILABLE:
            return
        for w in [self, self.preview_widget, self.preview_widget.canvas]:
            try:
                w.drop_target_register(DND_FILES)
                w.dnd_bind("<<Drop>>", self._on_drop)
            except Exception:
                pass

    def _on_drop(self, event):
        dropped = parse_dropped_files(self, event.data)
        exts = (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp")
        files = collect_files(dropped, exts)
        if files:
            self._load_image(files[0])

    def _open_image(self):
        path = filedialog.askopenfilename(
            title="Seleccionar imagen para OCR",
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.bmp *.tiff *.webp"),
                       ("Todos", "*.*")])
        if path:
            self._load_image(path)

    def _load_image(self, path):
        try:
            im = Image.open(path).convert("RGB")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir la imagen.\n\n{e}")
            return
        self._current_image = im
        self._current_path = path
        self.preview_widget.set_image(im)
        name = os.path.basename(path)
        w, h = im.size
        self.status_lbl.configure(text=f"{name}  |  {w}\u00d7{h} px")
        self.dnd_hint.configure(text=name)

    def _run_ocr(self):
        if not OCR_AVAILABLE:
            messagebox.showinfo("OCR",
                "Para usar OCR, instala rapidocr-onnxruntime:\n\n"
                "pip install rapidocr-onnxruntime")
            return
        if self._current_image is None:
            messagebox.showinfo("OCR", "Primero abre o arrastra una imagen.")
            return
        self.status_lbl.configure(text="Procesando OCR...")
        self.update_idletasks()
        img_np = np.array(self._current_image)

        def do_ocr():
            try:
                if self._ocr_reader is None:
                    self._ocr_reader = RapidOCR()
                results, _ = self._ocr_reader(img_np)
                if results:
                    text = "\n".join(r[1] for r in results)
                    count = len(results)
                else:
                    text = ""
                    count = 0
                self.after(0, lambda t=text, c=count: self._show_result(t, c))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error OCR", str(e)))
                self.after(0, lambda: self.status_lbl.configure(text="Error en OCR"))

        threading.Thread(target=do_ocr, daemon=True).start()

    def _show_result(self, text, count):
        self.ocr_box.delete("1.0", "end")
        self.ocr_box.insert("1.0", text.strip() or "(OCR no detectó texto)")
        name = os.path.basename(self._current_path) if self._current_path else "imagen"
        self.status_lbl.configure(text=f"OCR completado — {count} bloques en {name}")

    def _copy_text(self):
        text = self.ocr_box.get("1.0", "end").strip()
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.status_lbl.configure(text="Texto copiado al portapapeles")


# -------------------- App principal -------------------- #
class PDFStudioApp(BaseApp):
    def __init__(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        super().__init__()

        self.title("PDF Studio Pro")
        self.geometry("1400x900")
        self.minsize(1200, 800)
        self.configure(fg_color="#0b0f17")

        # Icono de ventana (opcional)
        for ico in ["assets/app.ico", "app.ico"]:
            if os.path.exists(ico):
                try:
                    self.iconbitmap(ico)
                except Exception:
                    pass
                break

        setup_treeview_dark_style(self)

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Header con logo
        header = ctk.CTkFrame(self, fg_color="#0f1420", corner_radius=0, height=74)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        header.grid_columnconfigure(1, weight=1)

        logo = load_logo_image()
        self.logo_ctk = ctk.CTkImage(light_image=logo, dark_image=logo, size=logo.size)

        ctk.CTkLabel(header, image=self.logo_ctk, text="").grid(row=0, column=0, padx=(16, 8), pady=12, sticky="w")
        ctk.CTkLabel(
            header,
            text="PDF Studio Pro",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="#f4f7ff"
        ).grid(row=0, column=1, sticky="w")

        ctk.CTkLabel(
            header,
            text="Convertir | Fusionar | Editar | OCR Imagen | Exportar JPG/PNG",
            text_color="#93a1ba",
            font=ctk.CTkFont(size=12)
        ).grid(row=0, column=1, padx=(220, 0), sticky="w")

        ctk.CTkButton(
            header, text="Info", width=60, height=32,
            fg_color="#2a3040", hover_color="#3c4560",
            font=ctk.CTkFont(size=12),
            command=self._show_info
        ).grid(row=0, column=2, padx=(0, 16), pady=12, sticky="e")

        # Tabs
        tabs = ctk.CTkTabview(
            self,
            fg_color="#0f1420",
            segmented_button_fg_color="#161b26",
            segmented_button_selected_color="#2f6fed",
            segmented_button_selected_hover_color="#3c7bff"
        )
        tabs.grid(row=1, column=0, sticky="nsew", padx=12, pady=12)

        t1 = tabs.add("Imágenes a PDF")
        t2 = tabs.add("Fusionar PDF")
        t3 = tabs.add("Editor de PDF")
        t4 = tabs.add("OCR Imagen")
        t5 = tabs.add("PDF a JPG/PNG")

        self.tab_images = ImagesToPdfTab(t1)
        self.tab_images.pack(fill="both", expand=True)

        self.tab_merge = MergePdfTab(t2)
        self.tab_merge.pack(fill="both", expand=True)

        self.tab_editor = EditPdfTab(t3)
        self.tab_editor.pack(fill="both", expand=True)

        self.tab_ocr = OcrImageTab(t4)
        self.tab_ocr.pack(fill="both", expand=True)

        self.tab_export = PdfToImageTab(t5)
        self.tab_export.pack(fill="both", expand=True)

    def _show_info(self):
        win = ctk.CTkToplevel(self)
        win.title("Acerca de PDF Studio Pro")
        win.geometry("520x520")
        win.resizable(False, False)
        win.configure(fg_color="#0f1420")
        win.transient(self)
        win.grab_set()

        # Center on parent
        win.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 520) // 2
        y = self.winfo_y() + (self.winfo_height() - 520) // 2
        win.geometry(f"+{x}+{y}")

        title_font = ctk.CTkFont(size=20, weight="bold")
        label_font = ctk.CTkFont(size=13)
        link_font = ctk.CTkFont(size=13, underline=True)
        small_font = ctk.CTkFont(size=12)
        section_font = ctk.CTkFont(size=13, weight="bold")

        pad = {"padx": 20, "sticky": "w"}

        ctk.CTkLabel(win, text="PDF Studio Pro", font=title_font,
                     text_color="#f4f7ff").pack(pady=(20, 2), **pad)
        ctk.CTkLabel(win, text=f"Version {APP_VERSION}  |  Licencia: Apache-2.0",
                     font=small_font, text_color="#93a1ba").pack(pady=(0, 12), **pad)

        ctk.CTkFrame(win, height=1, fg_color="#2a3040").pack(fill="x", padx=20, pady=4)

        ctk.CTkLabel(win, text="Autor", font=section_font,
                     text_color="#8cb0ff").pack(pady=(10, 2), **pad)
        ctk.CTkLabel(win, text="Rodolfo Cardenas Vigo", font=label_font,
                     text_color="#e4e9f5").pack(**pad)

        # --- Links ---
        links = [
            ("Correo:", "vicercavi@gmail.com", "mailto:vicercavi@gmail.com"),
            ("CTI VITAE:", "dina.concytec.gob.pe/...id=24502",
             "https://dina.concytec.gob.pe/appDirectorioCTI/VerDatosInvestigador.do?id_investigador=24502"),
            ("GitHub:", "github.com/vicercavi", "https://github.com/vicercavi"),
            ("LinkedIn:", "linkedin.com/in/rodolfo-cardenas-baa9aa7a",
             "https://www.linkedin.com/in/rodolfo-cardenas-baa9aa7a/"),
            ("Codigo fuente:", "github.com/vicercavi/pdf-studio-pro",
             "https://github.com/vicercavi/pdf-studio-pro"),
        ]

        for label_text, display, url in links:
            row = ctk.CTkFrame(win, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=1)
            ctk.CTkLabel(row, text=label_text, font=small_font,
                         text_color="#93a1ba", width=110, anchor="w").pack(side="left")
            link_lbl = ctk.CTkLabel(row, text=display, font=link_font,
                                     text_color="#5b9aff", cursor="hand2")
            link_lbl.pack(side="left", padx=(4, 0))
            link_lbl.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))

            def _copy_url(event, u=url, lbl=link_lbl):
                self.clipboard_clear()
                self.clipboard_append(u)
                orig = lbl.cget("text")
                lbl.configure(text="Copiado!", text_color="#00cc66")
                lbl.after(1200, lambda: lbl.configure(text=orig, text_color="#5b9aff"))

            link_lbl.bind("<Button-3>", _copy_url)

        # Hint
        ctk.CTkLabel(win, text="Click izquierdo = abrir  |  Click derecho = copiar URL",
                     font=ctk.CTkFont(size=11), text_color="#666f80").pack(pady=(6, 4), **pad)

        ctk.CTkFrame(win, height=1, fg_color="#2a3040").pack(fill="x", padx=20, pady=8)

        ctk.CTkLabel(win, text="Desarrollo", font=section_font,
                     text_color="#8cb0ff").pack(pady=(4, 4), **pad)
        ctk.CTkLabel(win, text="v1.0 — ChatGPT o1 pro", font=small_font,
                     text_color="#e4e9f5").pack(**pad)
        ctk.CTkLabel(win, text="v2.0 — Claude Opus 4.6 (Anthropic)", font=small_font,
                     text_color="#e4e9f5").pack(**pad)

        ctk.CTkButton(win, text="Cerrar", width=100, command=win.destroy).pack(pady=(16, 16))


if __name__ == "__main__":
    app = PDFStudioApp()
    app.mainloop()
