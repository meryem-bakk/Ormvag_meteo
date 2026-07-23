# -*- mode: python ; coding: utf-8 -*-
#
# Installateur autonome ORMVAG Meteo Manager : installe PostgreSQL, cree la
# base/le schema et seed les donnees de base. Distinct de ORMVAG-Meteo.spec
# (l'application principale) - a lancer une seule fois, avant elle.
# Usage : pyinstaller Installateur.spec

import os
import sys

block_cipher = None

# Memes DLL systeme que ORMVAG-Meteo.spec (voir ce fichier pour le detail) : necessaires
# a _ctypes/bcrypt (ffi-8.dll), non toujours detectees par PyInstaller. sys.base_prefix
# pointe dynamiquement vers l'installation Python de base (Anaconda/Miniconda/python.org)
# ayant servi a creer le venv, donc reste valide quelle que soit la machine de build -
# contrairement a un chemin absolu code en dur.
DOSSIERS_DLL_CANDIDATS = [
    os.path.join(sys.base_prefix, "Library", "bin"),  # disposition Anaconda/Miniconda
    os.path.join(sys.base_prefix, "DLLs"),             # disposition python.org standard
    sys.base_prefix,
]
dlls_requises = [
    "ffi-8.dll", "libssl-3-x64.dll", "libcrypto-3-x64.dll",
    "liblzma.dll", "libbz2.dll", "sqlite3.dll", "libexpat.dll",
]
binaries_supplementaires = []
for nom_dll in dlls_requises:
    for dossier in DOSSIERS_DLL_CANDIDATS:
        chemin = os.path.join(dossier, nom_dll)
        if os.path.exists(chemin):
            binaries_supplementaires.append((chemin, "."))
            break
    else:
        print(f"[Installateur.spec] ATTENTION : {nom_dll} introuvable "
              f"(cherché dans {DOSSIERS_DLL_CANDIDATS}) — l'exe risque de "
              f"planter au démarrage si cette DLL est réellement requise.")

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
