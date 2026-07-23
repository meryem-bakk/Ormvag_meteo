# Reconstruit ORMVAG-Meteo.exe sans perdre Rapports/, Sauvegardes/, .env ni le marqueur
# de tache quotidienne : PyInstaller supprime et recree entierement dist\ORMVAG-Meteo\
# a chaque build (mode onedir, exclude_binaries + COLLECT), donc tout fichier qui s'y
# trouve et qui n'est pas gere par le .spec (datas=[]) serait perdu sans cette
# sauvegarde/restauration - ML/ et assets/ ne sont pas dans "datas" non plus, ils
# doivent donc etre recopies depuis le depot a chaque fois.
#
# La restauration est dans un "finally" : meme si pyinstaller plante ou n'est pas
# trouve (PATH non configure dans ce terminal), Rapports/Sauvegardes/.env reviennent
# a leur place plutot que de rester bloques dans le dossier de sauvegarde temporaire.
#
# Usage : powershell -ExecutionPolicy Bypass -File rebuild_exe.ps1

$cible = "dist\ORMVAG-Meteo"
$sauvegarde = "dist\_sauvegarde_temp_rebuild"
$aConserver = @("Rapports", "Sauvegardes", ".env", ".dernier_run_quotidien")
$pyinstaller = Join-Path $PSScriptRoot "venv\Scripts\pyinstaller.exe"

if (-not (Test-Path $pyinstaller)) {
    Write-Host "pyinstaller introuvable dans $pyinstaller - venv absent ou deplace."
    exit 1
}

if (Test-Path $cible) {
    Write-Host "Sauvegarde de Rapports/Sauvegardes/.env avant reconstruction..."
    New-Item -ItemType Directory -Force -Path $sauvegarde | Out-Null
    foreach ($nom in $aConserver) {
        $source = Join-Path $cible $nom
        if (Test-Path $source) {
            Move-Item $source (Join-Path $sauvegarde $nom) -Force
        }
    }
}

$echec = $false
try {
    Write-Host "Reconstruction de l'exe (pyinstaller)..."
    & $pyinstaller "ORMVAG-Meteo.spec" "--noconfirm"
    if ($LASTEXITCODE -ne 0) { $echec = $true }
} catch {
    Write-Host "Erreur pendant la reconstruction : $_"
    $echec = $true
} finally {
    Write-Host "Restauration de Rapports/Sauvegardes/.env..."
    New-Item -ItemType Directory -Force -Path $cible | Out-Null
    foreach ($nom in $aConserver) {
        $source = Join-Path $sauvegarde $nom
        if (Test-Path $source) {
            Move-Item $source (Join-Path $cible $nom) -Force
        }
    }
    if (Test-Path $sauvegarde) { Remove-Item $sauvegarde -Recurse -Force -ErrorAction SilentlyContinue }
}

if ($echec) {
    Write-Host "Echec de la reconstruction (voir erreurs ci-dessus) - Rapports/Sauvegardes/.env restaures, exe non touche."
    exit 1
}

# Premiere construction (aucune sauvegarde existante) : partir du .env du depot.
if (-not (Test-Path (Join-Path $cible ".env")) -and (Test-Path ".env")) {
    Copy-Item ".env" (Join-Path $cible ".env") -Force
}

Write-Host "Copie des assets statiques (ML, assets) depuis le depot..."
Copy-Item "ML" (Join-Path $cible "ML") -Recurse -Force
Copy-Item "assets" (Join-Path $cible "assets") -Recurse -Force

Write-Host "Termine. Executable pret dans $cible\ORMVAG-Meteo.exe"
