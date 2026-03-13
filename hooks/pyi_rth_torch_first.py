# -*- coding: utf-8 -*-
"""
Runtime hook que se ejecuta PRIMERO para configurar el entorno de torch.
Previene problemas de importación circular con multiprocessing.
"""

import os
import sys

# Configurar variable de entorno para evitar inicialización de multiprocessing en torch
os.environ['TORCH_MULTIPROCESSING_START_METHOD'] = 'spawn'

# En Windows, configurar las rutas de DLL antes de cualquier importación
if sys.platform == 'win32' and hasattr(sys, '_MEIPASS'):
    base_path = sys._MEIPASS

    # Rutas de DLLs de torch
    dll_paths = [
        os.path.join(base_path, 'torch', 'lib'),
        os.path.join(base_path, 'torch', 'bin'),
        os.path.join(base_path, 'torch'),
        os.path.join(base_path, 'lib'),
        base_path,
    ]

    # Agregar al PATH
    current_path = os.environ.get('PATH', '')
    valid_paths = [p for p in dll_paths if os.path.isdir(p)]
    os.environ['PATH'] = os.pathsep.join(valid_paths) + os.pathsep + current_path

    # Usar add_dll_directory para Python 3.8+
    for p in valid_paths:
        try:
            os.add_dll_directory(p)
        except (AttributeError, OSError):
            pass
