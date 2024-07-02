# orion.spec
import sys
from PyInstaller.utils.hooks import collect_submodules

# Path to the entry point of your CLI application
entry_point = "orion_cli/cli.py"

# Additional hidden imports, if any
hidden_imports = collect_submodules('orion_cli.services')

# PyInstaller configuration
a = Analysis(
    [entry_point],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=hidden_imports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

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
    upx_exclude=[],
    runtime_tmpdir=None,
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
    name='orion'
)


