@echo off
rem Gera dist\ContadorDeBaus.exe (um arquivo so, com os modelos dentro)
cd /d "%~dp0"
py -m pip install -r requirements.txt pyinstaller
py -m PyInstaller --noconfirm --onefile --windowed --name ContadorDeBaus ^
  --icon assets\icone.ico ^
  --add-data "modelos;modelos" ^
  --hidden-import pystray._win32 ^
  contador_baus.py
echo.
echo Pronto: dist\ContadorDeBaus.exe
pause
