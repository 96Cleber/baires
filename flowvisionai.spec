# -*- mode: python ; coding: utf-8 -*-
"""
FlowVisionAI - PyInstaller Spec File
Configuración simplificada para evitar problemas con PyTorch DLLs.
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_all

block_cipher = None

# Ruta base del proyecto
BASE_PATH = os.path.dirname(os.path.abspath(SPEC))

# Recolectar datos de ultralytics (YOLO)
ultralytics_datas = collect_data_files('ultralytics')

# Recolectar TODO de torch
torch_datas, torch_binaries, torch_hiddenimports = collect_all('torch')

# Recolectar TODO de torchvision
torchvision_datas, torchvision_binaries, torchvision_hiddenimports = collect_all('torchvision')

# Submódulos ocultos
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

# Agregar submódulos
hidden_imports += collect_submodules('ultralytics')
hidden_imports += torch_hiddenimports
hidden_imports += torchvision_hiddenimports

# Combinar binaries
all_binaries = torch_binaries + torchvision_binaries

a = Analysis(
    [os.path.join(BASE_PATH, 'src', 'main_v3.py')],
    pathex=[
        os.path.join(BASE_PATH, 'src'),
        BASE_PATH,
    ],
    binaries=all_binaries,
    datas=[
        (os.path.join(BASE_PATH, 'src', 'ui', '*.ui'), 'ui'),
        (os.path.join(BASE_PATH, 'templates'), 'templates'),
        (os.path.join(BASE_PATH, 'weights'), 'weights'),
    ] + ultralytics_datas + torch_datas + torchvision_datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
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
    upx=False,
    console=True,
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
    upx=False,
    upx_exclude=[],
    name='FlowVisionAI',
)
