# Programme une collecte automatique chaque jour avec le Planificateur de tâches de Windows.
#
#   .\planifier-collecte.ps1                 # chaque jour à 8 h
#   .\planifier-collecte.ps1 -Heure 12:30    # chaque jour à 12 h 30
#   .\planifier-collecte.ps1 -Supprimer      # retirer la tâche
#
# La tâche lance collecte-reguliere.ps1 seulement quand vous êtes connecté à votre session.
# Si l'ordinateur est éteint à l'heure prévue, elle se lance dès qu'il est rallumé.
# Une collecte par jour reste bien en dessous des limites des sites.

param(
    [string]$Heure = "08:00",
    [switch]$Supprimer
)

$ErrorActionPreference = "Stop"
$nom = "jobs-insights - collecte des offres"

if ($Supprimer) {
    if (Get-ScheduledTask -TaskName $nom -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $nom -Confirm:$false
        Write-Host "Tâche « $nom » supprimée."
    } else {
        Write-Host "Aucune tâche « $nom » à supprimer."
    }
    exit 0
}

$script = Join-Path $PSScriptRoot "collecte-reguliere.ps1"
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`"" `
    -WorkingDirectory $PSScriptRoot
$declencheur = New-ScheduledTaskTrigger -Daily -At $Heure
$reglages = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Register-ScheduledTask -TaskName $nom -Action $action -Trigger $declencheur -Settings $reglages `
    -Description "Collecte des offres TI (Guichet-Emplois et Remotive) et mise à jour de offres.html" -Force | Out-Null

Write-Host "Tâche « $nom » programmée chaque jour à $Heure."
Write-Host "Pour la retirer : .\planifier-collecte.ps1 -Supprimer"
