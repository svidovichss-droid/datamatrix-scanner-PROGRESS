# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build specification for DataMatrix Scanner.
Target: Windows x64 (64-bit)
Author: А. Свидович / А. Петляков для PROGRESS

Usage (on Windows):
    pyinstaller datamatrix_scanner.spec --clean --noconfirm

Usage (GitHub Actions - Windows runner):
    Automatically handled by .github/workflows/build.yml
"""

import sys
import os

block_cipher = None

datas = [
    ('src/config.json', 'src'),
]

hiddenimports = [
    'PyQt5',
    'PyQt5.QtCore',
    'PyQt5.QtGui',
    'PyQt5.QtWidgets',
    'PyQt5.QtChart',
    'cv2',
    'numpy',
    'pylibdmtx',
    'pylibdmtx.pylibdmtx',
    'src.config',
    'src.camera',
    'src.detector',
    'src.quality',
    'src.database',
    'src.scanner',
    'src.ui',
]

a = Analysis(
    ['src\\main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'PIL',
        'tkinter',
        'notebook',
        'ipykernel',
        'jupyter',
        'scipy',
        'sklearn',
        'pandas',
        'IPython',
        'test',
        'unittest',
        'doctest',
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
    name='DataMatrixScanner',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='x64',
    codesign_identity=None,
    entitlements_file=None,
    icon='icons\\app.ico',
    version='version_info.txt',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DataMatrixScanner',
)
