# -*- mode: python ; coding: utf-8 -*-
"""
FlowVisionAI - PyInstaller Spec File
Genera un ejecutable standalone de la aplicación.
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_dynamic_libs

block_cipher = None

# Ruta base del proyecto
BASE_PATH = os.path.dirname(os.path.abspath(SPEC))

# Recolectar datos de ultralytics (YOLO)
ultralytics_datas = collect_data_files('ultralytics')

# Recolectar DLLs de torch para evitar WinError 1114
torch_binaries = collect_dynamic_libs('torch')
torch_datas = collect_data_files('torch')

# Recolectar submódulos ocultos
hidden_imports = [
    'PyQt5',
    'PyQt5.QtCore',
    'PyQt5.QtGui',
    'PyQt5.QtWidgets',
    'cv2',
    'numpy',
    'pandas',
    'torch',
    'torchvision',
    'ultralytics',
    'shapely',
    'shapely.geometry',
    'sqlite3',
    'reportlab',
    'reportlab.lib',
    'reportlab.platypus',
    'matplotlib',
    'matplotlib.pyplot',
    'openpyxl',
    'polars',
    'scipy',
    'PIL',
    'PIL.Image',
]

# Submódulos de ultralytics
hidden_imports += collect_submodules('ultralytics')

a = Analysis(
    [os.path.join(BASE_PATH, 'src', 'main_v3.py')],
    pathex=[
        os.path.join(BASE_PATH, 'src'),
        BASE_PATH,
    ],
    binaries=torch_binaries,  # Incluir DLLs de torch
    datas=[
        # Archivos UI de PyQt5
        (os.path.join(BASE_PATH, 'src', 'ui', '*.ui'), 'ui'),
        # Templates (tipologías, etc.)
        (os.path.join(BASE_PATH, 'templates'), 'templates'),
        # Pesos de YOLO (si existen localmente)
        (os.path.join(BASE_PATH, 'weights'), 'weights'),
    ] + ultralytics_datas + torch_datas,
    hiddenimports=hidden_imports,
    hookspath=[os.path.join(BASE_PATH, 'hooks')],  # Usar hooks personalizados
    hooksconfig={},
    runtime_hooks=[os.path.join(BASE_PATH, 'hooks', 'runtime_hook_torch.py')],  # Hook de runtime para torch
    excludes=[
        'tkinter',
        'matplotlib.backends.backend_tkagg',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FlowVisionAI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # True para ver errores en consola
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FlowVisionAI',
)
