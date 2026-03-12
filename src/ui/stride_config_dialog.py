"""
Diálogo de configuración de Stride Adaptativo
Permite ajustar los parámetros de velocidad de procesamiento desde la UI
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QSpinBox, QPushButton, QGroupBox, QFormLayout)
from PyQt5.QtCore import Qt


class StrideConfigDialog(QDialog):
    """Diálogo para configurar parámetros de stride adaptativo"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_app = parent
        self.setWindowTitle("Configuración de Velocidad")
        self.setMinimumWidth(400)
        self.init_ui()

    def init_ui(self):
        """Inicializar interfaz"""
        layout = QVBoxLayout()

        # Grupo: Stride Adaptativo
        stride_group = QGroupBox("Stride Adaptativo (Velocidad)")
        stride_layout = QFormLayout()

        # Stride activo (con vehículos)
        self.stride_active_spin = QSpinBox()
        self.stride_active_spin.setMinimum(1)
        self.stride_active_spin.setMaximum(100)  # Aumentado de 50 a 100
        self.stride_active_spin.setValue(getattr(self.parent_app, 'detection_stride_active', 3))
        self.stride_active_spin.setToolTip("Procesar cada N frames CUANDO HAY vehículos detectados")
        stride_layout.addRow("Stride CON actividad:", self.stride_active_spin)

        # Stride inactivo (sin vehículos)
        self.stride_inactive_spin = QSpinBox()
        self.stride_inactive_spin.setMinimum(1)
        self.stride_inactive_spin.setMaximum(500)  # Aumentado de 100 a 500 para videos nocturnos
        self.stride_inactive_spin.setValue(getattr(self.parent_app, 'detection_stride_inactive', 15))
        self.stride_inactive_spin.setToolTip("Procesar cada N frames CUANDO NO HAY vehículos (AVANCE RÁPIDO)\nPara videos nocturnos: 200-400 frames")
        stride_layout.addRow("Stride SIN actividad:", self.stride_inactive_spin)

        # Threshold de cambio
        self.threshold_spin = QSpinBox()
        self.threshold_spin.setMinimum(1)
        self.threshold_spin.setMaximum(200)  # Aumentado de 100 a 200
        self.threshold_spin.setValue(getattr(self.parent_app, 'adaptive_stride_threshold', 10))
        self.threshold_spin.setToolTip("Frames sin detección antes de activar avance rápido")
        stride_layout.addRow("Frames para acelerar:", self.threshold_spin)

        stride_group.setLayout(stride_layout)
        layout.addWidget(stride_group)

        # Descripción
        help_label = QLabel(
            "<b>Guía de configuración:</b><br>"
            "<b>Stride CON actividad:</b> Frames a saltar cuando HAY vehículos (1-100)<br>"
            "<b>Stride SIN actividad:</b> Frames a saltar cuando NO HAY vehículos (1-500)<br>"
            "<b>Frames para acelerar:</b> Qué tan pronto activar avance rápido (1-200)<br><br>"
            "<b>Presets recomendados:</b><br>"
            "• Balance: 3, 15, 10 (tráfico normal diurno)<br>"
            "• Rápido: 5, 30, 5 (tráfico moderado)<br>"
            "• Muy rápido: 10, 50, 3 (poco tráfico)<br>"
            "• Nocturno: 10, 200, 5 (videos nocturnos con poca actividad)<br>"
            "• Ultra rápido: 20, 400, 3 (casi sin actividad)"
        )
        help_label.setWordWrap(True)
        layout.addWidget(help_label)

        # Botones presets - Primera fila
        preset_layout1 = QHBoxLayout()

        balance_btn = QPushButton("Balance")
        balance_btn.setToolTip("Tráfico normal diurno (3, 15, 10)")
        balance_btn.clicked.connect(lambda: self.apply_preset(3, 15, 10))
        preset_layout1.addWidget(balance_btn)

        fast_btn = QPushButton("Rápido")
        fast_btn.setToolTip("Tráfico moderado (5, 30, 5)")
        fast_btn.clicked.connect(lambda: self.apply_preset(5, 30, 5))
        preset_layout1.addWidget(fast_btn)

        veryfast_btn = QPushButton("Muy Rápido")
        veryfast_btn.setToolTip("Poco tráfico (10, 50, 3)")
        veryfast_btn.clicked.connect(lambda: self.apply_preset(10, 50, 3))
        preset_layout1.addWidget(veryfast_btn)

        layout.addLayout(preset_layout1)

        # Botones presets - Segunda fila (nocturnos)
        preset_layout2 = QHBoxLayout()

        night_btn = QPushButton("Nocturno")
        night_btn.setToolTip("Videos nocturnos con poca actividad (10, 200, 5)")
        night_btn.clicked.connect(lambda: self.apply_preset(10, 200, 5))
        preset_layout2.addWidget(night_btn)

        ultra_btn = QPushButton("Ultra Rápido")
        ultra_btn.setToolTip("Casi sin actividad (20, 400, 3)")
        ultra_btn.clicked.connect(lambda: self.apply_preset(20, 400, 3))
        preset_layout2.addWidget(ultra_btn)

        layout.addLayout(preset_layout2)

        # Botones OK/Cancel
        button_layout = QHBoxLayout()
        ok_btn = QPushButton("Aplicar")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def apply_preset(self, active, inactive, threshold):
        """Aplicar preset predefinido"""
        self.stride_active_spin.setValue(active)
        self.stride_inactive_spin.setValue(inactive)
        self.threshold_spin.setValue(threshold)

    def get_values(self):
        """Obtener valores configurados"""
        return {
            'stride_active': self.stride_active_spin.value(),
            'stride_inactive': self.stride_inactive_spin.value(),
            'threshold': self.threshold_spin.value()
        }
