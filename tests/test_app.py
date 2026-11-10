import os, sqlite3, tempfile, unittest
from app.db import Repositorio
from app.models import Persona, Contacto, Condicion, Medicamento
from app.structures import ListaDoble, Pila, Cola, TablaHash, ArbolBST, normalizar
from app.security import (Autenticador, AutenticacionError, PermisoDenegado, Sesion,
                          crear_credencial, hash_clave, clave_valida)
from app.services import Servicio, Duplicado, NoEncontrado
from app.validators import ValidacionError
from app.bootstrap import sembrar_usuarios


def generar(n):
    """Personas sintéticas solo para las pruebas automatizadas."""
    res = []
    for i in range(n):
        p = Persona(f"{100000000 + i}", f"Nombre{i}", f"Apellido{i % 7}", "1960-05-15", "88887777")
        p.agregar_contacto(Contacto("Contacto", "Familiar", "61112222", 1))
        res.append(p)
    return res


def persona(ced="101230456", nombre="Ana", ape="Mora Solís", nac="1950-03-10"):
    p = Persona(ced, nombre, ape, nac, "88887777", "San José")
    p.agregar_contacto(Contacto("Luis Mora", "Hijo", "61112222", 1))
    return p


def servicio(rol="admin", repo=None):
    repo = repo or Repositorio()
    return Servicio(repo, Sesion("t", rol)), repo


class TestEstructuras(unittest.TestCase):
    def test_lista_orden_y_eliminar(self):
        l = ListaDoble()
        for x in (3, 1, 2, 2):
            l.insertar_ordenado(x, clave=lambda v: v)
        self.assertEqual(l.a_lista(), [1, 2, 2, 3])
        self.assertEqual(l.eliminar_si(lambda v: v == 2), 2)
        self.assertEqual((l.a_lista(), len(l)), ([1, 3], 2))

    def test_pila_cola(self):
        p, c = Pila(), Cola()
        for i in range(3):
            p.apilar(i); c.encolar(i)
        self.assertEqual([p.desapilar() for _ in range(3)], [2, 1, 0])
        self.assertEqual([c.desencolar() for _ in range(3)], [0, 1, 2])
        with self.assertRaises(IndexError): p.desapilar()
        with self.assertRaises(IndexError): c.desencolar()

    def test_hash_redimensiona(self):
        t = TablaHash(4)
        for i in range(1000):
            t.poner(str(i), i)
        self.assertEqual(len(t), 1000)
        self.assertTrue(all(t.obtener(str(i)) == i for i in range(1000)))
        self.assertTrue(t.quitar("500")); self.assertNotIn("500", t)
        self.assertFalse(t.quitar("500"))

    def test_bst(self):
        a = ArbolBST()
        for k in ["mora ana", "castro luis", "zuniga raul", "castro luis", "araya eva"]:
            a.insertar(k, k + "!")
        self.assertEqual(a.en_orden()[0], "araya eva!")
        self.assertEqual(len(a), 4)
        self.assertEqual(a.buscar_prefijo("cas"), ["castro luis!"])
        self.assertEqual(a.buscar_subcadena("ana"), ["mora ana!"])
        a.eliminar("mora ana", "mora ana!")
        self.assertEqual(len(a), 3)
        a.eliminar("castro luis", "castro luis!")
        self.assertEqual(a.buscar_prefijo("cas"), [])

    def test_bst_balanceado_altura(self):
        pares = [(f"{i:06d}", i) for i in range(10000)]
        self.assertLessEqual(ArbolBST.desde_ordenados(pares).altura(), 14)

    def test_bst_eliminar_dos_hijos(self):
        a = ArbolBST()
        for k in "mfsbhpt":
            a.insertar(k, k)
        a.eliminar("m", "m")
        self.assertEqual(a.en_orden(), list("bfhpst")); self.assertEqual(len(a), 6)

    def test_normalizar(self):
        self.assertEqual(normalizar("  Núñez "), "nunez")


class TestValidacion(unittest.TestCase):
    def test_campos_obligatorios(self):
        s, _ = servicio()
        with self.assertRaises(ValidacionError) as cm:
            s.crear(Persona("12", "", "", "2030-01-01"))
        msg = " ".join(cm.exception.errores)
        for frag in ("cédula", "nombre", "apellidos", "futura", "contacto"):
            self.assertIn(frag, msg.lower())

    def test_menor_de_edad_y_telefono(self):
        s, _ = servicio()
        p = persona(nac="2015-01-01"); p.telefono = "123"
        with self.assertRaises(ValidacionError) as cm:
            s.crear(p)
        self.assertTrue(any("mayor de edad" in e for e in cm.exception.errores))
        self.assertTrue(any("Teléfono" in e for e in cm.exception.errores))

    def test_condicion_y_medicamento_incompletos(self):
        s, _ = servicio()
        p = persona(); p.condiciones.append(Condicion("", "leve")); p.medicamentos.append(Medicamento("X", ""))
        with self.assertRaises(ValidacionError) as cm:
            s.crear(p)
        self.assertEqual(len(cm.exception.errores), 2)

    def test_cedula_con_guiones(self):
        s, _ = servicio()
        s.crear(persona(ced="1-0123-0456"))
        self.assertEqual(s.obtener("101230456").cedula, "101230456")


class TestCRUD(unittest.TestCase):
    def test_crear_leer_actualizar(self):
        s, repo = servicio()
        p = persona(); p.condiciones.append(Condicion("Asma", "leve")); p.medicamentos.append(Medicamento("Salbutamol", "2 puff"))
        p.agregar_contacto(Contacto("Rosa", "Vecina", "62223333", 2))
        s.crear(p)
        g = s.obtener("101230456")
        self.assertEqual([c.nombre for c in g.contactos], ["Luis Mora", "Rosa"])
        n = persona(ape="Mora Vargas"); s.actualizar(n)
        self.assertEqual(s.obtener("101230456").apellidos, "Mora Vargas")
        self.assertEqual(len(s.buscar("mora v")), 1)
        self.assertEqual(len(s.buscar("mora s")), 0)

    def test_duplicado(self):
        s, _ = servicio(); s.crear(persona())
        with self.assertRaises(Duplicado): s.crear(persona())

    def test_no_encontrado(self):
        s, _ = servicio()
        with self.assertRaises(NoEncontrado): s.obtener("999999999")

    def test_desactivacion_logica(self):
        s, repo = servicio(); s.crear(persona())
        s.desactivar("101230456")
        self.assertEqual(s.buscar("mora"), [])
        self.assertEqual(len(s.buscar("mora", incluir_inactivos=True)), 1)
        self.assertEqual(repo.con.execute("SELECT COUNT(*) FROM persona").fetchone()[0], 1)
        s.reactivar("101230456"); self.assertEqual(len(s.buscar("mora")), 1)

    def test_persistencia_al_reabrir(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "t.db")
            repo = Repositorio(ruta); s = Servicio(repo, Sesion("t", "admin"))
            for p in generar(30): s.crear(p)
            ced = s.listar()[0].cedula; n_ctc = len(s.obtener(ced).contactos)
            repo.cerrar()
            s2 = Servicio(Repositorio(ruta), Sesion("t", "admin"))
            self.assertEqual(len(s2.listar()), 30)
            self.assertEqual(len(s2.obtener(ced).contactos), n_ctc)

    def test_busqueda_por_cedula_y_homonimos(self):
        s, _ = servicio()
        s.crear(persona("111111111")); s.crear(persona("222222222"))
        self.assertEqual(len(s.buscar("ana mora")), 0)        # orden es apellidos nombre
        self.assertEqual(len(s.buscar("mora solis ana")), 2)   # homónimos, sin tildes
        self.assertEqual(s.buscar("222-222-222")[0].cedula, "222222222")

    def test_listado_ordenado(self):
        s, _ = servicio()
        for p in generar(50): s.crear(p)
        claves = [p.clave_orden for p in s.listar()]
        self.assertEqual(claves, sorted(claves))


class TestIntegridad(unittest.TestCase):
    def test_cascada_y_fk(self):
        s, repo = servicio(); s.crear(persona())
        repo.eliminar_fisico("101230456")
        self.assertEqual(repo.con.execute("SELECT COUNT(*) FROM contacto_emergencia").fetchone()[0], 0)
        with self.assertRaises(sqlite3.IntegrityError):
            repo.con.execute("INSERT INTO medicamento(persona_id,nombre,dosis) VALUES(999,'x','y')")

    def test_check_constraints(self):
        _, repo = servicio()
        with self.assertRaises(sqlite3.IntegrityError):
            repo.con.execute("INSERT INTO persona(cedula,nombre,apellidos,fecha_nacimiento) VALUES('1','a','b','1990-01-01')")

    def test_inyeccion_sql(self):
        s, repo = servicio(); s.crear(persona())
        for ataque in ["'; DROP TABLE persona; --", "' OR '1'='1", "mora' UNION SELECT * FROM usuario --"]:
            self.assertEqual(s.buscar(ataque), [])
        p = persona(ced="333333333", nombre="Robert'); DROP TABLE persona;--")
        s.crear(p)
        self.assertEqual(repo.con.execute("SELECT COUNT(*) FROM persona").fetchone()[0], 2)

    def test_indices_usados(self):
        _, repo = servicio()
        plan = " ".join(repo.plan_consulta("SELECT * FROM persona WHERE apellidos=? AND nombre=?", ("a", "b")))
        self.assertIn("idx_persona_nombre", plan)
        plan = " ".join(repo.plan_consulta("SELECT * FROM contacto_emergencia WHERE persona_id=?", (1,)))
        self.assertIn("idx_contacto_persona", plan)


class TestDeshacer(unittest.TestCase):
    def test_deshacer_tres_tipos(self):
        s, repo = servicio()
        s.crear(persona())
        s.actualizar(persona(ape="Cambiada Otra"))
        s.desactivar("101230456")
        s.deshacer(); self.assertTrue(s.obtener("101230456").activo)
        s.deshacer(); self.assertEqual(s.obtener("101230456").apellidos, "Mora Solís")
        self.assertEqual(repo.con.execute("SELECT apellidos FROM persona").fetchone()[0], "Mora Solís")
        s.deshacer()
        self.assertEqual(len(s.por_cedula), 0)
        self.assertEqual(repo.con.execute("SELECT COUNT(*) FROM persona").fetchone()[0], 0)
        with self.assertRaises(IndexError): s.deshacer()


class TestSeguridad(unittest.TestCase):
    def _auth(self, reloj=None):
        repo = Repositorio(); sembrar_usuarios(repo)
        return repo, Autenticador(repo, reloj=reloj or (lambda: 1000.0))

    def test_hash_no_texto_plano(self):
        repo, _ = self._auth()
        u = repo.obtener_usuario("admin")
        self.assertNotIn("Admin#2026", u["hash"]); self.assertEqual(len(u["hash"]), 64)
        self.assertNotEqual(u["hash"], repo.obtener_usuario("operador")["hash"])

    def test_login_ok_y_mal(self):
        repo, a = self._auth()
        self.assertEqual(a.iniciar_sesion("admin", "Admin#2026").rol, "admin")
        with self.assertRaises(AutenticacionError): a.iniciar_sesion("admin", "mala")
        with self.assertRaises(AutenticacionError): a.iniciar_sesion("noexiste", "x")

    def test_bloqueo_tras_3_intentos(self):
        t = [1000.0]; repo, a = self._auth(lambda: t[0])
        for _ in range(3):
            with self.assertRaises(AutenticacionError): a.iniciar_sesion("operador", "x")
        with self.assertRaises(AutenticacionError) as cm: a.iniciar_sesion("operador", "Operador#2026")
        self.assertIn("bloqueada", str(cm.exception))
        t[0] += 61
        self.assertEqual(a.iniciar_sesion("operador", "Operador#2026").rol, "operador")

    def test_roles(self):
        repo = Repositorio()
        s_admin = Servicio(repo, Sesion("a", "admin")); s_admin.crear(persona())
        s_con = Servicio(repo, Sesion("c", "consulta"))
        self.assertEqual(len(s_con.listar()), 1)
        with self.assertRaises(PermisoDenegado): s_con.crear(persona(ced="222222222"))
        with self.assertRaises(PermisoDenegado): s_con.desactivar("101230456")
        with self.assertRaises(PermisoDenegado): s_con.ver_bitacora()
        s_op = Servicio(repo, Sesion("o", "operador"))
        with self.assertRaises(PermisoDenegado): s_op.ver_bitacora()
        self.assertTrue(s_admin.ver_bitacora())

    def test_expiracion_sesion(self):
        t = [0.0]; ses = Sesion("a", "admin", timeout_s=10, reloj=lambda: t[0])
        ses.exigir("leer"); t[0] = 9; ses.exigir("leer")
        t[0] = 25
        with self.assertRaises(PermisoDenegado): ses.exigir("leer")

    def test_politica_clave(self):
        self.assertFalse(clave_valida("abc")); self.assertFalse(clave_valida("abcdefgh"))
        self.assertTrue(clave_valida("Segura123"))

    def test_bitacora_registra(self):
        s, repo = servicio(); s.crear(persona()); s.desactivar("101230456")
        acciones = [b["accion"] for b in s.ver_bitacora()]
        self.assertIn("CREAR", acciones); self.assertIn("DESACTIVAR", acciones)


if __name__ == "__main__":
    unittest.main(verbosity=2)
