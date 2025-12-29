# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for building gstack standalone executable."""

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect all pydantic data files and submodules
pydantic_datas = collect_data_files('pydantic')
pydantic_hiddenimports = collect_submodules('pydantic')

a = Analysis(
    ['gstack/main.py'],
    pathex=[],
    binaries=[],
    datas=pydantic_datas,
    hiddenimports=[
        *pydantic_hiddenimports,
        'typer',
        'rich',
        'click',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'PIL',
        'scipy',
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='gs',
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
