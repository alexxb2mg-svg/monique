@echo off
REM Lancement visible/debug de la coquille (127.0.0.1:8770). NE PAS mettre au boot
REM tant que la bascule n'est pas decidee.
cd /d "%~dp0"
".venv\Scripts\python.exe" -m uvicorn serveur:app --host 127.0.0.1 --port 8770
