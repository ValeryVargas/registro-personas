"""Capa de servicio: reglas de negocio, índices en memoria (estructuras dinámicas),
permisos, historial Deshacer y bitácora."""
import logging
from .models import Persona
from .structures import ArbolBST, TablaHash, Pila, Cola, normalizar
from .validators import validar_persona, ValidacionError, limpiar_cedula, limpiar_telefono
from .security import Sesion

log = logging.getLogger("registro")


class NoEncontrado(Exception):
    pass


class Duplicado(Exception):
    pass


class Servicio:
    def __init__(self, repo, sesion: Sesion):
        self.repo, self.sesion = repo, sesion
        self.por_cedula = TablaHash()      # O(1) por identificador
        self.por_nombre = ArbolBST()       # orden alfabético y prefijos
        self.historial = Pila()            # Deshacer
        self.eventos = Cola()              # bitácora pendiente
        self.recargar()

    # --- índices ----------------------------------------------------------------
    def recargar(self):
        self.por_cedula = TablaHash()
        personas = self.repo.cargar_todas()
        for p in personas:
            self.por_cedula.poner(p.cedula, p)
        self.por_nombre = ArbolBST.desde_ordenados(
            sorted(((p.clave_orden, p.cedula) for p in personas)))
        log.info("Índices cargados: %d personas, altura del árbol=%d",
                 len(self.por_cedula), self.por_nombre.altura())

    def _indexar(self, p):
        self.por_cedula.poner(p.cedula, p)
        self.por_nombre.insertar(p.clave_orden, p.cedula)

    def _desindexar(self, p):
        self.por_cedula.quitar(p.cedula)
        self.por_nombre.eliminar(p.clave_orden, p.cedula)

    def _evento(self, accion, p_ced, detalle=""):
        self.eventos.encolar((self.sesion.usuario, accion, "persona", p_ced, detalle))

    def _vaciar_eventos(self):
        while not self.eventos.vacia():
            self.repo.bitacora(*self.eventos.desencolar())

    def _normalizar(self, p: Persona):
        p.cedula = limpiar_cedula(p.cedula)
        p.telefono = limpiar_telefono(p.telefono)
        p.nombre, p.apellidos = p.nombre.strip(), p.apellidos.strip()
        for c in p.contactos:
            c.telefono = limpiar_telefono(c.telefono)

    # --- CRUD -------------------------------------------------------------------
    def crear(self, p: Persona) -> Persona:
        self.sesion.exigir("escribir")
        self._normalizar(p)
        errores = validar_persona(p)
        if errores:
            raise ValidacionError(errores)
        if p.cedula in self.por_cedula:
            raise Duplicado(f"Ya existe una persona con la cédula {p.cedula}.")
        p.id = self.repo.insertar_persona(p)
        self._indexar(p)
        ced = p.cedula
        self.historial.apilar((f"crear {ced}", lambda: self._deshacer_crear(ced)))
        self._evento("CREAR", ced, p.nombre_completo)
        self._vaciar_eventos()
        log.info("Persona creada: %s", ced)
        return p

    def obtener(self, cedula) -> Persona:
        self.sesion.exigir("leer")
        p = self.por_cedula.obtener(limpiar_cedula(cedula))
        if p is None:
            raise NoEncontrado(f"No existe la cédula {cedula}.")
        return p

    def actualizar(self, nuevo: Persona) -> Persona:
        self.sesion.exigir("escribir")
        self._normalizar(nuevo)
        errores = validar_persona(nuevo)
        if errores:
            raise ValidacionError(errores)
        viejo = self.por_cedula.obtener(nuevo.cedula)
        if viejo is None:
            raise NoEncontrado(f"No existe la cédula {nuevo.cedula}.")
        snapshot = viejo.to_dict()
        nuevo.id, nuevo.activo = viejo.id, viejo.activo
        self.repo.actualizar_persona(nuevo)
        self._desindexar(viejo)
        self._indexar(nuevo)
        self.historial.apilar((f"editar {nuevo.cedula}", lambda: self._restaurar(snapshot)))
        self._evento("ACTUALIZAR", nuevo.cedula, nuevo.nombre_completo)
        self._vaciar_eventos()
        log.info("Persona actualizada: %s", nuevo.cedula)
        return nuevo

    def desactivar(self, cedula):
        self.sesion.exigir("desactivar")
        p = self.obtener(cedula)
        self._fijar_activo(p, False)
        self.historial.apilar((f"desactivar {p.cedula}", lambda: self._fijar_activo(p, True, False)))
        self._evento("DESACTIVAR", p.cedula)
        self._vaciar_eventos()

    def reactivar(self, cedula):
        self.sesion.exigir("desactivar")
        p = self.obtener(cedula)
        self._fijar_activo(p, True)
        self.historial.apilar((f"reactivar {p.cedula}", lambda: self._fijar_activo(p, False, False)))
        self._evento("REACTIVAR", p.cedula)
        self._vaciar_eventos()

    def _fijar_activo(self, p, valor, auditar=True):
        self.repo.fijar_activo(p.cedula, valor)
        p.activo = valor

    # --- consultas --------------------------------------------------------------
    def listar(self, incluir_inactivos=False):
        self.sesion.exigir("leer")
        res = [self.por_cedula.obtener(c) for c in self.por_nombre.en_orden()]
        return res if incluir_inactivos else [p for p in res if p.activo]

    def buscar(self, texto: str, incluir_inactivos=False):
        """Cédula (solo dígitos) -> tabla hash O(1); texto -> prefijo en el árbol y,
        si no hay resultados, coincidencia parcial."""
        self.sesion.exigir("leer")
        t = texto.strip()
        if not t:
            return self.listar(incluir_inactivos)
        ced = limpiar_cedula(t)
        if ced.isdigit() and len(ced) >= 9:
            p = self.por_cedula.obtener(ced)
            res = [p] if p else []
        else:
            q = normalizar(t)
            ids = self.por_nombre.buscar_prefijo(q) or self.por_nombre.buscar_subcadena(q)
            res = [self.por_cedula.obtener(c) for c in ids]
        return res if incluir_inactivos else [p for p in res if p.activo]

    def ver_bitacora(self, limite=200):
        self.sesion.exigir("bitacora")
        return self.repo.listar_bitacora(limite)

    # --- deshacer ---------------------------------------------------------------
    def puede_deshacer(self):
        return not self.historial.vacia()

    def deshacer(self) -> str:
        self.sesion.exigir("escribir")
        if self.historial.vacia():
            raise IndexError("No hay acciones para deshacer.")
        desc, fn = self.historial.desapilar()
        fn()
        self.repo.bitacora(self.sesion.usuario, "DESHACER", "persona", None, desc)
        log.info("Deshacer: %s", desc)
        return desc

    def _deshacer_crear(self, ced):
        p = self.por_cedula.obtener(ced)
        self._desindexar(p)
        self.repo.eliminar_fisico(ced)

    def _restaurar(self, snap):
        actual = self.por_cedula.obtener(snap["cedula"])
        viejo = Persona.from_dict(snap)
        viejo.id = actual.id
        self.repo.actualizar_persona(viejo)
        self._desindexar(actual)
        self._indexar(viejo)
