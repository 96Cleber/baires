# -*- coding: utf-8 -*-
"""
PyInstaller hook para PyTorch.
Asegura que todas las DLLs de torch se incluyan correctamente.
"""

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

# Recolectar todas las librerías dinámicas de torch
binaries = collect_dynamic_libs('torch')

# Recolectar archivos de datos
datas = collect_data_files('torch')
