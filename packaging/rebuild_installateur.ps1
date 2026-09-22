# Reconstruit Installateur-ORMVAG.exe. PyInstaller supprime et recree
# entierement dist\Installateur-ORMVAG\ a chaque build (mode onedir) : le
# programme d'installation PostgreSQL embarque (installateur\bin\, ~370 Mo,
# non versionne - voir installateur/installer.py) n'est pas dans les "datas"
# du .spec, donc il faut le recopier a chaque fois, sans quoi l'installateur
# echoue avec "Installeur PostgreSQL introuvable".
#
# Usage (depuis n'importe quel dossier) : powershell -ExecutionPolicy Bypass -File packaging\rebuild_installateur.ps1

# Ce script vit dans packaging/ mais dist/ et venv/ sont a la racine du depot : on se
# repositionne explicitement dessus plutot que de dependre du dossier depuis lequel le
# script est lance.
$racineProjet = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location $racineProjet

$cible = "dist\Installateur-ORMVAG"
$pyinstaller = Join-Path $racineProjet "venv\Scripts\pyinstaller.exe"
$binPostgres = "packaging\installateur\bin"

if (-not (Test-Path $pyinstaller)) {
    Write-Host "pyinstaller introuvable dans $pyinstaller - venv absent ou deplace."
    Pop-Location
    exit 1
}
if (-not (Test-Path (Join-Path $binPostgres "postgresql-18.4-2-windows-x64.exe"))) {
    Write-Host "$binPostgres\postgresql-18.4-2-windows-x64.exe introuvable - a retelecharger depuis"
    Write-Host "https://get.enterprisedb.com/postgresql/postgresql-18.4-2-windows-x64.exe avant de continuer."
    Pop-Location
    exit 1
}

Write-Host "Reconstruction de l'installateur (pyinstaller)..."
& $pyinstaller "packaging\Installateur.spec" "--noconfirm"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Echec de la reconstruction (voir erreurs ci-dessus)."
    Pop-Location
    exit 1
}

Write-Host "Copie du programme d'installation PostgreSQL embarque..."
Copy-Item $binPostgres (Join-Path $cible "bin") -Recurse -Force

Write-Host "Termine. Executable pret dans $cible\Installateur-ORMVAG.exe"
Pop-Location
