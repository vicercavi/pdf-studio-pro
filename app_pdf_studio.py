# app_pdf_studio.py
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk
from PIL import Image, ImageOps, ImageTk, ImageDraw
import fitz  # PyMuPDF
from pypdf import PdfReader, PdfWriter

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

    # quitar duplicados preservando orden
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


# -------------------- Tab 1: Imágenes -> PDF -------------------- #
class ImagesToPdfTab(ctk.CTkFrame):
    IMG_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp")

    def __init__(self, master):
        super().__init__(master)
        self.records = []  # [{path, thumb_tk}]
        self.preview_img = None
        self._drag_from_index = None
        self.preview_size = (760, 560)

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

        # Panel derecho (preview)
        right = ctk.CTkFrame(self, fg_color="#121722")
        right.grid(row=1, column=1, sticky="nsew", padx=(8, 12), pady=(0, 12))
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(right, text="Vista previa", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w", padx=12, pady=(12, 6)
        )

        self.preview_label = ctk.CTkLabel(
            right,
            text="Selecciona una imagen",
            fg_color="#0f1420",
            corner_radius=12
        )
        self.preview_label.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

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

        for w in [self, self.tree, self.preview_label]:
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
                im = fit_to_box(im, *self.preview_size)
            self.preview_img = ctk.CTkImage(light_image=im, dark_image=im, size=im.size)
            self.preview_label.configure(image=self.preview_img, text="")
        except Exception as e:
            self.preview_label.configure(image=None, text=f"No se pudo cargar vista previa\n{e}")

    def clear_preview(self):
        self.preview_img = None
        self.preview_label.configure(image=None, text="Selecciona una imagen")

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
        self.preview_img = None
        self._drag_from_index = None
        self.preview_size = (760, 560)

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

        self.preview_label = ctk.CTkLabel(
            right,
            text="Selecciona una página",
            fg_color="#0f1420",
            corner_radius=12
        )
        self.preview_label.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

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

        for w in [self, self.tree, self.preview_label]:
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

                    # miniatura de la página
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
            pix = page.get_pixmap(matrix=fitz.Matrix(1.4, 1.4), alpha=False)
            doc.close()

            im = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            im = fit_to_box(im, *self.preview_size)

            self.preview_img = ctk.CTkImage(light_image=im, dark_image=im, size=im.size)
            self.preview_label.configure(image=self.preview_img, text="")
        except Exception as e:
            self.preview_label.configure(image=None, text=f"No se pudo cargar vista previa\n{e}")

    def clear_preview(self):
        self.preview_img = None
        self.preview_label.configure(image=None, text="Selecciona una página")

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


# -------------------- App Base (con/sin DnD) -------------------- #
class BaseApp(ctk.CTk):
    pass


if DND_AVAILABLE:
    class BaseApp(TkinterDnD.DnDWrapper, ctk.CTk):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.TkdndVersion = TkinterDnD._require(self)


# -------------------- App principal -------------------- #
class PDFStudioApp(BaseApp):
    def __init__(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        super().__init__()

        self.title("PDF Studio Pro")
        self.geometry("1340x860")
        self.minsize(1140, 760)
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
            text="Imágenes → PDF | Fusión por páginas | Drag & Drop | Miniaturas",
            text_color="#93a1ba",
            font=ctk.CTkFont(size=12)
        ).grid(row=0, column=1, padx=(220, 0), sticky="w")

        # Tabs
        tabs = ctk.CTkTabview(
            self,
            fg_color="#0f1420",
            segmented_button_fg_color="#161b26",
            segmented_button_selected_color="#2f6fed",
            segmented_button_selected_hover_color="#3c7bff"
        )
        tabs.grid(row=1, column=0, sticky="nsew", padx=12, pady=12)

        t1 = tabs.add("Imágenes → PDF")
        t2 = tabs.add("Fusionar PDF (página a página)")

        self.tab_images = ImagesToPdfTab(t1)
        self.tab_images.pack(fill="both", expand=True)

        self.tab_merge = MergePdfTab(t2)
        self.tab_merge.pack(fill="both", expand=True)


if __name__ == "__main__":
    app = PDFStudioApp()
    app.mainloop()
