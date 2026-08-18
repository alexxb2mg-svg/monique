' Lancement silencieux (pythonw, sans console). NE PAS mettre au boot tant que
' la bascule n'est pas decidee.
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
sh.CurrentDirectory = fso.GetParentFolderName(WScript.ScriptFullName)
sh.Run ".venv\Scripts\pythonw.exe -m uvicorn serveur:app --host 127.0.0.1 --port 8770", 0, False
