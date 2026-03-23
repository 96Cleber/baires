# -*- mode: python ; coding: utf-8 -*-
"""
FlowVisionAI LITE - PyInstaller Spec File
Versión ligera: Solo clasificación de crops (sin YOLO/PyTorch)
"""

import os
import sys

block_cipher = None

# Ruta base del proyecto
BASE_PATH = os.path.dirname(os.path.abspath(SPEC))

# Submódulos ocultos - SOLO lo necesario para clasificación
hidden_imports = [
    'PyQt5',
    'PyQt5.QtCore',
    'PyQt5.QtGui',
    'PyQt5.QtWidgets',
    'cv2',
    'numpy',
    'sqlite3',
    'PIL',
    'PIL.Image',
    'pathlib',
    # Módulos internos del proyecto
    'tools',
    'tools.typologies',
    'tools.crop_manager',
    'ui',
    'ui.classification_gallery_dialog',
]

a = Analysis(
    [os.path.join(BASE_PATH, 'src', 'main_lite.py')],
    pathex=[
        os.path.join(BASE_PATH, 'src'),
        BASE_PATH,
    ],
    binaries=[],
    datas=[
        # Lite version no requiere archivos .ui - UI se construye en codigo
        (os.path.join(BASE_PATH, 'templates'), 'templates'),
    ],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Excluir dependencias pesadas
        'torch',
        'torchvision',
        'ultralytics',
        'tensorflow',
        'keras',
        'scipy',
        'matplotlib',
        'pandas',
        'polars',
        'reportlab',
        'openpyxl',
        'tkinter',
        'IPython',
        'jupyter',
        'notebook',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ONEFILE: Todo incluido en un solo ejecutable
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='FlowVisionAI-Lite',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
