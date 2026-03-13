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
            os.path.join(base_path, 'torch', '_C'),
            os.path.join(base_path, 'torch'),
            os.path.join(base_path, 'lib'),
            base_path,
        ]

        # Agregar al PATH del sistema (al inicio para prioridad)
        current_path = os.environ.get('PATH', '')
        new_paths = [p for p in torch_paths if os.path.isdir(p)]

        if new_paths:
            os.environ['PATH'] = os.pathsep.join(new_paths) + os.pathsep + current_path

        # También configurar DLL directories en Windows
        if sys.platform == 'win32':
            try:
                # Python 3.8+ tiene add_dll_directory
                for p in new_paths:
                    if os.path.isdir(p):
                        os.add_dll_directory(p)
            except AttributeError:
                pass  # Python < 3.8, usar solo PATH

        # Agregar a sys.path si es necesario
        for p in new_paths:
            if p not in sys.path:
                sys.path.insert(0, p)

# Ejecutar la configuración inmediatamente
setup_torch_path()
