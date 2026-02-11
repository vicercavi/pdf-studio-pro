# PDF Studio Pro

Aplicación de escritorio en Python para:

- Convertir **múltiples imágenes** a un solo PDF.
- Fusionar **múltiples PDFs** a nivel de página (reordenando páginas individualmente).
- Ver **vista previa** antes de exportar.
- Reordenar con botones y también con **arrastre interno**.
- Soportar **drag & drop desde el Explorador de Windows**.
- Mostrar **miniaturas en la lista**.
- Interfaz moderna en **tema oscuro** con **logo de app**.

---

## Características principales

### 1) Imágenes → PDF
- Agregar imágenes por botón o arrastrando archivos/carpetas.
- Miniaturas por cada imagen.
- Reordenar elementos (subir/bajar o drag dentro de la lista).
- Exportar un PDF en el orden definido.

### 2) Fusionar PDF por páginas
- Agregar uno o varios PDFs por botón o drag & drop.
- Expandir cada PDF en páginas individuales.
- Miniaturas de cada página.
- Reordenar páginas libremente.
- Exportar PDF final en el orden elegido.

---

## Requisitos

- Windows 10/11
- Anaconda (o Miniconda)
- Python 3.10/3.11 recomendado
- Archivo principal: `app_pdf_studio.py`

---

## Estructura recomendada del proyecto

```text
pdf-studio-pro/
├─ app_pdf_studio.py
├─ README.md
└─ assets/
   ├─ logo.png      # opcional (logo en cabecera)
   └─ app.ico       # opcional (icono de ventana / exe)
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
  --collect-all customtkinter ^
  --collect-all pymupdf ^
  --collect-all PIL ^
  --collect-all tkinterdnd2 ^
  --hidden-import=tkinterdnd2 ^
  --add-data "assets;assets" ^
  app_pdf_studio.py
```

Salida:

* `dist\PDFStudioPro\PDFStudioPro.exe`

---

## Opción B: un solo archivo (onefile)

Más fácil de compartir, pero puede iniciar más lento.

```bash
pyinstaller --noconfirm --clean --onefile --windowed --name PDFStudioPro ^
  --collect-all customtkinter ^
  --collect-all pymupdf ^
  --collect-all PIL ^
  --collect-all tkinterdnd2 ^
  --hidden-import=tkinterdnd2 ^
  --add-data "assets;assets" ^
  app_pdf_studio.py
```

Salida:

* `dist\PDFStudioPro.exe`

---

## Icono del ejecutable (opcional)

Si tienes `assets/app.ico`, puedes incluirlo al compilar:

```bash
pyinstaller --noconfirm --clean --windowed --name PDFStudioPro ^
  --icon "assets\app.ico" ^
  --collect-all customtkinter ^
  --collect-all pymupdf ^
  --collect-all PIL ^
  --collect-all tkinterdnd2 ^
  --hidden-import=tkinterdnd2 ^
  --add-data "assets;assets" ^
  app_pdf_studio.py
```

---

## Uso rápido

1. Abre la app.
2. En **Imágenes → PDF**:

   * Agrega imágenes (botón o drag & drop).
   * Ordena con drag interno o Subir/Bajar.
   * Clic en **Convertir a PDF**.
3. En **Fusionar PDF**:

   * Agrega PDFs (botón o drag & drop).
   * Reordena páginas según necesidad.
   * Clic en **Fusionar PDF**.

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
  --hidden-import=tkinterdnd2 ^
  --add-data "assets;assets" ^
  app_pdf_studio.py
```

### 3) Error al leer PDF o mostrar miniaturas

* El PDF puede estar dañado o protegido.
* Prueba abrirlo en un lector PDF y guardarlo nuevamente.

### 4) Antivirus bloquea el ejecutable

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

## Licencia
Licencia: **Apache-2.0**. Proyecto creado con asistencia de **GPT-5.2 Thinking** mediante prompting del autor.

## Prompt usado (resumido)
“Crear una app en Python con interfaz gráfica moderna para convertir imágenes a PDF y fusionar PDFs por páginas, con vista previa, miniaturas, reordenamiento (incluido drag & drop) y generación de ejecutable para Windows.”

