# -*- coding: utf-8 -*-
"""
Runtime hook para PyTorch en PyInstaller.
Configura el PATH para que las DLLs de torch se carguen correctamente.

Este hook se ejecuta ANTES de que se importe cualquier módulo,
asegurando que las DLLs de torch estén accesibles.
"""

import os
import sys

def setup_torch_path():
    """Configurar PATH para las DLLs de PyTorch."""
    if hasattr(sys, '_MEIPASS'):
        # Estamos en un ejecutable PyInstaller
        base_path = sys._MEIPASS

        # Rutas donde torch guarda sus DLLs
        torch_paths = [
            os.path.join(base_path, 'torch', 'lib'),
            os.path.join(base_path, 'torch', 'bin'),
            os.path.join(base_path, 'torch'),
            base_path,
        ]

        # Agregar al PATH del sistema
        current_path = os.environ.get('PATH', '')
        new_paths = [p for p in torch_paths if os.path.exists(p)]

        if new_paths:
            os.environ['PATH'] = os.pathsep.join(new_paths) + os.pathsep + current_path

        # También agregar a sys.path si es necesario
        for p in new_paths:
            if p not in sys.path:
                sys.path.insert(0, p)

# Ejecutar la configuración
setup_torch_path()
