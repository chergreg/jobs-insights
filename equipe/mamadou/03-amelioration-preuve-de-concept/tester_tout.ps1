# Test complet en UNE commande (PowerShell) — Livrable 3 Mamadou.
# Usage (depuis ce dossier) :
#   .\tester_tout.ps1            -> mode RAPIDE : tests + consolidation hors ligne + CV + lettre + filtres (~10 s, sans Internet)
#   .\tester_tout.ps1 -Complet   -> mode COMPLET : PURGE totale (data/ + cache/) puis recollecte live sur les 5 sites (~5-10 min)
param([switch]$Complet)

$ErrorActionPreference = "Continue"
Set-Location -Path $PSScriptRoot
$py = "python"
$echecs = 0

function Etape($titre) { Write-Host "`n############ $titre ############" -ForegroundColor Cyan }
function Verifie($code, $nom) {
    if ($code -ne 0) { Write-Host "  >>> ECHEC : $nom (code $code)" -ForegroundColor Red; $script:echecs++ }
    else { Write-Host "  >>> OK : $nom" -ForegroundColor Green }
}

Etape "1/5 Tests unitaires hors ligne"
& $py -m unittest discover -s . -p "test_*.py"
Verifie $LASTEXITCODE "tests unitaires"

if ($Complet) {
    Etape "2/5 PURGE + collecte live sur les 5 sources (sans cache)"
    & $py -u poc_guichet_cnp_v2.py --purger --collecte-complete --sans-cache --html --format-commun
    Verifie $LASTEXITCODE "purge + collecte live"
} else {
    Etape "2/5 Consolidation hors ligne des 5 fichiers data/ (aucune purge)"
    & $py -u poc_guichet_cnp_v2.py --consolider-data --html --format-commun
    Verifie $LASTEXITCODE "consolidation"
}

Etape "3/5 Verification automatique des resultats (PASS / FAIL)"
& $py poc_guichet_cnp_v2.py --verifier
Verifie $LASTEXITCODE "verification des resultats"

Etape "4/5 Filtrage hors ligne (stages TI + Python en Capitale-Nationale)"
& $py poc_guichet_cnp_v2.py --filtrer --stages --top 3
& $py poc_guichet_cnp_v2.py --filtrer --region Capitale-Nationale --techno Python --top 3
Verifie $LASTEXITCODE "filtrage"

Etape "5/5 Assistant de candidature : CV + lettre"
& $py poc_guichet_cnp_v2.py --cv cv_etudiant_dec_exemple.txt --lettre lettre_motivation_exemple.txt --top 3
Verifie $LASTEXITCODE "CV + lettre"

Write-Host ""
if ($echecs -eq 0) { Write-Host "=== TOUT EST OK : 5 etapes validees ===" -ForegroundColor Green }
else { Write-Host "=== $echecs ETAPE(S) EN ECHEC ===" -ForegroundColor Red; exit 1 }
