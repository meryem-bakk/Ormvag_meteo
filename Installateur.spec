# -*- mode: python ; coding: utf-8 -*-
#
# Installateur autonome ORMVAG Meteo Manager : installe PostgreSQL, cree la
# base/le schema et seed les donnees de base. Distinct de ORMVAG-Meteo.spec
# (l'application principale) - a lancer une seule fois, avant elle.
# Usage : pyinstaller Installateur.spec

import os

block_cipher = None

# Memes DLL systeme que ORMVAG-Meteo.spec (voir ce fichier pour le detail) :
# necessaires a _ctypes/bcrypt (ffi-8.dll) et non toujours detectees par PyInstaller.
ANACONDA_LIB_BIN = r"C:\Users\hp\anaconda3\Library\bin"
dlls_requises = [
    "ffi-8.dll", "libssl-3-x64.dll", "libcrypto-3-x64.dll",
    "liblzma.dll", "libbz2.dll", "sqlite3.dll", "libexpat.dll",
]
binaries_supplementaires = [
    (os.path.join(ANACONDA_LIB_BIN, nom), ".")
    for nom in dlls_requises
    if os.path.exists(os.path.join(ANACONDA_LIB_BIN, nom))
]

a = Analysis(
    ["installateur/installer.py"],
    pathex=["."],
    binaries=binaries_supplementaires,
    datas=[],
    hiddenimports=[
        "psycopg",
        "psycopg_binary",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "pytest", "IPython", "notebook",
        "PySide6", "shiboken6", "matplotlib", "reportlab",
        "tensorflow", "keras", "sklearn", "scipy",
    ],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Installateur-ORMVAG",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,        # fenetre console visible : l'utilisateur doit suivre la progression
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Installateur-ORMVAG",
)
