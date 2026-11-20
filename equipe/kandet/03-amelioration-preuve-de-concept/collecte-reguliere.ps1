# Collecte régulière des offres : nouvelle collecte, page offres.html à jour, ménage du cache.
#
# À lancer à la main (clic droit > « Exécuter avec PowerShell ») ou automatiquement
# avec planifier-collecte.ps1. Tout ce qui s'affiche est ajouté à journal-collectes.log.
#
# La collecte respecte les règles des sites : 5 secondes entre deux pages du Guichet-Emplois,
# et la réponse de Remotive est gardée 24 heures (l'API demande au plus 4 appels par jour).

$ErrorActionPreference = "Stop"
$dossier = $PSScriptRoot
Set-Location $dossier

# Trouver Python (« python » ou, sinon, le lanceur « py »).
$commande = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $commande) { $commande = Get-Command py -ErrorAction SilentlyContinue }
if ($null -eq $commande) {
    Write-Error "Python est introuvable. Installez Python 3.12 ou plus récent (python.org)."
    exit 1
}

$journal = Join-Path $dossier "journal-collectes.log"
$sortie = Join-Path $env:TEMP "jobs-insights-sortie.txt"
$erreurs = Join-Path $env:TEMP "jobs-insights-erreurs.txt"
$env:PYTHONIOENCODING = "utf-8"

$debut = Get-Date
Add-Content -Path $journal -Encoding UTF8 -Value "`r`n===== Collecte du $($debut.ToString('yyyy-MM-dd HH:mm')) ====="

$processus = Start-Process -FilePath $commande.Source `
    -ArgumentList @("main.py", "--nettoyer-cache", "--html", "--resume-seulement") `
    -WorkingDirectory $dossier -NoNewWindow -Wait -PassThru `
    -RedirectStandardOutput $sortie -RedirectStandardError $erreurs

# Le résultat (stdout) au complet; pour les messages de progression (stderr), seulement les avertissements.
Get-Content -Path $sortie -Encoding UTF8 | Add-Content -Path $journal -Encoding UTF8
Get-Content -Path $erreurs -Encoding UTF8 |
    Where-Object { $_ -match "AVERTISSEMENT|HTTP|Error|Erreur|Traceback" } |
    Add-Content -Path $journal -Encoding UTF8

$duree = [int]((Get-Date) - $debut).TotalSeconds
if ($processus.ExitCode -eq 0) {
    Add-Content -Path $journal -Encoding UTF8 -Value "Terminée sans erreur en $duree s."
    Write-Host "Collecte terminée en $duree s. Détails : $journal"
} else {
    Add-Content -Path $journal -Encoding UTF8 -Value "ÉCHEC (code $($processus.ExitCode)) après $duree s."
    Write-Host "La collecte a échoué. Voir : $journal"
}
exit $processus.ExitCode
