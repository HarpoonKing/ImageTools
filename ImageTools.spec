# -*- mode: python ; coding: utf-8 -*-
import importlib.util
from pathlib import Path

# 定位 tkinterdnd2 包目录，确保运行时能找到 tkdnd 本地库
_tkdnd_spec = importlib.util.find_spec('tkinterdnd2')
_tkdnd_pkg  = str(Path(_tkdnd_spec.origin).parent)

a = Analysis(
    ['image_tools.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('resize_core.py', '.'),
        (_tkdnd_pkg, 'tkinterdnd2'),
    ],
    hiddenimports=['tkinterdnd2', 'tkinterdnd2.TkinterDnD'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# onedir 模式 —— macOS .app bundle 的标准方式
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ImageTools',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
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
    name='ImageTools',
)

app = BUNDLE(
    coll,
    name='ImageTools.app',
    icon=None,
    bundle_identifier=None,
)
