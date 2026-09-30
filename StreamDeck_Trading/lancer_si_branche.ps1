# Lance le logiciel Stream Deck seulement si le Stream Deck est branche (Elgato = VID_0FD9).
# Appele par la tache planifiee « Stream Deck - lancement au branchement » (branchement USB et ouverture de session).
# Le lancement automatique au demarrage de Windows a ete retire : sans Stream Deck branche (au travail), rien ne s'ouvre.
$exe = 'C:\Program Files\Elgato\StreamDeck\StreamDeck.exe'
if (Get-Process -Name StreamDeck -ErrorAction SilentlyContinue) { exit 0 }
$branche = Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | Where-Object { $_.InstanceId -like 'USB\VID_0FD9*' }
if ($branche -and (Test-Path $exe)) { Start-Process $exe -ArgumentList '--runinbk' }
