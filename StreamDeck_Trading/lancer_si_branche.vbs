' Lance lancer_si_branche.ps1 sans faire clignoter de fenetre PowerShell.
Set sh = CreateObject("WScript.Shell")
dossier = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
sh.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & dossier & "\lancer_si_branche.ps1""", 0, False
