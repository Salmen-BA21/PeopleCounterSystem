# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('web', 'web'),
        ('yolo26n.pt', '.'),
        ('yolo26s.pt', '.'),
    ] + collect_data_files('onvif'),
    hiddenimports=[
        # pywebview
        'webview',
        'webview.window',
        'webview.platforms',
        'webview.platforms.winforms',
        'clr',
        'System.Windows.Forms',
        'Microsoft.Web.WebView2',
        'pythonnet',
        # uvicorn
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'uvicorn.lifespan.off',
        # app modules
        'src',
        'src.count_people',
        'src.server',
        'src.discover_cameras',
        'src.prereqs',
        # detection / video
        'cv2',
        'numpy',
        'torch',
        'ultralytics',
    ] + collect_submodules('onvif') + collect_submodules('zeep') + collect_submodules('lxml'),
    excludes=[
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
        'cefpython3',
        'tkinter',
        'scipy',
        'pandas',
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
    name='PeopleCounter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX corrupts torch/WebView2 DLLs on some machines — silent CUDA failures
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='PeopleCounter',
)
