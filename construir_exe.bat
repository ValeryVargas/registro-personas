@echo off
REM Genera dist\RegistroPersonas.exe (ejecutar en Windows con Python 3.12 instalado)
python -m pip install --upgrade pyinstaller
python -m PyInstaller --noconsole --onefile --name RegistroPersonas ^
  --icon assets\icono.ico --add-data "assets;assets" ^
  --hidden-import app.gui main.py
echo.
echo Listo: dist\RegistroPersonas.exe
pause
