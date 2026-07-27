# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['new.py'],
    pathex=[],
    binaries=[],
    datas=[('leadhunter.ico', '.')],
    hiddenimports=['selenium.webdriver.chrome.webdriver', 'selenium.webdriver.common.by', 'PIL._tkinter_finder'],
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
    name='Lead Hunter v 3.0',
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
    icon=['leadhunter.ico'],
)
