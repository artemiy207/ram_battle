# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['ram_battle.py'],
    pathex=[],
    binaries=[],
    datas=[('sam.png', '.'), ('pc.png', '.'), ('ram.png', '.'), ('bg_battle.png', '.'), ('audio.ogg', '.'), ('mk.ogg', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ram_battle',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
