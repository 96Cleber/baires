# -*- coding: utf-8 -*-
"""
Created on Sat Aug 24 17:19:34 2024

@author: yeltsin.valero
"""

import sys
import os
from datetime import datetime, timedelta
from io import BytesIO
import logging

from PyQt5.uic import loadUi
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QTableWidgetItem, QDialog, QMessageBox, QErrorMessage
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QFontMetrics, QPolygonF
from PyQt5.QtCore import Qt, QPointF, QModelIndex
import cv2
import sqlite3
from shapely.geometry import LineString, box
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, Frame, PageTemplate
from reportlab.lib.units import inch
import numpy as np
from matplotlib import pyplot as plt

import json

# UI
from ui.info import Ui_GlobalInfo
from ui.project import Ui_projectWindow
from ui.ui3 import Ui_MainWindow
from ui.welcome import Ui_welcomeWindow

# Módulos
from tools.movement_detector import *
from tools.video_player import *
from tools.models import *
from tools.excel_orquestor import generate_excel_report

# Backend detector pipeline (YOLO + ByteTrack)
try:
    from tools.detection_pipeline import DetectorPipeline, LABEL_TO_CODE, CODE_TO_LABEL
    from tools.crop_manager import CropManager
    from ui.manual_classification_dialog import (ManualClassificationDialog,
                                               DatabaseUpdateThread,
                                               YoloRetrainingDialog)
    from ui.simple_classification_dialog import SimpleClassificationDialog
    from ui.stride_config_dialog import StrideConfigDialog
except Exception:
    DetectorPipeline = None # type: ignore
    CropManager = None  # type: ignore
    ManualClassificationDialog = None  # type: ignore
    DatabaseUpdateThread = None  # type: ignore
    YoloRetrainingDialog = None  # type: ignore
    SimpleClassificationDialog = None  # type: ignore
    LABEL_TO_CODE = {
        "person": 1, "bicycle": 2, "car": 3, "motorcycle": 4, "bus": 5, "truck": 6
    }
    CODE_TO_LABEL = {v: k for k, v in LABEL_TO_CODE.items()}

#Global variables
VIDEO_PATH = None
TYPOLOGIES_PATH = "./templates/tipologias.txt"

# DEMO_MODE: Cuando es True, la aplicación permite cargar y visualizar videos
# pero NO permite procesar/detectar vehículos. Útil para versiones de demostración.
# Se activa automáticamente cuando:
#   1. La variable de entorno FLOWVISIONAI_DEMO=1 está establecida, O
#   2. La aplicación se ejecuta como ejecutable empaquetado con PyInstaller (sys.frozen)
# Para desactivar en ejecutables, crear archivo 'license.key' junto al ejecutable
_is_frozen = getattr(sys, 'frozen', False)
_has_license = os.path.exists(os.path.join(os.path.dirname(sys.executable if _is_frozen else __file__), 'license.key'))
DEMO_MODE = os.environ.get('FLOWVISIONAI_DEMO', '0') == '1' or (_is_frozen and not _has_license)

class AnnotatorApp(QMainWindow):
    """
    Aplicación e interfaz de versión de escritorio de OpenFlowAI.

    Atributos
    ---------
    video_player : class
        Clase para manejar la reproducción del video.
    video_player.original_size : (int, int)
        Tupla con las dimensiones originales del video (ancho, alto).
    types_dict : dict
        Diccionario de asignación de códigos de las tipologías.
    bounding_boxes : list
        Lista de cajas de detección.
    counting_lines : list
        Lista de líneas de conteo.
    lines_relations : list
        TODO
    vehicle_states : dict
        TODO
    counts : dict
        TODO
    
    Métodos
    -------
    load_video()
        Cargar el video y mostrar el primer fotograma.
    load_data()
        Cargar las tipologías y cajas de detección.
    load_global_data()
        TODO
    add_new_counting_line()
        Añadir una nueva línea de conteo.
    remove_counting_line()
        Eliminar la línea de conteo seleccionada.
    create_od()
        Crear una relación origen-destino entre líneas de conteo.
    remove_od()
        Eliminar la relación origen-destino seleccionada.
    toggle_video_play()
        Cambiar entre pausa y reproducción del video.
    previous_frame()
        Retroceder la cantidad de fotogramas especificada en frameRateInput.
    next_frame()
        Avanzar la cantidad de fotogramas especificada en frameRateInput.
    videoPressEvent(event)
        Activar el movimiento de una línea de conteo.
    videoMoveEvent(event)
        Mover una línea de conteo.
    videoReleaseEvent(event)
        Soltar una línea de conteo.
    display_frame(frame)
        Mostrar el fotograma `frame` en la interfaz.
    redraw_current_frame()
        Actualizar el fotograma, líneas de conteo y cajas de detección.
    create_table_if_not_exists(cursor)
        TODO
    save_vehicle_count(origin_frame, destination_frame, line, vehicle_type)
        TODO
    get_counting_line_by_name(name)
        TODO
    generate_report()
        TODO
    procesar_datos_por_intervalos(datos_vehiculos, fps, hora_inicio)
        TODO
    get_vehicle_types()
        TODO
    get_video_start_time()
        TODO
    generar_grafico_tipos_apilados(tiempos, conteos_por_tipo)
        TODO
    crear_encabezado(canvas, doc)
        TODO
    detect_movement()
        TODO
    """

    def __init__(self, cfg: dict = {}):
        super(AnnotatorApp, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        # Inicializar configuración
        try:
            # Diccionario de tipos (código->string) y pipeline de detección
            self.types_dict = cfg.get('types', {})
            self.detector_pipeline = None
            self.crop_manager = None
            self.label_to_code = LABEL_TO_CODE
            self.code_to_label = CODE_TO_LABEL
            self.vehicle_states = {}
            self.selected_point = None
            self.track_history = {}
            # OPT-6: Cache de geometrías estáticas para evitar recrear LineStrings
            self.cached_counting_lines_shapely = {}
            # OPT-7: Stride adaptativo para máxima velocidad
            # Stride bajo cuando hay actividad, alto cuando no hay
            self.detection_stride_active = cfg.get('detection_stride_active', 3)
            self.detection_stride_inactive = cfg.get('detection_stride_inactive', 15)
            self.detection_stride = self.detection_stride_active
            self.frames_without_detections = 0
            self.adaptive_stride_threshold = cfg.get('adaptive_stride_threshold', 10)
            self.headless = bool(cfg.get('headless', False))
            self.headless_first_shown = False
            self.headless_update_interval = 30  # Actualizar UI cada 30 frames en modo headless (más rápido)

            self.bounding_boxes = []
            self.counting_lines = []
            for line in cfg.get('counting_lines', []):
                counting_line = CountingLine(line['id'], line['access'], line['name'], QPointF(float(line['start'][0]), float(line['start'][1])), QPointF(float(line['end'][0]), float(line['end'][1])))
                self.counting_lines.append(counting_line)
            self.movements = cfg.get('movements', [])
            for m in self.movements:
                if 'mode' not in m:
                    m['mode'] = 'Vehicular'
            self.counts = {}
            for movement in self.movements:
                self.counts[movement['id']] = {t: 0 for t in self.types_dict.values()}

            # OPT-6: Inicializar cache de geometrías
            self._update_line_cache()

            # Sistema de máscaras/ROI para detección
            self.detection_mask = None  # Máscara binaria (numpy array)
            self.roi_polygons = cfg.get('roi_polygons', [])  # Lista de polígonos para ROI
            self.roi_bbox = None  # Bounding box rectangular del ROI (x_min, y_min, x_max, y_max)
            self.drawing_roi = False
            self.current_roi_points = []
            self._update_detection_mask()

            # OPT-10: Pre-crear QPen objects para mejor rendimiento
            self.line_pen = QPen(Qt.green, 4)
            self.text_pen = QPen(Qt.black, 2)
            self.white_pen = QPen(QColor(255, 255, 255), 1)
            self.roi_pen = QPen(QColor(255, 165, 0), 3)  # Naranja para ROI

            # Activar/desactivar detección YOLO según movimiento
            self.process_all_frames = True # Temp: False para activar con movimiento
            self.yolo_active = True
            self.shutdown_counter = 0
            self.shutdown_date = '2026-12-31'
            
            # Verificar expiración de licencia
            current_date = datetime.now().date()
            expiration_date = datetime.strptime(self.shutdown_date, '%Y-%m-%d').date()
            
            if current_date > expiration_date:
                QMessageBox.critical(self, "Licencia expirada", "Gracias por usar FlowVisionAI.")
                self.ui.playButton.setEnabled(False)
                self.ui.previousFrameButton.setEnabled(False)
                self.ui.nextFrameButton.setEnabled(False)
                self.ui.reportButton.setEnabled(False)

            # Conectar acciones
            self.ui.actionLoadVideo.triggered.connect(self.load_video)
            self.ui.actionLoadData.triggered.connect(self.load_data)
            self.ui.actionLoadResults.triggered.connect(self.load_results)
            self.ui.actionSaveSettings.triggered.connect(self.save_settings)
            self.ui.actionLoadSettings.triggered.connect(self.load_settings)
            self.ui.actionVideoInfo.triggered.connect(self.load_global_data)
            # self.ui.actionHeadless.toggled.connect(self.on_headless_toggled)
            self.ui.actionManualClassification.triggered.connect(self.open_manual_classification)
            self.ui.actionClassificationGallery.triggered.connect(self.open_classification_gallery)
            self.ui.actionUpdateDatabase.triggered.connect(self.update_database_from_crops)
            # self.ui.actionRetrainModel.triggered.connect(self.open_yolo_retraining)

            # Acciones de ROI
            self.ui.actionDrawROI.triggered.connect(self.toggle_draw_roi)
            self.ui.actionClearROI.triggered.connect(self.clear_roi)
            self.ui.actionShowROI.setChecked(True)  # Mostrar ROI por defecto

            # Acción de configuración de velocidad
            self.ui.actionConfigSpeed.triggered.connect(self.open_stride_config)

            # Conectar botones
            self.ui.addCountingLineButton.clicked.connect(self.add_counting_line)
            self.ui.removeCountingLineButton.clicked.connect(self.remove_counting_line)
            self.ui.addMovementButton.clicked.connect(self.add_movement)
            self.ui.removeMovementButton.clicked.connect(self.remove_movement)
            self.ui.playButton.clicked.connect(self.toggle_play)
            self.ui.previousFrameButton.clicked.connect(self.previous_frame)
            self.ui.nextFrameButton.clicked.connect(self.next_frame)
            self.ui.reportButton.clicked.connect(self.generate_report)

            # Configurar controles de stride si existen en la UI
            if hasattr(self, 'strideActiveSpinBox'):
                self.ui.strideActiveSpinBox.setValue(self.detection_stride_active)
                self.ui.strideActiveSpinBox.valueChanged.connect(self.on_stride_active_changed)
            if hasattr(self, 'strideInactiveSpinBox'):
                self.ui.strideInactiveSpinBox.setValue(self.detection_stride_inactive)
                self.ui.strideInactiveSpinBox.valueChanged.connect(self.on_stride_inactive_changed)
            if hasattr(self, 'strideThresholdSpinBox'):
                self.ui.strideThresholdSpinBox.setValue(self.adaptive_stride_threshold)
                self.ui.strideThresholdSpinBox.valueChanged.connect(self.on_stride_threshold_changed)

            # Conectar eventos
            self.ui.videoLabel.mousePressEvent = self.videoPressEvent
            self.ui.videoLabel.mouseMoveEvent = self.videoMoveEvent
            self.ui.videoLabel.mouseReleaseEvent = self.videoReleaseEvent

            # Inicializar modelos y vistas de tablas
            self.countingLinesModel = countingLinesTableModel()
            self.ui.countingLinesTableView.setModel(self.countingLinesModel)

            self.movementsModel = movementsTableModel()
            self.ui.movementsTableView.setModel(self.movementsModel)

            self.accessDelegate = ComboBoxDelegate(['N', 'S', 'E', 'O', 'NE', 'NO', 'SE', 'SO'])
            self.ui.countingLinesTableView.setItemDelegateForColumn(1, self.accessDelegate)

            # Inicializar QWidgets
            self.ui.removeCountingLineButton.setEnabled(len(self.counting_lines) > 0)
            self.ui.addMovementButton.setEnabled(len(self.counting_lines) > 0)
            self.ui.removeMovementButton.setEnabled(len(self.movements) > 0)
            self.ui.actionHeadless.setChecked(self.headless)
            self.ui.actionSaveAllCrops.setChecked(bool(cfg.get('save_all_crops', False)))
            self.ui.actionSaveMovementCrops.setChecked(bool(cfg.get('save_od_crops', False)))

            self.countingLinesModel.lines = self.counting_lines
            self.countingLinesModel.layoutChanged.emit()

            delegate_list = [counting_line.id for counting_line in self.counting_lines]
            self.countingLineDelegateCol1 = ComboBoxDelegate(delegate_list)
            self.countingLineDelegateCol2 = ComboBoxDelegate(delegate_list)
            self.ui.movementsTableView.setItemDelegateForColumn(1, self.countingLineDelegateCol1)
            self.ui.movementsTableView.setItemDelegateForColumn(2, self.countingLineDelegateCol2)

            # Añadir delegado para la cuarta columna (Modo) - vehicular/peatonal
            self.modeDelegate = ComboBoxDelegate(['Vehicular', 'Peatonal'])
            self.ui.movementsTableView.setItemDelegateForColumn(3, self.modeDelegate)
            
            self.movementsModel.movements = self.movements
            self.movementsModel.layoutChanged.emit()

            # Inicializar detector de movimiento
            self.movement_detector = VehicleMovementDetector()

            # Los menús ya están definidos en ui3.ui - No es necesario agregarlos programáticamente
            # Las acciones están en ui3.ui: actionConfigSpeed, actionDrawROI, actionClearROI, actionShowROI
            print("[INFO] Menús avanzados cargados desde ui3.ui")

        except Exception as e:
            QErrorMessage(self).showMessage(f"Error inicializando la aplicación: {e}")

        # Inicializar video (puede ser None si no se cargó)
        self.video_player = None
        if VIDEO_PATH:
            try:
                self.video_player = VideoPlayer(VIDEO_PATH, self.display_frame)
                self.video_player.draw_frame(0)

                # Inicializar barra de progreso
                total = int(self.video_player.cap.get(cv2.CAP_PROP_FRAME_COUNT))
                self.ui.progressBar.setRange(0, max(1, total))
                self.ui.progressBar.setValue(0)
            except Exception as e:
                self.video_player = None
                QErrorMessage(self).showMessage(f"No se pudo cargar el video: {e}")

        # Inicializar tipos y pipeline de detección (YOLO + ByteTrack)
        try:
            # Establecer mapeo de tipos por defecto (para crear ODs y conteos)
            self.types_dict = dict(self.code_to_label)
            # Sincronizar stride de detección con stride de reproducción
            if self.video_player:
                self.detection_stride = self.video_player.display_rate

            # Inicializar crop manager
            if CropManager is not None and VIDEO_PATH:
                self.crop_manager = CropManager(VIDEO_PATH, TYPOLOGIES_PATH)
            else:
                self.crop_manager = None

            # DEMO_MODE: No inicializar detector, mostrar mensaje
            if DEMO_MODE:
                self.detector_pipeline = None
                QMessageBox.information(
                    self,
                    "Modo Demostración",
                    "Esta es una versión de demostración de FlowVisionAI.\n\n"
                    "Puede cargar y visualizar videos, configurar líneas de conteo y ROIs, "
                    "pero el procesamiento automático de vehículos está deshabilitado.\n\n"
                    "Contacte al proveedor para obtener la versión completa."
                )
            elif DetectorPipeline is not None and current_date <= expiration_date:
                # Buscar pesos por defecto en ./weights; si no, usar alias oficial para auto-descarga
                project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
                weights_dir = os.path.join(project_root, 'weights')
                os.makedirs(weights_dir, exist_ok=True)
                local_candidates = [
                    os.path.join(weights_dir, 'yolov8x.pt'),
                    os.path.join(weights_dir, 'yolov8l.pt'),
                    os.path.join(weights_dir, 'yolov8m.pt'),
                    os.path.join(weights_dir, 'yolov8s.pt'),
                    os.path.join(weights_dir, 'yolov8n.pt'),
                ]
                weights_path = next((p for p in local_candidates if os.path.exists(p)), None)
                if not weights_path:
                    # Intentar alias para auto-descarga con Ultralytics
                    weights_path = 'yolov8x.pt'
                try:
                    self.detector_pipeline = DetectorPipeline(weights_path)
                    try:
                        device = getattr(self.detector_pipeline, 'device', 'cpu')
                        device_name = getattr(self.detector_pipeline, 'device_name', device)
                        print(f"[FlowVisionAI] Detector usando dispositivo: {device} ({device_name})")
                        QMessageBox.information(self, "YOLO", f"Detector en: {device_name}")
                    except Exception:
                        pass
                except Exception:
                    # Último recurso: pedir al usuario seleccionar un archivo .pt local
                    QMessageBox.information(self, "YOLO Weights", "Selecciona el archivo de pesos YOLO (*.pt)")
                    sel_path, _ = QFileDialog.getOpenFileName(self, "Seleccionar pesos YOLO", "", "Model files (*.pt)")
                    if sel_path:
                        self.detector_pipeline = DetectorPipeline(sel_path)
                        try:
                            device = getattr(self.detector_pipeline, 'device', 'cpu')
                            device_name = getattr(self.detector_pipeline, 'device_name', device)
                            print(f"[FlowVisionAI] Detector usando dispositivo: {device} ({device_name})")
                            QMessageBox.information(self, "YOLO", f"Detector en: {device_name}")
                        except Exception:
                            pass
                    else:
                        self.detector_pipeline = None
            else:
                self.detector_pipeline = None
        except Exception as e:
            self.detector_pipeline = None
            err = QErrorMessage(self)
            err.showMessage(f"No se pudo inicializar el detector: {e}")

# Acciones
    def load_video(self):
        """
        Cargar el video y mostrar el primer fotograma.
        """
        global VIDEO_PATH
        VIDEO_PATH, _ = QFileDialog.getOpenFileName(self, "Seleccionar video", "", "Archivos de video (*.mp4 *.avi *.mov *.dav)")
        if VIDEO_PATH:
            annotator = AnnotatorApp()
            self.close()
            annotator.show()

    def load_data(self):
        """
        Cargar las tipologías y cajas de detección.
        """
        db_file, _ = QFileDialog.getOpenFileName(self, "Seleccionar base de datos", "", "Archivos SQLite (*.sqlite *.db)")
        if db_file:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()

            cursor.execute('SELECT road_user_type, type_string FROM objects_type')
            self.types_dict = {row[0]: row[1] for row in cursor.fetchall()}

            print("[INFO] types_dict recargado. Reconstruyendo self.counts...")
            new_counts = {}
            for movement in self.movements:
                movement_id = movement['id']
                # Inicia todos los nuevos tipos en 0
                new_counts_for_movement = {t: 0 for t in self.types_dict.values()}
                
                # Opcional: Si quieres intentar preservar conteos antiguos
                # (esto es más complejo si los nombres de tipo cambian)
                # old_counts_for_movement = self.counts.get(movement_id, {})
                # for old_type, old_count in old_counts_for_movement.items():
                #     if old_type in new_counts_for_movement:
                #         new_counts_for_movement[old_type] = old_count
                        
                new_counts[movement_id] = new_counts_for_movement
            self.counts = new_counts
            print("[INFO] self.counts reconstruido.")

            cursor.execute('''
                SELECT o.object_id, o.road_user_type, b.frame_number, b.x_top_left, b.y_top_left, b.x_bottom_right, b.y_bottom_right
                FROM bounding_boxes b
                JOIN objects o ON b.object_id = o.object_id
            ''')
            self.bounding_boxes = [
                BoundingBox(row[0], row[1], row[2], row[3], row[4], row[5], row[6])
                for row in cursor.fetchall()
            ]

            conn.close()
        
        if self.video_player:
            self.redraw_current_frame()

    def load_results(self):
        """
        Cargar resultados existentes (carpeta crops_od y base de datos de crops).
        No requiere tener un video cargado.
        """
        # Seleccionar carpeta de crops_od
        crops_dir = QFileDialog.getExistingDirectory(
            self,
            "Seleccionar carpeta de resultados (crops_od)",
            "",
            QFileDialog.ShowDirsOnly
        )

        if not crops_dir:
            return

        # Buscar la base de datos de crops asociada
        crops_dir_path = os.path.dirname(crops_dir)
        crops_folder_name = os.path.basename(crops_dir)

        # Intentar encontrar la base de datos de crops
        # El nombre suele ser: {video_name}_crops.db
        if crops_folder_name.endswith('_crops_od'):
            video_name = crops_folder_name.replace('_crops_od', '')
            crops_db_path = os.path.join(crops_dir_path, f"{video_name}_crops.db")
        else:
            video_name = crops_folder_name
            crops_db_path = None

        # También buscar Conteos.db
        conteos_db_path = os.path.join(crops_dir_path, "Conteos.db")

        loaded_items = []

        # Inicializar CropManager desde la carpeta existente (sin necesidad de video)
        if CropManager is not None:
            try:
                self.crop_manager = CropManager.load_existing(crops_dir, TYPOLOGIES_PATH)
                loaded_items.append(f"CropManager inicializado para: {video_name}")
            except Exception as e:
                print(f"[ERROR] No se pudo inicializar CropManager: {e}")
                self.crop_manager = None

        # Cargar base de datos de crops si existe
        if crops_db_path and os.path.exists(crops_db_path):
            try:
                conn = sqlite3.connect(crops_db_path)
                cursor = conn.cursor()

                # Verificar tablas disponibles
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]

                if 'OdCrops' in tables:
                    cursor.execute("SELECT COUNT(*) FROM OdCrops")
                    od_count = cursor.fetchone()[0]
                    loaded_items.append(f"OdCrops: {od_count} registros")

                if 'AllCrops' in tables:
                    cursor.execute("SELECT COUNT(*) FROM AllCrops")
                    all_count = cursor.fetchone()[0]
                    loaded_items.append(f"AllCrops: {all_count} registros")

                conn.close()
            except Exception as e:
                print(f"[ERROR] No se pudo cargar crops.db: {e}")

        # Cargar Conteos.db si existe
        if os.path.exists(conteos_db_path):
            try:
                conn = sqlite3.connect(conteos_db_path)
                cursor = conn.cursor()

                cursor.execute('SELECT road_user_type, type_string FROM objects_type')
                self.types_dict = {row[0]: row[1] for row in cursor.fetchall()}

                cursor.execute('''
                    SELECT o.object_id, o.road_user_type, b.frame_number, b.x_top_left, b.y_top_left, b.x_bottom_right, b.y_bottom_right
                    FROM bounding_boxes b
                    JOIN objects o ON b.object_id = o.object_id
                ''')
                self.bounding_boxes = [
                    BoundingBox(row[0], row[1], row[2], row[3], row[4], row[5], row[6])
                    for row in cursor.fetchall()
                ]

                loaded_items.append(f"Conteos.db: {len(self.bounding_boxes)} detecciones")
                conn.close()
            except Exception as e:
                print(f"[ERROR] No se pudo cargar Conteos.db: {e}")

        # Contar archivos de imagen en la carpeta (incluyendo subdirectorios)
        image_extensions = ('.jpg', '.jpeg', '.png', '.bmp')
        image_count = 0
        if os.path.isdir(crops_dir):
            for root, dirs, files in os.walk(crops_dir):
                image_count += sum(1 for f in files if f.lower().endswith(image_extensions))
        loaded_items.append(f"Imágenes en carpeta: {image_count}")

        # Mostrar resumen
        if loaded_items:
            QMessageBox.information(
                self,
                "Resultados cargados",
                "Se cargaron los siguientes datos:\n\n" + "\n".join(loaded_items) +
                "\n\nAhora puede usar las herramientas de clasificación."
            )
        else:
            QMessageBox.warning(
                self,
                "Sin resultados",
                "No se encontraron resultados válidos en la carpeta seleccionada."
            )

        if self.video_player:
            self.redraw_current_frame()

    def load_global_data(self):
        
        """
        TODO
        """
        # Cargar y mostrar otra interfaz
        self.video_global_info = GlobalInfo()
        self.video_global_info.show()

# Botones
    def add_counting_line(self):
        """
        Añadir una nueva línea de conteo.
        """
        # Añadir la línea de conteo
        id = "L" + str(len(self.counting_lines) + 1)
        name = f"Línea de conteo {len(self.counting_lines) + 1}"
        new_counting_line = CountingLine(id, 'N', name, QPointF(50, 50), QPointF(200, 200))

        new_row_index = len(self.counting_lines)

        self.countingLinesModel.beginInsertRows(
            QModelIndex(), new_row_index, new_row_index
        )

        self.counting_lines.append(new_counting_line)
        self.countingLinesModel.endInsertRows()

        delegate_list = [counting_line.id for counting_line in self.counting_lines]
        self.countingLineDelegateCol1 = ComboBoxDelegate(delegate_list)
        self.countingLineDelegateCol2 = ComboBoxDelegate(delegate_list)
        self.ui.movementsTableView.setItemDelegateForColumn(1, self.countingLineDelegateCol1)
        self.ui.movementsTableView.setItemDelegateForColumn(2, self.countingLineDelegateCol2)

        # Activar botones
        if not self.ui.removeCountingLineButton.isEnabled():
            self.ui.removeCountingLineButton.setEnabled(True)
            self.ui.addMovementButton.setEnabled(True)

        # OPT-6: Actualizar cache de geometrías
        self._update_line_cache()
        self.redraw_current_frame()

    def remove_counting_line(self):
        """
        Eliminar la línea de conteo seleccionada.
        """
        indexes = self.ui.countingLinesTableView.selectionModel().selectedIndexes()
        if indexes:
            index = indexes[0]
            line_id = self.ui.countingLinesTableView.model().data(index, Qt.DisplayRole)

            print(f"[DEBUG] Eliminando línea {line_id}")
            self.countingLinesModel.beginResetModel()
            new_lines = [line for line in self.counting_lines if line.id != line_id]
            self.counting_lines.clear()
            self.counting_lines.extend(new_lines)

            self.countingLinesModel.endResetModel()

            print(f"[DEBUG] Filtrando movimientos...")
            self.movementsModel.beginResetModel()

            new_movements = [m for m in self.movements if m['o'] != line_id and m['d'] != line_id]
            self.movements.clear()
            self.movements.extend(new_movements)

            self.movementsModel.endResetModel()

            print(f"[DEBUG] Movimientos restantes: {len(self.movements)}")

            delegate_list = [counting_line.id for counting_line in self.counting_lines]
            countingLineDelegateCol1 = ComboBoxDelegate(delegate_list)
            countingLineDelegateCol2 = ComboBoxDelegate(delegate_list)
            self.ui.movementsTableView.setItemDelegateForColumn(1, countingLineDelegateCol1)
            self.ui.movementsTableView.setItemDelegateForColumn(2, countingLineDelegateCol2)

        # Desactivar botón de eliminar línea de conteo
        if not self.counting_lines:
            self.ui.removeCountingLineButton.setEnabled(False)
            self.ui.addMovementButton.setEnabled(False)

        if not self.movements:
            self.ui.removeMovementButton.setEnabled(False)

        # OPT-6: Actualizar cache de geometrías
        self._update_line_cache()
        self.redraw_current_frame()

    def add_movement(self):
        """
        Crear una relación origen-destino entre líneas de conteo.
        """
        # Añadir el movimiento
        id = "M" + str(len(self.movements) + 1)
        new_movement = {
            "id": id,
            "o": self.counting_lines[0].id,
            "d": self.counting_lines[0].id,
            "mode": "Vehicular"
            }

        #new_row_index = len(self.movements)
        #self.movementsModel.beginInsertRows(
        #    QModelIndex(), new_row_index, new_row_index
        #)

        self.movements.append(new_movement)
        self.counts[id] = {type_string: 0 for type_string in self.types_dict.values()}

        # Actualizar tabla
        self.movementsModel.movements = self.movements
        self.movementsModel.layoutChanged.emit()

        # Activar botón de eliminar movimiento
        if not self.ui.removeMovementButton.isEnabled():
            self.ui.removeMovementButton.setEnabled(True)

    def remove_movement(self):
        """
        Eliminar la relación origen-destino seleccionada.
        """
        indexes = self.ui.movementsTableView.selectionModel().selectedIndexes()

        if not indexes: return

        rows_to_remove = sorted(list(set(idx.row() for idx in indexes)), reverse=True)

        for row in rows_to_remove:
            movement_id = self.movements[row]['id']
            print(f"[DEBUG] Eliminando fila {row}, ID: {movement_id}")

            self.movementsModel.beginRemoveRows(QModelIndex(), row, row)

            if movement_id in self.counts:
                self.counts.pop(movement_id)
            self.movements.pop(row)

            self.movementsModel.endRemoveRows()

        print(f"[DEBUG] Movimientos restantes: {len(self.movements)}")

        if not self.movements:
            self.ui.removeMovementButton.setEnabled(False)

    def toggle_play(self):
        """
        Cambiar entre pausa y reproducción del video.
        """
        # En DEMO_MODE, bloquear reproducción/procesamiento
        if DEMO_MODE:
            QMessageBox.warning(
                self,
                "Modo Demostración",
                "El procesamiento de video está deshabilitado en la versión de demostración.\n\n"
                "Puede navegar frame por frame usando los botones de avance/retroceso, "
                "configurar líneas de conteo y áreas ROI.\n\n"
                "Contacte al proveedor para obtener la versión completa."
            )
            return

        if self.video_player.video_playing:
            self.video_player.pause()
            self.ui.playButton.setText("⏵")
        else:
            self.video_player.play()
            self.ui.playButton.setText("⏸")

    def previous_frame(self):
        """
        Retroceder la cantidad de fotogramas especificada en frameRateInput.
        """
        self.video_player.frame_number -= int(self.ui.frameRateInput.text())
        self.redraw_current_frame()

    def next_frame(self):
        """
        Avanzar la cantidad de fotogramas especificada en frameRateInput.
        """
        self.video_player.frame_number += int(self.ui.frameRateInput.text())
        self.redraw_current_frame()

    # ===== Configuración (exportar/cargar) =====
    def save_settings(self):
        try:
            cfg = {}
            # Video
            if self.video_player:
                cap = self.video_player.cap
                cfg['video'] = {
                    'path': VIDEO_PATH,
                    'fps': cap.get(cv2.CAP_PROP_FPS) if cap else None,
                    'width': cap.get(cv2.CAP_PROP_FRAME_WIDTH) if cap else None,
                    'height': cap.get(cv2.CAP_PROP_FRAME_HEIGHT) if cap else None,
                    'frame_stride': getattr(self.video_player, 'frame_stride', 2),
                }
            # Líneas de conteo
            counting_lines = []
            for counting_line in getattr(self, 'counting_lines', []):
                counting_lines.append({
                    'id': counting_line.id,
                    'start': [counting_line.start.x(), counting_line.start.y()],
                    'end': [counting_line.end.x(), counting_line.end.y()],
                    'access': counting_line.access,
                    'name': counting_line.name,
                })
            cfg['counting_lines'] = counting_lines
            # Movimienots
            cfg['movements'] = list(getattr(self, 'movements', []))
            # Tipos
            cfg['types'] = dict(getattr(self, 'types_dict', {}))
            # Otros
            cfg['detection_stride'] = int(getattr(self, 'detection_stride', 2))
            cfg['headless'] = bool(getattr(self, 'headless', False))
            # Configuración de crops
            cfg['save_all_crops'] = (hasattr(self.ui, 'actionSaveAllCrops') and
                                    self.ui.actionSaveAllCrops.isChecked())
            cfg['save_od_crops'] = (hasattr(self.ui, 'actionSaveMovementCrops') and
                                   self.ui.actionSaveMovementCrops.isChecked())

            # Configuración de stride adaptativo
            cfg['detection_stride_active'] = getattr(self, 'detection_stride_active', 3)
            cfg['detection_stride_inactive'] = getattr(self, 'detection_stride_inactive', 15)
            cfg['adaptive_stride_threshold'] = getattr(self, 'adaptive_stride_threshold', 10)

            # Configuración de ROI (áreas de detección)
            cfg['roi_polygons'] = getattr(self, 'roi_polygons', [])

            path, _ = QFileDialog.getSaveFileName(self, 'Guardar configuración', '', 'JSON (*.json)')
            if not path:
                return
            if not path.endswith('.json'):
                path += '.json'
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, 'Exportar', 'Configuración exportada correctamente.')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'No se pudo exportar: {e}')

    def load_settings(self):
        global VIDEO_PATH
        path, _ = QFileDialog.getOpenFileName(self, 'Cargar Configuración', '', 'JSON (*.json)')
        if path:
            with open(path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            VIDEO_PATH = cfg.get('video', {}).get('path', None)
            annotator = AnnotatorApp(cfg)
            self.close()
            annotator.show()

    # def on_headless_toggled(self, checked: bool):
    #     self.headless = bool(checked)
    #     if hasattr(self, 'progressBar'):
    #         self.progressBar.setVisible(self.headless)
    #         if self.headless:
    #             # Asegurar que la barra de progreso esté configurada correctamente
    #             try:
    #                 total_frames = int(self.video_player.cap.get(cv2.CAP_PROP_FRAME_COUNT))
    #                 self.progressBar.setRange(0, max(1, total_frames))
    #                 current_frame = getattr(self.video_player, 'frame_number', 0)
    #                 self.progressBar.setValue(current_frame)
    #             except Exception:
    #                 pass

    # === Métodos para clasificación manual y reentrenamiento ===
    def open_manual_classification(self):
        """Abrir diálogo de clasificación manual"""
        if self.crop_manager is None:
            QMessageBox.warning(self, "Advertencia", 
                               "No hay un video cargado o el sistema de crops no está disponible.")
            return
        
        if ManualClassificationDialog is None:
            QMessageBox.critical(self, "Error", 
                               "El módulo de clasificación manual no está disponible.")
            return
        
        try:
            dialog = ManualClassificationDialog(self.crop_manager, self)
            dialog.exec_()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error abriendo clasificación manual: {e}")
            raise e
    
    def open_classification_gallery(self):
        """Abrir galería de clasificación manual"""
        if self.crop_manager is None:
            QMessageBox.warning(self, "Advertencia", 
                               "No hay un video cargado o el sistema de crops no está disponible.")
            return
        
        if SimpleClassificationDialog is None:
            QMessageBox.critical(self, "Error", 
                               "El módulo de clasificación simple no está disponible.")
            return
        
        try:
            typologies_path = "./templates/tipologias.txt"
            all_typologies = []
            with open(typologies_path, "r", encoding='utf-8') as file:
                for line in file:
                    clean_line = line.strip()
                    if not clean_line or clean_line.startswith("#"):
                        continue
                    all_typologies.append(clean_line)

            # Pasar todas las tipologías como default, lista vacía como additional
            dialog = SimpleClassificationDialog(self.crop_manager, all_typologies, [], self)
            dialog.exec_()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error abriendo clasificación simple: {e}")
    
    def update_database_from_crops(self):
        """Actualizar base de datos principal con clasificaciones manuales"""
        if self.crop_manager is None:
            QMessageBox.warning(self, "Advertencia",
                               "No hay resultados cargados. Cargue un video o resultados primero.")
            return

        if DatabaseUpdateThread is None:
            QMessageBox.critical(self, "Error",
                               "El módulo de actualización de base de datos no está disponible.")
            return

        # Obtener ruta de la base de datos desde el crop_manager
        video_dir = str(self.crop_manager.video_dir)
        video_name = self.crop_manager.video_name
        main_db_path = os.path.join(video_dir, "Conteos.db")
        
        if not os.path.exists(main_db_path):
            QMessageBox.warning(self, "Advertencia", 
                               "No se encontró la base de datos de conteos (Conteos.db).")
            return
        
        try:
            # Crear y ejecutar hilo de actualización
            self.update_thread = DatabaseUpdateThread(self.crop_manager, main_db_path)
            self.update_thread.finished.connect(self.on_database_update_finished)
            self.update_thread.error.connect(self.on_database_update_error)
            
            # Desactivar botón mientras se actualiza
            if hasattr(self, 'actionUpdate_Database'):
                self.ui.actionUpdateDatabase.setEnabled(False)
            
            QMessageBox.information(self, "Información", 
                                   "Iniciando actualización de base de datos...")
            self.update_thread.start()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error iniciando actualización: {e}")
    
    def on_database_update_finished(self, message):
        """Callback cuando termina la actualización de base de datos"""
        QMessageBox.information(self, "Actualización Completa", message)
        if hasattr(self, 'actionUpdate_Database'):
            self.ui.actionUpdateDatabase.setEnabled(True)
    
    def on_database_update_error(self, error_msg):
        """Callback cuando hay error en la actualización"""
        QMessageBox.critical(self, "Error de Actualización", error_msg)
        if hasattr(self, 'actionUpdate_Database'):
            self.ui.actionUpdateDatabase.setEnabled(True)
    
    # def open_yolo_retraining(self):
    #     """Abrir diálogo de reentrenamiento YOLO"""
    #     if self.crop_manager is None:
    #         QMessageBox.warning(self, "Advertencia", 
    #                            "No hay un video cargado o el sistema de crops no está disponible.")
    #         return
        
    #     if YoloRetrainingDialog is None:
    #         QMessageBox.critical(self, "Error", 
    #                            "El módulo de reentrenamiento no está disponible.")
    #         return
        
    #     try:
    #         dialog = YoloRetrainingDialog(self.crop_manager, self)
    #         dialog.exec_()
    #     except Exception as e:
    #         QMessageBox.critical(self, "Error", f"Error abriendo reentrenamiento: {e}")

# Eventos
    def videoPressEvent(self, event):
        """
        Activar el movimiento de una línea de conteo o dibujar ROI.

        Parámetros
        ----------
        event : class
            Clase QEvent de Qt con la información del evento.
        """

        try:
            displayed_size = self.ui.videoLabel.pixmap().size()
            x_scale = displayed_size.width() / self.video_player.original_size[0]
            y_scale = displayed_size.height() / self.video_player.original_size[1]

            # Modo de dibujo de ROI
            if self.drawing_roi and event.button() == Qt.LeftButton:
                # Convertir coordenadas a escala original del video
                x_orig = event.x() / x_scale
                y_orig = event.y() / y_scale
                self.current_roi_points.append([int(x_orig), int(y_orig)])
                print(f"[ROI] Punto agregado: ({int(x_orig)}, {int(y_orig)}) - Total: {len(self.current_roi_points)}")

                # Actualizar barra de estado con progreso
                if len(self.current_roi_points) < 3:
                    self.ui.statusBar.showMessage(f"Puntos agregados: {len(self.current_roi_points)}/3 (mínimo) - Clic derecho o ESC para finalizar")
                else:
                    self.ui.statusBar.showMessage(f"Puntos agregados: {len(self.current_roi_points)} - Clic derecho o ESC para cerrar polígono")

                self.redraw_current_frame()
                return
            elif self.drawing_roi and event.button() == Qt.RightButton:
                # Finalizar polígono con clic derecho
                if len(self.current_roi_points) >= 3:
                    print(f"[ROI] Finalizando polígono con {len(self.current_roi_points)} puntos")
                    self.toggle_draw_roi()
                else:
                    print(f"[ROI] No se puede finalizar - Se necesitan mínimo 3 puntos (actualmente: {len(self.current_roi_points)})")
                    self.ui.statusBar.showMessage("Se necesitan mínimo 3 puntos para crear el polígono ROI", 2000)
                return

            # Modo normal: mover líneas de conteo
            if event.button() == Qt.LeftButton:
                for counting_line in self.counting_lines:
                    scaled_start = QPointF(counting_line.start.x() * x_scale, counting_line.start.y() * y_scale)
                    scaled_end = QPointF(counting_line.end.x() * x_scale, counting_line.end.y() * y_scale)

                    if (scaled_start - QPointF(event.x(), event.y())).manhattanLength() < 10:
                        self.selected_point = counting_line.start
                        counting_line.selected = True
                        break
                    elif (scaled_end - QPointF(event.x(), event.y())).manhattanLength() < 10:
                        self.selected_point = counting_line.end
                        counting_line.selected = True
                        break
        except AttributeError as e:
            print("No se seleccionó un archivo de informe")

    def videoMoveEvent(self, event):
        """
        Mover una línea de conteo.

        Parámetros
        ----------
        event : class
            Clase QEvent de Qt con la información del evento.
        """
        if self.selected_point:
            displayed_size = self.ui.videoLabel.pixmap().size()
            x_scale = displayed_size.width() / self.video_player.original_size[0]
            y_scale = displayed_size.height() / self.video_player.original_size[1]

            self.selected_point.setX(event.x() / x_scale)
            self.selected_point.setY(event.y() / y_scale)
            self.redraw_current_frame()

    def videoReleaseEvent(self, event):
        """
        Soltar una línea de conteo.

        Parámetros
        ----------
        event : class
            Clase QEvent de Qt con la información del evento.
        """
        self.selected_point = None
        for counting_line in self.counting_lines:
            counting_line.selected = False
        # OPT-6: Actualizar cache si se movió una línea
        self._update_line_cache()

    def keyPressEvent(self, event):
        """
        Manejar eventos de teclado.

        Parámetros
        ----------
        event : QKeyEvent
            Evento de teclado de Qt.
        """
        # ESC: Cancelar o finalizar dibujo de ROI
        if event.key() == Qt.Key_Escape:
            if self.drawing_roi:
                print("[ROI] Finalizando polígono con tecla ESC")
                if len(self.current_roi_points) >= 3:
                    self.toggle_draw_roi()
                else:
                    print(f"[ROI] Cancelando - Solo hay {len(self.current_roi_points)} puntos")
                    self.drawing_roi = False
                    self.current_roi_points = []
                    self.ui.statusBar.showMessage("Dibujo de ROI cancelado", 2000)
                    self.redraw_current_frame()
                return

        # Llamar al handler base
        super().keyPressEvent(event)

# Métodos auxiliares
    def display_frame(self, frame):
        """
        Mostrar el fotograma `frame` en la interfaz.

        Parámetros
        ----------
        frame : ndarray
            Fotograma OpenCV.
        """
        # Ejecutar detección y seguimiento para cada fotograma mostrado
        if getattr(self, 'detector_pipeline', None) is not None:
            try:
                # Reemplazar bounding boxes del frame actual con nuevas detecciones
                if self.yolo_active or not self.ui.actionDetectMovement.isChecked():
                    current_fn = self.video_player.frame_number
                    self.bounding_boxes = [b for b in self.bounding_boxes if b.frame_number != current_fn]

                    # EXTRAER REGIÓN ROI para procesamiento eficiente
                    # YOLO solo procesa el crop rectangular (mucho más rápido)
                    frame_for_detection, roi_offset_x, roi_offset_y = self.apply_detection_mask(frame)

                    # IMPORTANTE: Pasar stride actual al tracker para tracking correcto
                    detections = self.detector_pipeline.process_frame(frame_for_detection, stride=self.detection_stride)

                    # STRIDE ADAPTATIVO: Ajustar velocidad según actividad
                    if len(detections) > 0:
                        # HAY detecciones: usar stride bajo (procesar más frames)
                        self.frames_without_detections = 0
                        if self.detection_stride != self.detection_stride_active:
                            self.detection_stride = self.detection_stride_active
                            self.video_player.display_rate = self.detection_stride_active
                            print(f"[VELOCIDAD] Actividad detectada - Stride BAJO (cada {self.detection_stride_active} frames)")
                    else:
                        # NO hay detecciones: incrementar contador
                        self.frames_without_detections += 1
                        # Si pasan N frames sin detecciones, usar stride alto (saltar más frames)
                        if self.frames_without_detections >= self.adaptive_stride_threshold:
                            if self.detection_stride != self.detection_stride_inactive:
                                self.detection_stride = self.detection_stride_inactive
                                self.video_player.display_rate = self.detection_stride_inactive
                                print(f"[VELOCIDAD] Sin actividad - Stride ALTO (cada {self.detection_stride_inactive} frames) - AVANCE RÁPIDO")

                    # Procesar detecciones y ajustar coordenadas al frame original
                    for det in detections:
                        x1, y1, x2, y2 = det['bbox']

                        # AJUSTAR coordenadas: sumar offset del ROI crop
                        x1 += roi_offset_x
                        y1 += roi_offset_y
                        x2 += roi_offset_x
                        y2 += roi_offset_y

                        label = det['label']
                        track_id = det['track_id']
                        code = self.label_to_code.get(label, 0)
                        if code == 0:
                            continue
                        self.bounding_boxes.append(
                            BoundingBox(track_id, code, current_fn, x1, y1, x2, y2)
                        )
                        
                        # Guardar crop de todas las detecciones si está habilitado
                        if self.ui.actionSaveAllCrops.isChecked() and self.crop_manager is not None:
                            detection_data = {
                                'object_id': track_id,
                                'class_name': label,
                                'confidence': det.get('confidence', 0.0),
                                'bbox': [x1, y1, x2, y2]
                            }
                            self.crop_manager.save_all_detection_crop(frame, detection_data, current_fn)
            except Exception as e:
                # En caso de error, continuar mostrando el frame sin detecciones nuevas
                print(f"[Detector ERROR] {e}")

        # Convertir el fotograma para mostrarlo en el QLabel
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = frame_rgb.shape
        bytes_per_line = ch * w
        q_image = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(q_image)

        # Escalar el pixmap para que se ajuste al largo del QLabel manteniendo la proporción
        scaled_pixmap = pixmap.scaled(self.ui.videoLabel.width(), self.ui.videoLabel.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation)

        # Obtener el tamaño real del video mostrado
        displayed_size = scaled_pixmap.size()

        # Ajustar el tamaño del QLabel al tamaño del video escalado
        self.ui.videoLabel.setFixedSize(displayed_size)

        # Calcular el factor de escala
        x_scale = displayed_size.width() / self.video_player.original_size[0]
        y_scale = displayed_size.height() / self.video_player.original_size[1]

        # Dibujar las líneas de conteo y cajas de detección sobre el fotograma
        if self.counting_lines or self.bounding_boxes:
            painter = QPainter(scaled_pixmap)
            # OPT-10: Desactivar antialiasing para mejor rendimiento
            painter.setRenderHint(QPainter.Antialiasing, False)
            painter.setRenderHint(QPainter.TextAntialiasing, False)
            # Mapa de colores por clase (RGB para Qt)
            label_to_color_rgb = {
                'person':     (255, 0, 0),   # rojo
                'bicycle':    (0, 255, 0),   # verde
                'car':        (0, 0, 255),   # azul
                'motorcycle': (255, 255, 0), # amarillo
                'bus':        (255, 0, 255), # magenta
                'truck':      (0, 255, 255), # cian
            }

            # Dibujar las líneas de conteo
            for counting_line in self.counting_lines:
                start = QPointF(counting_line.start.x() * x_scale, counting_line.start.y() * y_scale)
                end = QPointF(counting_line.end.x() * x_scale, counting_line.end.y() * y_scale)
                startText = QPointF(start.x() - 15, start.y() - 15)
                endText = QPointF(end.x() + 15, end.y() + 15)
                # OPT-10: Usar pens precreados
                painter.setPen(self.line_pen)
                painter.drawLine(start, end)
                painter.fillRect(int(start.x()) - 4, int(start.y()) - 4, 9, 9, Qt.black)
                painter.fillRect(int(end.x()) - 4, int(end.y()) - 4, 9, 9, Qt.black)
                painter.setPen(self.text_pen)
                painter.drawText(startText, counting_line.id)
                painter.drawText(endText, counting_line.id)

            # Preparar track labels y actualizar historial de trayectorias del frame actual
            current_bboxes = [b for b in self.bounding_boxes if b.frame_number == self.video_player.frame_number]
            current_labels = {}
            for b in current_bboxes:
                current_labels[b.id] = self.types_dict.get(b.road_user_type, self.code_to_label.get(b.road_user_type, 'car'))
                x1h, y1h, x2h, y2h = b.coordinates.bounds
                cxh = (x1h + x2h) / 2
                cyh = (y1h + y2h) / 2
                self.track_history.setdefault(b.id, []).append((cxh, cyh))
                # if len(self.track_history[b.id]) > 20:
                #     self.track_history[b.id] = self.track_history[b.id][-20:]

            # Dibujar las cajas de detección y realizar la detección de intersección
            for box in current_bboxes:
                x1, y1, x2, y2 = box.coordinates.bounds
                label = self.types_dict.get(box.road_user_type, self.code_to_label.get(box.road_user_type, 'car'))
                color_rgb = label_to_color_rgb.get(label, (128, 128, 128))
                pen = QPen(QColor(*color_rgb), 2)
                painter.setPen(pen)
                rx = round(x1 * x_scale)
                ry = round(y1 * y_scale)
                rw = round((x2 - x1) * x_scale)
                rh = round((y2 - y1) * y_scale)
                painter.drawRect(rx, ry, rw, rh)
                # Centroide con borde blanco
                cx = round((x1 + x2) / 2 * x_scale)
                cy = round((y1 + y2) / 2 * y_scale)
                painter.setPen(QPen(QColor(*color_rgb), 4))
                painter.drawEllipse(QPointF(cx, cy), 3, 3)
                # OPT-10: Usar pen precreado
                painter.setPen(self.white_pen)
                painter.drawEllipse(QPointF(cx, cy), 4, 4)
                # Texto label + id sobre fondo del color de la clase
                try:
                    text = f"{label} ID:{box.id}"
                except Exception:
                    text = str(label)
                fm = QFontMetrics(painter.font())
                try:
                    text_w = fm.width(text)
                except Exception:
                    text_w = fm.horizontalAdvance(text)
                text_h = fm.height()
                bg_w = text_w + 10
                bg_h = text_h + 6
                bg_x = rx
                bg_y = max(0, ry - bg_h - 2)
                painter.fillRect(bg_x, bg_y, bg_w, bg_h, QColor(color_rgb[0], color_rgb[1], color_rgb[2], 200))
                # OPT-10: Usar pen precreado
                painter.setPen(self.white_pen)
                painter.drawText(QPointF(bg_x + 5, bg_y + text_h), text)

                # Detección de giros
                if len(self.track_history.get(box.id, [])) >= 2:
                    for counting_line in self.counting_lines:
                        if LineString(self.track_history[box.id][-2:]).intersects(
                            self.cached_counting_lines_shapely.get(counting_line.id)
                        ):
                            
                            # Registrar que el vehículo cruzó la línea de conteo
                            if box.id not in self.vehicle_states:
                                self.vehicle_states[box.id] = []
                            self.vehicle_states[box.id].append({
                                "counting_line": counting_line.id,  # ID de la línea de origen
                                "frame": self.video_player.frame_number,
                            })

                            if len(self.vehicle_states[box.id]) > 1:
                                for movement in self.movements:
                                    origin_candidates = [state['counting_line'] for state in self.vehicle_states[box.id][:-1]]
                                    # destination_candidates = [state['counting_line'] for state in self.vehicle_states[box.id][1:]]
                                    # Verificar si el movimiento está registrado
                                    if movement['o'] in origin_candidates and movement['d'] == counting_line.id:
                                        vehicle_type = self.types_dict[box.road_user_type]
                                        origin_frame = self.vehicle_states[box.id][0]["frame"]
                                        destination_frame = self.vehicle_states[box.id][-1]["frame"]

                                        # Feedback visual
                                        start = QPointF(counting_line.start.x() * x_scale, counting_line.start.y() * y_scale)
                                        end = QPointF(counting_line.end.x() * x_scale, counting_line.end.y() * y_scale)
                                        startText = QPointF(start.x() - 15, start.y() - 15)
                                        endText = QPointF(end.x() + 15, end.y() + 15)
                                        feedback_pen = QPen(Qt.white, 4)
                                        painter.setPen(feedback_pen)
                                        painter.drawLine(start, end)

                                        # Guardar crop de cruce O/D si está habilitado
                                        if self.ui.actionSaveMovementCrops.isChecked() and self.crop_manager is not None:
                                            crossing_data = {
                                                'object_id': box.id,
                                                'class_name': vehicle_type,
                                                'confidence': 1.0,  # Confidence alta ya que pasó por ambas líneas
                                                'bbox': [x1, y1, x2, y2],
                                                'origin_frame': origin_frame,
                                                'destination_frame': destination_frame,
                                                'origin_line': movement['o'],
                                                'destination_line': movement['d'],
                                                'turn_name': movement['id']
                                            }
                                            self.crop_manager.save_od_crossing_crop(frame, crossing_data)
                                        
                                        # Registrar conteo
                                        self.counts[movement['id']][vehicle_type] += 1
                                        print(f"Vehículo contado: {box.id} ({vehicle_type}) cruzó de {movement['o']} a {movement['d']}")
                                        # print("Conteo actual:", self.counts)
                                        self.save_vehicle_count(movement['id'], f'{movement["o"]}-{movement["d"]}', vehicle_type, origin_frame, destination_frame)

                                        # Eliminar el estado del vehículo para evitar conteos duplicados
                                        self.vehicle_states[box.id] = []
                                        break  # Salir del bucle de movimientos una vez contado

            # Dibujar trayectorias recientes para tracks activos
            active_ids = set(current_labels.keys())
            for tid in active_ids:
                points = self.track_history.get(tid, [])
                if len(points) < 2:
                    continue
                label = current_labels.get(tid, 'car')
                color_rgb = label_to_color_rgb.get(label, (128, 128, 128))
                painter.setPen(QPen(QColor(*color_rgb), 1))
                # Escalar y dibujar polyline
                prev = None
                for (px, py) in points:
                    qx = px * x_scale
                    qy = py * y_scale
                    if prev is not None:
                        painter.drawLine(QPointF(prev[0], prev[1]), QPointF(qx, qy))
                    prev = (qx, qy)
                # Punto final destacado
                last_px, last_py = points[-1]
                painter.setPen(QPen(QColor(*color_rgb), 3))
                painter.drawEllipse(QPointF(last_px * x_scale, last_py * y_scale), 2, 2)

            # Dibujar polígonos ROI (áreas de detección)
            if self.ui.actionShowROI.isChecked():
                painter.setPen(self.roi_pen)
                # Dibujar polígonos completados
                for poly_points in self.roi_polygons:
                    if len(poly_points) >= 3:
                        scaled_points = [QPointF(p[0] * x_scale, p[1] * y_scale) for p in poly_points]
                        # Dibujar líneas del polígono
                        for i in range(len(scaled_points)):
                            painter.drawLine(scaled_points[i], scaled_points[(i + 1) % len(scaled_points)])
                        # Rellenar polígono con color semi-transparente
                        painter.setBrush(QColor(255, 165, 0, 30))
                        painter.drawPolygon(QPolygonF(scaled_points))
                        painter.setBrush(Qt.NoBrush)

                # Dibujar polígono en construcción
                if self.drawing_roi and len(self.current_roi_points) > 0:
                    painter.setPen(QPen(QColor(255, 255, 0), 3))  # Amarillo para polígono en construcción
                    scaled_current = [QPointF(p[0] * x_scale, p[1] * y_scale) for p in self.current_roi_points]

                    # Dibujar líneas entre puntos consecutivos
                    for i in range(len(scaled_current) - 1):
                        painter.drawLine(scaled_current[i], scaled_current[i + 1])

                    # Si hay 3 o más puntos, dibujar línea de cierre punteada
                    if len(scaled_current) >= 3:
                        closing_pen = QPen(QColor(0, 255, 0), 2)  # Verde para línea de cierre
                        closing_pen.setStyle(Qt.DashLine)
                        painter.setPen(closing_pen)
                        painter.drawLine(scaled_current[-1], scaled_current[0])
                        painter.setPen(QPen(QColor(255, 255, 0), 3))  # Volver a amarillo

                    # Dibujar puntos
                    for i, point in enumerate(scaled_current):
                        # Primer punto más grande para indicar inicio
                        if i == 0:
                            painter.setBrush(QColor(0, 255, 0))  # Verde para primer punto
                            painter.drawEllipse(point, 7, 7)
                            painter.setBrush(Qt.NoBrush)
                        else:
                            painter.drawEllipse(point, 5, 5)

            painter.end()

        if self.ui.actionDetectMovement.isChecked():
            self.detect_movement(frame)

        # Actualizar barra de progreso
        current_frame = getattr(self.video_player, 'frame_number', 0)
        self.ui.progressBar.setValue(current_frame)
        
        # Check if video processing is complete and show message
        # try:
        #     total_frames = int(self.video_player.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        #     if current_frame >= total_frames:
        #         QMessageBox.information(self, "Procesamiento Completo", "El video ha sido procesado completamente.")
        # except Exception:
        #     # If we can't get the total frame count, skip the check
        #     pass
            
        if self.ui.actionHeadless.isChecked():
            if not getattr(self, 'headless_first_shown', False):
                self.ui.videoLabel.setPixmap(scaled_pixmap)
                self.headless_first_shown = True

            # Actualizar barra de progreso y UI solo cada headless_update_interval frames
            if current_frame % self.headless_update_interval == 0:
                self.ui.progressBar.setValue(current_frame)
                QApplication.processEvents()
        else:
            # MODO NORMAL: Mostrar cada frame
            self.ui.progressBar.setValue(current_frame)
            self.ui.videoLabel.setPixmap(scaled_pixmap)

    def redraw_current_frame(self):
        """
        Actualizar el fotograma, líneas de conteo y cajas de detección.
        """
        frame = self.video_player.draw_frame(self.video_player.frame_number)
        if frame is not None:
            # Mostrar el fotograma
            self.display_frame(frame)

    def save_vehicle_count(self, movement, direction, vehicle_type, origin_frame, destination_frame):
        """
        TODO
        """
        try:
            conexion = sqlite3.connect(os.path.join(os.path.split(VIDEO_PATH)[0], 'Conteos.db'))
            cursor = conexion.cursor()

            # Crear tabla si no existe
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS VehicleCounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    movement TEXT,
                    direction TEXT,
                    vehicle_type TEXT,
                    origin_frame INTEGER,
                    destination_frame INTEGER,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Insertar los datos
            cursor.execute("""
                INSERT INTO VehicleCounts (movement, direction, vehicle_type, origin_frame, destination_frame)
                VALUES (?, ?, ?, ?, ?)
            """, (movement, direction, vehicle_type, origin_frame, destination_frame))

            # Confirmar los cambios
            conexion.commit()
            conexion.close()
    
        except Exception as e:
            QErrorMessage(self).showMessage(f"Error al guardar en la base de datos: {e}")

    def get_counting_line_by_id(self, id):
        """
        TODO
        """
        for line in self.counting_lines:
            if line.id == id:
                return line
        return None

    def _update_line_cache(self):
        """
        OPT-6: Actualizar cache de LineStrings para líneas de conteo
        """
        self.cached_counting_lines_shapely = {
            line.id: LineString([(line.start.x(), line.start.y()),
                                (line.end.x(), line.end.y())])
            for line in self.counting_lines
        }

    # === Métodos para controles de stride ===
    def on_stride_active_changed(self, value):
        """Actualizar stride activo desde UI"""
        self.detection_stride_active = value
        print(f"[CONFIG] Stride activo cambiado a: {value}")

    def on_stride_inactive_changed(self, value):
        """Actualizar stride inactivo desde UI"""
        self.detection_stride_inactive = value
        print(f"[CONFIG] Stride inactivo cambiado a: {value} (AVANCE RÁPIDO)")

    def on_stride_threshold_changed(self, value):
        """Actualizar threshold de cambio desde UI"""
        self.adaptive_stride_threshold = value
        print(f"[CONFIG] Threshold de cambio a stride rápido: {value} frames")

    def open_stride_config(self):
        """Abrir diálogo de configuración de velocidad/stride"""
        try:
            from ui.stride_config_dialog import StrideConfigDialog
            dialog = StrideConfigDialog(self)
            if dialog.exec_() == QDialog.Accepted:
                values = dialog.get_values()
                self.detection_stride_active = values['stride_active']
                self.detection_stride_inactive = values['stride_inactive']
                self.adaptive_stride_threshold = values['threshold']
                print(f"[CONFIG] Nueva configuración de stride:")
                print(f"  - Con actividad: cada {values['stride_active']} frames")
                print(f"  - Sin actividad: cada {values['stride_inactive']} frames (RÁPIDO)")
                print(f"  - Acelerar después de: {values['threshold']} frames sin detección")
                QMessageBox.information(self, "Configuración Guardada",
                                       f"Nueva configuración aplicada:\n"
                                       f"• Stride con actividad: {values['stride_active']}\n"
                                       f"• Stride sin actividad: {values['stride_inactive']}\n"
                                       f"• Threshold: {values['threshold']} frames")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error abriendo configuración: {e}")

    # === Métodos para sistema de máscaras/ROI ===
    def toggle_draw_roi(self):
        """Activar/desactivar modo de dibujo de ROI"""
        self.drawing_roi = not self.drawing_roi
        if self.drawing_roi:
            self.current_roi_points = []
            QMessageBox.information(self, "Dibujar ROI",
                                   "Haz clic en el video para definir los puntos del polígono ROI.\n\n"
                                   "CLIC IZQUIERDO: Agregar punto\n"
                                   "CLIC DERECHO o ESC: Finalizar polígono (mínimo 3 puntos)\n\n"
                                   "Solo se detectarán vehículos dentro de las áreas ROI.\n"
                                   "Esto optimiza el rendimiento procesando solo la zona de interés.")
            print("[ROI] Modo de dibujo ACTIVADO - Haz clic para agregar puntos")
            self.ui.statusBar.showMessage("MODO ROI: Clic izquierdo para agregar puntos | Clic derecho o ESC para finalizar")
        else:
            if len(self.current_roi_points) >= 3:
                self.roi_polygons.append(self.current_roi_points.copy())
                self._update_detection_mask()
                print(f"[ROI] Polígono guardado con {len(self.current_roi_points)} puntos")
                self.ui.statusBar.showMessage(f"Polígono ROI guardado con {len(self.current_roi_points)} puntos - Total: {len(self.roi_polygons)} áreas", 3000)
                QMessageBox.information(self, "ROI Guardado",
                                       f"Polígono guardado correctamente.\n\n"
                                       f"Puntos: {len(self.current_roi_points)}\n"
                                       f"Total de áreas ROI: {len(self.roi_polygons)}\n\n"
                                       f"YOLO ahora solo procesará dentro de las áreas definidas.\n"
                                       f"Esto reduce significativamente el tiempo de procesamiento.")
            elif len(self.current_roi_points) > 0:
                print(f"[ROI] Polígono descartado - Necesita mínimo 3 puntos (tiene {len(self.current_roi_points)})")
                self.ui.statusBar.showMessage(f"Polígono descartado - Necesita mínimo 3 puntos", 2000)
            else:
                self.ui.statusBar.showMessage("Modo ROI desactivado", 2000)
            self.current_roi_points = []
            self.redraw_current_frame()

    def clear_roi(self):
        """Limpiar todas las máscaras ROI"""
        reply = QMessageBox.question(self, "Limpiar ROI",
                                     "¿Eliminar todas las áreas ROI?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.roi_polygons = []
            self.detection_mask = None
            self.current_roi_points = []
            self.drawing_roi = False
            self._update_detection_mask()
            self.redraw_current_frame()
            print("[ROI] Todas las áreas ROI han sido eliminadas")

    def _update_detection_mask(self):
        """Calcular bounding box rectangular del ROI para crop eficiente"""
        if not self.roi_polygons or not hasattr(self, 'video_player') or not self.video_player:
            self.detection_mask = None
            self.roi_bbox = None
            return

        # Calcular bounding box rectangular que engloba todos los polígonos ROI
        all_points = []
        for poly_points in self.roi_polygons:
            all_points.extend(poly_points)

        all_points = np.array(all_points)
        x_min = int(np.min(all_points[:, 0]))
        y_min = int(np.min(all_points[:, 1]))
        x_max = int(np.max(all_points[:, 0]))
        y_max = int(np.max(all_points[:, 1]))

        # Asegurar que los límites estén dentro del frame
        height, width = self.video_player.original_size[1], self.video_player.original_size[0]
        x_min = max(0, x_min)
        y_min = max(0, y_min)
        x_max = min(width, x_max)
        y_max = min(height, y_max)

        self.roi_bbox = (x_min, y_min, x_max, y_max)

        # Crear máscara para visualización (opcional, solo para dibujar)
        mask = np.zeros((height, width), dtype=np.uint8)
        for poly_points in self.roi_polygons:
            if len(poly_points) >= 3:
                points = np.array(poly_points, dtype=np.int32)
                cv2.fillPoly(mask, [points], 255)
        self.detection_mask = mask

        roi_width = x_max - x_min
        roi_height = y_max - y_min
        roi_area_percent = (roi_width * roi_height) / (width * height) * 100

        print(f"[ROI] Bounding box calculado: ({x_min}, {y_min}) -> ({x_max}, {y_max})")
        print(f"[ROI] Área ROI: {roi_width}x{roi_height} ({roi_area_percent:.1f}% del frame)")
        print(f"[ROI] YOLO procesará solo esta región (más rápido)")

    def apply_detection_mask(self, frame):
        """
        Extraer región ROI del frame para procesamiento eficiente.

        En lugar de aplicar máscara al frame completo, hace crop de la región ROI.
        YOLO procesa solo el crop (más rápido).

        Returns:
            tuple: (frame_procesado, offset_x, offset_y)
                   Si no hay ROI: (frame_original, 0, 0)
                   Si hay ROI: (crop_roi, x_min, y_min)
        """
        if self.roi_bbox is None:
            # Sin ROI: procesar frame completo
            return frame, 0, 0

        # Con ROI: extraer solo la región rectangular
        x_min, y_min, x_max, y_max = self.roi_bbox
        roi_crop = frame[y_min:y_max, x_min:x_max].copy()

        return roi_crop, x_min, y_min

    def generate_report(self):
        # Seleccionar dónde guardar el reporte
        db_path, _ = QFileDialog.getOpenFileName(self, "Seleccionar base de datos", "", "Archivos SQLite (*.sqlite *.db)")

        if not db_path:
            QErrorMessage(self).showMessage("No se seleccionó una base de datos.")
            return

        try:
            generate_excel_report(db_path)
        except Exception as e:
            logging.error(f"Fallo en la generación del reporte: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Error al generar reporte: {str(e)}")
            return
            
        # Cerrar todos los handlers de logging para liberar archivos
        for handler in logging.root.handlers[:]:
            handler.close()
            logging.root.removeHandler(handler)
        
        # Generar gráfico para cada tipo de vehículo
        # buffer_grafico = self.generar_grafico_tipos_apilados(tiempos, conteo_por_tipo)

        QMessageBox.information(self, "Éxito", "Reporte generado correctamente.")

    # def get_vehicle_types(self):
    #     """
    #     TODO
    #     """
    #     conn = sqlite3.connect(
    #         os.path.join(
    #             os.path.split(self.video_player.video_path)[0], #Folder
    #             'Conteos.db'
    #         )
    #     )
    #     cursor = conn.cursor()
    
    #     # Obtener los tipos de vehículos desde la tabla de objetos o desde donde se almacenen
    #     cursor.execute("SELECT DISTINCT vehicle_type FROM VehicleCounts")
    #     tipos = [row[0] for row in cursor.fetchall()]  # Lista con los tipos de vehículos
    
    #     conn.close()
    #     return tipos

    # def get_video_start_time(self):
    #     """
    #     TODO
    #     """
    #     # Conectar a la base de datos
    #     conn = sqlite3.connect(
    #         os.path.join(
    #             os.path.split(self.video_player.video_path)[0], #Folder
    #             'Conteos.db'
    #         )
    #     )
    #     cursor = conn.cursor()
    
    #     # Consulta para obtener la fecha y hora de inicio desde la tabla GlobalData
    #     cursor.execute("SELECT fecha_conteo, hora_inicio FROM GlobalData ORDER BY id DESC LIMIT 1")
    #     resultado = cursor.fetchone()
        
    #     if resultado:
    #         fecha_conteo, hora_inicio = resultado  # Suponiendo formato 'yyyy-mm-dd' para fecha y 'HH:mm:ss' para hora
    #     else:
    #         # En caso de que no haya datos en la tabla GlobalData
    #         QMessageBox.critical(self, "Error", "No se encontró la hora de inicio en la base de datos.")
    #         return None
    
    #     # Cerrar la conexión
    #     conn.close()
    
    #     # Combinar la fecha y hora en un solo objeto datetime
    #     hora_inicio_datetime = datetime.strptime(f"{fecha_conteo} {hora_inicio}", "%Y-%m-%d %H:%M")
    #     return hora_inicio_datetime
    
    # def generar_grafico_tipos_apilados(self, tiempos, conteos_por_tipo):
    #     """
    #     TODO
    #     """
    #     plt.figure(figsize=(8, 4), dpi=200)
    
    #     # Convertir los datos a formato compatible con barras apiladas
    #     labels = tiempos
    #     bottom = np.zeros(len(tiempos))
    
    #     # Generar barras apiladas para cada tipo de vehículo
    #     for tipo, conteos in conteos_por_tipo.items():
    #         plt.bar(labels, conteos, bottom=bottom, label=tipo)
    #         bottom += np.array(conteos)
    
    #     plt.xlabel('Horario')
    #     plt.ylabel('Número de Vehículos')
    #     plt.title('Conteo de Vehículos por Tipo (Barras Apiladas)')
    #     plt.xticks(rotation=90)  # Rotar las etiquetas de horas a vertical
    #     plt.legend()
    
    #     # Guardar el gráfico en un buffer
    #     buffer = BytesIO()
    #     plt.savefig(buffer, format='png', bbox_inches='tight')
    #     buffer.seek(0)
    #     plt.close()
    
    #     return buffer
    
    # def crear_encabezado(self, canvas, doc):
    #     """
    #     TODO
    #     """
    #     # Conectar a la base de datos para obtener la información global
    #     conn = sqlite3.connect(
    #         os.path.join(
    #             os.path.split(self.video_player.video_path)[0], #Folder
    #             'Conteos.db'
    #         )
    #     )
    #     cursor = conn.cursor()
    
    #     # Obtener la fecha, hora de inicio, ciudad e intersección desde la tabla GlobalData
    #     cursor.execute("SELECT fecha_conteo, hora_inicio, ciudad, interseccion FROM GlobalData ORDER BY id DESC LIMIT 1")
    #     resultado = cursor.fetchone()
    
    #     if resultado:
    #         fecha_conteo, hora_inicio, ciudad, interseccion = resultado
    #     else:
    #         # Si no se encuentra la información, utilizar valores predeterminados
    #         fecha_conteo = "Fecha no disponible"
    #         hora_inicio = "00:00"
    #         ciudad = "Ciudad no disponible"
    #         interseccion = "Intersección no disponible"
    
    #     conn.close()
    
    #     # Combinar fecha y hora de inicio en un solo string
    #     fecha_hora_inicio = f"{fecha_conteo} {hora_inicio}"
    
    #     # Definir los datos del encabezado
    #     encabezado = [
    #         ["", "Reporte de Conteo de Vehículos", ""],
    #         ["Fecha:", fecha_conteo, ""],
    #         ["Hora de Inicio:", hora_inicio, ""],
    #         ["Ubicación:", ciudad, ""],
    #         ["Intersección:", interseccion, ""]
    #     ]
    
    #     # Configurar los estilos de la tabla del encabezado
    #     tabla_encabezado = Table(encabezado, colWidths=[2.5 * inch, 2 * inch, 2 * inch])
    #     estilo_encabezado = TableStyle([
    #         ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
    #         ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
    #         ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
    #         ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
    #         ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    #         ('FONTSIZE', (0, 0), (-1, -1), 12),
    #         ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    #         ('TOPPADDING', (0, 0), (-1, -1), 4),
    #     ])
    #     tabla_encabezado.setStyle(estilo_encabezado)
    
    #     # Dibujar el encabezado en cada página
    #     tabla_encabezado.wrapOn(canvas, doc.width, doc.topMargin)
    #     tabla_encabezado.drawOn(canvas, doc.leftMargin, doc.height + doc.topMargin - 100)
    
    def detect_movement(self, frame):
        """
        TODO
        """
        # Preprocesar el frame
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) # Escala de grises
        blurred = cv2.GaussianBlur(gray, (5, 5), 0) # Desenfoque gaussiano para reducir ruido

        # Aplicar sustracción de fondo
        fg_mask = self.movement_detector.bg_subtractor.apply(blurred)
        fg_mask[fg_mask == 127] = 0 # Remover sombras (valor 127 en MOG2)

        # Operaciones morfológicas para limpiar la máscara
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, self.movement_detector.kernel_close)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, self.movement_detector.kernel_open)

        # Encontrar contornos
        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Filtrar contornos con áreas definidas para un vehículo
        vehicle_contours = [contour for contour in contours if self.movement_detector.min_area <= cv2.contourArea(contour) <= self.movement_detector.max_area]
        if vehicle_contours and not self.yolo_active:
            self.yolo_active = True
            self.shutdown_counter = 0
        elif not vehicle_contours and self.yolo_active:
            self.shutdown_counter += 1
            if self.shutdown_counter >= 30:
                self.yolo_active = False

class GlobalInfo(QDialog):
    """
    TODO
    
    Métodos
    -------
    create_table_if_not_exists(cursor)
        TODO
    save_info()
        TODO
    """
    def __init__(self):
        super(GlobalInfo, self).__init__()
        self.ui = Ui_GlobalInfo()
        self.ui.setupUi(self)
    
        # Conectar el botón OK para que guarde la información en la base de datos
        self.ui.buttonBox.accepted.connect(self.save_info)

    def create_table_if_not_exists(self, cursor):
        """
        TODO
        """
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS GlobalData (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha_conteo TEXT,
                hora_inicio TEXT,
                interseccion TEXT,
                ciudad TEXT
            )
        """)

    def save_info(self):
        """
        TODO
        """
        # Obtener los valores de los widgets
        fecha_conteo = self.ui.dateEdit.date().toString("yyyy-MM-dd")
        hora_inicio = self.ui.timeEdit.time().toString("HH:mm")
        interseccion = self.ui.infoIntersection.text()
        ciudad = self.ui.infoIntersection_3.text()

        # Validar que los campos no estén vacíos
        if not interseccion or not ciudad:
            QMessageBox.warning(self, "Campos incompletos", "Por favor, rellena todos los campos antes de continuar.")
            return

        # Conectar a la base de datos y crear la tabla si no existe
        try:
            conexion = sqlite3.connect(
                os.path.join(
                    os.path.split(VIDEO_PATH)[0], #Folder
                    'Conteos.db'
                )
            )
            #conexion = sqlite3.connect('base_de_datos.db')  # Especifica la ruta a tu base de datos
            cursor = conexion.cursor()

            # Crear la tabla si no existe
            self.create_table_if_not_exists(cursor)

            # Insertar los datos en la tabla
            cursor.execute("""
                INSERT INTO GlobalData (fecha_conteo, hora_inicio, interseccion, ciudad)
                VALUES (?, ?, ?, ?)
            """, (fecha_conteo, hora_inicio, interseccion, ciudad))

            # Confirmar los cambios
            conexion.commit()
            conexion.close()

            QMessageBox.information(self, "Guardado", "La información se ha guardado correctamente.")
            self.accept()  # Cierra el diálogo si se guarda correctamente

        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar la información: {str(e)}")

class WelcomeDialog(QDialog):
    """
    Ventana de bienvenida de FlowVisionAI.

    Métodos
    -------
    new_project()
        Abrir la ventana de información para crear un proyecto nuevo.
    open_project()
        Abrir un proyecto existente.
    """
    def __init__(self):
        super(WelcomeDialog, self).__init__()
        self.ui = Ui_welcomeWindow()
        self.ui.setupUi(self)

        # Conectar botones
        self.ui.newProjectButton.clicked.connect(self.new_project)
        self.ui.openProjectButton.clicked.connect(self.open_project)

    def new_project(self):
        """
        TODO
        """
        global VIDEO_PATH
        VIDEO_PATH, _ = QFileDialog.getOpenFileName(self, "Seleccionar video", "", "Archivos de video (*.mp4 *.avi *.mov *.dav)")
        if VIDEO_PATH:
            annotator = AnnotatorApp()
            welcome.accept()
            annotator.show()

    def open_project(self):
        """
        Abrir un proyecto existente.
        """
        path, _ = QFileDialog.getOpenFileName(self, 'Cargar Configuración', '', 'JSON (*.json)')
        if path:
            global VIDEO_PATH
            with open(path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            VIDEO_PATH = cfg.get('video', {}).get('path', None)
            welcome.accept()
            annotator = AnnotatorApp(cfg)
            annotator.show()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Iniciar directamente la aplicación (sin cargar video ni configuraciones)
    annotator = AnnotatorApp()
    annotator.show()
    sys.exit(app.exec_())