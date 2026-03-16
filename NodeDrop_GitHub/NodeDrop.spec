# -*- mode: python ; coding: utf-8 -*-

"""
NodeDrop.spec
Build PyInstaller recommandé pour NodeDrop V1 (Windows, PySide6, mode onedir).

À placer à la racine du projet NodeDrop.

Arborescence attendue :
- NodeDrop.spec
- assets/NodeDrop.ico   (facultatif)
- src/main.py

Commande à lancer depuis la racine du projet :
    python -m PyInstaller --noconfirm --clean NodeDrop.spec
"""

from pathlib import Path

project_root = Path.cwd()
src_dir = project_root / "src"
icon_file = project_root / "assets" / "NodeDrop.ico"

a = Analysis(
    [str(src_dir / "main.py")],
    pathex=[str(project_root), str(src_dir)],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pytest",
        "pytest_cov",
        "unittest",
        "tkinter",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="NodeDrop",
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
    icon=str(icon_file) if icon_file.exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="NodeDrop",
)