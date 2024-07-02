# orion_arm.spec
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['orion_cli/cli.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('orion_cli/services/*.py', 'orion_cli/services'),
        # Include Python shared library and other required files
        ('/path/to/python/library/dylib', '_internal/Python'),
        ('/path/to/other/required/files', '_internal')
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

