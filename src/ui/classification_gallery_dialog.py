"""
Diálogo de galería para clasificación manual rápida de crops
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QComboBox, QScrollArea, QWidget, 
                            QMessageBox, QProgressBar, QGroupBox, QCheckBox, 
                            QGridLayout, QFrame, QSplitter, QTabWidget,
                            QInputDialog, QLineEdit, QToolTip, QErrorMessage)
from PyQt5.QtGui import QPixmap, QFont, QPainter, QPen, QColor, QCursor
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QRect, QSize, QTimer
import os
from pathlib import Path
from typing import List, Dict, Optional
from collections import defaultdict


class ThumbnailLabel(QLabel):
    """Label personalizado para miniaturas con funcionalidad de click"""

    clicked = pyqtSignal(str, dict, object)  # crop_filename, crop_data, QMouseEvent
    
    def __init__(self, crop_data: dict, crop_path: Path, thumbnail_size=120):
        super().__init__()
        self.crop_data = crop_data
        self.crop_path = crop_path
        self.thumbnail_size = thumbnail_size
        self.is_selected = False
        
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
        """Cargar y mostrar la miniatura"""
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
        self.available_classes = ['person', 'bicycle', 'car', 'motorcycle', 'bus', 'truck']
        
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
        
        # Mapeo de clases a etiquetas en español
        class_labels = {
            'person': 'Persona',
            'bicycle': 'Bicicleta', 
            'car': 'Auto',
            'motorcycle': 'Moto',
            'bus': 'Bus',
            'truck': 'Camion'
        }
        
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
        
        # Mapeo de clases a etiquetas en español
        class_labels = {
            'person': 'Persona',
            'bicycle': 'Bicicleta', 
            'car': 'Carro',
            'motorcycle': 'Moto',
            'bus': 'Bus',
            'truck': 'Camión'
        }
        
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
        
        # Mapeo inverso para obtener el nombre de clase
        class_labels = {
            'Persona': 'person',
            'Bicicleta': 'bicycle', 
            'Auto': 'car',
            'Moto': 'motorcycle',
            'Bus': 'bus',
            'Camion': 'truck'
        }
        
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
    def __init__(self, crop_manager, default_typologies, additional_typologies, parent=None):
        super().__init__(parent)
        self.default_typologies = default_typologies
        self.additional_typologies = additional_typologies
        self.crop_manager = crop_manager
        self.current_crops = []
        self.classifications_changed = []
        self.available_classes = ['person', 'bicycle', 'car', 'motorcycle', 'bus', 'truck']
        self.selected_class = 'car'  # Clase por defecto
        self.thumbnail_widgets = {}
        self.selected_thumbnail = None

        # Atributos para selección múltiple
        self.selected_thumbnails = []  # Lista de thumbnails seleccionados
        self.last_selected_index = -1  # Índice del último seleccionado (para Shift)

        self.setWindowTitle("Galería de Clasificación Manual")
        self.setMinimumSize(1000, 700)
        
        self.init_ui()
        self.load_class_thumbnails()
    
    def init_ui(self):
        """Inicializar interfaz de usuario"""
        layout = QVBoxLayout()
        
        # Controles superiores
        controls_layout = QHBoxLayout()
        
        # Selector de clase
        class_group = QGroupBox("Seleccionar Clase")
        class_layout = QHBoxLayout()
        
        # Mapeo de clases a etiquetas en español
        self.class_labels = {
            'person': 'Persona',
            'bicycle': 'Bicicleta', 
            'car': 'Auto',
            'motorcycle': 'Moto',
            'bus': 'Bus',
            'truck': 'Camion'
        }

        # Chequeo de clases por defecto
        default_spa_labels = [typo for typo in self.class_labels.values()]
        if not sorted(default_spa_labels) == sorted(self.default_typologies):
            error_message = QErrorMessage()
            error_message.showMessage("La tipología por defecto ha sido alterada. Descargue nuevamente el archivo tipologias.txt.")

        self.class_combo = QComboBox()
        for class_name in self.available_classes:
            display_name = self.class_labels.get(class_name, class_name.title())
            self.class_combo.addItem(display_name, class_name)
        
        # Establecer "Carros" como selección por defecto
        default_index = self.class_combo.findData('car')
        if default_index >= 0:
            self.class_combo.setCurrentIndex(default_index)
        
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
        
        controls_layout.addWidget(class_group)
        controls_layout.addWidget(type_group)
        
        # Información de resumen
        self.summary_label = QLabel("Cargando...")
        controls_layout.addWidget(self.summary_label)
        
        layout.addLayout(controls_layout)
        
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
        
        layout.addWidget(self.scroll_area)

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
    
    def on_class_changed(self):
        """Manejar cambio de clase seleccionada"""
        selected_data = self.class_combo.currentData()
        if selected_data:
            self.selected_class = selected_data
            self.load_class_thumbnails()
    
    def load_class_thumbnails(self):
        """Cargar miniaturas de la clase seleccionada desde las carpetas"""
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
            if not selected_class:
                selected_class = 'car'
            
            # Buscar imágenes en las carpetas de la clase
            thumbnail_data = []
            
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
            
            # Crear miniaturas
            cols = 8  # Número de columnas
            for i, thumb_data in enumerate(thumbnail_data):
                thumbnail = ThumbnailLabel(thumb_data, thumb_data['path'])
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
            # Deshabilitar botón de reclasificación
            self.reclassify_button.setEnabled(False)
        elif count == 1:
            self.selection_info_label.setText("1 imagen seleccionada")
            self.clear_selection_button.setEnabled(True)
            # Habilitar si hay clase seleccionada
            self.reclassify_button.setEnabled(self.reclassify_combo.currentIndex() > 0)
        else:
            self.selection_info_label.setText(f"{count} imágenes seleccionadas")
            self.clear_selection_button.setEnabled(True)
            # Habilitar si hay clase seleccionada
            self.reclassify_button.setEnabled(self.reclassify_combo.currentIndex() > 0)

    def apply_reclassification(self, dialog, thumb_data: dict, new_class: str):
        """Aplicar la reclasificación seleccionada"""
        dialog.accept()
        
        if new_class and new_class != thumb_data['class']:
            self.reclassify_single(thumb_data, new_class)
    
    def reclassify_single(self, thumb_data: dict, new_class: str):
        """Reclasificar una sola imagen"""
        if new_class == thumb_data['class']:
            return  # No hay cambio
        
        try:
            # Mover archivo a la nueva carpeta de clase
            old_path = thumb_data['path']
            
            if thumb_data['type'] == 'all':
                new_dir = self.crop_manager.all_crops_dir / new_class
            else:
                new_dir = self.crop_manager.od_crops_dir / new_class
            
            new_dir.mkdir(exist_ok=True)
            new_path = new_dir / thumb_data['filename']
            
            # Mover archivo
            old_path.rename(new_path)
            
            # Actualizar datos en base de datos
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
            
            # Recargar vista actual
            self.load_class_thumbnails()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error reclasificando imagen: {e}")
    
    def reclassify_all_visible(self):
        """Reclasificar todas las imágenes visibles"""
        new_class_data = self.reclassify_combo.currentData()
        if not new_class_data:
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
            # Obtener todas las imágenes actuales
            current_thumbnails = []
            for filename, thumbnail in self.thumbnail_widgets.items():
                thumb_data = thumbnail.crop_data
                current_thumbnails.append(thumb_data)
            
            # Reclasificar cada una
            for thumb_data in current_thumbnails:
                self.reclassify_single(thumb_data, new_class_data)
        
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
            # Reclasificar cada una
            for thumbnail in self.selected_thumbnails:
                thumb_data = thumbnail.crop_data
                self.reclassify_single(thumb_data, new_class_data)

            # Limpiar selección después de reclasificar
            self.clear_all_selections()

        # Resetear combo
        self.reclassify_combo.setCurrentIndex(0)

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