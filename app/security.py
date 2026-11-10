"""Autenticación local (PBKDF2-HMAC-SHA256), roles, bloqueo por intentos fallidos
y expiración de sesión por inactividad."""
import hashlib, hmac, os, time

ITERACIONES = 200_000
PERMISOS = {
    "admin": {"leer", "escribir", "desactivar", "bitacora"},
    "operador": {"leer", "escribir", "desactivar"},
    "consulta": {"leer"},
}


class PermisoDenegado(Exception):
    pass


class AutenticacionError(Exception):
    pass


def hash_clave(clave: str, sal: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", clave.encode(), sal, ITERACIONES).hex()


def crear_credencial(clave: str):
    sal = os.urandom(16)
    return sal.hex(), hash_clave(clave, sal)


def clave_valida(clave: str) -> bool:
    return (len(clave) >= 8 and any(c.isdigit() for c in clave)
            and any(c.isalpha() for c in clave))


class Sesion:
    def __init__(self, usuario: str, rol: str, timeout_s: int = 300, reloj=time.monotonic):
        self.usuario, self.rol, self.timeout_s, self._reloj = usuario, rol, timeout_s, reloj
        self._ultimo = reloj()

    def expirada(self) -> bool:
        return self._reloj() - self._ultimo > self.timeout_s

    def tocar(self):
        self._ultimo = self._reloj()

    def exigir(self, permiso: str):
        if self.expirada():
            raise PermisoDenegado("La sesión expiró por inactividad.")
        if permiso not in PERMISOS.get(self.rol, ()):
            raise PermisoDenegado(f"El rol '{self.rol}' no tiene permiso para '{permiso}'.")
        self.tocar()


class Autenticador:
    MAX_INTENTOS = 3
    BLOQUEO_S = 60

    def __init__(self, repo, reloj=time.time, timeout_sesion=300):
        self.repo, self._reloj, self.timeout = repo, reloj, timeout_sesion

    def iniciar_sesion(self, usuario: str, clave: str) -> Sesion:
        u = self.repo.obtener_usuario(usuario)
        ahora = self._reloj()
        if u is None:
            hash_clave(clave, b"0" * 16)            # igualar tiempos de respuesta
            raise AutenticacionError("Usuario o contraseña incorrectos.")
        if u["bloqueado_hasta"] and ahora < u["bloqueado_hasta"]:
            raise AutenticacionError(
                f"Cuenta bloqueada. Intente en {int(u['bloqueado_hasta'] - ahora) + 1} s.")
        calculado = hash_clave(clave, bytes.fromhex(u["sal"]))
        if hmac.compare_digest(calculado, u["hash"]):
            self.repo.registrar_intento(usuario, 0, None)
            self.repo.bitacora(usuario, "LOGIN", "usuario", None, "inicio de sesión correcto")
            return Sesion(usuario, u["rol"], self.timeout)
        intentos = u["intentos"] + 1
        bloqueo = ahora + self.BLOQUEO_S if intentos >= self.MAX_INTENTOS else None
        self.repo.registrar_intento(usuario, 0 if bloqueo else intentos, bloqueo)
        self.repo.bitacora(usuario, "LOGIN_FALLIDO", "usuario", None, f"intento {intentos}")
        raise AutenticacionError("Usuario o contraseña incorrectos.")
