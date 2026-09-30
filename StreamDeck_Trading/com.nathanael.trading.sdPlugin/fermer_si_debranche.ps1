# Ferme le logiciel Stream Deck si le Stream Deck (Elgato = VID_0FD9) n'est plus branche.
# Lance par le plugin quand le logiciel signale un debranchement (deviceDidDisconnect).
# On attend quelques secondes et on revérifie : une micro-coupure USB ou un rebranchement rapide ne ferme rien.
Start-Sleep -Seconds 5
$branche = Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | Where-Object { $_.InstanceId -like 'USB\VID_0FD9*' }
if ($branche) { exit 0 }
$p = Get-Process -Name StreamDeck -ErrorAction SilentlyContinue
if (-not $p) { exit 0 }
# fermeture normale d'abord (le logiciel enregistre son etat), forcee seulement s'il ne repond pas
& taskkill.exe /IM StreamDeck.exe | Out-Null
Start-Sleep -Seconds 8
if (Get-Process -Name StreamDeck -ErrorAction SilentlyContinue) { Stop-Process -Name StreamDeck -Force }
