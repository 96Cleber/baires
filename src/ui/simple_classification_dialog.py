"""
Diálogo simple para clasificación manual de crops con lista desplegable
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QComboBox, QScrollArea, QWidget, 
                            QMessageBox, QGroupBox, QCheckBox, 
                            QGridLayout, QListWidget, QListWidgetItem, QErrorMessage)
from PyQt5.QtGui import QPixmap, QFont, QIcon
from PyQt5.QtCore import Qt, QSize
import os
from pathlib import Path
from typing import List, Dict, Optional


class SimpleClassificationDialog(QDialog):
    """Diálogo simple para clasificación manual rápida"""
    
    def __init__(self, crop_manager, default_typologies: list[str], additional_typologies: list[str], parent=None):
        super().__init__(parent)
        self.crop_manager = crop_manager
        self.current_images = []
        self.changes_made = 0

        # Mapeo de nombres en inglés (carpetas) a español (interfaz)
        self.english_to_spanish = {
            'person': 'Persona',
            'bicycle': 'Bicicleta',
            'car': 'Auto',
            'motorcycle': 'Moto',
            'bus': 'Bus',
            'truck': 'Camion',
            'camioneta': 'Camioneta',
            'microbus': 'Microbus',
            'mototaxi': 'Mototaxi',
            'omnibus': 'Omnibus',
            'remolque': 'Remolque',
            'taxi': 'Taxi',
            'trailer': 'Trailer',
            'otros': 'Otros',
        }

        # Nombres en español que deben ignorarse (usar versión inglés)
        self.spanish_duplicates = {'auto', 'moto', 'persona', 'bicicleta', 'camion'}

        # Detectar carpetas existentes en crops_od y crops_all
        existing_classes = set()
        for crops_dir in [self.crop_manager.od_crops_dir, self.crop_manager.all_crops_dir]:
            if crops_dir.exists():
                for subdir in crops_dir.iterdir():
                    if subdir.is_dir():
                        folder_name = subdir.name.lower()
                        # Ignorar carpetas con nombres en español si ya existe la versión inglés
                        if folder_name not in self.spanish_duplicates:
                            existing_classes.add(folder_name)

        # Crear mapeo de clases: key = nombre carpeta (inglés), value = nombre mostrado (español)
        self.class_labels = {}
        for cls in existing_classes:
            display_name = self.english_to_spanish.get(cls, cls.title())
            self.class_labels[cls] = display_name

        # Si no hay carpetas, usar las clases por defecto
        if not self.class_labels:
            self.class_labels = dict(self.english_to_spanish)

        self.available_classes = list(self.class_labels.keys())
        self.selected_class = 'car' if 'car' in self.available_classes else (self.available_classes[0] if self.available_classes else 'car')

        self.setWindowTitle("Clasificación Manual Rápida")
        self.setMinimumSize(800, 600)
        
        self.init_ui()
        self.load_class_images()
    
    def init_ui(self):
        """Inicializar interfaz de usuario"""
        layout = QVBoxLayout()
        
        # Controles superiores
        controls_layout = QHBoxLayout()
        
        # Selector de clase
        controls_layout.addWidget(QLabel("Clase:"))

        self.class_combo = QComboBox()
        for class_name, display_name in self.class_labels.items():
            self.class_combo.addItem(display_name, class_name)

        # Establecer "Auto" como selección por defecto
        default_index = self.class_combo.findData('auto')
        if default_index >= 0:
            self.class_combo.setCurrentIndex(default_index)
        
        self.class_combo.currentTextChanged.connect(self.on_class_changed)
        controls_layout.addWidget(self.class_combo)
        
        # Filtros de tipo
        self.all_crops_cb = QCheckBox("Detecciones generales")
        self.all_crops_cb.setChecked(True)
        self.all_crops_cb.toggled.connect(self.load_class_images)
        
        self.od_crops_cb = QCheckBox("Cruces O/D")
        self.od_crops_cb.setChecked(True)
        self.od_crops_cb.toggled.connect(self.load_class_images)
        
        controls_layout.addWidget(self.all_crops_cb)
        controls_layout.addWidget(self.od_crops_cb)
        
        # Info de cambios
        self.changes_label = QLabel("0 cambios realizados")
        controls_layout.addWidget(self.changes_label)
        
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        
        # Lista de imágenes con selección múltiple
        self.image_list = QListWidget()
        self.image_list.setViewMode(QListWidget.IconMode)
        self.image_list.setIconSize(QSize(120, 120))
        self.image_list.setResizeMode(QListWidget.Adjust)
        self.image_list.setSpacing(10)
        # Habilitar selección múltiple con Ctrl/Shift
        self.image_list.setSelectionMode(QListWidget.ExtendedSelection)
        # Conectar señal de cambio de selección en lugar de click
        self.image_list.itemSelectionChanged.connect(self.on_selection_changed)

        layout.addWidget(self.image_list)

        # Información de selección múltiple
        selection_info_layout = QHBoxLayout()
        self.selection_info_label = QLabel("Ninguna imagen seleccionada")
        self.selection_info_label.setStyleSheet("color: #0078d4; font-weight: bold; font-size: 11pt;")
        selection_info_layout.addWidget(self.selection_info_label)

        self.clear_selection_button = QPushButton("Limpiar Selección")
        self.clear_selection_button.clicked.connect(self.clear_selection)
        self.clear_selection_button.setEnabled(False)
        selection_info_layout.addWidget(self.clear_selection_button)

        selection_info_layout.addStretch()
        layout.addLayout(selection_info_layout)
        
        # Selector de nueva clase
        reclassify_group = QGroupBox("Reclasificar Seleccionadas Como")
        reclassify_layout = QHBoxLayout()
        reclassify_layout.addWidget(QLabel("Seleccionar nueva clase:"))

        self.target_class_combo = QComboBox()
        self.target_class_combo.addItem("-- Seleccionar clase --", None)
        for class_name, display_name in self.class_labels.items():
            self.target_class_combo.addItem(display_name, class_name)

        self.target_class_combo.currentTextChanged.connect(self.on_target_class_changed)
        reclassify_layout.addWidget(self.target_class_combo)

        self.reclassify_button = QPushButton("Aplicar a Seleccionadas")
        self.reclassify_button.clicked.connect(self.reclassify_selected_images)
        self.reclassify_button.setEnabled(False)
        reclassify_layout.addWidget(self.reclassify_button)

        reclassify_layout.addStretch()
        reclassify_group.setLayout(reclassify_layout)
        layout.addWidget(reclassify_group)
        
        # Botones
        button_layout = QHBoxLayout()
        
        self.close_button = QPushButton("Cerrar")
        self.close_button.clicked.connect(self.accept)
        
        button_layout.addWidget(self.close_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def on_class_changed(self):
        """Cambio de clase seleccionada"""
        selected_data = self.class_combo.currentData()
        if selected_data:
            self.selected_class = selected_data
            self.load_class_images()
    
    def load_class_images(self):
        """Cargar imágenes de la clase seleccionada"""
        try:
            # Limpiar selección al cambiar de clase
            self.image_list.clearSelection()
            self.image_list.clear()
            self.current_images.clear()

            selected_class = self.selected_class
            if not selected_class:
                return

            # Extensiones de imagen soportadas
            image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.bmp']

            # Buscar imágenes en las carpetas
            image_paths = []

            if self.all_crops_cb.isChecked():
                all_class_dir = self.crop_manager.all_crops_dir / selected_class
                if all_class_dir.exists():
                    for ext in image_extensions:
                        for img_file in all_class_dir.glob(ext):
                            image_paths.append({
                                'path': img_file,
                                'filename': img_file.name,
                                'type': 'all',
                                'current_class': selected_class
                            })

            if self.od_crops_cb.isChecked():
                od_class_dir = self.crop_manager.od_crops_dir / selected_class
                if od_class_dir.exists():
                    for ext in image_extensions:
                        for img_file in od_class_dir.glob(ext):
                            image_paths.append({
                                'path': img_file,
                                'filename': img_file.name,
                                'type': 'od',
                                'current_class': selected_class
                            })
            
            self.current_images = image_paths
            
            # Crear items en la lista
            for img_data in image_paths:
                if img_data['path'].exists():
                    pixmap = QPixmap(str(img_data['path']))
                    if not pixmap.isNull():
                        # Escalar la imagen (FastTransformation para mejor rendimiento)
                        scaled_pixmap = pixmap.scaled(
                            120, 120,
                            Qt.KeepAspectRatio,
                            Qt.FastTransformation
                        )
                        
                        # Crear item
                        item = QListWidgetItem()
                        item.setIcon(QIcon(scaled_pixmap))
                        item.setText(img_data['filename'])
                        item.setToolTip(f"Archivo: {img_data['filename']}\\nTipo: {img_data['type']}")
                        item.setData(Qt.UserRole, img_data)
                        
                        self.image_list.addItem(item)
            
            # Actualizar contador
            class_display = self.class_labels.get(selected_class, selected_class.title())
            self.setWindowTitle(f"Clasificación Manual - {class_display} ({len(image_paths)} imágenes)")

            # Actualizar UI de selección
            self.on_selection_changed()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error cargando imágenes: {e}")
    
    def on_selection_changed(self):
        """Actualizar UI cuando cambia la selección"""
        selected_items = self.image_list.selectedItems()
        count = len(selected_items)

        if count == 0:
            self.selection_info_label.setText("Ninguna imagen seleccionada")
            self.clear_selection_button.setEnabled(False)
            self.reclassify_button.setEnabled(False)
        elif count == 1:
            self.selection_info_label.setText("1 imagen seleccionada")
            self.clear_selection_button.setEnabled(True)
            # Habilitar botón solo si hay clase destino seleccionada
            self.reclassify_button.setEnabled(self.target_class_combo.currentData() is not None)
        else:
            self.selection_info_label.setText(f"{count} imágenes seleccionadas")
            self.clear_selection_button.setEnabled(True)
            # Habilitar botón solo si hay clase destino seleccionada
            self.reclassify_button.setEnabled(self.target_class_combo.currentData() is not None)

    def clear_selection(self):
        """Limpiar toda la selección"""
        self.image_list.clearSelection()

    def on_target_class_changed(self):
        """Cuando cambia la clase destino"""
        selected_count = len(self.image_list.selectedItems())
        has_target = self.target_class_combo.currentData() is not None
        self.reclassify_button.setEnabled(selected_count > 0 and has_target)

    def reclassify_selected_images(self):
        """Reclasificar las imágenes seleccionadas"""
        selected_items = self.image_list.selectedItems()

        if not selected_items:
            QMessageBox.warning(
                self,
                "Advertencia",
                "No hay imágenes seleccionadas.\n\nUse Ctrl+Click para seleccionar múltiples imágenes o Shift+Click para seleccionar un rango."
            )
            return

        target_class = self.target_class_combo.currentData()
        if not target_class:
            QMessageBox.warning(self, "Advertencia", "Seleccione una clase de destino.")
            return

        count = len(selected_items)
        target_display = self.class_labels.get(target_class, target_class.title())

        # Confirmar acción
        reply = QMessageBox.question(
            self,
            'Confirmar Reclasificación',
            f'¿Reclasificar {count} imagen(es) seleccionada(s) como {target_display}?',
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # Usar UNA sola conexión SQLite para todas las actualizaciones
            import sqlite3

            try:
                with sqlite3.connect(self.crop_manager.crops_db_path) as conn:
                    cursor = conn.cursor()
                    success_count = 0

                    # Reclasificar todas las imágenes en una sola transacción
                    for item in selected_items:
                        img_data = item.data(Qt.UserRole)
                        if img_data:
                            try:
                                # Mover archivo físico
                                old_path = img_data['path']

                                if img_data['type'] == 'all':
                                    new_dir = self.crop_manager.all_crops_dir / target_class
                                else:
                                    new_dir = self.crop_manager.od_crops_dir / target_class

                                new_dir.mkdir(exist_ok=True)
                                new_path = new_dir / img_data['filename']
                                old_path.rename(new_path)

                                # Actualizar BD (sin abrir nueva conexión)
                                table = 'AllCrops' if img_data['type'] == 'all' else 'OdCrops'
                                cursor.execute(f"""
                                    UPDATE {table}
                                    SET manual_classification = ?, verified = TRUE
                                    WHERE crop_filename = ?
                                """, (target_class, img_data['filename']))

                                success_count += 1
                            except Exception as e:
                                print(f"Error reclasificando {img_data['filename']}: {e}")

                    # UN SOLO commit para todas las operaciones
                    conn.commit()

                # Actualizar contador de cambios
                self.changes_made += success_count
                self.changes_label.setText(f"{self.changes_made} cambios realizados")

                # Remover solo los items reclasificados (Optimización 2 - no recargar todo)
                for item in selected_items:
                    row = self.image_list.row(item)
                    if row >= 0:
                        self.image_list.takeItem(row)

                # Actualizar título con el nuevo conteo
                remaining = self.image_list.count()
                class_display = self.class_labels.get(self.selected_class, self.selected_class.title())
                self.setWindowTitle(f"Clasificación Manual - {class_display} ({remaining} imágenes)")

                # Limpiar selección y resetear combo
                self.image_list.clearSelection()
                self.target_class_combo.setCurrentIndex(0)

                # Actualizar UI de selección
                self.on_selection_changed()

                QMessageBox.information(
                    self,
                    "Éxito",
                    f"{success_count} imagen(es) reclasificada(s) exitosamente como {target_display}"
                )
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error en reclasificación masiva: {e}")
    
    def reclassify_image_silent(self, img_data, new_class):
        """Reclasificar una imagen sin mostrar mensajes (para reclasificación masiva)"""
        old_path = img_data['path']

        # Determinar directorio destino
        if img_data['type'] == 'all':
            new_dir = self.crop_manager.all_crops_dir / new_class
        else:
            new_dir = self.crop_manager.od_crops_dir / new_class

        new_dir.mkdir(exist_ok=True)
        new_path = new_dir / img_data['filename']

        # Mover archivo
        old_path.rename(new_path)

        # Actualizar base de datos
        self.update_crop_in_database(img_data['filename'], new_class, img_data['type'])

    def reclassify_image(self, img_data, new_class):
        """Reclasificar una imagen (versión original - no se usa actualmente)"""
        try:
            self.reclassify_image_silent(img_data, new_class)

            # Incrementar contador de cambios
            self.changes_made += 1
            self.changes_label.setText(f"{self.changes_made} cambios realizados")

            # Recargar vista
            self.load_class_images()

            QMessageBox.information(
                self,
                "Éxito",
                f'Imagen reclasificada a {self.class_labels.get(new_class, new_class.title())}'
            )

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error reclasificando imagen: {e}")
    
    def update_crop_in_database(self, filename, new_class, crop_type):
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