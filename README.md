# PDF Studio Pro

Aplicación de escritorio en Python para trabajar con archivos PDF de forma completa:

- Convertir **múltiples imágenes** a un solo PDF.
- Fusionar **múltiples PDFs** a nivel de página (reordenando páginas individualmente).
- **Editar PDFs**: insertar texto, imágenes, resaltar y modificar páginas.
- **Estilos de texto por selección**: fuente, tamaño, negrita, cursiva, subrayado y color aplicables a partes específicas del texto.
- **Undo / Redo**: Ctrl+Z y Ctrl+Y para deshacer y rehacer cambios en el editor.
- **Redimensionar objetos**: arrastra la esquina de cualquier imagen o cuadro de texto para cambiar su tamaño.
- **OCR Página**: reconoce texto en PDFs escaneados y lo convierte en **bloques editables** sobre la página (borde cyan para diferenciar del texto nativo). No aplica OCR sobre áreas que ya tienen texto nativo editable.
- **OCR Imagen** (pestaña independiente): extrae texto de cualquier imagen (PNG, JPG, etc.) con vista previa, zoom y drag & drop.
- OCR con `rapidocr-onnxruntime` — ONNX Runtime, liviano y sin PyTorch.
- **Zoom** en todas las herramientas (Ctrl+Rueda o botones +/−).
- **Drag & drop** desde el Explorador de Windows en todas las pestañas.
- **Exportar PDF a JPG/PNG** con DPI y calidad configurables.
- Interfaz moderna en **tema oscuro** con **logo de app**.

---

## Pestañas de la aplicación

| # | Pestaña | Descripción |
|---|---------|-------------|
| 1 | **Imágenes a PDF** | Convierte múltiples imágenes en un solo PDF |
| 2 | **Fusionar PDF** | Fusiona PDFs reordenando páginas individualmente |
| 3 | **Editor de PDF** | Editor interactivo con texto, imágenes, OCR y estilos |
| 4 | **OCR Imagen** | Extrae texto de imágenes sueltas mediante OCR |
| 5 | **PDF a JPG/PNG** | Exporta páginas de PDF como imágenes |

---

## Características principales

### 1) Imágenes a PDF
- Agregar imágenes por botón o arrastrando archivos/carpetas.
- Miniaturas por cada imagen.
- Reordenar elementos (subir/bajar o drag dentro de la lista).
- Zoom interactivo en la vista previa.
- Exportar un PDF en el orden definido.

### 2) Fusionar PDF por páginas
- Agregar uno o varios PDFs por botón o drag & drop.
- Expandir cada PDF en páginas individuales.
- Miniaturas de cada página.
- Reordenar páginas libremente.
- Zoom interactivo en la vista previa.
- Exportar PDF final en el orden elegido.

### 3) Editor de PDF (interactivo)
- **Edición inline de texto**: doble-click sobre cualquier bloque de texto existente para editarlo directamente en su lugar.
- **Estilos por selección**: selecciona parte del texto y cambia fuente (Helvetica, Times Roman, Courier), tamaño, negrita, cursiva, subrayado o color independientemente por cada selección.
- **Mover objetos**: arrastra cualquier bloque de texto o imagen insertada a una nueva posición.
- **Redimensionar objetos**: selecciona un objeto y arrastra el cuadrado azul en la esquina inferior derecha para cambiar su tamaño.
- **Agregar texto nuevo**: en modo "Agregar Texto", haz click en la página para crear un cuadro de texto editable con todas las opciones de estilo.
- **Agregar imagen (drag-draw)**: en modo "Agregar Imagen", dibuja un rectángulo sobre la página arrastrando el mouse, luego selecciona la imagen a insertar.
- **Eliminar objetos**: selecciona un bloque y presiona Delete/Suprimir para eliminarlo.
- **Resaltar (highlight)**: en modo "Resaltar", arrastra un rectángulo para crear anotación amarilla.
- **Undo / Redo**: Ctrl+Z para deshacer, Ctrl+Y para rehacer. Historial independiente por página, hasta 50 niveles.
- **Rotar página**: 90° derecha, 90° izquierda.
- **Eliminar página**: con confirmación antes de borrar.
- **Extraer texto**: obtiene el texto embebido en la página (sin OCR).
- **OCR Página**: reconoce texto en PDFs escaneados y crea **bloques editables** sobre la página con borde **cyan** para diferenciarlos del texto nativo del PDF. Los bloques son editables (doble-click), movibles y redimensionables como cualquier otro objeto. **No aplica OCR sobre áreas que ya tienen texto nativo editable** del PDF — el área bajo los bloques OCR se blanquea para que solo se vea el texto reconocido.
- **Copiar texto al portapapeles**: un click para copiar el texto extraído/OCR.
- **Zoom**: botones −/+/Ajustar y Ctrl+Rueda del mouse. Scrollbars horizontal y vertical.
- **Drag & drop**: arrastra un PDF desde el explorador para abrirlo.
- **Guardar / Guardar como**: guardado seguro mediante archivo temporal. Las ediciones se preservan al navegar entre páginas.
- Canvas interactivo con modos: Seleccionar, Agregar Texto, Agregar Imagen, Resaltar.
- Miniaturas de todas las páginas con actualización en tiempo real.

### 4) OCR Imagen (pestaña independiente)
- **Abrir imagen**: selecciona cualquier imagen (PNG, JPG, BMP, TIFF, WebP) por botón o drag & drop.
- **Vista previa** con zoom interactivo (botones +/−/Ajustar y Ctrl+Rueda).
- **Ejecutar OCR**: procesa la imagen y muestra el texto reconocido en el panel lateral.
- **Copiar texto** al portapapeles con un click.
- OCR con `rapidocr-onnxruntime` (ONNX Runtime, liviano, sin PyTorch).

### 5) PDF a JPG/PNG
- **DPI configurable**: 72, 150, 300, 600.
- **Formato de salida**: JPG o PNG.
- **Calidad JPG**: 70, 80, 90, 95, 100.
- **Exportar página actual**: guarda como `nombre_pdf_pag_N.ext`.
- **Exportar todas las páginas**: crea una carpeta con el nombre del PDF y dentro guarda cada página como `nombre_pdf_pag_N.ext`.
- **Exportar rango personalizado**: desde página X hasta página Y. Si son varias páginas, crea subcarpeta automáticamente.
- Vista previa con zoom interactivo.
- Drag & drop de PDFs soportado.

---

## Atajos de teclado (Editor de PDF)

| Atajo | Acción |
|-------|--------|
| `Ctrl+Z` | Deshacer último cambio |
| `Ctrl+Y` | Rehacer cambio deshecho |
| `Ctrl+Rueda` | Zoom in / out |
| `Delete` / `Supr` | Eliminar objeto seleccionado |
| `Doble-click` | Editar texto inline |
| `Tab` | Confirmar edición de texto |
| `Escape` | Cancelar edición de texto |

---

## Requisitos

- Windows 10/11
- Anaconda (o Miniconda)
- Python 3.10/3.11 recomendado
- Archivo principal: `app_pdf_studio.py`

### Dependencias principales

| Paquete | Uso |
|---------|-----|
| `customtkinter` | Interfaz gráfica moderna (tema oscuro) |
| `pillow` | Procesamiento de imágenes |
| `pymupdf` | Renderizado, edición y OCR de PDFs |
| `pypdf` | Fusión de páginas PDF |
| `tkinterdnd2` | Drag & drop desde el explorador |
| `rapidocr-onnxruntime` | OCR con ONNX Runtime, liviano y sin PyTorch (opcional) |
| `pyinstaller` | Generar ejecutable .exe |

---

## Estructura recomendada del proyecto

```text
pdf-studio-pro/
├─ app_pdf_studio.py   # App principal (tabs 1, 2, 4, 5 + OCR Imagen + arranque)
├─ editor_tab.py       # Editor interactivo de PDF (tab 3)
├─ README.md           # Documentacion en español
├─ README_EN.md        # Documentation in English
├─ assets/
│  ├─ logo.png         # opcional (logo en cabecera)
│  └─ app.ico          # opcional (icono de ventana / exe)
````

> Si `assets/logo.png` no existe, la app genera un logo simple por defecto.
> Si `assets/app.ico` no existe, la app funciona igual (sin icono personalizado).

---

## Instalación con Anaconda

Abre **Anaconda Prompt** en la carpeta del proyecto:

### 1) Crear y activar entorno

```bash
conda create -n pdfstudio python=3.11 -y
conda activate pdfstudio
```

### 2) Actualizar pip e instalar dependencias

```bash
python -m pip install --upgrade pip
pip install customtkinter pillow pymupdf pypdf tkinterdnd2 pyinstaller
```

### 3) OCR (opcional)

Para habilitar el reconocimiento óptico de caracteres en PDFs escaneados e imágenes:

```bash
pip install rapidocr-onnxruntime
```

> `rapidocr-onnxruntime` usa ONNX Runtime (mucho más liviano que PyTorch, ~50 MB). No requiere software externo.

> Sin este paquete, la app funciona perfectamente para todas las demás funciones. La extracción de texto embebido (no OCR) funciona sin dependencias adicionales.

---

## Ejecutar en modo desarrollo

```bash
python app_pdf_studio.py
```

---

## Generar ejecutable para Windows (.exe)

## Opción A (recomendada): modo carpeta (onedir)

Más estable para apps con GUI y dependencias nativas.

```bash
pyinstaller --noconfirm --clean --windowed --name PDFStudioPro ^
  --icon "assets\app.ico" ^
  --collect-all customtkinter ^
  --collect-all pymupdf ^
  --collect-all PIL ^
  --collect-all tkinterdnd2 ^
  --collect-all rapidocr_onnxruntime ^
  --hidden-import=tkinterdnd2 ^
  --add-data "assets;assets" ^
  --add-data "editor_tab.py;." ^
  app_pdf_studio.py
```

Salida:

* `dist\PDFStudioPro\PDFStudioPro.exe`

---

## Opción B: un solo archivo (onefile)

Más fácil de compartir, pero puede iniciar más lento.

```bash
pyinstaller --noconfirm --clean --onefile --windowed --name PDFStudioPro ^
  --icon "assets\app.ico" ^
  --collect-all customtkinter ^
  --collect-all pymupdf ^
  --collect-all PIL ^
  --collect-all tkinterdnd2 ^
  --collect-all rapidocr_onnxruntime ^
  --hidden-import=tkinterdnd2 ^
  --add-data "assets;assets" ^
  --add-data "editor_tab.py;." ^
  app_pdf_studio.py
```

Salida:

* `dist\PDFStudioPro.exe`

> **Importante**: `--collect-all rapidocr_onnxruntime` es necesario para que OCR funcione en el ejecutable (incluye `config.yaml` y los modelos ONNX).


---

## Uso rápido

1. Abre la app.
2. En **Imágenes a PDF**:
   * Agrega imágenes (botón o drag & drop).
   * Ordena con drag interno o Subir/Bajar.
   * Clic en **Convertir a PDF**.
3. En **Fusionar PDF**:
   * Agrega PDFs (botón o drag & drop).
   * Reordena páginas según necesidad.
   * Clic en **Fusionar PDF**.
4. En **Editor de PDF**:
   * Abre un PDF con el botón **Abrir PDF** o arrastrando un PDF.
   * **Editar texto existente**: en modo "Seleccionar", haz doble-click sobre un bloque de texto. Se abrirá un campo editable con barra de estilos. Modifica el texto y presiona Tab o haz click fuera para confirmar.
   * **Estilos por selección**: selecciona parte del texto y cambia fuente, tamaño, negrita (B), cursiva (I), subrayado (U) o color desde la barra flotante.
   * **Mover objetos**: en modo "Seleccionar", arrastra cualquier bloque de texto o imagen a una nueva posición.
   * **Redimensionar**: selecciona un objeto y arrastra el cuadrado azul de la esquina inferior derecha.
   * **Eliminar**: selecciona un objeto y presiona Delete/Suprimir.
   * **Deshacer/Rehacer**: Ctrl+Z / Ctrl+Y (hasta 50 niveles por página).
   * **Agregar texto nuevo**: cambia al modo "Agregar Texto" y haz click en la página para crear un cuadro de texto editable.
   * **Agregar imagen**: cambia al modo "Agregar Imagen", dibuja un rectángulo sobre la página arrastrando, y selecciona la imagen.
   * **Resaltar**: cambia al modo "Resaltar" y arrastra un rectángulo.
   * **OCR Página**: reconoce texto en PDFs escaneados y lo convierte en bloques editables (borde cyan). No aplica OCR sobre áreas con texto nativo.
   * Las ediciones se mantienen al navegar entre páginas.
   * Guarda con **Guardar** o **Guardar como...**.
5. En **OCR Imagen**:
   * Abre una imagen (botón o drag & drop).
   * Haz clic en **Ejecutar OCR**.
   * El texto reconocido aparece en el panel derecho.
   * Copia el texto con **Copiar texto**.
6. En **PDF a JPG/PNG**:
   * Abre un PDF (botón o drag & drop).
   * Configura DPI, formato y calidad.
   * Exporta la página actual, todas las páginas o un rango personalizado.

---

## Solución de problemas

### 1) Drag & Drop no funciona

* Verifica que `tkinterdnd2` esté instalado:

  ```bash
  pip show tkinterdnd2
  ```
* Si en desarrollo no funciona, confirma que ejecutas dentro del entorno correcto:

  ```bash
  conda activate pdfstudio
  python app_pdf_studio.py
  ```

### 2) El .exe abre y se cierra

Compila temporalmente sin `--windowed` para ver errores en consola:

```bash
pyinstaller --noconfirm --clean --name PDFStudioPro ^
  --collect-all customtkinter ^
  --collect-all pymupdf ^
  --collect-all PIL ^
  --collect-all tkinterdnd2 ^
  --collect-all rapidocr_onnxruntime ^
  --hidden-import=tkinterdnd2 ^
  --add-data "assets;assets" ^
  --add-data "editor_tab.py;." ^
  app_pdf_studio.py
```

### 3) Error al leer PDF o mostrar miniaturas

* El PDF puede estar dañado o protegido.
* Prueba abrirlo en un lector PDF y guardarlo nuevamente.

### 4) OCR no funciona

* Verifica que rapidocr-onnxruntime esté instalado:
  ```bash
  pip show rapidocr-onnxruntime
  ```
* La función **Extraer texto** (sin OCR) solo funciona con PDFs que tienen texto embebido, no con documentos escaneados como imagen.

### 5) Antivirus bloquea el ejecutable

Puede ocurrir con apps empaquetadas:

* Preferir `onedir` para reducir falsos positivos.
* Firmar digitalmente el ejecutable si aplica.

---

## Comandos útiles de limpieza (Windows CMD)

```bash
rmdir /s /q build
rmdir /s /q dist
del /q PDFStudioPro.spec
```

---

## Autor

**Rodolfo Cardenas Vigo**

- Correo: vicercavi@gmail.com
- CTI VITAE: [https://dina.concytec.gob.pe/appDirectorioCTI/VerDatosInvestigador.do?id_investigador=24502](https://dina.concytec.gob.pe/appDirectorioCTI/VerDatosInvestigador.do?id_investigador=24502)
- GitHub: [https://github.com/vicercavi](https://github.com/vicercavi)
- LinkedIn: [https://www.linkedin.com/in/rodolfo-cardenas-baa9aa7a/](https://www.linkedin.com/in/rodolfo-cardenas-baa9aa7a/)
- Codigo fuente: [https://github.com/vicercavi/pdf-studio-pro](https://github.com/vicercavi/pdf-studio-pro)

### Desarrollo

| Version | Herramienta |
|---------|-------------|
| v1.0 | ChatGPT o1 pro |
| v2.0 | Claude Opus 4.6 (Anthropic) |

---

## Licencia
Licencia: **Apache-2.0**.
