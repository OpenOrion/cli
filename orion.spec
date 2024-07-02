# orion.spec
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
        # Include the entire lib directory to ensure all necessary files are bundled
        (str(venv_path / 'lib'), '_internal/Python'),
        # Include the Python executable
        (str(venv_path / 'bin' / 'python3.11'), '_internal/Python/bin/python3.11')
    ],
    hiddenimports=[],
    hookspath=['hooks'],
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
    name='orion',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    target_arch="universal2",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='orion'
)





