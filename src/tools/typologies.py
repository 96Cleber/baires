"""
Módulo centralizado para gestión de tipologías de vehículos.

Este módulo carga las tipologías desde tipologias.txt y genera automáticamente
todos los mapeos necesarios entre:
- Tipologías en español (Auto, Moto, Bus, etc.)
- Clases YOLO en inglés (car, motorcycle, bus, etc.)
- Nombres de carpetas para crops

IMPORTANTE: Las clases YOLO son INVARIABLES (person, bicycle, car, motorcycle, bus, truck).
Las tipologías adicionales se cargan dinámicamente desde tipologias.txt.
"""

import os
import sys
from typing import Dict, List, Set


def get_resource_path(relative_path: str) -> str:
    """Obtener ruta de recurso, compatible con PyInstaller"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    # Desarrollo normal - subir dos niveles desde tools/
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), relative_path)


# =============================================================================
# CONSTANTES INVARIABLES - Mapeo YOLO (NO MODIFICAR)
# =============================================================================

# Clases que YOLO puede detectar (en inglés)
YOLO_CLASSES: List[str] = ['person', 'bicycle', 'car', 'motorcycle', 'bus', 'truck']

# Mapeo fijo de YOLO a tipología en español
# Este mapeo es INVARIABLE porque depende del modelo YOLO
YOLO_TO_TIPOLOGIA: Dict[str, str] = {
    'person': 'Persona',
    'bicycle': 'Bicicleta',
    'car': 'Auto',
    'motorcycle': 'Moto',
    'bus': 'Bus',
    'truck': 'Camion',
}

# Mapeo inverso: tipología española a clase YOLO
TIPOLOGIA_TO_YOLO: Dict[str, str] = {v: k for k, v in YOLO_TO_TIPOLOGIA.items()}


# =============================================================================
# FUNCIONES PARA CARGAR TIPOLOGÍAS DINÁMICAMENTE
# =============================================================================

def load_typologies_from_file(filepath: str = None) -> List[str]:
    """
    Cargar tipologías desde archivo.

    Args:
        filepath: Ruta al archivo de tipologías. Si es None, usa la ruta por defecto.

    Returns:
        Lista de tipologías (ej: ['Auto', 'Bicicleta', 'Bus', ...])
    """
    if filepath is None:
        filepath = get_resource_path("templates/tipologias.txt")

    typologies = []
    try:
        if os.path.exists(filepath):
            with open(filepath, "r", encoding='utf-8') as f:
                for line in f:
                    clean = line.strip()
                    if clean and not clean.startswith("#"):
                        typologies.append(clean)
    except Exception as e:
        print(f"Error cargando tipologías: {e}")

    return typologies


def get_default_typologies() -> List[str]:
    """
    Obtener tipologías por defecto (fallback si no se puede leer el archivo).
    Basado en las tipologías estándar del proyecto.
    """
    return [
        "Auto", "Bicicleta", "Bus", "Camion", "Camioneta",
        "Combi", "Microbus", "Moto", "Mototaxi", "Omnibus",
        "Persona", "Remolque", "Taxi", "Trailer", "Otros"
    ]


def get_typologies(filepath: str = None) -> List[str]:
    """
    Obtener lista de tipologías, con fallback a valores por defecto.

    Args:
        filepath: Ruta opcional al archivo de tipologías.

    Returns:
        Lista de tipologías
    """
    typologies = load_typologies_from_file(filepath)
    if not typologies:
        typologies = get_default_typologies()
    return typologies


# =============================================================================
# GENERACIÓN DINÁMICA DE MAPEOS
# =============================================================================

def generate_folder_classes(typologies: List[str] = None) -> List[str]:
    """
    Generar lista de clases para crear carpetas de crops.

    Incluye:
    - Clases YOLO (en inglés): person, bicycle, car, motorcycle, bus, truck
    - Tipologías adicionales (en minúscula): camioneta, combi, microbus, etc.

    Args:
        typologies: Lista de tipologías. Si es None, se cargan del archivo.

    Returns:
        Lista de nombres de carpetas
    """
    if typologies is None:
        typologies = get_typologies()

    # Empezar con las clases YOLO
    folder_classes = list(YOLO_CLASSES)

    # Tipologías que ya están cubiertas por YOLO
    covered_by_yolo = set(YOLO_TO_TIPOLOGIA.values())

    # Agregar tipologías adicionales (las que no están en YOLO)
    for typ in typologies:
        if typ not in covered_by_yolo:
            folder_name = typ.lower()
            if folder_name not in folder_classes:
                folder_classes.append(folder_name)

    return folder_classes


def generate_tipologia_to_folder(typologies: List[str] = None) -> Dict[str, str]:
    """
    Generar mapeo de tipología española a nombre de carpeta.

    Ejemplos:
        'Auto' -> 'car'
        'Moto' -> 'motorcycle'
        'Camioneta' -> 'camioneta'

    Args:
        typologies: Lista de tipologías. Si es None, se cargan del archivo.

    Returns:
        Diccionario de mapeo tipología -> carpeta
    """
    if typologies is None:
        typologies = get_typologies()

    mapping = {}

    for typ in typologies:
        if typ in TIPOLOGIA_TO_YOLO:
            # Tipología cubierta por YOLO -> usar clase YOLO
            mapping[typ] = TIPOLOGIA_TO_YOLO[typ]
        else:
            # Tipología adicional -> usar nombre en minúscula
            mapping[typ] = typ.lower()

    return mapping


def generate_folder_to_tipologia(typologies: List[str] = None) -> Dict[str, str]:
    """
    Generar mapeo de nombre de carpeta a tipología española.

    Ejemplos:
        'car' -> 'Auto'
        'motorcycle' -> 'Moto'
        'camioneta' -> 'Camioneta'

    Args:
        typologies: Lista de tipologías. Si es None, se cargan del archivo.

    Returns:
        Diccionario de mapeo carpeta -> tipología
    """
    if typologies is None:
        typologies = get_typologies()

    mapping = dict(YOLO_TO_TIPOLOGIA)  # Empezar con mapeo YOLO

    # Agregar tipologías adicionales
    for typ in typologies:
        if typ not in TIPOLOGIA_TO_YOLO:
            folder_name = typ.lower()
            mapping[folder_name] = typ

    return mapping


def generate_all_mappings(typologies: List[str] = None) -> Dict[str, any]:
    """
    Generar todos los mapeos necesarios en una sola llamada.

    Args:
        typologies: Lista de tipologías. Si es None, se cargan del archivo.

    Returns:
        Diccionario con:
        - 'typologies': Lista de tipologías
        - 'folder_classes': Lista de clases para carpetas
        - 'tipologia_to_folder': Mapeo tipología -> carpeta
        - 'folder_to_tipologia': Mapeo carpeta -> tipología
    """
    if typologies is None:
        typologies = get_typologies()

    return {
        'typologies': typologies,
        'folder_classes': generate_folder_classes(typologies),
        'tipologia_to_folder': generate_tipologia_to_folder(typologies),
        'folder_to_tipologia': generate_folder_to_tipologia(typologies),
    }


# =============================================================================
# INSTANCIAS PRE-CALCULADAS (para uso común)
# =============================================================================

# Cargar tipologías al importar el módulo
_cached_typologies = None
_cached_mappings = None


def _ensure_cache():
    """Asegurar que el caché está inicializado."""
    global _cached_typologies, _cached_mappings
    if _cached_typologies is None:
        _cached_typologies = get_typologies()
        _cached_mappings = generate_all_mappings(_cached_typologies)


def get_cached_typologies() -> List[str]:
    """Obtener tipologías cacheadas."""
    _ensure_cache()
    return _cached_typologies


def get_cached_folder_classes() -> List[str]:
    """Obtener clases de carpetas cacheadas."""
    _ensure_cache()
    return _cached_mappings['folder_classes']


def get_cached_tipologia_to_folder() -> Dict[str, str]:
    """Obtener mapeo tipología->carpeta cacheado."""
    _ensure_cache()
    return _cached_mappings['tipologia_to_folder']


def get_cached_folder_to_tipologia() -> Dict[str, str]:
    """Obtener mapeo carpeta->tipología cacheado."""
    _ensure_cache()
    return _cached_mappings['folder_to_tipologia']


def reload_typologies(filepath: str = None):
    """
    Recargar tipologías desde archivo (útil si se modifica el archivo en runtime).

    Args:
        filepath: Ruta opcional al archivo de tipologías.
    """
    global _cached_typologies, _cached_mappings
    _cached_typologies = get_typologies(filepath)
    _cached_mappings = generate_all_mappings(_cached_typologies)


# =============================================================================
# FUNCIONES DE COMPATIBILIDAD (para facilitar migración)
# =============================================================================

def get_translations() -> Dict[str, str]:
    """
    Obtener diccionario TRANSLATIONS compatible con write_counts.py
    Mapea clase YOLO/carpeta -> tipología española.
    """
    return get_cached_folder_to_tipologia()


def get_class_mapping_for_ui() -> Dict[str, str]:
    """
    Obtener mapeo para UIs de clasificación.
    Incluye tanto clases YOLO como tipologías adicionales.
    """
    return get_cached_folder_to_tipologia()


def get_reverse_mapping_for_ui() -> Dict[str, str]:
    """
    Obtener mapeo inverso para UIs de clasificación.
    Mapea tipología española -> nombre de carpeta.
    """
    return get_cached_tipologia_to_folder()
