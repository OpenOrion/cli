# orion_arm.spec
# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

block_cipher = None

# Determine the virtual environment path dynamically
venv_path = Path(sys.prefix)

a = Analysis(
    ['orion_cli/cli.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('orion_cli/services/*.py', 'orion_cli/services'),
        # Correct path to the Python shared library within the Poetry environment
        (str(venv_path / 'lib' / 'python3.11' / 'site-packages'), '_internal/Python')
    ],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='orion_arm',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='orion_arm'
)


