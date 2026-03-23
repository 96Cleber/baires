"""
Diálogo para clasificación manual de crops
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                            QPushButton, QComboBox, QGridLayout, QScrollArea,
                            QWidget, QMessageBox, QProgressBar, QGroupBox,
                            QCheckBox, QSpinBox, QInputDialog, QLineEdit)
from PyQt5.QtGui import QPixmap, QFont, QPainter, QPen, QColor
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QRect
import os
import sys
from pathlib import Path
from typing import List, Dict

# Importar módulo de tipologías centralizado
def _get_tools_path():
    if hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(__file__))

sys.path.insert(0, _get_tools_path())
from tools.typologies import get_cached_folder_to_tipologia, get_cached_folder_classes


class ManualClassificationDialog(QDialog):
    """Diálogo para clasificación manual de detecciones"""

    def __init__(self, crop_manager, parent=None):
        super().__init__(parent)
        self.crop_manager = crop_manager
        self.current_crops = []
        self.current_index = 0
        self.classifications_changed = []
        # Clases cargadas dinámicamente desde el módulo centralizado
        self.available_classes = get_cached_folder_classes()
        self.custom_classes = []
        
        self.setWindowTitle("Clasificación Manual de Detecciones")
        self.setMinimumSize(800, 600)
        
        self.init_ui()
        self.load_unverified_crops()
    
    def init_ui(self):
        """Inicializar interfaz de usuario"""
        layout = QVBoxLayout()
        
        # Controles superiores
        controls_layout = QHBoxLayout()
        
        # Tipo de crops a mostrar
        type_group = QGroupBox("Tipo de Crops")
        type_layout = QHBoxLayout()
        
        self.all_crops_cb = QCheckBox("Todas las detecciones")
        self.all_crops_cb.setChecked(True)
        self.all_crops_cb.toggled.connect(self.load_unverified_crops)
        
        self.od_crops_cb = QCheckBox("Cruces O/D únicamente")
        self.od_crops_cb.toggled.connect(self.load_unverified_crops)
        
        type_layout.addWidget(self.all_crops_cb)
        type_layout.addWidget(self.od_crops_cb)
        type_group.setLayout(type_layout)
        
        controls_layout.addWidget(type_group)
        
        # Información de progreso
        progress_group = QGroupBox("Progreso")
        progress_layout = QVBoxLayout()
        
        self.progress_label = QLabel("0 / 0")
        self.progress_bar = QProgressBar()
        
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)
        progress_group.setLayout(progress_layout)
        
        controls_layout.addWidget(progress_group)
        layout.addLayout(controls_layout)
        
        # Área principal de clasificación
        main_layout = QHBoxLayout()
        
        # Panel izquierdo - Imagen
        image_group = QGroupBox("Imagen a Clasificar")
        image_layout = QVBoxLayout()
        
        self.image_label = QLabel()
        self.image_label.setMinimumSize(400, 300)
        self.image_label.setStyleSheet("border: 2px solid gray;")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setScaledContents(True)
        
        # Información de la detección actual
        self.info_label = QLabel("No hay crops para clasificar")
        self.info_label.setFont(QFont("Arial", 10))
        self.info_label.setWordWrap(True)
        
        image_layout.addWidget(self.image_label)
        image_layout.addWidget(self.info_label)
        image_group.setLayout(image_layout)
        
        main_layout.addWidget(image_group)
        
        # Panel derecho - Controles de clasificación
        classification_group = QGroupBox("Clasificación")
        classification_layout = QVBoxLayout()
        
        # Clasificación original y nueva
        self.original_class_label = QLabel("Clasificación original: -")
        self.original_class_label.setFont(QFont("Arial", 10, QFont.Bold))
        
        class_header_layout = QHBoxLayout()
        class_header_layout.addWidget(QLabel("Nueva clasificación:"))
        
        self.add_class_button = QPushButton("+ Nueva Clase")
        self.add_class_button.clicked.connect(self.add_new_class)
        class_header_layout.addWidget(self.add_class_button)
        
        self.class_combo = QComboBox()
        self.update_class_combo()
        self.class_combo.currentTextChanged.connect(self.on_classification_changed)
        
        classification_layout.addWidget(self.original_class_label)
        classification_layout.addLayout(class_header_layout)
        classification_layout.addWidget(self.class_combo)
        
        # Botones de navegación
        nav_layout = QHBoxLayout()
        
        self.prev_button = QPushButton("← Anterior")
        self.prev_button.clicked.connect(self.show_previous)
        
        self.next_button = QPushButton("Siguiente →")
        self.next_button.clicked.connect(self.show_next)
        
        nav_layout.addWidget(self.prev_button)
        nav_layout.addWidget(self.next_button)
        
        classification_layout.addLayout(nav_layout)
        
        # Botones de acción rápida
        quick_actions_layout = QGridLayout()
        
        # Actualizar botones rápidos dinámicamente
        self.quick_buttons_layout = quick_actions_layout
        self.update_quick_buttons()
        
        classification_layout.addLayout(quick_actions_layout)
        classification_group.setLayout(classification_layout)
        
        main_layout.addWidget(classification_group)
        layout.addLayout(main_layout)
        
        # Botones inferiores
        button_layout = QHBoxLayout()
        
        self.save_button = QPushButton("Guardar Cambios")
        self.save_button.clicked.connect(self.save_classifications)
        self.save_button.setEnabled(False)
        
        self.close_button = QPushButton("Cerrar")
        self.close_button.clicked.connect(self.accept)
        
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.close_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # Habilitar navegación por teclado
        self.setFocusPolicy(Qt.StrongFocus)
    
    def keyPressEvent(self, event):
        """Manejar eventos de teclado"""
        if event.key() == Qt.Key_Left or event.key() == Qt.Key_Up:
            self.show_previous()
            event.accept()
        elif event.key() == Qt.Key_Right or event.key() == Qt.Key_Down:
            self.show_next()
            event.accept()
        elif event.key() >= Qt.Key_1 and event.key() <= Qt.Key_6:
            # Navegación rápida por números
            index = event.key() - Qt.Key_1
            if index < self.class_combo.count():
                self.class_combo.setCurrentIndex(index)
                event.accept()
        else:
            super().keyPressEvent(event)
            
    def update_class_combo(self):
        """Actualizar el combo box con todas las clases disponibles"""
        current_text = self.class_combo.currentText() if self.class_combo.currentText() else None
        
        self.class_combo.clear()
        all_classes = self.available_classes + self.custom_classes
        self.class_combo.addItems(all_classes)
        
        # Restaurar selección si era válida
        if current_text and current_text in all_classes:
            self.class_combo.setCurrentText(current_text)
            
    def add_new_class(self):
        """Agregar una nueva clase de vehículo"""
        new_class, ok = QInputDialog.getText(
            self, 'Nueva Clase', 'Nombre de la nueva clase:',
            QLineEdit.Normal, ''
        )
        
        if ok and new_class.strip():
            new_class = new_class.strip().lower()
            
            # Verificar que no exista ya
            all_classes = self.available_classes + self.custom_classes
            if new_class not in all_classes:
                self.custom_classes.append(new_class)
                self.update_class_combo()
                self.update_quick_buttons()  # Actualizar botones rápidos
                self.class_combo.setCurrentText(new_class)
                
                QMessageBox.information(
                    self, 'Éxito', 
                    f'Clase "{new_class}" agregada exitosamente.'
                )
            else:
                QMessageBox.warning(
                    self, 'Advertencia', 
                    f'La clase "{new_class}" ya existe.'
                )
                
    def update_quick_buttons(self):
        """Actualizar botones de clasificación rápida"""
        # Limpiar botones existentes
        for i in reversed(range(self.quick_buttons_layout.count())):
            child = self.quick_buttons_layout.itemAt(i).widget()
            if child:
                child.deleteLater()

        # Mapeo de clases a etiquetas en español (cargado dinámicamente)
        class_labels = get_cached_folder_to_tipologia()

        # Añadir botones para todas las clases disponibles
        all_classes = self.available_classes + self.custom_classes
        
        for i, class_name in enumerate(all_classes):
            # Usar etiqueta en español si existe, sino usar el nombre de la clase
            button_text = class_labels.get(class_name, class_name.title())
            
            button = QPushButton(button_text)
            button.clicked.connect(lambda checked, cn=class_name: self.quick_classify(cn))
            
            # Organizar en 2 columnas
            row = i // 2
            col = i % 2
            self.quick_buttons_layout.addWidget(button, row, col)
                
    def load_unverified_crops(self):
        """Cargar crops no verificados"""
        try:
            self.current_crops = []
            
            if self.all_crops_cb.isChecked():
                all_crops = self.crop_manager.get_unverified_crops('all')
                self.current_crops.extend(all_crops)
            
            if self.od_crops_cb.isChecked():
                od_crops = self.crop_manager.get_unverified_crops('od')
                self.current_crops.extend(od_crops)
            
            self.current_index = 0
            self.classifications_changed = []
            
            # Actualizar interfaz
            total_crops = len(self.current_crops)
            self.progress_bar.setMaximum(total_crops)
            self.progress_label.setText(f"0 / {total_crops}")
            
            if total_crops > 0:
                self.show_current_crop()
            else:
                self.image_label.setText("No hay crops para clasificar")
                self.info_label.setText("Todos los crops han sido verificados")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error cargando crops: {e}")
    
    def show_current_crop(self):
        """Mostrar el crop actual"""
        if not self.current_crops or self.current_index >= len(self.current_crops):
            return
            
        crop_data = self.current_crops[self.current_index]
        
        # Cargar imagen
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
        
        if crop_path and crop_path.exists():
            pixmap = QPixmap(str(crop_path))
            if not pixmap.isNull():
                # Crear una copia para dibujar el resaltado
                highlighted_pixmap = self.add_class_highlight(pixmap, crop_data)
                
                # Escalar imagen manteniendo aspecto
                scaled_pixmap = highlighted_pixmap.scaled(
                    self.image_label.size(), 
                    Qt.KeepAspectRatio, 
                    Qt.SmoothTransformation
                )
                self.image_label.setPixmap(scaled_pixmap)
            else:
                self.image_label.setText("Error cargando imagen")
        else:
            self.image_label.setText("Imagen no encontrada")
        
        # Actualizar información
        original_class = crop_data['detection_class']
        self.original_class_label.setText(f"Clasificación original: {original_class}")
        
        # Establecer clasificación actual
        current_class = crop_data.get('manual_classification', original_class)
        if current_class:
            index = self.class_combo.findText(current_class)
            if index >= 0:
                self.class_combo.setCurrentIndex(index)
        
        # Información adicional
        if 'frame_number' in crop_data:
            # Crop de detección general
            info_text = f"""
            Archivo: {crop_filename}
            Frame: {crop_data['frame_number']}
            ID Objeto: {crop_data['object_id']}
            Confianza: {crop_data['confidence']:.2f}
            """
        else:
            # Crop de cruce O/D
            info_text = f"""
            Archivo: {crop_filename}
            Objeto: {crop_data['object_id']}
            Frames: {crop_data['origin_frame']} → {crop_data['destination_frame']}
            Giro: {crop_data['turn_name']}
            Líneas: {crop_data['origin_line']} → {crop_data['destination_line']}
            """
        
        self.info_label.setText(info_text.strip())
        
        # Actualizar progreso
        self.progress_bar.setValue(self.current_index + 1)
        self.progress_label.setText(f"{self.current_index + 1} / {len(self.current_crops)}")
        
        # Actualizar botones
        self.prev_button.setEnabled(self.current_index > 0)
        self.next_button.setEnabled(self.current_index < len(self.current_crops) - 1)
        
    def add_class_highlight(self, pixmap, crop_data):
        """Agregar resaltado visual de la clase actual"""
        highlighted_pixmap = QPixmap(pixmap)
        painter = QPainter(highlighted_pixmap)
        
        # Obtener clase actual (manual o original)
        current_class = crop_data.get('manual_classification')
        if not current_class:
            current_class = crop_data['detection_class']
            
        # Colores por clase
        class_colors = {
            'person': QColor(255, 0, 0),      # Rojo
            'bicycle': QColor(0, 255, 0),     # Verde
            'car': QColor(0, 0, 255),         # Azul
            'motorcycle': QColor(255, 255, 0), # Amarillo
            'bus': QColor(255, 0, 255),       # Magenta
            'truck': QColor(0, 255, 255),     # Cian
        }
        
        # Color por defecto para clases nuevas
        color = class_colors.get(current_class, QColor(128, 128, 128))
        
        # Dibujar borde resaltado
        pen = QPen(color, 8)
        painter.setPen(pen)
        
        # Dibujar rectángulo en el borde de la imagen
        rect = QRect(4, 4, highlighted_pixmap.width() - 8, highlighted_pixmap.height() - 8)
        painter.drawRect(rect)
        
        # Agregar texto con la clase
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.setFont(QFont("Arial", 16, QFont.Bold))
        
        text_rect = QRect(10, 10, highlighted_pixmap.width() - 20, 40)
        painter.fillRect(text_rect, QColor(0, 0, 0, 180))  # Fondo semi-transparente
        painter.drawText(text_rect, Qt.AlignCenter, current_class.upper())
        
        painter.end()
        return highlighted_pixmap
    
    def show_previous(self):
        """Mostrar crop anterior"""
        if self.current_index > 0:
            self.current_index -= 1
            self.show_current_crop()
    
    def show_next(self):
        """Mostrar crop siguiente"""
        if self.current_index < len(self.current_crops) - 1:
            self.current_index += 1
            self.show_current_crop()
    
    def quick_classify(self, class_name: str):
        """Clasificación rápida con botones"""
        self.class_combo.setCurrentText(class_name)
        self.on_classification_changed()
        
        # Avanzar automáticamente al siguiente
        if self.current_index < len(self.current_crops) - 1:
            self.show_next()
    
    def on_classification_changed(self):
        """Manejar cambio en la clasificación"""
        if not self.current_crops:
            return
            
        current_crop = self.current_crops[self.current_index]
        new_class = self.class_combo.currentText()
        
        # Actualizar el crop con la nueva clasificación
        current_crop['manual_classification'] = new_class
        
        # Actualizar la imagen con el nuevo resaltado
        self.update_current_image()
        
        # Marcar como cambiado si es diferente a la original
        crop_id = current_crop['id']
        original_class = current_crop['detection_class']
        
        # Buscar si ya hay un cambio registrado para este crop
        existing_change = None
        for i, change in enumerate(self.classifications_changed):
            if change['crop_id'] == crop_id:
                existing_change = i
                break
        
        if new_class != original_class:
            change_data = {
                'crop_id': crop_id,
                'new_class': new_class,
                'crop_type': 'all' if 'frame_number' in current_crop else 'od'
            }
            
            if existing_change is not None:
                self.classifications_changed[existing_change] = change_data
            else:
                self.classifications_changed.append(change_data)
        else:
            # Remover cambio si se volvió a la clasificación original
            if existing_change is not None:
                self.classifications_changed.pop(existing_change)
        
        # Habilitar botón de guardar si hay cambios
        self.save_button.setEnabled(len(self.classifications_changed) > 0)
        
    def update_current_image(self):
        """Actualizar la imagen actual con el resaltado"""
        if not self.current_crops or self.current_index >= len(self.current_crops):
            return
            
        crop_data = self.current_crops[self.current_index]
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
        
        if crop_path and crop_path.exists():
            pixmap = QPixmap(str(crop_path))
            if not pixmap.isNull():
                # Crear una copia para dibujar el resaltado
                highlighted_pixmap = self.add_class_highlight(pixmap, crop_data)
                
                # Escalar imagen manteniendo aspecto
                scaled_pixmap = highlighted_pixmap.scaled(
                    self.image_label.size(), 
                    Qt.KeepAspectRatio, 
                    Qt.SmoothTransformation
                )
                self.image_label.setPixmap(scaled_pixmap)
    
    def save_classifications(self):
        """Guardar las clasificaciones manuales"""
        if not self.classifications_changed:
            return
            
        try:
            for change in self.classifications_changed:
                self.crop_manager.update_manual_classification(
                    change['crop_id'],
                    change['new_class'],
                    change['crop_type'],
                    verified=True
                )
            
            QMessageBox.information(
                self, 
                "Éxito", 
                f"Se guardaron {len(self.classifications_changed)} clasificaciones manuales."
            )
            
            # Recargar crops no verificados
            self.load_unverified_crops()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error guardando clasificaciones: {e}")


class DatabaseUpdateThread(QThread):
    """Hilo para actualizar la base de datos principal"""
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, crop_manager, main_db_path):
        super().__init__()
        self.crop_manager = crop_manager
        self.main_db_path = main_db_path
    
    def run(self):
        """Ejecutar actualización de base de datos"""
        try:
            import sqlite3
            
            # Obtener clasificaciones manuales verificadas
            with sqlite3.connect(self.crop_manager.crops_db_path) as crops_conn:
                cursor = crops_conn.cursor()
                
                # Obtener cambios de crops O/D (estos afectan VehicleCounts)
                cursor.execute("""
                    SELECT object_id, origin_frame, destination_frame, 
                           detection_class, manual_classification
                    FROM OdCrops 
                    WHERE manual_classification IS NOT NULL AND verified = TRUE
                """)
                
                od_updates = cursor.fetchall()
            
            if not od_updates:
                self.finished.emit("No hay clasificaciones manuales para aplicar.")
                return
            
            # Actualizar base de datos principal
            with sqlite3.connect(self.main_db_path) as main_conn:
                cursor = main_conn.cursor()
                
                updated_count = 0
                for object_id, origin_frame, dest_frame, old_class, new_class in od_updates:
                    # Actualizar registros en VehicleCounts
                    cursor.execute("""
                        UPDATE VehicleCounts 
                        SET vehicle_type = ?
                        WHERE origin_frame = ? AND destination_frame = ?
                    """, (new_class, origin_frame, dest_frame))
                    
                    if cursor.rowcount > 0:
                        updated_count += cursor.rowcount
                
                main_conn.commit()
            
            self.finished.emit(f"Se actualizaron {updated_count} registros en la base de datos principal.")
            
        except Exception as e:
            self.error.emit(f"Error actualizando base de datos: {e}")


class YoloRetrainingDialog(QDialog):
    """Diálogo para reentrenar modelo YOLO"""
    
    def __init__(self, crop_manager, parent=None):
        super().__init__(parent)
        self.crop_manager = crop_manager
        
        self.setWindowTitle("Reentrenar Modelo YOLO")
        self.setMinimumSize(600, 400)
        
        self.init_ui()
    
    def init_ui(self):
        """Inicializar interfaz"""
        layout = QVBoxLayout()
        
        # Información
        info_label = QLabel("""
        Esta función preparará los datos de los crops clasificados manualmente
        para reentrenar el modelo YOLO. Se creará un dataset en formato YOLO
        con las clasificaciones corregidas.
        """)
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Estadísticas
        stats_group = QGroupBox("Estadísticas de Crops")
        stats_layout = QVBoxLayout()
        
        self.stats_label = QLabel("Cargando estadísticas...")
        stats_layout.addWidget(self.stats_label)
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        # Parámetros de entrenamiento
        params_group = QGroupBox("Parámetros de Reentrenamiento")
        params_layout = QVBoxLayout()
        
        epochs_layout = QHBoxLayout()
        epochs_layout.addWidget(QLabel("Épocas:"))
        self.epochs_spin = QSpinBox()
        self.epochs_spin.setRange(1, 1000)
        self.epochs_spin.setValue(50)
        epochs_layout.addWidget(self.epochs_spin)
        params_layout.addLayout(epochs_layout)
        
        self.use_verified_only = QCheckBox("Solo usar crops verificados manualmente")
        self.use_verified_only.setChecked(True)
        params_layout.addWidget(self.use_verified_only)
        
        params_group.setLayout(params_layout)
        layout.addWidget(params_group)
        
        # Botones
        button_layout = QHBoxLayout()
        
        self.prepare_button = QPushButton("Preparar Dataset")
        self.prepare_button.clicked.connect(self.prepare_dataset)
        
        self.train_button = QPushButton("Iniciar Entrenamiento")
        self.train_button.clicked.connect(self.start_training)
        self.train_button.setEnabled(False)
        
        self.close_button = QPushButton("Cerrar")
        self.close_button.clicked.connect(self.accept)
        
        button_layout.addWidget(self.prepare_button)
        button_layout.addWidget(self.train_button)
        button_layout.addWidget(self.close_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        self.load_statistics()
    
    def load_statistics(self):
        """Cargar estadísticas de crops"""
        try:
            stats = self.crop_manager.get_crop_statistics()
            
            stats_text = "Crops de detecciones generales:\n"
            for class_name, total, verified in stats['all_crops']:
                stats_text += f"  {class_name}: {total} total, {verified} verificados\n"
            
            stats_text += "\nCrops de cruces O/D:\n"
            for class_name, total, verified in stats['od_crops']:
                stats_text += f"  {class_name}: {total} total, {verified} verificados\n"
            
            self.stats_label.setText(stats_text)
            
        except Exception as e:
            self.stats_label.setText(f"Error cargando estadísticas: {e}")
    
    def prepare_dataset(self):
        """Preparar dataset para reentrenamiento"""
        QMessageBox.information(self, "Información", 
                               "Funcionalidad de preparación de dataset en desarrollo.")
        self.train_button.setEnabled(True)
    
    def start_training(self):
        """Iniciar entrenamiento del modelo"""
        QMessageBox.information(self, "Información", 
                               "Funcionalidad de reentrenamiento en desarrollo.")