# -*- mode: python ; coding: utf-8 -*-
#
# Fichier de configuration PyInstaller pour ORMVAG Météo Manager.
# Usage : pyinstaller ORMVAG-Meteo.spec
#
# Remplace la ligne de commande "pyinstaller --name ... --windowed --onefile main.py"
# et fige la configuration pour que les prochains builds soient reproductibles
# sans avoir à retoucher le $env:PATH à chaque fois.

import os
import sys

block_cipher = None

# --- DLL système nécessaires à _ctypes/bcrypt (ffi-8.dll) et à SSL/compression ---
# Ces DLL viennent de l'installation Python de base (Anaconda, Miniconda ou python.org)
# utilisée pour créer le venv, et ne sont pas toujours détectées automatiquement par
# PyInstaller. sys.base_prefix pointe dynamiquement vers cette installation de base (et
# non vers le dossier du venv lui-même) : ce chemin reste donc valide quelle que soit la
# machine de build, contrairement à un chemin absolu codé en dur (ex.
# "C:\Users\<utilisateur>\anaconda3\..."), qui casse silencieusement le build dès qu'on
# change de machine ou de nom d'utilisateur Windows.
DOSSIERS_DLL_CANDIDATS = [
    os.path.join(sys.base_prefix, "Library", "bin"),  # disposition Anaconda/Miniconda
    os.path.join(sys.base_prefix, "DLLs"),             # disposition python.org standard
    sys.base_prefix,
]

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
    for dossier in DOSSIERS_DLL_CANDIDATS:
        chemin = os.path.join(dossier, nom_dll)
        if os.path.exists(chemin):
            binaries_supplementaires.append((chemin, "."))
            break
    else:
        print(f"[ORMVAG-Meteo.spec] ATTENTION : {nom_dll} introuvable "
              f"(cherché dans {DOSSIERS_DLL_CANDIDATS}) — l'exe risque de "
              f"planter au démarrage si cette DLL est réellement requise.")

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
    # Le detecteur d'anomalies (ML/detecteur_anomalies.joblib) est un modele
    # scikit-learn charge dynamiquement via joblib.load/pickle : le code ne
    # fait jamais "import sklearn" explicitement, donc PyInstaller ne le
    # detectait pas et l'exe plantait silencieusement (ModuleNotFoundError
    # avale par le mode windowed) des l'ouverture de la page Indicateurs.
    "sklearn",
    "sklearn.ensemble",
    "sklearn.ensemble._iforest",
    "sklearn.tree",
    "sklearn.utils",
    "sklearn.neighbors",
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

# Mode "onedir" plutot que "onefile" : l'exe onefile doit se re-decompresser
# entierement dans un nouveau dossier temporaire a CHAQUE lancement, et
# l'antivirus rescanne alors des centaines de fichiers (pandas, scikit-learn)
# comme s'ils etaient inconnus, ce qui rend le premier usage de pages lourdes
# (Indicateurs agroclimatiques, qui charge le modele IA) tres lent. En onedir,
# les fichiers restent extraits en permanence a cote de l'exe : demarrage
# rapide et reproductible. L'app est de toute facon deja distribuee sous
# forme de dossier (.env, assets/, ML/ a cote de l'exe), donc rien ne change
# pour l'utilisateur.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ORMVAG-Meteo",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,        # équivalent de --windowed
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/logo.ico",             # mettre le chemin d'un .ico ici si vous en avez un, ex: "assets/icone.ico"
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ORMVAG-Meteo",
)
