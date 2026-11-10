"""Interfaz Tkinter: inicio de sesión, listado con búsqueda, ficha individual,
formulario de alta/edición, bitácora y bloqueo por inactividad."""
import os, sys
import tkinter as tk
from tkinter import ttk, messagebox
from .models import Persona, Contacto, Condicion, Medicamento, SEVERIDADES
from .security import Autenticador, AutenticacionError, PermisoDenegado, PERMISOS
from .services import Servicio, Duplicado, NoEncontrado
from .validators import ValidacionError

FUENTE = ("Segoe UI", 10)


def ruta_recurso(rel):
    """Ruta a un recurso, tanto en desarrollo como dentro del .exe de PyInstaller."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, rel)


def poner_icono(ventana):
    try:
        ventana.iconphoto(True, tk.PhotoImage(file=ruta_recurso("assets/icono.png")))
    except Exception:
        pass


class Login(tk.Toplevel):
    def __init__(self, master, repo, al_entrar):
        super().__init__(master)
        self.title("Iniciar sesión"); self.resizable(False, False)
        self.repo, self.al_entrar = repo, al_entrar
        self.auth = Autenticador(repo)
        f = ttk.Frame(self, padding=20); f.grid()
        ttk.Label(f, text="Registro de personas y contactos de emergencia",
                  font=("Segoe UI", 11, "bold")).grid(columnspan=2, pady=(0, 12))
        ttk.Label(f, text="Usuario").grid(row=1, column=0, sticky="e", pady=3)
        ttk.Label(f, text="Contraseña").grid(row=2, column=0, sticky="e", pady=3)
        self.u, self.c = tk.StringVar(), tk.StringVar()
        self.eu = ttk.Entry(f, textvariable=self.u, width=26); self.eu.grid(row=1, column=1, padx=6)
        ec = ttk.Entry(f, textvariable=self.c, show="•", width=26); ec.grid(row=2, column=1, padx=6)
        self.msg = ttk.Label(f, text="", foreground="#b00020", wraplength=260)
        self.msg.grid(row=3, columnspan=2, pady=6)
        ttk.Button(f, text="Entrar", command=self.entrar).grid(row=4, columnspan=2)
        ec.bind("<Return>", lambda e: self.entrar()); self.eu.focus()
        self.protocol("WM_DELETE_WINDOW", master.destroy)

    def entrar(self):
        try:
            ses = self.auth.iniciar_sesion(self.u.get().strip(), self.c.get())
        except AutenticacionError as e:
            self.msg.config(text=str(e)); self.c.set(""); return
        self.destroy(); self.al_entrar(ses)


class Formulario(tk.Toplevel):
    """Alta / edición de una persona con contactos, condiciones y medicamentos."""

    def __init__(self, master, servicio, persona=None, al_guardar=None):
        super().__init__(master)
        self.s, self.p, self.al_guardar = servicio, persona, al_guardar
        self.title("Editar persona" if persona else "Nueva persona")
        self.geometry("640x600"); self.transient(master)
        f = ttk.Frame(self, padding=10); f.pack(fill="both", expand=True)
        self.v = {k: tk.StringVar() for k in ("cedula", "nombre", "apellidos", "nac", "tel", "dir")}
        etiquetas = [("Cédula (9 dígitos)", "cedula"), ("Nombre", "nombre"), ("Apellidos", "apellidos"),
                     ("Nacimiento (AAAA-MM-DD)", "nac"), ("Teléfono", "tel"), ("Dirección", "dir")]
        for i, (t, k) in enumerate(etiquetas):
            ttk.Label(f, text=t).grid(row=i, column=0, sticky="e", pady=2)
            e = ttk.Entry(f, textvariable=self.v[k], width=44); e.grid(row=i, column=1, sticky="w", padx=6)
            if persona and k == "cedula": e.state(["disabled"])
        nb = ttk.Notebook(f); nb.grid(row=6, columnspan=2, sticky="nsew", pady=8)
        f.rowconfigure(6, weight=1); f.columnconfigure(1, weight=1)
        self.t_ctc = self._tabla(nb, "Contactos", ("Nombre", "Parentesco", "Teléfono", "Prioridad"), self._pedir_contacto)
        self.t_con = self._tabla(nb, "Condiciones", ("Descripción", "Severidad"), self._pedir_condicion)
        self.t_med = self._tabla(nb, "Medicamentos", ("Nombre", "Dosis", "Frecuencia"), self._pedir_med)
        self.err = tk.Text(f, height=6, width=70, foreground="#b00020", relief="flat", background=self.cget("bg"))
        self.err.grid(row=7, columnspan=2); self.err.config(state="disabled")
        b = ttk.Frame(f); b.grid(row=8, columnspan=2, pady=6)
        ttk.Button(b, text="Guardar", command=self.guardar).pack(side="left", padx=4)
        ttk.Button(b, text="Cancelar", command=self.destroy).pack(side="left", padx=4)
        if persona:
            d = persona
            for k, val in (("cedula", d.cedula), ("nombre", d.nombre), ("apellidos", d.apellidos),
                           ("nac", d.fecha_nacimiento), ("tel", d.telefono), ("dir", d.direccion)):
                self.v[k].set(val)
            for c in d.contactos: self.t_ctc.insert("", "end", values=(c.nombre, c.parentesco, c.telefono, c.prioridad))
            for c in d.condiciones: self.t_con.insert("", "end", values=(c.descripcion, c.severidad))
            for m in d.medicamentos: self.t_med.insert("", "end", values=(m.nombre, m.dosis, m.frecuencia))

    def _tabla(self, nb, titulo, cols, pedir):
        fr = ttk.Frame(nb); nb.add(fr, text=titulo)
        t = ttk.Treeview(fr, columns=cols, show="headings", height=5)
        for c in cols: t.heading(c, text=c); t.column(c, width=120)
        t.pack(fill="both", expand=True)
        bf = ttk.Frame(fr); bf.pack(fill="x")
        ttk.Button(bf, text="Agregar", command=lambda: pedir(t)).pack(side="left", padx=2, pady=2)
        ttk.Button(bf, text="Quitar", command=lambda: [t.delete(i) for i in t.selection()]).pack(side="left")
        return t

    def _dialogo(self, titulo, campos, tabla, vals_defecto=None):
        d = tk.Toplevel(self); d.title(titulo); d.transient(self)
        vs = []
        for i, (etq, defecto) in enumerate(campos):
            ttk.Label(d, text=etq).grid(row=i, column=0, padx=6, pady=3, sticky="e")
            v = tk.StringVar(value=defecto)
            if etq == "Severidad":
                w = ttk.Combobox(d, textvariable=v, values=SEVERIDADES, state="readonly", width=22)
            else:
                w = ttk.Entry(d, textvariable=v, width=24)
            w.grid(row=i, column=1, padx=6); vs.append(v)

        def ok():
            tabla.insert("", "end", values=[v.get() for v in vs]); d.destroy()
        ttk.Button(d, text="Aceptar", command=ok).grid(columnspan=2, pady=6)
        d.grab_set()
        return d, vs, ok

    def _pedir_contacto(self, t):
        n = len(t.get_children()) + 1
        self._dialogo("Contacto", [("Nombre", ""), ("Parentesco", ""), ("Teléfono", ""), ("Prioridad", str(n))], t)

    def _pedir_condicion(self, t):
        self._dialogo("Condición", [("Descripción", ""), ("Severidad", "leve")], t)

    def _pedir_med(self, t):
        self._dialogo("Medicamento", [("Nombre", ""), ("Dosis", ""), ("Frecuencia", "")], t)

    def construir_persona(self) -> Persona:
        v = {k: x.get() for k, x in self.v.items()}
        p = Persona(v["cedula"], v["nombre"], v["apellidos"], v["nac"].strip(), v["tel"], v["dir"])
        for it in self.t_ctc.get_children():
            n, par, tel, pri = self.t_ctc.item(it)["values"]
            try: pri = int(pri)
            except (ValueError, TypeError): pri = 0
            p.agregar_contacto(Contacto(str(n), str(par), str(tel), pri))
        for it in self.t_con.get_children():
            d, s = self.t_con.item(it)["values"]; p.condiciones.append(Condicion(str(d), str(s)))
        for it in self.t_med.get_children():
            n, d, f = self.t_med.item(it)["values"]; p.medicamentos.append(Medicamento(str(n), str(d), str(f)))
        return p

    def mostrar_error(self, lineas):
        self.err.config(state="normal"); self.err.delete("1.0", "end")
        self.err.insert("1.0", "\n".join(lineas)); self.err.config(state="disabled")

    def guardar(self):
        try:
            p = self.construir_persona()
            (self.s.actualizar if self.p else self.s.crear)(p)
        except ValidacionError as e:
            self.mostrar_error(["• " + x for x in e.errores]); return
        except (Duplicado, NoEncontrado, PermisoDenegado) as e:
            self.mostrar_error([str(e)]); return
        if self.al_guardar: self.al_guardar()
        self.destroy()


class App(tk.Tk):
    def __init__(self, repo):
        super().__init__()
        self.title("Registro de personas y contactos de emergencia")
        self.geometry("1000x600"); self.repo = repo; self.s = None
        poner_icono(self); self._icono = True
        self.withdraw()
        Login(self, repo, self.iniciar)

    # --- construcción de la interfaz principal ----------------------------------
    def iniciar(self, sesion):
        self.s = Servicio(self.repo, sesion)
        for w in self.winfo_children(): w.destroy()
        self.deiconify()
        top = ttk.Frame(self, padding=8); top.pack(fill="x")
        ttk.Label(top, text="Buscar (nombre o cédula):").pack(side="left")
        self.q = tk.StringVar(); self.q.trace_add("write", lambda *a: self.refrescar())
        ttk.Entry(top, textvariable=self.q, width=30).pack(side="left", padx=6)
        self.ver_inact = tk.BooleanVar()
        ttk.Checkbutton(top, text="Incluir inactivos", variable=self.ver_inact,
                        command=self.refrescar).pack(side="left", padx=6)
        self.lbl_user = ttk.Label(top, text=f"Usuario: {sesion.usuario} ({sesion.rol})")
        self.lbl_user.pack(side="right")
        ttk.Button(top, text="Cerrar sesión", command=self.cerrar_sesion).pack(side="right", padx=8)
        barra = ttk.Frame(self, padding=(8, 0)); barra.pack(fill="x")
        puede = lambda p: p in PERMISOS[sesion.rol]
        self.botones = {}
        for txt, cmd, perm in (("Nuevo", self.nuevo, "escribir"), ("Editar", self.editar, "escribir"),
                               ("Desactivar/Reactivar", self.alternar, "desactivar"),
                               ("Deshacer", self.deshacer, "escribir"), ("Bitácora", self.bitacora, "bitacora")):
            b = ttk.Button(barra, text=txt, command=cmd); b.pack(side="left", padx=3, pady=4)
            if not puede(perm): b.state(["disabled"])
        self.estado = ttk.Label(barra, text="", foreground="#1b5e20"); self.estado.pack(side="left", padx=10)
        pan = ttk.PanedWindow(self, orient="horizontal"); pan.pack(fill="both", expand=True, padx=8, pady=8)
        izq = ttk.Frame(pan); pan.add(izq, weight=3)
        cols = ("cedula", "nombre", "edad", "estado")
        self.tv = ttk.Treeview(izq, columns=cols, show="headings", selectmode="browse")
        for c, t, w in (("cedula", "Cédula", 100), ("nombre", "Apellidos y nombre", 260), ("edad", "Edad", 50), ("estado", "Estado", 70)):
            self.tv.heading(c, text=t); self.tv.column(c, width=w)
        self.tv.pack(fill="both", expand=True); self.tv.tag_configure("inactivo", foreground="#888")
        self.tv.bind("<<TreeviewSelect>>", lambda e: self.mostrar_ficha())
        self.tv.bind("<Double-1>", lambda e: self.editar())
        self.ficha = tk.Text(pan, width=48, wrap="word", state="disabled", padx=10, pady=8)
        self.ficha.tag_configure("h", font=("Segoe UI", 12, "bold")); self.ficha.tag_configure("b", font=("Segoe UI", 10, "bold"))
        pan.add(self.ficha, weight=2)
        self.bind_all("<Key>", lambda e: self.s.sesion.tocar()); self.bind_all("<Button>", lambda e: self.s.sesion.tocar())
        self.refrescar(); self.after(5000, self.vigilar_inactividad)

    def vigilar_inactividad(self):
        if self.s and self.s.sesion.expirada():
            self.cerrar_sesion(); return
        self.after(5000, self.vigilar_inactividad)

    def cerrar_sesion(self):
        self.s = None
        for w in self.winfo_children(): w.destroy()
        self.withdraw(); Login(self, self.repo, self.iniciar)

    # --- acciones ---------------------------------------------------------------
    def seleccion(self):
        s = self.tv.selection()
        return s[0] if s else None

    def refrescar(self, seleccionar=None):
        if not self.s: return
        try:
            res = self.s.buscar(self.q.get(), self.ver_inact.get())
        except PermisoDenegado:
            self.cerrar_sesion(); return
        self.tv.delete(*self.tv.get_children())
        for p in res:
            self.tv.insert("", "end", iid=p.cedula, values=(p.cedula, f"{p.apellidos}, {p.nombre}", p.edad(),
                           "Activo" if p.activo else "Inactivo"), tags=(() if p.activo else ("inactivo",)))
        if seleccionar and self.tv.exists(seleccionar):
            self.tv.selection_set(seleccionar)
        self.mostrar_ficha()
        self.estado.config(text=f"{len(res)} registro(s)")

    def mostrar_ficha(self):
        t = self.ficha; t.config(state="normal"); t.delete("1.0", "end")
        ced = self.tv.selection()[0] if self.tv.selection() else None
        if ced:
            p = self.s.obtener(ced)
            t.insert("end", p.nombre_completo + "\n", "h")
            t.insert("end", f"Cédula: {p.cedula}   Edad: {p.edad()}   {'Activo' if p.activo else 'INACTIVO'}\n")
            t.insert("end", f"Tel.: {p.telefono or '—'}\nDirección: {p.direccion or '—'}\n\n")
            t.insert("end", "Contactos de emergencia (por prioridad)\n", "b")
            for c in p.contactos: t.insert("end", f"  {c.prioridad}. {c.nombre} ({c.parentesco}) · {c.telefono}\n")
            t.insert("end", "\nCondiciones de salud declaradas\n", "b")
            for c in p.condiciones: t.insert("end", f"  • {c.descripcion} [{c.severidad}]\n")
            if not p.condiciones: t.insert("end", "  (ninguna)\n")
            t.insert("end", "\nMedicamentos\n", "b")
            for m in p.medicamentos: t.insert("end", f"  • {m.nombre} {m.dosis} {m.frecuencia}\n")
            if not p.medicamentos: t.insert("end", "  (ninguno)\n")
        else:
            t.insert("end", "Seleccione una persona para ver su ficha.")
        t.config(state="disabled")

    def nuevo(self):
        Formulario(self, self.s, None, lambda: (self.refrescar(), self.estado.config(text="Persona creada")))

    def editar(self):
        ced = self.seleccion()
        if not ced or "escribir" not in PERMISOS[self.s.sesion.rol]: return
        Formulario(self, self.s, self.s.obtener(ced),
                   lambda: (self.refrescar(ced), self.estado.config(text="Cambios guardados")))

    def alternar(self):
        ced = self.seleccion()
        if not ced: return
        ced = ced; p = self.s.obtener(ced)
        (self.s.desactivar if p.activo else self.s.reactivar)(ced)
        self.refrescar(ced); self.estado.config(text="Estado actualizado")

    def deshacer(self):
        try:
            d = self.s.deshacer(); self.refrescar(); self.estado.config(text=f"Deshecho: {d}")
        except IndexError:
            self.estado.config(text="No hay acciones para deshacer")

    def bitacora(self):
        w = tk.Toplevel(self); w.title("Bitácora de actividad"); w.geometry("780x360")
        cols = ("fecha", "usuario", "accion", "entidad_id", "detalle")
        tv = ttk.Treeview(w, columns=cols, show="headings")
        for c, ancho in zip(cols, (140, 80, 110, 100, 300)):
            tv.heading(c, text=c.capitalize()); tv.column(c, width=ancho)
        tv.pack(fill="both", expand=True)
        for r in self.s.ver_bitacora(300):
            tv.insert("", "end", values=(r["fecha"], r["usuario"], r["accion"], r["entidad_id"] or "", r["detalle"]))
