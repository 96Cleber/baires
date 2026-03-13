# -*- coding: utf-8 -*-
"""
Runtime hook personalizado para multiprocessing.
Reemplaza el hook por defecto de PyInstaller para evitar
importación circular con torch.

Este archivo DEBE tener el mismo nombre que el hook de PyInstaller
para reemplazarlo.
"""

import sys
import os

# Configurar multiprocessing sin importar torch
if sys.platform == 'win32':
    import multiprocessing
    # Establecer método de inicio para Windows
    try:
        multiprocessing.set_start_method('spawn', force=True)
    except RuntimeError:
        pass  # Ya fue establecido

# NO importar torch.multiprocessing aquí para evitar importación circular
