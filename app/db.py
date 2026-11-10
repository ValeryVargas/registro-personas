"""Capa de persistencia SQLite (patrón Repositorio). Todas las consultas usan
parámetros (?) para evitar inyección SQL; claves foráneas activadas."""
import sqlite3, time
from .models import Persona

ESQUEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS usuario(
  id INTEGER PRIMARY KEY,
  username TEXT NOT NULL UNIQUE,
  sal TEXT NOT NULL, hash TEXT NOT NULL,
  rol TEXT NOT NULL CHECK(rol IN ('admin','operador','consulta')),
  intentos INTEGER NOT NULL DEFAULT 0,
  bloqueado_hasta REAL
);
CREATE TABLE IF NOT EXISTS persona(
  id INTEGER PRIMARY KEY,
  cedula TEXT NOT NULL UNIQUE CHECK(length(cedula)=9),
  nombre TEXT NOT NULL CHECK(length(trim(nombre))>0),
  apellidos TEXT NOT NULL CHECK(length(trim(apellidos))>0),
  fecha_nacimiento TEXT NOT NULL,
  telefono TEXT NOT NULL DEFAULT '',
  direccion TEXT NOT NULL DEFAULT '',
  activo INTEGER NOT NULL DEFAULT 1 CHECK(activo IN (0,1)),
  creado TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  modificado TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS contacto_emergencia(
  id INTEGER PRIMARY KEY,
  persona_id INTEGER NOT NULL REFERENCES persona(id) ON DELETE CASCADE,
  nombre TEXT NOT NULL, parentesco TEXT NOT NULL, telefono TEXT NOT NULL,
  prioridad INTEGER NOT NULL DEFAULT 1 CHECK(prioridad>=1)
);
CREATE TABLE IF NOT EXISTS condicion_salud(
  id INTEGER PRIMARY KEY,
  persona_id INTEGER NOT NULL REFERENCES persona(id) ON DELETE CASCADE,
  descripcion TEXT NOT NULL,
  severidad TEXT NOT NULL CHECK(severidad IN ('leve','moderada','grave'))
);
CREATE TABLE IF NOT EXISTS medicamento(
  id INTEGER PRIMARY KEY,
  persona_id INTEGER NOT NULL REFERENCES persona(id) ON DELETE CASCADE,
  nombre TEXT NOT NULL, dosis TEXT NOT NULL, frecuencia TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS bitacora(
  id INTEGER PRIMARY KEY,
  fecha TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  usuario TEXT NOT NULL, accion TEXT NOT NULL,
  entidad TEXT NOT NULL, entidad_id TEXT, detalle TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_persona_nombre ON persona(apellidos, nombre);
CREATE INDEX IF NOT EXISTS idx_persona_activo ON persona(activo);
CREATE INDEX IF NOT EXISTS idx_contacto_persona ON contacto_emergencia(persona_id);
CREATE INDEX IF NOT EXISTS idx_condicion_persona ON condicion_salud(persona_id);
CREATE INDEX IF NOT EXISTS idx_medicamento_persona ON medicamento(persona_id);
CREATE INDEX IF NOT EXISTS idx_bitacora_fecha ON bitacora(fecha);
CREATE TRIGGER IF NOT EXISTS trg_persona_mod AFTER UPDATE ON persona
BEGIN UPDATE persona SET modificado=CURRENT_TIMESTAMP WHERE id=NEW.id; END;
"""


class Repositorio:
    def __init__(self, ruta=":memory:"):
        self.ruta = ruta
        self.con = sqlite3.connect(ruta)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA foreign_keys = ON")
        self.con.executescript(ESQUEMA)
        self.con.commit()

    def cerrar(self):
        self.con.close()

    # --- personas -------------------------------------------------------------
    def _insertar_hijos(self, pid, p: Persona):
        c = self.con
        c.executemany("INSERT INTO contacto_emergencia(persona_id,nombre,parentesco,telefono,prioridad) VALUES(?,?,?,?,?)",
                      [(pid, x.nombre, x.parentesco, x.telefono, x.prioridad) for x in p.contactos])
        c.executemany("INSERT INTO condicion_salud(persona_id,descripcion,severidad) VALUES(?,?,?)",
                      [(pid, x.descripcion, x.severidad) for x in p.condiciones])
        c.executemany("INSERT INTO medicamento(persona_id,nombre,dosis,frecuencia) VALUES(?,?,?,?)",
                      [(pid, x.nombre, x.dosis, x.frecuencia) for x in p.medicamentos])

    def insertar_persona(self, p: Persona) -> int:
        with self.con:                                   # transacción atómica
            cur = self.con.execute(
                "INSERT INTO persona(cedula,nombre,apellidos,fecha_nacimiento,telefono,direccion,activo) VALUES(?,?,?,?,?,?,?)",
                (p.cedula, p.nombre, p.apellidos, p.fecha_nacimiento, p.telefono, p.direccion, int(p.activo)))
            self._insertar_hijos(cur.lastrowid, p)
        return cur.lastrowid

    def actualizar_persona(self, p: Persona):
        with self.con:
            self.con.execute(
                "UPDATE persona SET nombre=?,apellidos=?,fecha_nacimiento=?,telefono=?,direccion=?,activo=? WHERE cedula=?",
                (p.nombre, p.apellidos, p.fecha_nacimiento, p.telefono, p.direccion, int(p.activo), p.cedula))
            pid = self.con.execute("SELECT id FROM persona WHERE cedula=?", (p.cedula,)).fetchone()["id"]
            for t in ("contacto_emergencia", "condicion_salud", "medicamento"):
                self.con.execute(f"DELETE FROM {t} WHERE persona_id=?", (pid,))
            self._insertar_hijos(pid, p)

    def fijar_activo(self, cedula, activo: bool):
        with self.con:
            self.con.execute("UPDATE persona SET activo=? WHERE cedula=?", (int(activo), cedula))

    def eliminar_fisico(self, cedula):
        with self.con:
            self.con.execute("DELETE FROM persona WHERE cedula=?", (cedula,))

    def cargar_todas(self):
        """Carga personas con sus hijos usando 4 consultas (no N+1)."""
        from .models import Contacto, Condicion, Medicamento
        c = self.con
        personas, por_id = [], {}
        for r in c.execute("SELECT * FROM persona ORDER BY apellidos, nombre"):
            p = Persona(r["cedula"], r["nombre"], r["apellidos"], r["fecha_nacimiento"],
                        r["telefono"], r["direccion"], bool(r["activo"]), r["id"])
            personas.append(p); por_id[p.id] = p
        for r in c.execute("SELECT * FROM contacto_emergencia ORDER BY persona_id, prioridad, id"):
            por_id[r["persona_id"]].agregar_contacto(
                Contacto(r["nombre"], r["parentesco"], r["telefono"], r["prioridad"]))
        for r in c.execute("SELECT * FROM condicion_salud ORDER BY id"):
            por_id[r["persona_id"]].condiciones.append(Condicion(r["descripcion"], r["severidad"]))
        for r in c.execute("SELECT * FROM medicamento ORDER BY id"):
            por_id[r["persona_id"]].medicamentos.append(
                Medicamento(r["nombre"], r["dosis"], r["frecuencia"]))
        return personas

    # --- usuarios / bitácora --------------------------------------------------
    def crear_usuario(self, username, sal, hash_, rol):
        with self.con:
            self.con.execute("INSERT OR IGNORE INTO usuario(username,sal,hash,rol) VALUES(?,?,?,?)",
                             (username, sal, hash_, rol))

    def obtener_usuario(self, username):
        r = self.con.execute("SELECT * FROM usuario WHERE username=?", (username,)).fetchone()
        return dict(r) if r else None

    def registrar_intento(self, username, intentos, bloqueado_hasta):
        with self.con:
            self.con.execute("UPDATE usuario SET intentos=?, bloqueado_hasta=? WHERE username=?",
                             (intentos, bloqueado_hasta, username))

    def bitacora(self, usuario, accion, entidad, entidad_id, detalle=""):
        with self.con:
            self.con.execute("INSERT INTO bitacora(usuario,accion,entidad,entidad_id,detalle) VALUES(?,?,?,?,?)",
                             (usuario, accion, entidad, None if entidad_id is None else str(entidad_id), detalle))

    def listar_bitacora(self, limite=200):
        return [dict(r) for r in self.con.execute(
            "SELECT fecha,usuario,accion,entidad,entidad_id,detalle FROM bitacora ORDER BY id DESC LIMIT ?", (limite,))]

    def plan_consulta(self, sql, params=()):
        return [r[3] for r in self.con.execute("EXPLAIN QUERY PLAN " + sql, params)]
