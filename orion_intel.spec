# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['orion_cli/cli.py'],
    pathex=[],
    binaries=[],
    datas=[('orion_cli/services/*.py', 'orion_cli/services')],
    hiddenimports=['requests', 'pygithub'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=2,  # Optimize the bytecode
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='orion_intel',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,  # Strip the executable
    upx=False,  # Disable UPX compression
    console=True,
    onefile=True,  # Ensure single-file mode
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='orion_intel',
)

