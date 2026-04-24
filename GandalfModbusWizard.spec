# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all

datas = [('GandalfModbusWizard_BMP.ico', '.'), ('gandalf-modbus-wizard-256.png', '.')]
binaries = []
hiddenimports = ['PIL.Image', 'PIL.ImageTk', 'PIL._tkinter_finder', 'matplotlib', 'matplotlib.backends.backend_tkagg', 'pymodbus', 'serial']
tmp_ret = collect_all('customtkinter')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

tmp_ret_pil = collect_all('PIL')
datas += tmp_ret_pil[0]; binaries += tmp_ret_pil[1]; hiddenimports += tmp_ret_pil[2]

a = Analysis(
    ['GandalfModbusWizard.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    name='GandalfModbusWizard',
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
    icon=['GandalfModbusWizard_BMP.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='GandalfModbusWizard',
)