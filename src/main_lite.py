# -*- coding: utf-8 -*-
"""
FlowVisionAI Lite - Solo clasificacion de crops
Punto de entrada ligero sin dependencias pesadas (YOLO, PyTorch)
"""

import sys
import os
from pathlib import Path
from typing import Dict, List, Optional


def get_resource_path(relative_path: str) -> str:
    """Obtener ruta de recurso, compatible con PyInstaller"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), relative_path)


# Agregar path para importar módulo de tipologías
sys.path.insert(0, os.path.dirname(__file__))
from tools.typologies import get_typologies, get_default_typologies


def load_typologies() -> list:
    """Cargar tipologias desde archivo usando el módulo centralizado"""
    typologies = get_typologies()
    if not typologies:
        typologies = get_default_typologies()
    return typologies


def find_crop_folders_recursive(parent_folder: str, pattern_start: str = "hiv",
                                 pattern_end: str = "_crops_od") -> list:
    """Buscar recursivamente carpetas que coincidan con el patron."""
    found = []
    parent_path = Path(parent_folder).resolve()

    def search(folder: Path):
        try:
            for item in folder.iterdir():
                if item.is_dir():
                    name = item.name.lower()
                    if name.startswith(pattern_start.lower()) and name.endswith(pattern_end.lower()):
                        found.append(item)
                    else:
                        search(item)
        except PermissionError:
            pass

    search(parent_path)
    found.sort(key=lambda x: str(x))  # Ordenar por ruta completa
    return found


def count_images_in_folder(folder: Path) -> tuple:
    """Contar imágenes en una carpeta de crops

    Returns:
        Tupla (total, validadas) con el conteo de imágenes
    """
    total = 0
    validated = 0
    try:
        for subdir in folder.iterdir():
            if subdir.is_dir():
                # Saltar la carpeta validados para el conteo de pendientes
                if subdir.name == "validados":
                    continue

                # Contar imágenes pendientes
                total += len(list(subdir.glob("*.jpg")))
                total += len(list(subdir.glob("*.png")))

                # Contar imágenes validadas en subcarpeta validados/
                validated_dir = subdir / "validados"
                if validated_dir.exists():
                    validated += len(list(validated_dir.glob("*.jpg")))
                    validated += len(list(validated_dir.glob("*.png")))
    except Exception:
        pass

    # El total incluye tanto pendientes como validadas
    total_all = total + validated
    return total_all, validated


def build_folder_tree(folders: List[Path], root_folder: Path) -> Dict:
    """
    Construir estructura de árbol desde lista de carpetas.

    Args:
        folders: Lista de carpetas crops_od encontradas
        root_folder: Carpeta raíz seleccionada por el usuario

    Returns:
        Diccionario con estructura de árbol
    """
    tree = {}

    for folder in folders:
        # Obtener ruta relativa desde la carpeta raíz
        try:
            rel_path = folder.relative_to(root_folder)
        except ValueError:
            rel_path = Path(folder.name)

        parts = rel_path.parts
        current = tree

        # Construir ramas del árbol
        for i, part in enumerate(parts):
            if part not in current:
                is_leaf = (i == len(parts) - 1)
                current[part] = {
                    '_is_leaf': is_leaf,
                    '_path': folder if is_leaf else root_folder / Path(*parts[:i+1]),
                    '_children': {}
                }
            current = current[part]['_children']

    return tree


def main():
    from PyQt5.QtWidgets import (QApplication, QMainWindow, QFileDialog,
                                  QVBoxLayout, QHBoxLayout, QPushButton,
                                  QWidget, QLabel, QMessageBox, QFrame,
                                  QTreeWidget, QTreeWidgetItem, QHeaderView,
                                  QCheckBox)
    from PyQt5.QtGui import QFont, QColor
    from PyQt5.QtCore import Qt

    from ui.classification_gallery_dialog import ClassificationGalleryDialog

    class LiteMainWindow(QMainWindow):
        """Ventana principal de FlowVisionAI Lite"""

        def __init__(self):
            super().__init__()
            self.crop_folders = []  # Todas las carpetas encontradas (hojas)
            self.root_folder = None  # Carpeta raíz seleccionada
            self.leaf_items = []  # Lista de QTreeWidgetItem que son hojas (crops_od)
            self.init_ui()

        def init_ui(self):
            """Inicializar interfaz"""
            self.setWindowTitle("FlowVisionAI Lite - Clasificacion de Crops")
            self.setMinimumSize(750, 550)

            central = QWidget()
            self.setCentralWidget(central)
            layout = QVBoxLayout(central)
            layout.setSpacing(15)
            layout.setContentsMargins(40, 30, 40, 30)

            # Titulo
            title = QLabel("FlowVisionAI Lite")
            title.setFont(QFont("Arial", 24, QFont.Bold))
            title.setAlignment(Qt.AlignCenter)
            layout.addWidget(title)

            subtitle = QLabel("Clasificacion manual de crops")
            subtitle.setFont(QFont("Arial", 12))
            subtitle.setAlignment(Qt.AlignCenter)
            subtitle.setStyleSheet("color: #666;")
            layout.addWidget(subtitle)

            # Separador
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setStyleSheet("background-color: #ddd;")
            layout.addWidget(line)

            # Checkbox "Seleccionar todas"
            self.select_all_cb = QCheckBox("Seleccionar todas")
            self.select_all_cb.setFont(QFont("Arial", 10, QFont.Bold))
            self.select_all_cb.setChecked(True)
            self.select_all_cb.toggled.connect(self.toggle_select_all)
            self.select_all_cb.setVisible(False)
            layout.addWidget(self.select_all_cb)

            # Árbol de carpetas
            self.tree_widget = QTreeWidget()
            self.tree_widget.setHeaderLabels(["Carpeta", "Imágenes", "Validadas"])
            self.tree_widget.setMinimumHeight(250)
            self.tree_widget.setMaximumHeight(350)
            self.tree_widget.setStyleSheet("""
                QTreeWidget {
                    border: 1px solid #ccc;
                    border-radius: 5px;
                    background-color: #fafafa;
                    font-size: 11px;
                }
                QTreeWidget::item {
                    padding: 4px;
                }
                QTreeWidget::item:hover {
                    background-color: #e8f4fc;
                }
            """)
            self.tree_widget.setVisible(False)
            self.tree_widget.itemChanged.connect(self.on_item_changed)

            # Configurar columnas
            header = self.tree_widget.header()
            header.setStretchLastSection(False)
            header.setSectionResizeMode(0, QHeaderView.Stretch)
            header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeToContents)

            layout.addWidget(self.tree_widget)

            # Label de estado/resumen
            self.status_label = QLabel("No hay carpetas cargadas")
            self.status_label.setAlignment(Qt.AlignCenter)
            self.status_label.setStyleSheet("color: #888; font-style: italic;")
            self.status_label.setWordWrap(True)
            layout.addWidget(self.status_label)

            # Botones
            btn_layout = QHBoxLayout()
            btn_layout.addStretch()

            self.load_btn = QPushButton("Cargar Carpetas (hiv*_crops_od)")
            self.load_btn.setMinimumSize(280, 50)
            self.load_btn.setFont(QFont("Arial", 11))
            self.load_btn.setStyleSheet("""
                QPushButton {
                    background-color: #0078d4;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    padding: 10px 20px;
                }
                QPushButton:hover {
                    background-color: #006cbd;
                }
                QPushButton:pressed {
                    background-color: #005a9e;
                }
            """)
            self.load_btn.clicked.connect(self.load_crop_folders)
            btn_layout.addWidget(self.load_btn)

            self.classify_btn = QPushButton("Abrir Clasificador")
            self.classify_btn.setMinimumSize(200, 50)
            self.classify_btn.setFont(QFont("Arial", 11))
            self.classify_btn.setEnabled(False)
            self.classify_btn.setStyleSheet("""
                QPushButton {
                    background-color: #28a745;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    padding: 10px 20px;
                }
                QPushButton:hover {
                    background-color: #218838;
                }
                QPushButton:pressed {
                    background-color: #1e7e34;
                }
                QPushButton:disabled {
                    background-color: #cccccc;
                    color: #888888;
                }
            """)
            self.classify_btn.clicked.connect(self.open_classifier)
            btn_layout.addWidget(self.classify_btn)

            btn_layout.addStretch()
            layout.addLayout(btn_layout)

            # Info
            info_label = QLabel("Version Lite: Solo clasificacion de crops (sin procesamiento de video)")
            info_label.setAlignment(Qt.AlignCenter)
            info_label.setStyleSheet("color: #aaa; font-size: 10px;")
            layout.addWidget(info_label)

        def load_crop_folders(self):
            """Cargar carpetas de crops buscando recursivamente"""
            folder = QFileDialog.getExistingDirectory(
                self,
                "Seleccionar carpeta padre (busca hiv*_crops_od recursivamente)",
                "",
                QFileDialog.ShowDirsOnly
            )

            if not folder:
                return

            self.root_folder = Path(folder).resolve()

            # Buscar carpetas recursivamente
            self.crop_folders = find_crop_folders_recursive(folder)

            if not self.crop_folders:
                QMessageBox.warning(
                    self,
                    "Sin resultados",
                    "No se encontraron carpetas hiv*_crops_od.\n\n"
                    "Verifique que existan carpetas con ese patron."
                )
                return

            # Limpiar árbol anterior
            self.tree_widget.clear()
            self.leaf_items.clear()

            # Construir árbol
            tree_structure = build_folder_tree(self.crop_folders, self.root_folder)

            # Bloquear señales mientras construimos el árbol
            self.tree_widget.blockSignals(True)

            # Crear items del árbol
            self._populate_tree(tree_structure, self.tree_widget.invisibleRootItem())

            # Expandir todo
            self.tree_widget.expandAll()

            self.tree_widget.blockSignals(False)

            # Mostrar elementos
            self.select_all_cb.setVisible(True)
            self.select_all_cb.setChecked(True)
            self.tree_widget.setVisible(True)

            self.update_selection_summary()

        def _populate_tree(self, tree_dict: Dict, parent_item):
            """Poblar árbol recursivamente"""
            for name, data in sorted(tree_dict.items()):
                if name.startswith('_'):
                    continue

                item = QTreeWidgetItem(parent_item)
                item.setText(0, name)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsAutoTristate)
                item.setCheckState(0, Qt.Checked)

                # Guardar datos en el item
                item.setData(0, Qt.UserRole, data['_path'])
                item.setData(0, Qt.UserRole + 1, data['_is_leaf'])

                if data['_is_leaf']:
                    # Es una carpeta crops_od (hoja)
                    image_count, validated_count = count_images_in_folder(data['_path'])
                    item.setText(1, f"{image_count:,}")
                    item.setData(0, Qt.UserRole + 2, image_count)
                    item.setData(0, Qt.UserRole + 3, validated_count)  # Guardar validadas

                    # Mostrar porcentaje de validación
                    if image_count > 0:
                        percent = (validated_count / image_count) * 100
                        item.setText(2, f"{percent:.0f}% ({validated_count:,})")
                        # Color según porcentaje
                        if percent == 100:
                            item.setForeground(2, QColor("#28a745"))  # Verde
                        elif percent >= 50:
                            item.setForeground(2, QColor("#ffc107"))  # Amarillo
                        else:
                            item.setForeground(2, QColor("#dc3545"))  # Rojo
                    else:
                        item.setText(2, "0%")

                    self.leaf_items.append(item)
                else:
                    # Es una carpeta intermedia (rama)
                    item.setFont(0, QFont("Arial", 10, QFont.Bold))

                # Procesar hijos
                if data['_children']:
                    self._populate_tree(data['_children'], item)

                    # Calcular total de imágenes para carpetas intermedias
                    if not data['_is_leaf']:
                        total, validated = self._count_images_recursive(item)
                        item.setText(1, f"({total:,})")
                        if total > 0:
                            percent = (validated / total) * 100
                            item.setText(2, f"{percent:.0f}% ({validated:,})")
                            if percent == 100:
                                item.setForeground(2, QColor("#28a745"))
                            elif percent >= 50:
                                item.setForeground(2, QColor("#ffc107"))
                            else:
                                item.setForeground(2, QColor("#dc3545"))

        def _count_images_recursive(self, item: QTreeWidgetItem) -> tuple:
            """Contar imágenes en todos los hijos recursivamente

            Returns:
                Tupla (total, validadas)
            """
            total = 0
            validated = 0
            for i in range(item.childCount()):
                child = item.child(i)
                is_leaf = child.data(0, Qt.UserRole + 1)
                if is_leaf:
                    total += child.data(0, Qt.UserRole + 2) or 0
                    validated += child.data(0, Qt.UserRole + 3) or 0
                else:
                    child_total, child_validated = self._count_images_recursive(child)
                    total += child_total
                    validated += child_validated
            return total, validated

        def on_item_changed(self, item: QTreeWidgetItem, column: int):
            """Manejar cambio de estado de checkbox"""
            if column == 0:
                self.update_selection_summary()

        def toggle_select_all(self, checked: bool):
            """Seleccionar/deseleccionar todas las carpetas"""
            self.tree_widget.blockSignals(True)

            root = self.tree_widget.invisibleRootItem()
            state = Qt.Checked if checked else Qt.Unchecked

            for i in range(root.childCount()):
                self._set_check_state_recursive(root.child(i), state)

            self.tree_widget.blockSignals(False)
            self.update_selection_summary()

        def _set_check_state_recursive(self, item: QTreeWidgetItem, state: Qt.CheckState):
            """Establecer estado de checkbox recursivamente"""
            item.setCheckState(0, state)
            for i in range(item.childCount()):
                self._set_check_state_recursive(item.child(i), state)

        def update_selection_summary(self):
            """Actualizar resumen de selección"""
            selected_count = 0
            selected_images = 0
            selected_validated = 0
            total_count = len(self.leaf_items)
            total_images = 0
            total_validated = 0

            for item in self.leaf_items:
                image_count = item.data(0, Qt.UserRole + 2) or 0
                validated_count = item.data(0, Qt.UserRole + 3) or 0
                total_images += image_count
                total_validated += validated_count

                if item.checkState(0) == Qt.Checked:
                    selected_count += 1
                    selected_images += image_count
                    selected_validated += validated_count

            if selected_count > 0:
                # Calcular porcentaje de validación
                if selected_images > 0:
                    percent = (selected_validated / selected_images) * 100
                    validation_text = f"  •  Validadas: {percent:.1f}%"
                else:
                    validation_text = ""

                self.status_label.setText(
                    f"Seleccionadas: {selected_count}/{total_count} carpetas  •  "
                    f"{selected_images:,} imágenes{validation_text}"
                )
                self.status_label.setStyleSheet("color: #28a745; font-weight: bold;")
                self.classify_btn.setEnabled(True)
            else:
                # Calcular porcentaje total
                if total_images > 0:
                    percent = (total_validated / total_images) * 100
                    validation_text = f", {percent:.1f}% validadas"
                else:
                    validation_text = ""

                self.status_label.setText(
                    f"Ninguna carpeta seleccionada (Total: {total_count} carpetas, "
                    f"{total_images:,} imágenes{validation_text})"
                )
                self.status_label.setStyleSheet("color: #dc3545; font-weight: bold;")
                self.classify_btn.setEnabled(False)

            # Actualizar estado de "Seleccionar todas"
            self.select_all_cb.blockSignals(True)
            if selected_count == total_count and total_count > 0:
                self.select_all_cb.setChecked(True)
            elif selected_count == 0:
                self.select_all_cb.setChecked(False)
            self.select_all_cb.blockSignals(False)

        def get_selected_folders(self) -> list:
            """Obtener solo las carpetas seleccionadas (hojas marcadas)"""
            selected = []
            for item in self.leaf_items:
                if item.checkState(0) == Qt.Checked:
                    folder_path = item.data(0, Qt.UserRole)
                    if folder_path:
                        selected.append(folder_path)
            return selected

        def open_classifier(self):
            """Abrir dialogo de clasificacion"""
            selected_folders = self.get_selected_folders()

            if not selected_folders:
                QMessageBox.warning(self, "Error", "Seleccione al menos una carpeta")
                return

            typologies = load_typologies()

            dialog = ClassificationGalleryDialog(
                crop_folders=selected_folders,
                default_typologies=typologies,
                additional_typologies=[],
                parent=self
            )
            dialog.exec_()

    # Iniciar aplicacion
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = LiteMainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
