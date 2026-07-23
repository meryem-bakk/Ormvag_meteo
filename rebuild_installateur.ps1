# Reconstruit Installateur-ORMVAG.exe. PyInstaller supprime et recree
# entierement dist\Installateur-ORMVAG\ a chaque build (mode onedir) : le
# programme d'installation PostgreSQL embarque (installateur\bin\, ~370 Mo,
# non versionne - voir installateur/installer.py) n'est pas dans les "datas"
# du .spec, donc il faut le recopier a chaque fois, sans quoi l'installateur
# echoue avec "Installeur PostgreSQL introuvable".
#
# Usage : powershell -ExecutionPolicy Bypass -File rebuild_installateur.ps1

$cible = "dist\Installateur-ORMVAG"
$pyinstaller = Join-Path $PSScriptRoot "venv\Scripts\pyinstaller.exe"

if (-not (Test-Path $pyinstaller)) {
    Write-Host "pyinstaller introuvable dans $pyinstaller - venv absent ou deplace."
    exit 1
}
if (-not (Test-Path "installateur\bin\postgresql-18.4-2-windows-x64.exe")) {
    Write-Host "installateur\bin\postgresql-18.4-2-windows-x64.exe introuvable - a retelecharger depuis"
    Write-Host "https://get.enterprisedb.com/postgresql/postgresql-18.4-2-windows-x64.exe avant de continuer."
    exit 1
}

Write-Host "Reconstruction de l'installateur (pyinstaller)..."
& $pyinstaller "Installateur.spec" "--noconfirm"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Echec de la reconstruction (voir erreurs ci-dessus)."
    exit 1
}

Write-Host "Copie du programme d'installation PostgreSQL embarque..."
Copy-Item "installateur\bin" (Join-Path $cible "bin") -Recurse -Force

Write-Host "Termine. Executable pret dans $cible\Installateur-ORMVAG.exe"
