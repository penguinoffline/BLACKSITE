# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['BLACKSITE_v1.0.py'],
    pathex=[],
    binaries=[],
    datas=[],
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
    [],
    exclude_binaries=True,
    name='BLACKSITE',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='BLACKSITE',
)
app = BUNDLE(
    coll,
    name='BLACKSITE.app',
    icon='assets/blacksite_icon.icns',
    bundle_identifier=None,
    version='1.0.0',
    info_plist={
        'CFBundleVersion': '1',
    },
)
