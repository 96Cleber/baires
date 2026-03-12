# Proyecto: FlowVisionAI

Este proyecto integra una interfaz PyQt5 con detección y seguimiento en tiempo real (YOLOv8 + ByteTrack), conteo por líneas, relaciones Origen/Destino y reporte. Soporta ejecución con GPU (CUDA) y un modo “headless” para procesar más rápido sin visualizar todos los frames.

## Novedades principales

- Integración de backend YOLOv8 + ByteTrack en `src/tools/` y enlazado en `src/main_v3.py`.
- Detección usando GPU (si está disponible) o CPU en caso contrario.
- Visualización mejorada: color por clase, centroides, y trayectorias recientes.
- Modo headless: procesar sin visualizar con barra de progreso en tiempo real.
- **Clasificación manual avanzada**: interfaz visual para corregir detecciones automáticas.
- **Creación de clases personalizadas**: agregar nuevos tipos de vehículos dinámicamente.
- **Navegación por teclado**: flechas y atajos numéricos para clasificación rápida.
- Exportar/Cargar configuración (líneas, O/D, tipos, stride, headless, metadata de video).
- Conteos guardados en SQLite (`Conteos.db`) junto al video.

## Estructura del Proyecto

```
flowvisionai/
  src/
    main_v3.py            # App principal (PyQt5 + integración YOLO/ByteTrack)
    ui/ui3.ui             # Interfaz (menus, paneles, checkbox headless, barra de progreso)
    tools/
      detection_pipeline.py  # Pipeline YOLO + ByteTrack
      bytetrack.py           # Tracker simple estilo ByteTrack
      crop_manager.py        # Gestor de crops para clasificación manual
      read_db.py, send2excel.py
    ui/
      manual_classification_dialog.py  # Interfaz de clasificación manual
  requirements.txt        # Requisitos base (UI y procesamiento)
  requirements_yolo.txt   # Requisitos YOLO (CPU)
  requirements_gpu.txt    # Requisitos YOLO (CUDA/cu124)
  .gitignore              # Excluye weights/ y *.pt
  README.md
```

## Requisitos

- Python 3.13 (probado) o compatible.
- Para GPU: NVIDIA Driver + CUDA Runtime acorde al wheel (cu124). Usa `requirements_gpu.txt`.

### Instalar (CPU)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements_yolo.txt
```

### Instalar (GPU, cu124)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements_gpu.txt
```

La primera vez, el modelo se descarga automáticamente si seleccionas el alias `yolov8x.pt` o si no existe un archivo en `weights/`.

## Ejecución

```bash
python src/main_v3.py
```

- Menú File > Load Video: selecciona el video.
- Se te pedirá el modelo (si no existe en `weights/`), puedes elegir `yolov8x.pt` (descarga automática) o una ruta local.
- Dibuja líneas de conteo y crea O/D.
- Play: procesa el video (detección por GPU si está disponible). Por defecto muestra 1 de cada 2 frames.

## Modo Headless (sin visualizar)

- Activa el checkbox "Procesar sin visualizar".
- Solo se muestra el primer frame y una barra de progreso en tiempo real.
- La barra de progreso se actualiza automáticamente mostrando el avance del procesamiento.
- La detección y conteo siguen ejecutándose en segundo plano.

## Exportar / Cargar configuración

- File > Exportar Configuración: genera un JSON con:
  - Video (ruta, fps, tamaño, frame_stride)
  - Líneas (id, access, name, coordenadas)
  - Relaciones O/D
  - Tipos de vehículo
  - Parámetros (detection_stride, headless)
- File > Cargar Configuración: carga el JSON y aplica todo.

## Clasificación Manual

### Características principales:
- **Interfaz visual intuitiva**: resaltado por colores según la clase del vehículo
- **Creación de clases personalizadas**: botón "+ Nueva Clase" para agregar tipos específicos
- **Navegación por teclado**:
  - `←` / `↑`: imagen anterior
  - `→` / `↓`: imagen siguiente  
  - `1-6`: selección rápida de clase estándar
- **Actualización en tiempo real**: el resaltado visual cambia automáticamente
- **Botones de acción rápida**: clasificación con un solo clic
- **Validación automática**: previene clases duplicadas

### Uso:
1. Menú Tools > Manual Classification
2. Selecciona tipo de crops (todas las detecciones o solo cruces O/D)
3. Navega con flechas o botones
4. Cambia clasificación con combo box o botones rápidos
5. Guarda cambios para actualizar la base de datos

## Salida (Conteos)

- La base `Conteos.db` se crea junto al video cargado.
- Tabla `VehicleCounts`: origin_frame, destination_frame, access, line (turn), vehicle_type, timestamp.
- Base adicional de crops para clasificación manual y reentrenamiento.

## Características Técnicas

### Procesamiento:
- **GPU/CPU automático**: fallback inteligente según disponibilidad de CUDA
- **ByteTrack**: seguimiento consistente de objetos entre frames
- **Stride configurable**: balance entre velocidad y precisión (defecto: 2)
- **Clasificación robusta**: heurísticas para mejorar detecciones automáticas

### Interfaz:
- **PyQt5**: interfaz nativa multiplataforma
- **Visualización en tiempo real**: colores por clase, trayectorias, centroides
- **Modo headless**: procesamiento rápido sin visualización completa
- **Configuración persistente**: exportar/importar configuraciones JSON

### Datos:
- **SQLite**: almacenamiento local de conteos y crops
- **Crops automáticos**: extracción de detecciones para análisis manual
- **Exportación**: reportes PDF y Excel

## Notas

- `weights/` y `*.pt` están ignorados por Git (no suben al repo).
- Crops y bases de datos se crean automáticamente junto al video.
- El stride de detección se sincroniza con el stride de visualización.
- Soporte para clases personalizadas persistentes entre sesiones.
