# -*- coding: utf-8 -*-
"""
FlowVisionAI Lite - Solo clasificacion de crops
Punto de entrada ligero sin dependencias pesadas (YOLO, PyTorch)
"""

import sys
import os
from pathlib import Path


def get_resource_path(relative_path: str) -> str:
    """Obtener ruta de recurso, compatible con PyInstaller"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), relative_path)


TYPOLOGIES_PATH = get_resource_path("templates/tipologias.txt")


def load_typologies() -> list:
    """Cargar tipologias desde archivo"""
    typologies = []
    try:
        if os.path.exists(TYPOLOGIES_PATH):
            with open(TYPOLOGIES_PATH, "r", encoding='utf-8') as f:
                for line in f:
                    clean = line.strip()
                    if clean and not clean.startswith("#"):
                        typologies.append(clean)
    except Exception:
        pass

    if not typologies:
        typologies = [
            "Auto", "Bicicleta", "Bus", "Camion", "Camioneta",
            "Combi", "Microbus", "Moto", "Mototaxi", "Omnibus",
            "Persona", "Remolque", "Taxi", "Trailer", "Otros"
        ]
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
    found.sort(key=lambda x: x.name)
    return found


def main():
    from PyQt5.QtWidgets import (QApplication, QMainWindow, QFileDialog,
                                  QVBoxLayout, QHBoxLayout, QPushButton,
                                  QWidget, QLabel, QMessageBox, QFrame)
    from PyQt5.QtGui import QFont
    from PyQt5.QtCore import Qt

    from ui.classification_gallery_dialog import ClassificationGalleryDialog

    class LiteMainWindow(QMainWindow):
        """Ventana principal de FlowVisionAI Lite"""

        def __init__(self):
            super().__init__()
            self.crop_folders = []
            self.init_ui()

        def init_ui(self):
            """Inicializar interfaz"""
            self.setWindowTitle("FlowVisionAI Lite - Clasificacion de Crops")
            self.setMinimumSize(600, 400)

            central = QWidget()
            self.setCentralWidget(central)
            layout = QVBoxLayout(central)
            layout.setSpacing(20)
            layout.setContentsMargins(40, 40, 40, 40)

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

            layout.addSpacing(20)

            # Separador
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setStyleSheet("background-color: #ddd;")
            layout.addWidget(line)

            layout.addSpacing(20)

            # Estado actual
            self.status_label = QLabel("No hay carpetas cargadas")
            self.status_label.setAlignment(Qt.AlignCenter)
            self.status_label.setStyleSheet("color: #888; font-style: italic;")
            self.status_label.setWordWrap(True)
            layout.addWidget(self.status_label)

            layout.addSpacing(20)

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

            layout.addStretch()

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

            # Contar imagenes totales
            total_images = 0
            for crop_folder in self.crop_folders:
                for subdir in crop_folder.iterdir():
                    if subdir.is_dir():
                        total_images += len(list(subdir.glob("*.jpg")))
                        total_images += len(list(subdir.glob("*.png")))

            folder_names = [f.name for f in self.crop_folders[:5]]
            self.status_label.setText(
                f"Carpetas encontradas: {len(self.crop_folders)}\n"
                f"({', '.join(folder_names)}{'...' if len(self.crop_folders) > 5 else ''})\n"
                f"Total de imagenes: {total_images}"
            )
            self.status_label.setStyleSheet("color: #28a745; font-weight: bold;")
            self.classify_btn.setEnabled(True)

        def open_classifier(self):
            """Abrir dialogo de clasificacion"""
            if not self.crop_folders:
                QMessageBox.warning(self, "Error", "Primero cargue carpetas de crops")
                return

            typologies = load_typologies()

            dialog = ClassificationGalleryDialog(
                crop_folders=self.crop_folders,
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
