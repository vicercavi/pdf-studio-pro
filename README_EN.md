# PDF Studio Pro

A Python desktop application for working with PDF files:

- Convert **multiple images** into a single PDF.
- Merge **multiple PDFs** at page level (reordering pages individually).
- **Edit PDFs**: insert text, images, highlight and modify pages.
- **Per-selection text styles**: font, size, bold, italic, underline and color applicable to specific parts of the text.
- **Undo / Redo**: Ctrl+Z and Ctrl+Y to undo and redo changes in the editor.
- **Resize objects**: drag the corner of any image or text box to change its size.
- **OCR Page**: recognizes text in scanned PDFs and converts it into **editable blocks** on the page (cyan border to differentiate from native text). Does not apply OCR on areas that already have editable native text.
- **OCR Image** (standalone tab): extracts text from any image (PNG, JPG, etc.) with preview, zoom and drag & drop.
- OCR powered by `rapidocr-onnxruntime` — ONNX Runtime, lightweight, no PyTorch required.
- **Zoom** in all tools (Ctrl+Wheel or +/- buttons).
- **Drag & drop** from Windows Explorer in all tabs.
- **Export PDF to JPG/PNG** with configurable DPI and quality.
- Modern **dark theme** interface with **app logo**.

---

## Application Tabs

| # | Tab | Description |
|---|-----|-------------|
| 1 | **Images to PDF** | Converts multiple images into a single PDF |
| 2 | **Merge PDF** | Merges PDFs by reordering pages individually |
| 3 | **PDF Editor** | Interactive editor with text, images, OCR and styles |
| 4 | **OCR Image** | Extracts text from standalone images via OCR |
| 5 | **PDF to JPG/PNG** | Exports PDF pages as images |

---

## Main Features

### 1) Images to PDF
- Add images by button or by dragging files/folders.
- Thumbnails for each image.
- Reorder items (up/down or drag within the list).
- Interactive zoom in the preview.
- Export a PDF in the defined order.

### 2) Merge PDF by Pages
- Add one or more PDFs by button or drag & drop.
- Expand each PDF into individual pages.
- Thumbnails for each page.
- Freely reorder pages.
- Interactive zoom in the preview.
- Export the final PDF in the chosen order.

### 3) PDF Editor (Interactive)
- **Inline text editing**: double-click on any existing text block to edit it directly in place.
- **Per-selection styles**: select part of the text and change font (Helvetica, Times Roman, Courier), size, bold, italic, underline or color independently for each selection.
- **Move objects**: drag any text block or inserted image to a new position.
- **Resize objects**: select an object and drag the blue square at the bottom-right corner to change its size.
- **Add new text**: in "Add Text" mode, click on the page to create an editable text box with all style options.
- **Add image (drag-draw)**: in "Add Image" mode, draw a rectangle on the page by dragging the mouse, then select the image to insert.
- **Delete objects**: select a block and press Delete to remove it.
- **Highlight**: in "Highlight" mode, drag a rectangle to create a yellow annotation.
- **Undo / Redo**: Ctrl+Z to undo, Ctrl+Y to redo. Independent history per page, up to 50 levels.
- **Rotate page**: 90° right, 90° left.
- **Delete page**: with confirmation before deleting.
- **Extract text**: gets the embedded text on the page (without OCR).
- **OCR Page**: recognizes text in scanned PDFs and creates **editable blocks** on the page with a **cyan** border to differentiate them from native PDF text. Blocks are editable (double-click), movable and resizable like any other object. **Does not apply OCR on areas that already have editable native text** — the area under OCR blocks is blanked so only the recognized text is visible.
- **Copy text to clipboard**: one click to copy extracted/OCR text.
- **Zoom**: -/+/Fit buttons and Ctrl+Mouse wheel. Horizontal and vertical scrollbars.
- **Drag & drop**: drag a PDF from the explorer to open it.
- **Save / Save as**: safe saving via temporary file. Edits are preserved when navigating between pages.
- Interactive canvas with modes: Select, Add Text, Add Image, Highlight.
- Thumbnails of all pages with real-time updates.

### 4) OCR Image (Standalone Tab)
- **Open image**: select any image (PNG, JPG, BMP, TIFF, WebP) by button or drag & drop.
- **Preview** with interactive zoom (+/-/Fit buttons and Ctrl+Wheel).
- **Run OCR**: processes the image and shows the recognized text in the side panel.
- **Copy text** to clipboard with one click.
- OCR powered by `rapidocr-onnxruntime` (ONNX Runtime, lightweight, no PyTorch).

### 5) PDF to JPG/PNG
- **Configurable DPI**: 72, 150, 300, 600.
- **Output format**: JPG or PNG.
- **JPG quality**: 70, 80, 90, 95, 100.
- **Export current page**: saves as `pdf_name_pag_N.ext`.
- **Export all pages**: creates a folder named after the PDF and saves each page as `pdf_name_pag_N.ext` inside it.
- **Export custom range**: from page X to page Y. If multiple pages, automatically creates a subfolder.
- Preview with interactive zoom.
- PDF drag & drop supported.

---

## Keyboard Shortcuts (PDF Editor)

| Shortcut | Action |
|----------|--------|
| `Ctrl+Z` | Undo last change |
| `Ctrl+Y` | Redo undone change |
| `Ctrl+Wheel` | Zoom in / out |
| `Delete` | Delete selected object |
| `Double-click` | Edit text inline |
| `Tab` | Confirm text editing |
| `Escape` | Cancel text editing |

---

## Requirements

- Windows 10/11
- Anaconda (or Miniconda)
- Python 3.10/3.11 recommended
- Main file: `app_pdf_studio.py`

### Main Dependencies

| Package | Use |
|---------|-----|
| `customtkinter` | Modern GUI (dark theme) |
| `pillow` | Image processing |
| `pymupdf` | PDF rendering, editing and OCR |
| `pypdf` | PDF page merging |
| `tkinterdnd2` | Drag & drop from explorer |
| `rapidocr-onnxruntime` | OCR with ONNX Runtime, lightweight, no PyTorch (optional) |
| `pyinstaller` | Generate .exe executable |

---

## Recommended Project Structure

```text
pdf-studio-pro/
├─ app_pdf_studio.py   # Main app (tabs 1, 2, 4, 5 + OCR Image + startup)
├─ editor_tab.py       # Interactive PDF editor (tab 3)
├─ README.md           # Spanish documentation
├─ README_EN.md        # English documentation
├─ assets/
│  ├─ logo.png         # optional (header logo)
│  └─ app.ico          # optional (window / exe icon)
````

> If `assets/logo.png` does not exist, the app generates a simple default logo.
> If `assets/app.ico` does not exist, the app works without a custom icon.

---

## Installation with Anaconda

Open **Anaconda Prompt** in the project folder:

### 1) Create and activate environment

```bash
conda create -n pdfstudio python=3.11 -y
conda activate pdfstudio
```

### 2) Update pip and install dependencies

```bash
python -m pip install --upgrade pip
pip install customtkinter pillow pymupdf pypdf tkinterdnd2 pyinstaller
```

### 3) OCR (optional)

To enable optical character recognition on scanned PDFs and images:

```bash
pip install rapidocr-onnxruntime
```

> `rapidocr-onnxruntime` uses ONNX Runtime (much lighter than PyTorch, ~50 MB). No external software required.

> Without this package, the app works perfectly for all other features. Embedded text extraction (non-OCR) works without additional dependencies.

---

## Run in Development Mode

```bash
python app_pdf_studio.py
```

---

## Build Windows Executable (.exe)

## Option A (recommended): folder mode (onedir)

More stable for GUI apps with native dependencies.

```bash
pyinstaller --noconfirm --clean --windowed --name PDFStudioPro ^
  --collect-all customtkinter ^
  --collect-all pymupdf ^
  --collect-all PIL ^
  --collect-all tkinterdnd2 ^
  --hidden-import=tkinterdnd2 ^
  --add-data "assets;assets" ^
  --add-data "editor_tab.py;." ^
  app_pdf_studio.py
```

Output:

* `dist\PDFStudioPro\PDFStudioPro.exe`

---

## Option B: single file (onefile)

Easier to share, but may start slower.

```bash
pyinstaller --noconfirm --clean --onefile --windowed --name PDFStudioPro ^
  --collect-all customtkinter ^
  --collect-all pymupdf ^
  --collect-all PIL ^
  --collect-all tkinterdnd2 ^
  --hidden-import=tkinterdnd2 ^
  --add-data "assets;assets" ^
  --add-data "editor_tab.py;." ^
  app_pdf_studio.py
```

Output:

* `dist\PDFStudioPro.exe`

---

## Executable Icon (optional)

If you have `assets/app.ico`, you can include it when building:

```bash
pyinstaller --noconfirm --clean --windowed --name PDFStudioPro ^
  --icon "assets\app.ico" ^
  --collect-all customtkinter ^
  --collect-all pymupdf ^
  --collect-all PIL ^
  --collect-all tkinterdnd2 ^
  --hidden-import=tkinterdnd2 ^
  --add-data "assets;assets" ^
  --add-data "editor_tab.py;." ^
  app_pdf_studio.py
```

---

## Quick Start

1. Open the app.
2. In **Images to PDF**:
   * Add images (button or drag & drop).
   * Sort with internal drag or Up/Down.
   * Click **Convert to PDF**.
3. In **Merge PDF**:
   * Add PDFs (button or drag & drop).
   * Reorder pages as needed.
   * Click **Merge PDF**.
4. In **PDF Editor**:
   * Open a PDF with the **Open PDF** button or by dragging a PDF.
   * **Edit existing text**: in "Select" mode, double-click on a text block. An editable field with a style bar will open. Modify the text and press Tab or click outside to confirm.
   * **Per-selection styles**: select part of the text and change font, size, bold (B), italic (I), underline (U) or color from the floating bar.
   * **Move objects**: in "Select" mode, drag any text block or image to a new position.
   * **Resize**: select an object and drag the blue square at the bottom-right corner.
   * **Delete**: select an object and press Delete.
   * **Undo/Redo**: Ctrl+Z / Ctrl+Y (up to 50 levels per page).
   * **Add new text**: switch to "Add Text" mode and click on the page to create an editable text box.
   * **Add image**: switch to "Add Image" mode, draw a rectangle on the page by dragging, and select the image.
   * **Highlight**: switch to "Highlight" mode and drag a rectangle.
   * **OCR Page**: recognizes text in scanned PDFs and converts it into editable blocks (cyan border). Does not apply OCR on areas with native text.
   * Edits are preserved when navigating between pages.
   * Save with **Save** or **Save as...**.
5. In **OCR Image**:
   * Open an image (button or drag & drop).
   * Click **Run OCR**.
   * The recognized text appears in the right panel.
   * Copy the text with **Copy text**.
6. In **PDF to JPG/PNG**:
   * Open a PDF (button or drag & drop).
   * Configure DPI, format and quality.
   * Export the current page, all pages or a custom range.

---

## Troubleshooting

### 1) Drag & Drop not working

* Verify that `tkinterdnd2` is installed:

  ```bash
  pip show tkinterdnd2
  ```
* If it doesn't work in development, confirm you are running within the correct environment:

  ```bash
  conda activate pdfstudio
  python app_pdf_studio.py
  ```

### 2) The .exe opens and closes

Temporarily compile without `--windowed` to see console errors:

```bash
pyinstaller --noconfirm --clean --name PDFStudioPro ^
  --collect-all customtkinter ^
  --collect-all pymupdf ^
  --collect-all PIL ^
  --collect-all tkinterdnd2 ^
  --hidden-import=tkinterdnd2 ^
  --add-data "assets;assets" ^
  --add-data "editor_tab.py;." ^
  app_pdf_studio.py
```

### 3) Error reading PDF or showing thumbnails

* The PDF may be corrupted or protected.
* Try opening it in a PDF reader and saving it again.

### 4) OCR not working

* Verify that rapidocr-onnxruntime is installed:
  ```bash
  pip show rapidocr-onnxruntime
  ```
* The **Extract text** function (without OCR) only works with PDFs that have embedded text, not with documents scanned as images.

### 5) Antivirus blocks the executable

This can happen with packaged apps:

* Prefer `onedir` to reduce false positives.
* Digitally sign the executable if applicable.

---

## Cleanup Commands (Windows CMD)

```bash
rmdir /s /q build
rmdir /s /q dist
del /q PDFStudioPro.spec
```

---

## Author

**Rodolfo Cardenas Vigo**

- Email: vicercavi@gmail.com
- CTI VITAE: [https://dina.concytec.gob.pe/appDirectorioCTI/VerDatosInvestigador.do?id_investigador=24502](https://dina.concytec.gob.pe/appDirectorioCTI/VerDatosInvestigador.do?id_investigador=24502)
- GitHub: [https://github.com/vicercavi](https://github.com/vicercavi)
- LinkedIn: [https://www.linkedin.com/in/rodolfo-cardenas-baa9aa7a/](https://www.linkedin.com/in/rodolfo-cardenas-baa9aa7a/)
- Source code: [https://github.com/vicercavi/pdf-studio-pro](https://github.com/vicercavi/pdf-studio-pro)

### Development

| Version | Tool |
|---------|------|
| v1.0 | ChatGPT o1 pro |
| v2.0 | Claude Opus 4.6 (Anthropic) |

---

## License
License: **Apache-2.0**.
