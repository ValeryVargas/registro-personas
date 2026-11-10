"""Punto de entrada: python main.py  (usuarios demo en README.md)"""
import os, sys
from app.db import Repositorio
from app.bootstrap import sembrar_usuarios, configurar_logging


def carpeta_datos():
    """En desarrollo: la carpeta del proyecto. Como .exe: una carpeta del usuario
    (los datos no deben quedar dentro del ejecutable temporal)."""
    if getattr(sys, "frozen", False):
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        ruta = os.path.join(base, "RegistroPersonas")
    else:
        ruta = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(ruta, exist_ok=True)
    return ruta


def main():
    base = carpeta_datos()
    configurar_logging(os.path.join(base, "logs", "app.log"))
    repo = Repositorio(os.path.join(base, "registro.db"))
    sembrar_usuarios(repo)
    from app.gui import App
    App(repo).mainloop()


if __name__ == "__main__":
    main()
