# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['spacehaven-modloader.py'],
    pathex=[],
    binaries=[],   # leave as empty
    datas=[
        ('spacehaven-modloader.png', '.'),
        ('textures_annotations.xml','.'), 
        ('README.md','.'), 
        ('CHANGELOG.md','.')
    ],
    hiddenimports=['click', 'lxml', 'pypng'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='spacehaven-modloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='spacehaven-modloader'
)
