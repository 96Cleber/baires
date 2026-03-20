"""
Crop Manager para guardar y gestionar crops de detecciones.
Maneja crops para todas las detecciones y para cruces O/D específicamente.
"""

import os
import sys
import cv2
import json
import sqlite3
import numpy as np
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from queue import Queue


def get_resource_path(relative_path: str) -> str:
    """Obtener ruta de recurso, compatible con PyInstaller"""
    if hasattr(sys, '_MEIPASS'):
        # Ejecutable PyInstaller
        return os.path.join(sys._MEIPASS, relative_path)
    # Desarrollo normal
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), relative_path)

try:
    from PyQt5.QtCore import QThread, pyqtSignal
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False


if PYQT_AVAILABLE:
    class AsyncCropWriter(QThread):
        """
        OPT-2: Worker thread para escritura asíncrona de crops
        Maneja el I/O de imágenes en un thread separado para no bloquear el procesamiento
        """
        finished_signal = pyqtSignal()

        def __init__(self):
            super().__init__()
            self.write_queue = Queue()
            self.running = True

        def run(self):
            """Procesar cola de escritura de crops"""
            while self.running:
                try:
                    # Timeout para permitir verificar self.running periódicamente
                    if self.write_queue.empty():
                        self.msleep(10)  # Sleep 10ms
                        continue

                    crop_data = self.write_queue.get(timeout=0.1)

                    if crop_data is None:  # Señal de terminación
                        break

                    # Escribir la imagen
                    filepath = crop_data['filepath']
                    image = crop_data['image']
                    cv2.imwrite(str(filepath), image)

                    self.write_queue.task_done()
                except Exception as e:
                    print(f"Error en AsyncCropWriter: {e}")

            self.finished_signal.emit()

        def enqueue_crop(self, filepath: str, image: np.ndarray):
            """Agregar crop a la cola de escritura"""
            self.write_queue.put({
                'filepath': filepath,
                'image': image.copy()  # Copiar para evitar problemas de concurrencia
            })

        def stop(self):
            """Detener el worker thread"""
            self.running = False
            self.write_queue.put(None)  # Señal de terminación
            self.wait()  # Esperar a que termine
else:
    AsyncCropWriter = None


class CropManager:
    """Gestiona el guardado y manejo de crops de detecciones"""

    @classmethod
    def load_existing(cls, crops_od_dir: str, typologies_path: str = None):
        """
        Cargar un CropManager desde una carpeta de crops existente.
        Útil para cargar resultados sin necesidad del video original.

        Args:
            crops_od_dir: Ruta a la carpeta de crops_od existente
            typologies_path: Ruta al archivo de tipologías

        Returns:
            CropManager configurado para la carpeta existente
        """
        # Usar ruta por defecto si no se especifica
        if typologies_path is None:
            typologies_path = get_resource_path("templates/tipologias.txt")

        # Asegurarse de usar rutas absolutas para evitar problemas
        crops_path = Path(crops_od_dir).resolve()
        parent_dir = crops_path.parent
        folder_name = crops_path.name

        # Extraer nombre del video de la carpeta (ej: "video_crops_od" -> "video")
        if folder_name.endswith('_crops_od'):
            video_name = folder_name.replace('_crops_od', '')
        else:
            video_name = folder_name

        # Crear un video_path "virtual" para compatibilidad
        virtual_video_path = str(parent_dir / f"{video_name}.mp4")

        # Crear instancia
        instance = cls.__new__(cls)
        instance.video_path = virtual_video_path
        instance.video_dir = parent_dir
        instance.video_name = video_name
        instance.typologies_path = typologies_path

        # Usar directorios existentes
        instance.all_crops_dir = parent_dir / f"{video_name}_crops_all"
        instance.od_crops_dir = crops_path

        # Crear directorios si no existen
        instance.all_crops_dir.mkdir(exist_ok=True)
        instance.od_crops_dir.mkdir(exist_ok=True)

        # Inicializar diccionario de clases
        instance.class_dirs = {}
        instance._create_class_directories()

        # Base de datos de crops
        instance.crops_db_path = parent_dir / f"{video_name}_crops.db"

        # Inicializar conexión y locks
        instance._conn = None
        instance._conn_lock = threading.Lock()
        instance.pending_all_crops = []
        instance.pending_od_crops = []
        instance.batch_size = 50

        # Async writer
        if AsyncCropWriter is not None:
            instance.async_writer = AsyncCropWriter()
            instance.async_writer.start()
        else:
            instance.async_writer = None

        # Inicializar base de datos si no existe
        instance._init_crops_database()

        return instance

    def __init__(self, video_path: str, typologies_path: str):
        self.video_path = video_path
        self.video_dir = Path(video_path).parent
        self.video_name = Path(video_path).stem
        self.typologies_path = typologies_path
        
        # Crear directorios para crops
        self.all_crops_dir = self.video_dir / f"{self.video_name}_crops_all"
        self.od_crops_dir = self.video_dir / f"{self.video_name}_crops_od"
        
        self.all_crops_dir.mkdir(exist_ok=True)
        self.od_crops_dir.mkdir(exist_ok=True)
        
        # Crear subdirectorios por clase
        self.class_dirs = {}
        self._create_class_directories()
        
        # Base de datos para metadatos de crops
        self.crops_db_path = self.video_dir / f"{self.video_name}_crops.db"

        # OPT-8: Connection pooling - mantener conexión abierta
        self._conn = None
        self._conn_lock = threading.Lock()

        # OPT-3: Batch operations - acumular inserts
        self.pending_all_crops = []
        self.pending_od_crops = []
        self.batch_size = 50  # Flush cada 50 inserts

        # OPT-2: Async I/O writer
        if AsyncCropWriter is not None:
            self.async_writer = AsyncCropWriter()
            self.async_writer.start()
        else:
            self.async_writer = None

        self._init_crops_database()
    
    def _create_class_directories(self):
        """Crear directorios para cada clase de vehículo"""
        # Clases YOLO (inglés) + clases adicionales para reclasificación (español)
        classes = [
            # Clases YOLO (inglés)
            'person', 'bicycle', 'car', 'motorcycle', 'bus', 'truck',
            # Clases adicionales para reclasificación manual (español)
            'camioneta', 'combi', 'microbus', 'mototaxi', 'omnibus',
            'remolque', 'taxi', 'trailer', 'van', 'minivan', 'otros'
        ]

        for crop_dir in [self.all_crops_dir, self.od_crops_dir]:
            for class_name in classes:
                class_dir = crop_dir / class_name
                class_dir.mkdir(exist_ok=True)
                self.class_dirs[class_name] = class_dir
    
    def _get_connection(self):
        """OPT-8: Obtener conexión persistente a la base de datos"""
        if self._conn is None:
            self._conn = sqlite3.connect(self.crops_db_path, check_same_thread=False)
        return self._conn

    def _init_crops_database(self):
        """Inicializar base de datos para metadatos de crops"""
        with self._conn_lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Tabla para crops de todas las detecciones
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS AllCrops (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    crop_filename TEXT UNIQUE,
                    frame_number INTEGER,
                    object_id INTEGER,
                    detection_class TEXT,
                    confidence REAL,
                    bbox_x1 INTEGER,
                    bbox_y1 INTEGER,
                    bbox_x2 INTEGER,
                    bbox_y2 INTEGER,
                    timestamp TEXT,
                    manual_classification TEXT DEFAULT NULL,
                    verified BOOLEAN DEFAULT FALSE
                )
            """)
            
            # Tabla para crops de cruces O/D
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS OdCrops (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    crop_filename TEXT UNIQUE,
                    object_id INTEGER,
                    origin_frame INTEGER,
                    destination_frame INTEGER,
                    origin_line TEXT,
                    destination_line TEXT,
                    turn_name TEXT,
                    detection_class TEXT,
                    confidence REAL,
                    bbox_x1 INTEGER,
                    bbox_y1 INTEGER,
                    bbox_x2 INTEGER,
                    bbox_y2 INTEGER,
                    timestamp TEXT,
                    manual_classification TEXT DEFAULT NULL,
                    verified BOOLEAN DEFAULT FALSE
                )
            """)

            conn.commit()
    
    def save_all_detection_crop(self, frame: np.ndarray, detection: Dict, frame_number: int) -> str:
        """
        Guardar crop de una detección individual
        
        Args:
            frame: Frame del video
            detection: Diccionario con datos de la detección
            frame_number: Número del frame
            
        Returns:
            Ruta del archivo guardado
        """
        try:
            # Extraer información de la detección
            object_id = detection['object_id']
            class_name = detection['class_name']
            confidence = detection['confidence']
            bbox = detection['bbox']  # [x1, y1, x2, y2]

            # Crear crop
            x1, y1, x2, y2 = [int(coord) for coord in bbox]
            crop = frame[y1:y2, x1:x2]

            # Nombre del archivo
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            filename = f"all_{frame_number:06d}_{object_id}_{class_name}_{timestamp}.jpg"

            # Ruta completa
            class_dir = self.all_crops_dir / class_name
            class_dir.mkdir(exist_ok=True)
            filepath = class_dir / filename

            # OPT-2: Guardar imagen asíncronamente si está disponible
            if self.async_writer:
                self.async_writer.enqueue_crop(str(filepath), crop)
            else:
                cv2.imwrite(str(filepath), crop)
            
            # Guardar metadatos en base de datos
            self._save_crop_metadata(
                'AllCrops', filename, frame_number, object_id, class_name,
                confidence, x1, y1, x2, y2, timestamp
            )
            
            return str(filepath)
            
        except Exception as e:
            print(f"Error guardando crop de detección: {e}")
            return ""
    
    def save_od_crossing_crop(self, frame: np.ndarray, crossing_data: Dict) -> str:
        """
        Guardar crop de un cruce O/D
        
        Args:
            frame: Frame del video donde ocurrió el cruce
            crossing_data: Datos del cruce O/D
            
        Returns:
            Ruta del archivo guardado
        """
        try:
            # Extraer información del cruce
            object_id = crossing_data['object_id']
            class_name = crossing_data['class_name']
            confidence = crossing_data.get('confidence', 0.0)
            bbox = crossing_data['bbox']  # [x1, y1, x2, y2]
            origin_frame = crossing_data['origin_frame']
            destination_frame = crossing_data['destination_frame']
            origin_line = crossing_data['origin_line']
            destination_line = crossing_data['destination_line']
            turn_name = crossing_data['turn_name']

            # Crear crop
            x1, y1, x2, y2 = [int(coord) for coord in bbox]
            crop = frame[y1:y2, x1:x2]

            # Nombre del archivo
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            filename = f"od_{origin_frame:06d}_{destination_frame:06d}_{object_id}_{class_name}_{turn_name}_{timestamp}.jpg"

            # Ruta completa
            class_dir = self.od_crops_dir / class_name
            class_dir.mkdir(exist_ok=True)
            filepath = class_dir / filename

            # OPT-2: Guardar imagen asíncronamente si está disponible
            if self.async_writer:
                self.async_writer.enqueue_crop(str(filepath), crop)
            else:
                cv2.imwrite(str(filepath), crop)
            
            # Guardar metadatos en base de datos
            self._save_od_crop_metadata(
                filename, object_id, origin_frame, destination_frame,
                origin_line, destination_line, turn_name, class_name,
                confidence, x1, y1, x2, y2, timestamp
            )
            
            return str(filepath)
            
        except Exception as e:
            print(f"Error guardando crop de cruce O/D: {e}")
            return ""
    
    def _save_crop_metadata(self, table: str, filename: str, frame_number: int,
                           object_id: int, class_name: str, confidence: float,
                           x1: int, y1: int, x2: int, y2: int, timestamp: str):
        """OPT-3: Acumular metadatos del crop para batch insert"""
        data = (filename, frame_number, object_id, class_name, confidence,
                x1, y1, x2, y2, timestamp)

        if table == 'AllCrops':
            self.pending_all_crops.append(data)
            if len(self.pending_all_crops) >= self.batch_size:
                self._flush_all_crops()
        else:
            # Esto no debería pasar, pero por si acaso
            self._flush_all_crops()
            with self._conn_lock:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute(f"""
                    INSERT INTO {table}
                    (crop_filename, frame_number, object_id, detection_class, confidence,
                     bbox_x1, bbox_y1, bbox_x2, bbox_y2, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, data)
                conn.commit()
    
    def _save_od_crop_metadata(self, filename: str, object_id: int,
                              origin_frame: int, destination_frame: int,
                              origin_line: str, destination_line: str,
                              turn_name: str, class_name: str, confidence: float,
                              x1: int, y1: int, x2: int, y2: int, timestamp: str):
        """OPT-3: Acumular metadatos del crop O/D para batch insert"""
        data = (filename, object_id, origin_frame, destination_frame,
                origin_line, destination_line, turn_name, class_name,
                confidence, x1, y1, x2, y2, timestamp)

        self.pending_od_crops.append(data)
        if len(self.pending_od_crops) >= self.batch_size:
            self._flush_od_crops()

    def _flush_all_crops(self):
        """OPT-3: Ejecutar batch insert para crops generales"""
        if not self.pending_all_crops:
            return

        with self._conn_lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            try:
                cursor.executemany("""
                    INSERT INTO AllCrops
                    (crop_filename, frame_number, object_id, detection_class, confidence,
                     bbox_x1, bbox_y1, bbox_x2, bbox_y2, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, self.pending_all_crops)
                conn.commit()
                self.pending_all_crops.clear()
            except Exception as e:
                print(f"Error en batch insert AllCrops: {e}")
                conn.rollback()

    def _flush_od_crops(self):
        """OPT-3: Ejecutar batch insert para crops O/D"""
        if not self.pending_od_crops:
            return

        with self._conn_lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            try:
                cursor.executemany("""
                    INSERT INTO OdCrops
                    (crop_filename, object_id, origin_frame, destination_frame,
                     origin_line, destination_line, turn_name, detection_class,
                     confidence, bbox_x1, bbox_y1, bbox_x2, bbox_y2, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, self.pending_od_crops)
                conn.commit()
                self.pending_od_crops.clear()
            except Exception as e:
                print(f"Error en batch insert OdCrops: {e}")
                conn.rollback()

    def flush_all(self):
        """OPT-3: Forzar flush de todos los pending inserts"""
        self._flush_all_crops()
        self._flush_od_crops()

    def close(self):
        """Cerrar conexión y flush pending data"""
        self.flush_all()

        # OPT-2: Detener async writer y esperar a que termine
        if self.async_writer:
            self.async_writer.stop()

        if self._conn:
            self._conn.close()
            self._conn = None

    def get_unverified_crops(self, crop_type: str = 'all') -> List[Dict]:
        """
        Obtener crops no verificados para clasificación manual

        Args:
            crop_type: 'all' para todos los crops, 'od' para cruces O/D

        Returns:
            Lista de crops no verificados
        """
        table = 'AllCrops' if crop_type == 'all' else 'OdCrops'

        # OPT-3: Flush pending antes de leer
        self.flush_all()

        with self._conn_lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT * FROM {table}
                WHERE verified = FALSE
                ORDER BY id
            """)

            columns = [description[0] for description in cursor.description]
            results = []

            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))

            return results
    
    def update_manual_classification(self, crop_id: int, new_class: str,
                                   crop_type: str = 'all', verified: bool = True):
        """
        Actualizar clasificación manual de un crop

        Args:
            crop_id: ID del crop
            new_class: Nueva clasificación
            crop_type: 'all' o 'od'
            verified: Marcar como verificado
        """
        table = 'AllCrops' if crop_type == 'all' else 'OdCrops'

        with self._conn_lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(f"""
                UPDATE {table}
                SET manual_classification = ?, verified = ?
                WHERE id = ?
            """, (new_class, verified, crop_id))
            conn.commit()
    
    def get_crop_statistics(self) -> Dict:
        """Obtener estadísticas de los crops guardados"""
        # OPT-3: Flush pending antes de leer estadísticas
        self.flush_all()

        with self._conn_lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            stats = {}

            # Estadísticas de crops generales
            cursor.execute("""
                SELECT detection_class, COUNT(*) as count,
                       SUM(CASE WHEN verified THEN 1 ELSE 0 END) as verified_count
                FROM AllCrops GROUP BY detection_class
            """)
            stats['all_crops'] = cursor.fetchall()

            # Estadísticas de crops O/D
            cursor.execute("""
                SELECT detection_class, COUNT(*) as count,
                       SUM(CASE WHEN verified THEN 1 ELSE 0 END) as verified_count
                FROM OdCrops GROUP BY detection_class
            """)
            stats['od_crops'] = cursor.fetchall()

            return stats