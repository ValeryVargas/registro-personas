"""Inicialización: usuarios de demostración y logging."""
import logging, os
from .security import crear_credencial

USUARIOS_DEMO = [("admin", "Admin#2026", "admin"),
                 ("operador", "Operador#2026", "operador"),
                 ("consulta", "Consulta#2026", "consulta")]


def sembrar_usuarios(repo):
    for u, clave, rol in USUARIOS_DEMO:
        if repo.obtener_usuario(u) is None:
            sal, h = crear_credencial(clave)
            repo.crear_usuario(u, sal, h, rol)


def configurar_logging(ruta="logs/app.log"):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    logging.basicConfig(filename=ruta, level=logging.INFO, filemode="a",
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", force=True)
