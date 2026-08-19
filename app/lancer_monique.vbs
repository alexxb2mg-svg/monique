' Lanceur Monique - demarre le serveur SANS console puis ouvre le navigateur.
' IMPORTANT : sous pythonw (sans console), uvicorn plante sur son log de demarrage si stdout est
' invalide. On redirige donc la sortie vers un fichier (handles valides) via "cmd /c ... > log 2>&1",
' le tout lance cache (window style 0). Port 8790, host 0.0.0.0 (accessible depuis le telephone).
Option Explicit
Dim sh, appdir, pyw, logf, cmd
Set sh = CreateObject("WScript.Shell")
appdir = "C:\Users\ALEX\Desktop\BSTEGagentiks\noyaux\bureau-detude\BSTEG_Logiciel\secretaire\app"
pyw = appdir & "\.venv\Scripts\pythonw.exe"
logf = sh.ExpandEnvironmentStrings("%TEMP%") & "\monique_server.log"
sh.CurrentDirectory = appdir
cmd = "cmd /c """ & pyw & """ -m uvicorn serveur:app --host 0.0.0.0 --port 8790 --log-level warning > """ & logf & """ 2>&1"
' 0 = fenetre cachee, False = ne pas attendre
sh.Run cmd, 0, False
' laisse le serveur demarrer, puis ouvre Monique dans le navigateur par defaut
WScript.Sleep 3800
sh.Run "http://localhost:8790/", 1, False
