# orion.spec
# This is a basic PyInstaller spec file for the orion_cli project.

# Import the Analysis, PYZ, EXE, COLLECT, and BUNDLE classes
import sys
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.__main__ import run

# Path to the entry point of your CLI application
entry_point = "orion_cli/cli.py"

# Determine the platform-specific binary name
platform = sys.platform
binary_name = "orion"

if platform.startswith("linux"):
    binary_name += "_linux"
elif platform.startswith("darwin"):
    binary_name += "_mac"
elif platform.startswith("win"):
    binary_name += "_windows.exe"

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
    name=binary_name,
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
