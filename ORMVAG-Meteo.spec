# -*- mode: python ; coding: utf-8 -*-
#
# Fichier de configuration PyInstaller pour ORMVAG Météo Manager.
# Usage : pyinstaller ORMVAG-Meteo.spec
#
# Remplace la ligne de commande "pyinstaller --name ... --windowed --onefile main.py"
# et fige la configuration pour que les prochains builds soient reproductibles
# sans avoir à retoucher le $env:PATH à chaque fois.

import os

block_cipher = None

# --- DLL système nécessaires à _ctypes/bcrypt (ffi-8.dll) et à SSL/compression ---
# Ces DLL viennent de l'installation Anaconda de base et ne sont pas toujours
# détectées automatiquement par PyInstaller. Ajustez ce chemin si le projet
# est buildé sur une autre machine ou avec une autre installation Anaconda.
ANACONDA_LIB_BIN = r"C:\Users\hp\anaconda3\Library\bin"

dlls_requises = [
    "ffi-8.dll",
    "libssl-3-x64.dll",
    "libcrypto-3-x64.dll",
    "liblzma.dll",
    "libbz2.dll",
    "sqlite3.dll",
    "libexpat.dll",  # dépendance de pyexpat.pyd, requise par matplotlib.font_manager (via plistlib)
]

binaries_supplementaires = []
for nom_dll in dlls_requises:
    chemin = os.path.join(ANACONDA_LIB_BIN, nom_dll)
    if os.path.exists(chemin):
        binaries_supplementaires.append((chemin, "."))

# --- Modules non utilisés par l'application, exclus pour réduire la taille du build ---
modules_exclus = [
    "tkinter",
    "pytest",
    "IPython",
    "notebook",
    "PySide6.QtTest",
    "PySide6.QtBluetooth",
    "PySide6.QtNfc",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DRender",
    "PySide6.QtRemoteObjects",
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries_supplementaires,
    datas=[],
    hiddenimports=[
    "_cffi_backend",
    "unittest",
    "unittest.case",
    "unittest.loader",
    "unittest.result",
    "unittest.runner",
    "unittest.suite",
],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=modules_exclus,
    noarchive=False,
    cipher=block_cipher,
)

# --- Retire des binaires inutiles embarqués automatiquement par les hooks ---
# "excludes" ci-dessus ne joue que sur les imports Python — il faut filtrer les
# binaires collectés automatiquement directement dans a.binaries/a.datas :
# - clavier virtuel Qt (dépendance indirecte de QtQuick/QtWebEngine)
# - plugin AVIF de Pillow (format d'image jamais utilisé par l'application)
MOTIFS_A_RETIRER = ["virtualkeyboard", "_avif", "avifimageplugin"]


def _a_retirer(nom_fichier):
    nom = nom_fichier.lower()
    return any(motif in nom for motif in MOTIFS_A_RETIRER)


a.binaries = [x for x in a.binaries if not _a_retirer(x[0])]
a.datas = [x for x in a.datas if not _a_retirer(x[0])]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="ORMVAG-Meteo",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX (compression des binaires pour reduire la taille de l'exe) a corrompu
    # a deux reprises des fichiers differents (clavier virtuel Qt, plugin AVIF
    # de Pillow), provoquant des echecs de decompression au demarrage
    # ("decompression resulted in return code -1"). Desactive : l'exe est plus
    # gros mais fiable, plutot que d'exclure les fichiers un par un a chaque
    # nouvelle erreur decouverte.
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,        # équivalent de --windowed
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/logo.ico",             # mettre le chemin d'un .ico ici si vous en avez un, ex: "assets/icone.ico"
)
