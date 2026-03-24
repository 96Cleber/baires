"""
Diálogo de galería para clasificación manual rápida de crops
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                            QPushButton, QComboBox, QScrollArea, QWidget,
                            QMessageBox, QProgressBar, QGroupBox, QCheckBox,
                            QGridLayout, QFrame, QSplitter, QTabWidget,
                            QInputDialog, QLineEdit, QToolTip, QErrorMessage,
                            QApplication)
from PyQt5.QtGui import QPixmap, QFont, QPainter, QPen, QColor, QCursor
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QRect, QSize, QTimer
import os
import sys
from pathlib import Path
from typing import List, Dict, Optional
from collections import defaultdict

# Importar módulo de tipologías centralizado
def _get_tools_path():
    if hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(__file__))

sys.path.insert(0, _get_tools_path())
from tools.typologies import (
    get_cached_folder_to_tipologia,
    get_cached_tipologia_to_folder,
    get_cached_folder_classes
)


class ThumbnailLabel(QLabel):
    """Label personalizado para miniaturas con funcionalidad de click"""

    clicked = pyqtSignal(str, dict, object)  # crop_filename, crop_data, QMouseEvent

    def __init__(self, crop_data: dict, crop_path: Path, thumbnail_size=180, pixmap_cache=None):
        super().__init__()
        self.crop_data = crop_data
        self.crop_path = crop_path
        self.thumbnail_size = thumbnail_size
        self.is_selected = False
        self._cached_pixmap = pixmap_cache  # Pixmap precargado

        self.setFixedSize(thumbnail_size, thumbnail_size)
        self.setStyleSheet("""
            QLabel {
                border: 2px solid #cccccc;
                border-radius: 5px;
                background-color: white;
                padding: 2px;
            }
            QLabel:hover {
                border-color: #0078d4;
                background-color: #f0f8ff;
            }
        """)
        self.setAlignment(Qt.AlignCenter)
        self.setScaledContents(True)
        self.setCursor(QCursor(Qt.PointingHandCursor))

        self.load_thumbnail()
        self.setToolTip(self.create_tooltip())

    def load_thumbnail(self):
        """Cargar y mostrar la miniatura (usa cache si está disponible)"""
        # Usar pixmap cacheado si existe
        if self._cached_pixmap is not None:
            self.setPixmap(self._cached_pixmap)
            return

        # Cargar desde disco si no hay cache
        if self.crop_path.exists():
            pixmap = QPixmap(str(self.crop_path))
            if not pixmap.isNull():
                # Escalar manteniendo aspecto
                scaled_pixmap = pixmap.scaled(
                    self.thumbnail_size - 10,
                    self.thumbnail_size - 10,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.setPixmap(scaled_pixmap)
            else:
                self.setText("Error")
        else:
            self.setText("No encontrado")
    
    def create_tooltip(self):
        """Crear tooltip informativo"""
        crop_data = self.crop_data
        
        try:
            filename = crop_data.get('filename', 'N/A')
            class_name = crop_data.get('class', 'N/A')
            crop_type = crop_data.get('type', 'N/A')
            
            tooltip = f"""
            Archivo: {filename}
            Clase Actual: {class_name}
            Tipo: {crop_type}
            """
                
            return tooltip.strip()
        except Exception:
            return "Error cargando información del crop"
    
    def mousePressEvent(self, event):
        """Manejar click en miniatura con soporte para modificadores Shift/Ctrl"""
        if event.button() == Qt.LeftButton:
            filename = self.crop_data.get('filename', self.crop_data.get('crop_filename', 'unknown'))
            # Emitir el evento completo para acceder a los modificadores
            self.clicked.emit(filename, self.crop_data, event)
        super().mousePressEvent(event)
    
    def set_selected(self, selected: bool):
        """Marcar miniatura como seleccionada"""
        self.is_selected = selected
        if selected:
            self.setStyleSheet("""
                QLabel {
                    border: 3px solid #0078d4;
                    border-radius: 5px;
                    background-color: #e6f3ff;
                    padding: 2px;
                }
            """)
        else:
            self.setStyleSheet("""
                QLabel {
                    border: 2px solid #cccccc;
                    border-radius: 5px;
                    background-color: white;
                    padding: 2px;
                }
                QLabel:hover {
                    border-color: #0078d4;
                    background-color: #f0f8ff;
                }
            """)
    
    def update_classification_visual(self):
        """Actualizar visualización basada en clasificación"""
        # Actualizar tooltip
        self.setToolTip(self.create_tooltip())


class ClassGroupWidget(QWidget):
    """Widget que agrupa miniaturas por clase"""
    
    image_selected = pyqtSignal(str, dict)  # crop_filename, crop_data
    classification_changed = pyqtSignal(str, str, dict)  # crop_filename, new_class, crop_data
    
    def __init__(self, class_name: str, crops: List[dict], crop_manager, parent=None):
        super().__init__(parent)
        self.class_name = class_name
        self.crops = crops
        self.crop_manager = crop_manager
        self.thumbnail_widgets = {}
        self.selected_thumbnail = None
        # Clases cargadas dinámicamente desde el módulo centralizado
        self.available_classes = get_cached_folder_classes()

        self.init_ui()
    
    def init_ui(self):
        """Inicializar interfaz del grupo"""
        layout = QVBoxLayout()
        layout.setSpacing(10)
        
        # Encabezado de clase
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 8px;
                margin: 4px;
            }
        """)
        
        header_layout = QHBoxLayout()
        
        # Mapeo de clases a español (cargado dinámicamente)
        class_labels = get_cached_folder_to_tipologia()

        if self.class_name:
            display_name = class_labels.get(self.class_name, self.class_name.title())
        else:
            display_name = 'Sin Clasificar'
        
        # Título de la clase
        title_label = QLabel(f"{display_name} ({len(self.crops)} imágenes)")
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        
        # Combo para reclasificar todas
        self.reclassify_combo = QComboBox()
        self.reclassify_combo.addItem("Reclasificar todas como...")
        for cls in self.available_classes:
            if cls != self.class_name:
                self.reclassify_combo.addItem(class_labels.get(cls, cls.title()))
        
        self.reclassify_combo.currentTextChanged.connect(self.reclassify_all)
        
        # Checkbox para expandir/colapsar
        self.expand_checkbox = QCheckBox("Mostrar miniaturas")
        self.expand_checkbox.setChecked(True)
        self.expand_checkbox.toggled.connect(self.toggle_thumbnails)
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.reclassify_combo)
        header_layout.addWidget(self.expand_checkbox)
        
        header_frame.setLayout(header_layout)
        layout.addWidget(header_frame)
        
        # Área de miniaturas con scroll
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setMaximumHeight(400)
        
        # Widget contenedor de miniaturas
        self.thumbnails_widget = QWidget()
        self.thumbnails_layout = QGridLayout()
        self.thumbnails_layout.setSpacing(5)
        
        self.load_thumbnails()
        
        self.thumbnails_widget.setLayout(self.thumbnails_layout)
        self.scroll_area.setWidget(self.thumbnails_widget)
        
        layout.addWidget(self.scroll_area)
        self.setLayout(layout)
    
    def load_thumbnails(self):
        """Cargar todas las miniaturas del grupo"""
        cols = 6  # Número de columnas
        
        for i, crop_data in enumerate(self.crops):
            crop_filename = crop_data['crop_filename']
            
            # Determinar directorio según el tipo de crop
            if crop_filename.startswith('all_'):
                crop_dir = self.crop_manager.all_crops_dir
            else:
                crop_dir = self.crop_manager.od_crops_dir
            
            # Buscar archivo en subdirectorios de clases
            crop_path = None
            for class_dir in crop_dir.iterdir():
                if class_dir.is_dir():
                    potential_path = class_dir / crop_filename
                    if potential_path.exists():
                        crop_path = potential_path
                        break
            
            if crop_path:
                thumbnail = ThumbnailLabel(crop_data, crop_path)
                thumbnail.clicked.connect(self.on_thumbnail_clicked)
                
                row = i // cols
                col = i % cols
                self.thumbnails_layout.addWidget(thumbnail, row, col)
                
                self.thumbnail_widgets[crop_filename] = thumbnail
    
    def on_thumbnail_clicked(self, crop_filename: str, crop_data: dict, event=None):
        """Manejar click en miniatura"""
        # Deseleccionar miniatura anterior
        if self.selected_thumbnail:
            self.selected_thumbnail.set_selected(False)

        # Seleccionar nueva miniatura
        thumbnail = self.thumbnail_widgets.get(crop_filename)
        if thumbnail:
            thumbnail.set_selected(True)
            self.selected_thumbnail = thumbnail

            # Mostrar menú contextual para reclasificar
            self.show_reclassify_menu(thumbnail, crop_data)
        
        self.image_selected.emit(crop_filename, crop_data)
    
    def show_reclassify_menu(self, thumbnail: ThumbnailLabel, crop_data: dict):
        """Mostrar menú de reclasificación"""
        from PyQt5.QtWidgets import QMenu, QAction

        menu = QMenu(self)

        # Mapeo de clases a español (cargado dinámicamente)
        class_labels = get_cached_folder_to_tipologia()

        # Agregar acciones para cada clase
        for class_name in self.available_classes:
            display_name = class_labels.get(class_name, class_name.title())
            
            action = QAction(display_name, self)
            action.triggered.connect(
                lambda checked, cn=class_name: self.reclassify_single(crop_data, cn)
            )
            
            # Marcar la clase actual
            current_class = crop_data.get('manual_classification', crop_data['detection_class'])
            if class_name == current_class:
                action.setCheckable(True)
                action.setChecked(True)
            
            menu.addAction(action)
        
        # Mostrar menú en la posición del cursor
        menu.exec_(QCursor.pos())
    
    def reclassify_single(self, crop_data: dict, new_class: str):
        """Reclasificar una sola imagen"""
        crop_filename = crop_data['crop_filename']
        
        # Actualizar datos
        crop_data['manual_classification'] = new_class
        
        # Actualizar visualización
        thumbnail = self.thumbnail_widgets.get(crop_filename)
        if thumbnail:
            thumbnail.update_classification_visual()
        
        self.classification_changed.emit(crop_filename, new_class, crop_data)
    
    def reclassify_all(self, selected_text: str):
        """Reclasificar todas las imágenes del grupo"""
        if selected_text == "Reclasificar todas como...":
            return

        # Mapeo inverso: español display -> nombre carpeta (cargado dinámicamente)
        class_labels = get_cached_tipologia_to_folder()

        new_class = class_labels.get(selected_text)
        if not new_class:
            return
        
        # Confirmar acción
        reply = QMessageBox.question(
            self, 
            'Confirmar Reclasificación',
            f'¿Reclasificar todas las {len(self.crops)} imágenes como {selected_text}?',
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            for crop_data in self.crops:
                self.reclassify_single(crop_data, new_class)
        
        # Resetear combo
        self.reclassify_combo.setCurrentIndex(0)
    
    def toggle_thumbnails(self, checked: bool):
        """Mostrar/ocultar miniaturas"""
        self.scroll_area.setVisible(checked)
        
        if checked:
            self.setMaximumHeight(600)
        else:
            self.setMaximumHeight(80)


class ClassificationGalleryDialog(QDialog):
    """Diálogo de galería para clasificación manual rápida"""
    # TODO: Chequear como afecta acá las tipologías adicionales
    def __init__(self, crop_manager=None, default_typologies=None, additional_typologies=None,
                 parent=None, crop_folders=None):
        """
        Args:
            crop_manager: CropManager individual (modo tradicional)
            default_typologies: Lista de tipologías por defecto
            additional_typologies: Lista de tipologías adicionales
            parent: Widget padre
            crop_folders: Lista de carpetas de crops (modo multi-carpeta)
        """
        super().__init__(parent)
        self.default_typologies = default_typologies or []
        self.additional_typologies = additional_typologies or []
        self.crop_manager = crop_manager
        self.crop_folders = crop_folders or []  # Lista de Path para modo multi-carpeta
        self.current_crops = []
        self.classifications_changed = []
        # Clases cargadas dinámicamente desde el módulo centralizado
        self.available_classes = get_cached_folder_classes()
        self.selected_class = None  # Sin clase seleccionada al inicio
        self.thumbnail_widgets = {}
        self.selected_thumbnail = None

        # Atributos para selección múltiple
        self.selected_thumbnails = []  # Lista de thumbnails seleccionados
        self.last_selected_index = -1  # Índice del último seleccionado (para Shift)

        # Cache de datos e imágenes precargadas
        self.all_images_data = {}  # {class_name: [thumb_data, ...]}
        self.pixmap_cache = {}  # {file_path: QPixmap} - cache de imágenes cargadas

        self.setWindowTitle("Galería de Clasificación Manual")
        self.setMinimumSize(800, 600)
        self.resize(1200, 800)  # Tamaño inicial

        # Permitir redimensionar libremente
        from PyQt5.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.init_ui()
        self.preload_all_images()  # Precargar todas las imágenes al inicio
        self.load_class_thumbnails()
    
    def init_ui(self):
        """Inicializar interfaz de usuario"""
        layout = QVBoxLayout()
        
        # Controles superiores
        controls_layout = QHBoxLayout()
        
        # Selector de clase
        class_group = QGroupBox("Seleccionar Clase")
        class_layout = QHBoxLayout()
        
        # Mapeo de clases a etiquetas en español (cargado dinámicamente)
        self.class_labels = get_cached_folder_to_tipologia()

        self.class_combo = QComboBox()
        # Agregar placeholder - sin clase seleccionada al inicio
        self.class_combo.addItem("-- Seleccionar clase --", None)
        for class_name in self.available_classes:
            display_name = self.class_labels.get(class_name, class_name.title())
            self.class_combo.addItem(display_name, class_name)

        # No seleccionar ninguna clase por defecto (queda en el placeholder)
        self.class_combo.setCurrentIndex(0)

        self.class_combo.currentTextChanged.connect(self.on_class_changed)
        
        class_layout.addWidget(QLabel("Clase:"))
        class_layout.addWidget(self.class_combo)
        class_layout.addStretch()
        class_group.setLayout(class_layout)
        
        # Filtros de tipo de crops
        type_group = QGroupBox("Tipo de Crops")
        type_layout = QHBoxLayout()

        self.all_crops_cb = QCheckBox("Detecciones generales")
        self.all_crops_cb.setChecked(True)
        self.all_crops_cb.toggled.connect(self.load_class_thumbnails)

        self.od_crops_cb = QCheckBox("Cruces O/D")
        self.od_crops_cb.setChecked(True)
        self.od_crops_cb.toggled.connect(self.load_class_thumbnails)

        type_layout.addWidget(self.all_crops_cb)
        type_layout.addWidget(self.od_crops_cb)
        type_group.setLayout(type_layout)

        # Filtro de validados
        filter_group = QGroupBox("Filtro")
        filter_layout = QHBoxLayout()

        self.pending_only_cb = QCheckBox("Solo pendientes")
        self.pending_only_cb.setChecked(True)
        self.pending_only_cb.setToolTip("Ocultar imágenes ya validadas")
        self.pending_only_cb.toggled.connect(self.load_class_thumbnails)
        filter_layout.addWidget(self.pending_only_cb)

        filter_group.setLayout(filter_layout)
        
        controls_layout.addWidget(class_group)
        controls_layout.addWidget(type_group)
        controls_layout.addWidget(filter_group)

        # Información de resumen
        self.summary_label = QLabel("Cargando...")
        controls_layout.addWidget(self.summary_label)

        layout.addLayout(controls_layout)

        # Barra de progreso de validación global
        validation_layout = QHBoxLayout()

        self.global_validation_label = QLabel("Progreso de validación global:")
        self.global_validation_label.setFont(QFont("Arial", 10, QFont.Bold))
        validation_layout.addWidget(self.global_validation_label)

        self.validation_progress = QProgressBar()
        self.validation_progress.setMinimum(0)
        self.validation_progress.setMaximum(100)
        self.validation_progress.setValue(0)
        self.validation_progress.setFormat("%v% (%p validadas de %m)")
        self.validation_progress.setMinimumWidth(300)
        self.validation_progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 5px;
                text-align: center;
                background-color: #f0f0f0;
            }
            QProgressBar::chunk {
                background-color: #28a745;
                border-radius: 4px;
            }
        """)
        validation_layout.addWidget(self.validation_progress)

        self.validation_stats_label = QLabel("")
        self.validation_stats_label.setStyleSheet("color: #666; font-size: 10pt;")
        validation_layout.addWidget(self.validation_stats_label)

        validation_layout.addStretch()
        layout.addLayout(validation_layout)
        
        # Área de miniaturas con scroll
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Widget contenedor de miniaturas
        self.thumbnails_widget = QWidget()
        self.thumbnails_layout = QGridLayout()
        self.thumbnails_layout.setSpacing(5)
        
        self.thumbnails_widget.setLayout(self.thumbnails_layout)
        self.scroll_area.setWidget(self.thumbnails_widget)

        # El scroll_area se expande para llenar el espacio disponible
        layout.addWidget(self.scroll_area, stretch=1)

        # Información de selección múltiple
        selection_info_layout = QHBoxLayout()
        self.selection_info_label = QLabel("Ninguna imagen seleccionada")
        self.selection_info_label.setStyleSheet("color: #0078d4; font-weight: bold; font-size: 11pt;")
        selection_info_layout.addWidget(self.selection_info_label)

        self.clear_selection_button = QPushButton("Limpiar Selección")
        self.clear_selection_button.clicked.connect(self.clear_all_selections)
        self.clear_selection_button.setEnabled(False)
        selection_info_layout.addWidget(self.clear_selection_button)

        selection_info_layout.addStretch()
        layout.addLayout(selection_info_layout)

        # Controles de reclasificación rápida
        reclassify_group = QGroupBox("Reclasificar Seleccionadas Como")
        reclassify_layout = QHBoxLayout()
        
        self.reclassify_combo = QComboBox()
        self.reclassify_combo.addItem("Seleccionar nueva clase...")
        for class_name in self.available_classes:
            display_name = self.class_labels.get(class_name, class_name.title())
            self.reclassify_combo.addItem(display_name, class_name)
        
        self.reclassify_button = QPushButton("Aplicar a Seleccionadas")
        self.reclassify_button.clicked.connect(self.reclassify_selected_images)
        self.reclassify_button.setEnabled(False)
        
        self.reclassify_combo.currentTextChanged.connect(
            lambda: self.reclassify_button.setEnabled(self.reclassify_combo.currentIndex() > 0)
        )
        
        reclassify_layout.addWidget(self.reclassify_combo)
        reclassify_layout.addWidget(self.reclassify_button)

        # Separador visual
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setStyleSheet("color: #ccc;")
        reclassify_layout.addWidget(separator)

        # Botón de validar
        self.validate_button = QPushButton("Validar Seleccionadas")
        self.validate_button.setToolTip("Marcar las imágenes seleccionadas como correctamente clasificadas")
        self.validate_button.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                padding: 5px 15px;
                border: none;
                border-radius: 3px;
            }
            QPushButton:hover { background-color: #218838; }
            QPushButton:disabled { background-color: #cccccc; }
        """)
        self.validate_button.clicked.connect(self.validate_selected_images)
        self.validate_button.setEnabled(False)
        reclassify_layout.addWidget(self.validate_button)

        reclassify_layout.addStretch()
        reclassify_group.setLayout(reclassify_layout)

        layout.addWidget(reclassify_group)
        
        # Botones inferiores
        button_layout = QHBoxLayout()
        
        self.save_button = QPushButton("Guardar Cambios")
        self.save_button.clicked.connect(self.save_all_classifications)
        self.save_button.setEnabled(False)
        
        self.close_button = QPushButton("Cerrar")
        self.close_button.clicked.connect(self.accept)
        
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.close_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)

        # Cargar estadísticas globales iniciales
        self.update_global_validation_display()

    def on_class_changed(self):
        """Manejar cambio de clase seleccionada"""
        selected_data = self.class_combo.currentData()
        self.selected_class = selected_data  # Puede ser None si es el placeholder
        self.load_class_thumbnails()
    
    def load_class_thumbnails(self):
        """Cargar miniaturas de la clase seleccionada usando el cache precargado"""
        try:
            # Limpiar selección múltiple
            self.selected_thumbnails.clear()
            self.last_selected_index = -1

            # Limpiar thumbnails anteriores
            for i in reversed(range(self.thumbnails_layout.count())):
                child = self.thumbnails_layout.itemAt(i).widget()
                if child:
                    child.deleteLater()

            self.thumbnail_widgets.clear()
            self.current_crops = []

            # Obtener la clase actual seleccionada
            selected_class = self.selected_class

            # Si no hay clase seleccionada, no mostrar nada
            if not selected_class:
                self.summary_label.setText("Seleccione una clase para ver las imágenes")
                self.update_selection_ui()
                return

            # Usar datos del cache si está disponible
            if self.all_images_data and selected_class in self.all_images_data:
                show_pending_only = self.pending_only_cb.isChecked()

                # Filtrar según configuración
                thumbnail_data = []
                for thumb in self.all_images_data[selected_class]:
                    # Filtrar por estado de validación
                    if show_pending_only and thumb.get('validated', False):
                        continue
                    thumbnail_data.append(thumb)
            else:
                # Fallback: cargar desde disco si no hay cache
                thumbnail_data = self._load_thumbnails_from_disk(selected_class)

            # Crear miniaturas usando el cache de pixmaps
            cols = 6  # Número de columnas (ajustado para thumbnails de 180px)
            for i, thumb_data in enumerate(thumbnail_data):
                # Usar pixmap cacheado si existe
                cached_pixmap = self.pixmap_cache.get(str(thumb_data['path']))
                thumbnail = ThumbnailLabel(thumb_data, thumb_data['path'], pixmap_cache=cached_pixmap)
                thumbnail.clicked.connect(self.on_thumbnail_clicked)

                row = i // cols
                col = i % cols
                self.thumbnails_layout.addWidget(thumbnail, row, col)

                self.thumbnail_widgets[thumb_data['filename']] = thumbnail

            # Actualizar resumen
            class_display = self.class_labels.get(selected_class, selected_class.title())
            total_images = len(thumbnail_data)

            self.summary_label.setText(
                f"{class_display}: {total_images} imágenes"
            )

            # Actualizar UI de selección
            self.update_selection_ui()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error cargando imágenes: {e}")
    
    def on_thumbnail_clicked(self, filename: str, thumb_data: dict, event=None):
        """Manejar click en miniatura con soporte para selección múltiple"""
        thumbnail = self.thumbnail_widgets.get(filename)
        if not thumbnail:
            return

        # Detectar modificadores del evento
        modifiers = event.modifiers() if event else Qt.NoModifier
        ctrl_pressed = bool(modifiers & Qt.ControlModifier)
        shift_pressed = bool(modifiers & Qt.ShiftModifier)

        if ctrl_pressed:
            # Ctrl: Toggle selección individual
            if thumbnail in self.selected_thumbnails:
                thumbnail.set_selected(False)
                self.selected_thumbnails.remove(thumbnail)
            else:
                thumbnail.set_selected(True)
                self.selected_thumbnails.append(thumbnail)
                self.last_selected_index = self.get_thumbnail_index(thumbnail)

        elif shift_pressed:
            # Shift: Selección de rango
            if self.last_selected_index >= 0:
                current_index = self.get_thumbnail_index(thumbnail)
                start = min(self.last_selected_index, current_index)
                end = max(self.last_selected_index, current_index)

                # Seleccionar rango
                all_thumbnails = self.get_all_thumbnails_ordered()
                for i in range(start, end + 1):
                    thumb = all_thumbnails[i]
                    if thumb not in self.selected_thumbnails:
                        thumb.set_selected(True)
                        self.selected_thumbnails.append(thumb)
            else:
                # Primer click con Shift = selección simple
                thumbnail.set_selected(True)
                self.selected_thumbnails.append(thumbnail)
                self.last_selected_index = self.get_thumbnail_index(thumbnail)

        else:
            # Click normal: Solo seleccionar (no abrir diálogo automáticamente)
            self.clear_all_selections()
            thumbnail.set_selected(True)
            self.selected_thumbnails = [thumbnail]
            self.last_selected_index = self.get_thumbnail_index(thumbnail)

        # Actualizar UI según selección
        self.selected_thumbnail = thumbnail
        self.update_selection_ui()

    def _load_thumbnails_from_disk(self, selected_class: str) -> list:
        """Fallback: cargar datos de thumbnails desde disco (sin cache)"""
        thumbnail_data = []
        show_pending_only = self.pending_only_cb.isChecked()

        if self.crop_folders:
            for crop_folder in self.crop_folders:
                class_dir = crop_folder / selected_class
                if class_dir.exists():
                    for img_file in class_dir.glob("*.jpg"):
                        if img_file.parent.name == "validados":
                            continue
                        thumbnail_data.append({
                            'path': img_file,
                            'filename': img_file.name,
                            'type': 'od',
                            'class': selected_class,
                            'source_folder': crop_folder,
                            'validated': False
                        })
                    for img_file in class_dir.glob("*.png"):
                        if img_file.parent.name == "validados":
                            continue
                        thumbnail_data.append({
                            'path': img_file,
                            'filename': img_file.name,
                            'type': 'od',
                            'class': selected_class,
                            'source_folder': crop_folder,
                            'validated': False
                        })

                    if not show_pending_only:
                        validated_dir = class_dir / "validados"
                        if validated_dir.exists():
                            for img_file in validated_dir.glob("*.jpg"):
                                thumbnail_data.append({
                                    'path': img_file,
                                    'filename': img_file.name,
                                    'type': 'od',
                                    'class': selected_class,
                                    'source_folder': crop_folder,
                                    'validated': True
                                })
                            for img_file in validated_dir.glob("*.png"):
                                thumbnail_data.append({
                                    'path': img_file,
                                    'filename': img_file.name,
                                    'type': 'od',
                                    'class': selected_class,
                                    'source_folder': crop_folder,
                                    'validated': True
                                })

        elif self.crop_manager:
            if self.all_crops_cb.isChecked():
                all_class_dir = self.crop_manager.all_crops_dir / selected_class
                if all_class_dir.exists():
                    for img_file in all_class_dir.glob("*.jpg"):
                        thumbnail_data.append({
                            'path': img_file,
                            'filename': img_file.name,
                            'type': 'all',
                            'class': selected_class
                        })

            if self.od_crops_cb.isChecked():
                od_class_dir = self.crop_manager.od_crops_dir / selected_class
                if od_class_dir.exists():
                    for img_file in od_class_dir.glob("*.jpg"):
                        thumbnail_data.append({
                            'path': img_file,
                            'filename': img_file.name,
                            'type': 'od',
                            'class': selected_class
                        })

        return thumbnail_data

    def show_class_selection_dialog(self, thumb_data: dict):
        """Mostrar diálogo de selección de clase"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Reclasificar Imagen")
        dialog.setMinimumWidth(300)
        
        layout = QVBoxLayout()
        
        # Información de la imagen
        info_label = QLabel(f"Imagen: {thumb_data.get('filename', 'N/A')}")
        info_label.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(info_label)
        
        current_class_label = QLabel(f"Clase actual: {self.class_labels.get(thumb_data['class'], thumb_data['class'])}")
        layout.addWidget(current_class_label)
        
        # Selector de nueva clase
        layout.addWidget(QLabel("Seleccionar nueva clase:"))
        
        class_combo = QComboBox()
        for class_name in self.available_classes:
            display_name = self.class_labels.get(class_name, class_name.title())
            class_combo.addItem(display_name, class_name)
            
            # Seleccionar la clase actual por defecto
            if class_name == thumb_data['class']:
                class_combo.setCurrentIndex(class_combo.count() - 1)
        
        layout.addWidget(class_combo)
        
        # Botones
        button_layout = QHBoxLayout()
        
        ok_button = QPushButton("Reclasificar")
        ok_button.clicked.connect(lambda: self.apply_reclassification(
            dialog, thumb_data, class_combo.currentData()
        ))
        
        cancel_button = QPushButton("Cancelar")
        cancel_button.clicked.connect(dialog.reject)
        
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        dialog.setLayout(layout)
        dialog.exec_()

    def get_thumbnail_index(self, thumbnail):
        """Obtener índice de thumbnail en el grid"""
        all_thumbs = self.get_all_thumbnails_ordered()
        return all_thumbs.index(thumbnail) if thumbnail in all_thumbs else -1

    def get_all_thumbnails_ordered(self):
        """Obtener todos los thumbnails en orden del grid"""
        thumbs = []
        for i in range(self.thumbnails_layout.count()):
            widget = self.thumbnails_layout.itemAt(i).widget()
            if isinstance(widget, ThumbnailLabel):
                thumbs.append(widget)
        return thumbs

    def clear_all_selections(self):
        """Limpiar todas las selecciones"""
        for thumb in self.selected_thumbnails:
            thumb.set_selected(False)
        self.selected_thumbnails.clear()
        self.last_selected_index = -1
        self.update_selection_ui()

    def update_selection_ui(self):
        """Actualizar UI basado en selección actual"""
        count = len(self.selected_thumbnails)

        if count == 0:
            self.selection_info_label.setText("Ninguna imagen seleccionada")
            self.clear_selection_button.setEnabled(False)
            self.reclassify_button.setEnabled(False)
            self.validate_button.setEnabled(False)
        elif count == 1:
            self.selection_info_label.setText("1 imagen seleccionada")
            self.clear_selection_button.setEnabled(True)
            self.reclassify_button.setEnabled(self.reclassify_combo.currentIndex() > 0)
            self.validate_button.setEnabled(True)
        else:
            self.selection_info_label.setText(f"{count} imágenes seleccionadas")
            self.clear_selection_button.setEnabled(True)
            self.reclassify_button.setEnabled(self.reclassify_combo.currentIndex() > 0)
            self.validate_button.setEnabled(True)

    def apply_reclassification(self, dialog, thumb_data: dict, new_class: str):
        """Aplicar la reclasificación seleccionada"""
        dialog.accept()
        
        if new_class and new_class != thumb_data['class']:
            self.reclassify_single(thumb_data, new_class)
    
    def reclassify_single(self, thumb_data: dict, new_class: str, reload_view: bool = True):
        """Reclasificar una sola imagen

        Args:
            thumb_data: Datos del thumbnail
            new_class: Nueva clase de clasificación
            reload_view: Si True, recarga la galería después de reclasificar.
                         Usar False cuando se reclasifican múltiples imágenes en lote.
        """
        if new_class == thumb_data['class']:
            return  # No hay cambio

        try:
            # Mover archivo a la nueva carpeta de clase
            old_path = thumb_data['path']

            # Modo multi-carpeta: usar source_folder del thumbnail
            if 'source_folder' in thumb_data:
                # Al reclasificar, mover directamente a validados/ (ya fue verificada)
                new_dir = thumb_data['source_folder'] / new_class / "validados"
            # Modo tradicional: usar crop_manager
            elif self.crop_manager:
                if thumb_data['type'] == 'all':
                    new_dir = self.crop_manager.all_crops_dir / new_class / "validados"
                else:
                    new_dir = self.crop_manager.od_crops_dir / new_class / "validados"
            else:
                raise ValueError("No se puede determinar la carpeta destino")

            new_dir.mkdir(parents=True, exist_ok=True)
            new_path = new_dir / thumb_data['filename']

            # Mover archivo
            old_path.rename(new_path)

            # Actualizar cache de datos
            old_class = thumb_data['class']
            if self.all_images_data:
                # Remover de la clase antigua
                if old_class in self.all_images_data:
                    self.all_images_data[old_class] = [
                        t for t in self.all_images_data[old_class]
                        if str(t['path']) != str(old_path)
                    ]
                # Agregar a la nueva clase
                if new_class in self.all_images_data:
                    new_thumb_data = thumb_data.copy()
                    new_thumb_data['path'] = new_path
                    new_thumb_data['class'] = new_class
                    new_thumb_data['validated'] = True
                    self.all_images_data[new_class].append(new_thumb_data)

                # Actualizar cache de pixmap con la nueva ruta
                old_path_str = str(old_path)
                if old_path_str in self.pixmap_cache:
                    self.pixmap_cache[str(new_path)] = self.pixmap_cache.pop(old_path_str)

            # Actualizar datos en base de datos (solo si hay crop_manager)
            if self.crop_manager:
                self.update_crop_classification_in_db(thumb_data['filename'], new_class, thumb_data['type'])

            # Registrar cambio
            self.classifications_changed.append({
                'filename': thumb_data['filename'],
                'old_class': thumb_data['class'],
                'new_class': new_class,
                'type': thumb_data['type']
            })

            # Habilitar botón de guardar
            self.save_button.setEnabled(len(self.classifications_changed) > 0)

            # Recargar vista actual solo si se solicita
            if reload_view:
                self.load_class_thumbnails()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error reclasificando imagen: {e}")
    
    def reclassify_all_visible(self):
        """Reclasificar todas las imágenes visibles"""
        new_class_data = self.reclassify_combo.currentData()
        if not new_class_data:
            return

        # Verificar que hay clase seleccionada
        if not self.selected_class:
            QMessageBox.warning(self, "Advertencia", "No hay clase seleccionada.")
            return

        current_images = len(self.thumbnail_widgets)
        if current_images == 0:
            return

        # Confirmar acción
        current_class_name = self.class_labels.get(self.selected_class, self.selected_class.title())
        new_class_name = self.class_labels.get(new_class_data, new_class_data.title())

        reply = QMessageBox.question(
            self,
            'Confirmar Reclasificación Masiva',
            f'¿Reclasificar todas las {current_images} imágenes de {current_class_name} como {new_class_name}?',
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # Recoger datos de todos los thumbnails antes de procesar
            current_thumbnails = [
                thumbnail.crop_data for thumbnail in self.thumbnail_widgets.values()
            ]

            # Reclasificar cada una SIN recargar la vista en cada iteración
            for thumb_data in current_thumbnails:
                self.reclassify_single(thumb_data, new_class_data, reload_view=False)

            # Recargar la vista UNA SOLA VEZ al final
            self.load_class_thumbnails()

        # Resetear combo
        self.reclassify_combo.setCurrentIndex(0)

    def reclassify_selected_images(self):
        """Reclasificar las imágenes seleccionadas"""
        if not self.selected_thumbnails:
            QMessageBox.warning(self, "Advertencia", "No hay imágenes seleccionadas.\n\nUse Ctrl+Click para seleccionar múltiples imágenes o Shift+Click para seleccionar un rango.")
            return

        new_class_data = self.reclassify_combo.currentData()
        if not new_class_data:
            QMessageBox.warning(self, "Advertencia", "Seleccione una clase de destino.")
            return

        count = len(self.selected_thumbnails)
        new_class_name = self.class_labels.get(new_class_data, new_class_data.title())

        # Confirmar acción
        reply = QMessageBox.question(
            self,
            'Confirmar Reclasificación',
            f'¿Reclasificar {count} imagen(es) seleccionada(s) como {new_class_name}?',
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # Recoger datos de los thumbnails antes de procesar
            # (evita problemas si la lista se modifica durante iteración)
            thumbnails_to_process = [
                thumbnail.crop_data for thumbnail in self.selected_thumbnails
            ]

            # Reclasificar cada una SIN recargar la vista en cada iteración
            for thumb_data in thumbnails_to_process:
                self.reclassify_single(thumb_data, new_class_data, reload_view=False)

            # Limpiar selección después de reclasificar
            self.clear_all_selections()

            # Recargar la vista UNA SOLA VEZ al final
            self.load_class_thumbnails()

            # Actualizar estadísticas globales
            self.update_global_validation_display()

        # Resetear combo
        self.reclassify_combo.setCurrentIndex(0)

    def validate_selected_images(self):
        """Validar las imágenes seleccionadas (moverlas a subcarpeta validados/)"""
        if not self.selected_thumbnails:
            QMessageBox.warning(
                self, "Advertencia",
                "No hay imágenes seleccionadas.\n\n"
                "Use Ctrl+Click para seleccionar múltiples imágenes."
            )
            return

        count = len(self.selected_thumbnails)

        reply = QMessageBox.question(
            self,
            'Confirmar Validación',
            f'¿Marcar {count} imagen(es) como validadas?\n\n'
            'Las imágenes validadas no aparecerán cuando "Solo pendientes" esté activado.',
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # Recoger datos antes de procesar
        thumbnails_to_validate = [
            thumbnail.crop_data for thumbnail in self.selected_thumbnails
        ]

        validated_count = 0
        for thumb_data in thumbnails_to_validate:
            if self.validate_single(thumb_data):
                validated_count += 1

        # Limpiar selección
        self.clear_all_selections()

        # Recargar vista
        self.load_class_thumbnails()

        # Actualizar estadísticas globales
        self.update_global_validation_display()

        if validated_count > 0:
            QMessageBox.information(
                self, "Validación Completada",
                f"Se validaron {validated_count} imagen(es)."
            )

    def validate_single(self, thumb_data: dict) -> bool:
        """
        Validar una sola imagen moviéndola a la subcarpeta validados/.

        Args:
            thumb_data: Datos del thumbnail incluyendo path y source_folder

        Returns:
            True si se validó correctamente
        """
        try:
            old_path = Path(thumb_data['path'])

            # Determinar carpeta de validados
            if 'source_folder' in thumb_data:
                # Modo multi-carpeta
                validated_dir = thumb_data['source_folder'] / thumb_data['class'] / "validados"
            elif self.crop_manager:
                # Modo tradicional
                if thumb_data['type'] == 'all':
                    validated_dir = self.crop_manager.all_crops_dir / thumb_data['class'] / "validados"
                else:
                    validated_dir = self.crop_manager.od_crops_dir / thumb_data['class'] / "validados"
            else:
                return False

            # Crear carpeta validados si no existe
            validated_dir.mkdir(parents=True, exist_ok=True)

            # Mover archivo
            new_path = validated_dir / old_path.name
            old_path.rename(new_path)

            # Actualizar cache de datos
            current_class = thumb_data['class']
            if self.all_images_data and current_class in self.all_images_data:
                # Actualizar el estado de validación en el cache
                for t in self.all_images_data[current_class]:
                    if str(t['path']) == str(old_path):
                        t['path'] = new_path
                        t['validated'] = True
                        break

                # Actualizar cache de pixmap
                old_path_str = str(old_path)
                if old_path_str in self.pixmap_cache:
                    self.pixmap_cache[str(new_path)] = self.pixmap_cache.pop(old_path_str)

            return True

        except Exception as e:
            print(f"Error validando imagen: {e}")
            return False

    def update_crop_classification_in_db(self, filename: str, new_class: str, crop_type: str):
        """Actualizar clasificación en base de datos"""
        try:
            import sqlite3
            table = 'AllCrops' if crop_type == 'all' else 'OdCrops'
            
            with sqlite3.connect(self.crop_manager.crops_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(f"""
                    UPDATE {table} 
                    SET manual_classification = ?, verified = TRUE
                    WHERE crop_filename = ?
                """, (new_class, filename))
                conn.commit()
        except Exception as e:
            print(f"Error actualizando base de datos: {e}")
    
    def save_all_classifications(self):
        """Guardar todas las clasificaciones modificadas"""
        if not self.classifications_changed:
            QMessageBox.information(self, "Información", "No hay cambios pendientes para guardar.")
            return
        
        try:
            changes_count = len(self.classifications_changed)
            
            QMessageBox.information(
                self,
                "Éxito",
                f"Se procesaron {changes_count} reclasificaciones.\n\nLos archivos ya fueron movidos a las carpetas correctas y la base de datos ha sido actualizada."
            )
            
            # Limpiar cambios
            self.classifications_changed.clear()
            self.save_button.setEnabled(False)
            
            # Recargar vista actual
            self.load_class_thumbnails()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error guardando: {e}")

    def calculate_global_validation_stats(self):
        """Calcular estadísticas globales de validación de todas las carpetas"""
        total_images = 0
        validated_images = 0

        # Modo multi-carpeta
        if self.crop_folders:
            for crop_folder in self.crop_folders:
                try:
                    for class_dir in crop_folder.iterdir():
                        if class_dir.is_dir() and class_dir.name != "validados":
                            # Contar pendientes
                            total_images += len(list(class_dir.glob("*.jpg")))
                            total_images += len(list(class_dir.glob("*.png")))

                            # Contar validadas
                            validated_dir = class_dir / "validados"
                            if validated_dir.exists():
                                val_count = len(list(validated_dir.glob("*.jpg")))
                                val_count += len(list(validated_dir.glob("*.png")))
                                validated_images += val_count
                                total_images += val_count
                except Exception:
                    pass

        # Modo tradicional con crop_manager
        elif self.crop_manager:
            for base_dir in [self.crop_manager.all_crops_dir, self.crop_manager.od_crops_dir]:
                if base_dir and base_dir.exists():
                    try:
                        for class_dir in base_dir.iterdir():
                            if class_dir.is_dir() and class_dir.name != "validados":
                                total_images += len(list(class_dir.glob("*.jpg")))
                                total_images += len(list(class_dir.glob("*.png")))

                                validated_dir = class_dir / "validados"
                                if validated_dir.exists():
                                    val_count = len(list(validated_dir.glob("*.jpg")))
                                    val_count += len(list(validated_dir.glob("*.png")))
                                    validated_images += val_count
                                    total_images += val_count
                    except Exception:
                        pass

        return total_images, validated_images

    def update_global_validation_display(self):
        """Actualizar la visualización de estadísticas globales de validación"""
        total, validated = self.calculate_global_validation_stats()

        if total > 0:
            percent = int((validated / total) * 100)
            self.validation_progress.setMaximum(total)
            self.validation_progress.setValue(validated)
            self.validation_progress.setFormat(f"{percent}%")
            self.validation_stats_label.setText(
                f"{validated:,} de {total:,} imágenes validadas"
            )
        else:
            self.validation_progress.setValue(0)
            self.validation_stats_label.setText("Sin imágenes")

    def preload_all_images(self):
        """Precargar todas las imágenes y datos al inicio para cambios instantáneos"""
        self.all_images_data = {cls: [] for cls in self.available_classes}
        self.pixmap_cache = {}

        # Contar total de imágenes primero para la barra de progreso
        total_files = 0
        files_to_load = []

        # Recopilar todos los archivos
        if self.crop_folders:
            for crop_folder in self.crop_folders:
                for class_name in self.available_classes:
                    class_dir = crop_folder / class_name
                    if class_dir.exists():
                        # Imágenes pendientes
                        for img_file in class_dir.glob("*.jpg"):
                            if img_file.parent.name != "validados":
                                files_to_load.append((img_file, class_name, crop_folder, False))
                        for img_file in class_dir.glob("*.png"):
                            if img_file.parent.name != "validados":
                                files_to_load.append((img_file, class_name, crop_folder, False))

                        # Imágenes validadas
                        validated_dir = class_dir / "validados"
                        if validated_dir.exists():
                            for img_file in validated_dir.glob("*.jpg"):
                                files_to_load.append((img_file, class_name, crop_folder, True))
                            for img_file in validated_dir.glob("*.png"):
                                files_to_load.append((img_file, class_name, crop_folder, True))

        elif self.crop_manager:
            for base_dir, crop_type in [(self.crop_manager.all_crops_dir, 'all'),
                                         (self.crop_manager.od_crops_dir, 'od')]:
                if base_dir and base_dir.exists():
                    for class_name in self.available_classes:
                        class_dir = base_dir / class_name
                        if class_dir.exists():
                            for img_file in class_dir.glob("*.jpg"):
                                files_to_load.append((img_file, class_name, base_dir, False, crop_type))
                            for img_file in class_dir.glob("*.png"):
                                files_to_load.append((img_file, class_name, base_dir, False, crop_type))

        total_files = len(files_to_load)
        if total_files == 0:
            return

        # Mostrar progreso de carga
        self.validation_stats_label.setText(f"Precargando {total_files} imágenes...")
        QApplication.processEvents()

        # Cargar imágenes en lotes para mantener la UI responsiva
        batch_size = 50
        for i, file_info in enumerate(files_to_load):
            if len(file_info) == 4:
                img_file, class_name, source_folder, validated = file_info
                crop_type = 'od'
            else:
                img_file, class_name, source_folder, validated, crop_type = file_info

            # Crear datos del thumbnail
            thumb_data = {
                'path': img_file,
                'filename': img_file.name,
                'type': crop_type,
                'class': class_name,
                'source_folder': source_folder,
                'validated': validated
            }
            self.all_images_data[class_name].append(thumb_data)

            # Precargar pixmap (miniatura)
            if img_file.exists():
                pixmap = QPixmap(str(img_file))
                if not pixmap.isNull():
                    # Escalar a tamaño de miniatura
                    scaled = pixmap.scaled(170, 170, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.pixmap_cache[str(img_file)] = scaled

            # Actualizar progreso cada batch
            if (i + 1) % batch_size == 0:
                percent = int((i + 1) / total_files * 100)
                self.validation_stats_label.setText(f"Precargando... {percent}% ({i+1}/{total_files})")
                QApplication.processEvents()

        self.validation_stats_label.setText("")