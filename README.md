# Registro de personas y contactos de emergencia
Aplicación de escritorio (Python 3.12 + Tkinter + SQLite).

## Ejecutar desde el código
    python main.py
Requiere Tkinter (en Ubuntu: `sudo apt install python3-tk`). Solo usa la biblioteca estándar.

## Generar el programa de escritorio (.exe, Windows)
Doble clic en `construir_exe.bat` -> `dist\RegistroPersonas.exe`.
Los datos se guardan en `%LOCALAPPDATA%\RegistroPersonas`.

## Usuarios iniciales (cambiar contraseñas antes de uso real)
| usuario | contraseña | rol |
|---|---|---|
| admin | Admin#2026 | todo + bitácora |
| operador | Operador#2026 | crear/editar/desactivar |
| consulta | Consulta#2026 | solo lectura |

## Pruebas
    python -m unittest discover -s tests -t . -v
